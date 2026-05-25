"""
Laboratorio de carga Li-ion — asistente por pasos (Streamlit).
Ejecutar: streamlit run main.py
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.interpolate import UnivariateSpline
from scipy.optimize import newton

from battery_models import logistic_c, newton_time_for_target, report_fit_stats
from report_data import (
    CHARGE_TIME_REAL_MIN,
    DELIVERY_DATE,
    EFFICIENCY_PCT,
    ENERGY_WH,
    INSTITUTION,
    K_RATE,
    METHODOLOGY_STEPS,
    NEWTON_80_ITER,
    NEWTON_80_MIN,
    SAMPLES_ALT,
    SAMPLES_MAIN,
    T0_INFL,
    TEAM,
    TIME_IDEAL_MIN,
    WIZARD_LAB_STEPS,
    samples_dataframe,
)
from theme import ACCENT_CYAN, ACCENT_YELLOW, BG, GRID, TEXT_MUTED, inject_global_style
from wizard_ui import render_step_header, step_nav_buttons


@dataclass
class BatteryReading:
    level: int | None
    voltage_mv: int | None
    current_ua: int | None
    temperature_c: float | None
    raw_text: str
    error: str | None = None


def run_dumpsys_battery(adb_bin: str = "adb", timeout_s: float = 12.0) -> str:
    result = subprocess.run(
        [adb_bin, "shell", "dumpsys", "battery"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"adb salió con código {result.returncode}")
    return result.stdout or ""


def parse_dumpsys_battery(text: str) -> BatteryReading:
    level = voltage = current = None
    temp_raw: int | None = None
    for line in text.splitlines():
        m = re.match(r"^\s*level:\s*(\d+)\s*$", line, re.I)
        if m:
            level = int(m.group(1))
            continue
        m = re.match(r"^\s*voltage:\s*(\d+)\s*$", line, re.I)
        if m:
            voltage = int(m.group(1))
            continue
        m = re.match(r"^\s*temperature:\s*(\d+)\s*$", line, re.I)
        if m:
            temp_raw = int(m.group(1))
            continue
        m = re.match(r"^\s*current now:\s*(-?\d+)\s*$", line, re.I)
        if m:
            current = int(m.group(1))
            continue
    temp_c = (temp_raw / 10.0) if temp_raw is not None else None
    return BatteryReading(level, voltage, current, temp_c, text, None)


def fetch_battery_reading(adb_bin: str) -> BatteryReading:
    try:
        return parse_dumpsys_battery(run_dumpsys_battery(adb_bin))
    except Exception as exc:  # noqa: BLE001
        return BatteryReading(None, None, None, None, "", str(exc))


class BatteryNumericEngine:
    def __init__(self, times_h: np.ndarray, levels: np.ndarray) -> None:
        self._t = np.asarray(times_h, dtype=float).ravel()
        self._y = np.asarray(levels, dtype=float).ravel()
        order = np.argsort(self._t)
        self._t, self._y = self._t[order], self._y[order]
        self._spline: UnivariateSpline | None = None

    def fit_smoothing_spline(self, smoothing: float | None = None) -> UnivariateSpline:
        n = self._t.size
        k = int(min(3, max(1, n - 1)))
        s = (
            max(0.0, (n * float(np.var(self._y))) * 0.05)
            if smoothing is None and n >= 4
            else float(smoothing or 0.0)
        )
        self._spline = UnivariateSpline(self._t, self._y, k=k, s=s)
        return self._spline

    def evaluate(self, t_grid: np.ndarray) -> np.ndarray:
        if self._spline is None:
            self.fit_smoothing_spline()
        assert self._spline is not None
        return self._spline(t_grid)

    def r2_and_ssr(self) -> tuple[float, float]:
        if self._spline is None:
            self.fit_smoothing_spline()
        assert self._spline is not None
        y_hat = self._spline(self._t)
        ss_res = float(np.sum((self._y - y_hat) ** 2))
        ss_tot = float(np.sum((self._y - np.mean(self._y)) ** 2))
        return (1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0), ss_res

    def time_to_soc_newton(self, target: float = 100.0, tol: float = 1e-4, maxiter: int = 80):
        if self._spline is None:
            self.fit_smoothing_spline()
        sp = self._spline
        d1 = sp.derivative(n=1)

        def f(tt: float) -> float:
            return float(sp(tt) - target)

        def fprime(tt: float) -> float:
            return float(d1(tt))

        t_last, y_last = float(self._t[-1]), float(self._y[-1])
        if y_last >= target - 1e-6:
            return t_last, "Ya alcanzó el objetivo"
        dt = max(self._t[-1] - self._t[-2], 1e-6) if self._t.size >= 2 else 1e-6
        slope = (self._y[-1] - self._y[-2]) / dt
        if slope <= 1e-6:
            return None, "Serie no creciente"
        t0 = t_last + max((target - y_last) / slope, 1e-3)
        try:
            root = newton(f, t0, fprime=fprime, tol=tol, maxiter=maxiter)
        except RuntimeError as exc:
            return None, f"Sin convergencia: {exc}"
        return (float(root), "Convergió") if np.isfinite(root) else (None, "Raíz no finita")


def _fig_charge(
    df: pd.DataFrame,
    t_model: np.ndarray | None = None,
    y_model: np.ndarray | None = None,
    t_smooth_h: np.ndarray | None = None,
    y_smooth: np.ndarray | None = None,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["t_min"],
            y=df["level"],
            mode="markers+lines",
            name="Medido",
            line=dict(color=ACCENT_YELLOW, width=1),
            marker=dict(size=8, color=ACCENT_YELLOW),
        )
    )
    if t_model is not None and y_model is not None:
        fig.add_trace(
            go.Scatter(
                x=t_model,
                y=y_model,
                mode="lines",
                name="Sigmoide C(t)",
                line=dict(color=ACCENT_CYAN, width=2),
            )
        )
    if t_smooth_h is not None and y_smooth is not None:
        fig.add_trace(
            go.Scatter(
                x=t_smooth_h * 60,
                y=y_smooth,
                mode="lines",
                name="Spline S(t)",
                line=dict(color="#B388FF", width=1, dash="dot"),
            )
        )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED, annotation_text="80% CC→CV")
    fig.add_hline(y=100, line_dash="dash", line_color=TEXT_MUTED, annotation_text="100%")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Carga (%) vs tiempo (min)", font=dict(color=ACCENT_CYAN)),
        xaxis_title="t (min)",
        yaxis_title="C (%)",
        yaxis=dict(range=[0, 105]),
        height=480,
        legend=dict(orientation="h", y=1.05),
    )
    return fig


def _ensure_data() -> pd.DataFrame:
    if "lab_df" not in st.session_state:
        st.session_state.lab_df = samples_dataframe()
    return st.session_state.lab_df


def step_inicio() -> None:
    st.subheader("Proyecto: ajuste de curva Li-ion")
    st.caption(INSTITUTION)
    st.markdown(
        """
        Modelar matemáticamente la **carga de una batería** para predecir el tiempo total
        y explicar por qué los primeros minutos son más rápidos que el tramo final (protocolo **CC-CV**).
        """
    )
    st.markdown(f"**Entrega:** {DELIVERY_DATE}")
    st.markdown("#### Integrantes")
    st.table(pd.DataFrame(TEAM, columns=["Nombre", "Rol", "Responsabilidad"]))
    c1, c2, c3 = st.columns(3)
    c1.metric("Muestras del reporte", "12")
    c2.metric("Intervalo", "5 min")
    c3.metric("Duración real", f"{CHARGE_TIME_REAL_MIN:.0f} min")


def step_metodologia() -> None:
    st.subheader("Metodología experimental")
    for num, titulo, desc in METHODOLOGY_STEPS:
        st.markdown(f"**{num}. {titulo}** — {desc}")
    st.markdown("#### Fases CC-CV")
    c1, c2 = st.columns(2)
    with c1:
        st.success("**CC (0–80%)** — corriente casi constante; crecimiento rápido.")
    with c2:
        st.warning("**CV (80–100%)** — voltaje fijo; corriente baja; curva se aplana.")
    st.latex(r"C(t)=\frac{L}{1+e^{-k(t-t_0)}},\quad L=100\%")


def step_recoleccion() -> None:
    st.subheader("Recolección de muestras")
    fuente = st.radio(
        "Fuente de datos",
        ["Reporte (12 mediciones)", "ADB en vivo", "Comparar 2º dispositivo"],
        horizontal=True,
    )
    if fuente == "Reporte (12 mediciones)":
        st.session_state.lab_df = samples_dataframe()
    elif fuente == "Comparar 2º dispositivo":
        st.session_state.lab_df = samples_dataframe(SAMPLES_ALT)
    else:
        adb = st.text_input("Ruta adb", value="adb")
        if st.button("Tomar lectura ahora"):
            r = fetch_battery_reading(adb)
            if r.error:
                st.error(r.error)
            elif r.level is not None:
                if "live_rows" not in st.session_state:
                    st.session_state.live_rows = []
                st.session_state.live_rows.append(
                    {"t_min": len(st.session_state.live_rows) * 5, "level": float(r.level), "t_h": len(st.session_state.live_rows) * 5 / 60}
                )
        if st.session_state.get("live_rows"):
            st.session_state.lab_df = pd.DataFrame(st.session_state.live_rows)
        if st.button("Cargar datos del reporte como base"):
            st.session_state.lab_df = samples_dataframe()

    df = _ensure_data()
    st.dataframe(df[["t_min", "level"]], use_container_width=True, hide_index=True)
    st.caption("Protocolo: modo avión, brillo 0%, registro cada 5 min desde <5% hasta 100%.")
    t_m = np.linspace(0, float(df["t_min"].max()), 200)
    st.plotly_chart(_fig_charge(df, t_m, logistic_c(t_m)), use_container_width=True)


def step_modelo() -> None:
    st.subheader("Modelación y R²")
    df = _ensure_data()
    stats = report_fit_stats(df)
    t_line = np.linspace(0, float(df["t_min"].max()), 200)
    y_log = logistic_c(t_line)
    c1, c2, c3 = st.columns(3)
    c1.metric("R² logístico", f"{stats['r2_logistic']:.4f}")
    c2.metric("R² lineal", f"{stats['r2_linear']:.4f}")
    c3.metric("Muestras", int(stats["n_samples"]))

    engine = BatteryNumericEngine(df["t_h"].to_numpy(), df["level"].to_numpy())
    engine.fit_smoothing_spline()
    t_h = np.linspace(0, float(df["t_h"].max()) + 0.1, 200)
    y_sp = engine.evaluate(t_h)
    r2s, _ = engine.r2_and_ssr()
    st.metric("R² spline (Lab)", f"{r2s:.4f}")
    st.plotly_chart(_fig_charge(df, t_line, y_log, t_h, y_sp), use_container_width=True)
    st.caption(f"Parámetros del reporte: k={K_RATE}, t₀={T0_INFL} min.")


def step_newton() -> None:
    st.subheader("Newton-Raphson")
    st.markdown("Resolver **C(t) − objetivo = 0** para estimar en qué minuto se alcanza un porcentaje.")
    objetivo = st.slider("Porcentaje objetivo (%)", 10, 99, 80)
    t_star, msg, steps = newton_time_for_target(float(objetivo))
    if t_star is not None:
        mm = int(t_star)
        ss = int(round((t_star - mm) * 60))
        st.success(f"Tiempo estimado: **{mm} min {ss} s** — {msg}")
    else:
        st.error(msg)
    if steps:
        st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)
    st.info(
        f"Referencia del reporte: 80% en **{NEWTON_80_MIN} min** "
        f"({NEWTON_80_ITER} iteraciones). El ajuste multivariable (k, t₀) reportó NaN."
    )


def step_stats() -> None:
    st.subheader("Resultados del reporte")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Energía", f"{ENERGY_WH} Wh")
    c2.metric("Tiempo real", f"{CHARGE_TIME_REAL_MIN:.0f} min")
    c3.metric("Tiempo ideal", f"{TIME_IDEAL_MIN:.1f} min")
    c4.metric("Eficiencia útil", f"~{EFFICIENCY_PCT}%")
    st.markdown(
        """
        **Conclusiones (reporte):**
        - La carga sigue un comportamiento **sigmoide** (no lineal).
        - Newton-Raphson **funciona** en el problema escalar (tiempo para un %).
        - El ajuste simultáneo de parámetros puede **diverger** (NaN) — usar semillas estables o Levenberg-Marquardt.
        """
    )
    st.markdown("**Recomendaciones:** gradiente descendente, eliminar extremos 0%/100% del ajuste global, validar con Python/MATLAB.")


def main() -> None:
    st.set_page_config(
        page_title="Laboratorio Li-ion",
        page_icon="🔋",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_style()

    idx = render_step_header(
        WIZARD_LAB_STEPS,
        "lab_step",
        "Laboratorio de batería",
        "Asistente del proyecto de Métodos Numéricos — carga Li-ion",
    )
    step_id = WIZARD_LAB_STEPS[idx][0]

    if step_id == "inicio":
        step_inicio()
    elif step_id == "metodo":
        step_metodologia()
    elif step_id == "datos":
        step_recoleccion()
    elif step_id == "modelo":
        step_modelo()
    elif step_id == "newton":
        step_newton()
    else:
        step_stats()

    step_nav_buttons("lab_step", len(WIZARD_LAB_STEPS))


if __name__ == "__main__":
    main()
