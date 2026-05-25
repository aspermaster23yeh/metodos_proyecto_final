"""
Laboratorio de carga Li-ion — asistente por pasos (Streamlit).
Ejecutar: streamlit run main.py
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime

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
from sample_store import clear_session, export_csv_bytes, load_session, rows_to_dataframe, save_session
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


def list_adb_devices(adb_bin: str = "adb") -> tuple[list[str], str | None]:
    """Lista dispositivos Android conectados por USB/Wi‑Fi debugging."""
    try:
        result = subprocess.run(
            [adb_bin, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return [], result.stderr.strip() or "Error al ejecutar adb devices"
        devices: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices, None
    except FileNotFoundError:
        return [], "No se encontró `adb`. Instala Android platform-tools."
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def _init_live_state() -> None:
    if "live_rows" not in st.session_state:
        data = load_session()
        st.session_state.live_rows = list(data.get("rows", []))
    if "live_t0" not in st.session_state:
        st.session_state.live_t0 = time.time()
    if "live_monitoring" not in st.session_state:
        st.session_state.live_monitoring = False
    if "last_sample_ts" not in st.session_state:
        st.session_state.last_sample_ts = 0.0


def _elapsed_min() -> float:
    return (time.time() - st.session_state.live_t0) / 60.0


def _append_live_row(
    level: float,
    *,
    source: str,
    voltage_mv: int | None = None,
    current_ua: int | None = None,
    temperature_c: float | None = None,
) -> None:
    t_min = _elapsed_min()
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "t_min": round(t_min, 2),
        "t_h": round(t_min / 60.0, 4),
        "level": float(level),
        "voltage_mv": voltage_mv,
        "current_ua": current_ua,
        "temperature_c": temperature_c,
        "source": source,
    }
    st.session_state.live_rows.append(row)
    st.session_state.last_sample_ts = time.time()
    save_session(
        st.session_state.live_rows,
        device_label=st.session_state.get("device_label", ""),
        platform=st.session_state.get("platform", "android"),
        session_started=st.session_state.get("session_started"),
    )


def _capture_adb_sample(adb_bin: str) -> bool:
    reading = fetch_battery_reading(adb_bin)
    if reading.error:
        st.error(f"ADB: {reading.error}")
        return False
    if reading.level is None:
        st.error("No se pudo leer el nivel de batería.")
        return False
    _append_live_row(
        reading.level,
        source="adb",
        voltage_mv=reading.voltage_mv,
        current_ua=reading.current_ua,
        temperature_c=reading.temperature_c,
    )
    return True


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
    st.info(
        "**Android:** lectura automática con USB y depuración USB activada (`adb`). "
        "**iPhone:** Apple no permite ADB; usa **entrada manual** cada 5 min (mismo protocolo del reporte)."
    )

    fuente = st.radio(
        "Fuente de datos",
        ["Tiempo real (guardar bitácora)", "Reporte (12 mediciones)", "Comparar 2º dispositivo (reporte)"],
        horizontal=True,
    )

    if fuente == "Reporte (12 mediciones)":
        st.session_state.lab_df = samples_dataframe()
        st.session_state.live_monitoring = False
    elif fuente == "Comparar 2º dispositivo (reporte)":
        st.session_state.lab_df = samples_dataframe(SAMPLES_ALT)
        st.session_state.live_monitoring = False
    else:
        _init_live_state()
        plataforma = st.radio(
            "Tipo de dispositivo",
            ["Android (ADB automático)", "Manual — iPhone u otro (tú ingresas el %)"],
            horizontal=True,
        )
        es_android = plataforma.startswith("Android")
        st.session_state.platform = "android" if es_android else "manual"
        st.session_state.device_label = st.text_input(
            "Nombre del dispositivo (opcional)",
            value=st.session_state.get("device_label", ""),
            placeholder="Ej. Samsung A54, iPhone 13",
        )

        intervalo_s = st.slider(
            "Intervalo entre muestras automáticas (segundos)",
            min_value=30,
            max_value=600,
            value=300,
            step=30,
            help="El reporte usa 5 min (300 s). En pruebas puedes bajar a 30 s.",
        )

        adb_bin = "adb"
        if es_android:
            adb_bin = st.text_input("Ruta de adb", value="adb", key="adb_path")
            if st.button("Buscar dispositivos conectados"):
                devices, err = list_adb_devices(adb_bin)
                if err:
                    st.error(err)
                elif not devices:
                    st.warning(
                        "No hay dispositivos. Conecta el Android por USB, activa "
                        "**Opciones de desarrollador → Depuración USB** y acepta la llave RSA."
                    )
                else:
                    st.success("Conectados: " + ", ".join(devices))
        else:
            st.caption(
                "En cada intervalo actualiza el % que ves en Ajustes → Batería y pulsa **Muestra ahora**, "
                "o deja el valor actualizado antes del auto-muestreo."
            )
            manual_pct = st.number_input("Porcentaje actual (%)", 0, 100, 50, key="manual_pct")

        st.markdown("#### Control en tiempo real")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("▶ Iniciar monitoreo", type="primary", disabled=st.session_state.live_monitoring):
                st.session_state.live_monitoring = True
                st.session_state.live_t0 = time.time()
                st.session_state.last_sample_ts = 0.0
                st.session_state.session_started = datetime.now().isoformat(timespec="seconds")
                if es_android:
                    _capture_adb_sample(adb_bin)
                else:
                    _append_live_row(float(manual_pct), source="manual")
                st.rerun()
        with c2:
            if st.button("⏹ Detener", disabled=not st.session_state.live_monitoring):
                st.session_state.live_monitoring = False
                st.rerun()
        with c3:
            if st.button("📸 Muestra ahora"):
                if es_android:
                    if _capture_adb_sample(adb_bin):
                        st.toast("Muestra guardada")
                else:
                    _append_live_row(float(manual_pct), source="manual")
                    st.toast("Muestra guardada")
                st.rerun()
        with c4:
            if st.button("💾 Guardar bitácora"):
                save_session(
                    st.session_state.live_rows,
                    device_label=st.session_state.get("device_label", ""),
                    platform=st.session_state.get("platform", "android"),
                    session_started=st.session_state.get("session_started"),
                )
                st.success(f"Guardado en `data/charge_samples.json` ({len(st.session_state.live_rows)} filas)")

        acc1, acc2, acc3 = st.columns(3)
        with acc1:
            if st.button("Cargar bitácora guardada"):
                data = load_session()
                st.session_state.live_rows = list(data.get("rows", []))
                st.session_state.device_label = data.get("device_label", "")
                st.rerun()
        with acc2:
            if st.button("Reiniciar bitácora"):
                st.session_state.live_rows = []
                st.session_state.live_monitoring = False
                clear_session()
                st.rerun()
        with acc3:
            st.download_button(
                "Descargar CSV",
                data=export_csv_bytes(st.session_state.live_rows),
                file_name="bitacora_carga.csv",
                mime="text/csv",
                disabled=len(st.session_state.live_rows) == 0,
            )

        if st.session_state.live_monitoring:
            st.markdown(
                f"<p style='color:{ACCENT_YELLOW};font-weight:600;'>● EN VIVO — "
                f"próxima muestra automática cada {intervalo_s}s</p>",
                unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Muestras", len(st.session_state.live_rows))
            m2.metric("Tiempo transcurrido (min)", f"{_elapsed_min():.1f}")
            if st.session_state.live_rows:
                m3.metric("Último %", f"{st.session_state.live_rows[-1]['level']:.0f}")

        if st.session_state.live_rows:
            st.session_state.lab_df = rows_to_dataframe(st.session_state.live_rows)
        else:
            st.warning("Sin muestras aún. Pulsa **Iniciar monitoreo** o **Muestra ahora**.")

        # Bucle en vivo: toma muestra y recarga cuando pasa el intervalo
        if st.session_state.live_monitoring:
            now = time.time()
            if now - st.session_state.last_sample_ts >= intervalo_s:
                if es_android:
                    _capture_adb_sample(adb_bin)
                else:
                    _append_live_row(float(manual_pct), source="manual")
            time.sleep(2)
            st.rerun()

    df = _ensure_data()
    if df.empty:
        st.stop()
    cols_show = [c for c in ["t_min", "level", "voltage_mv", "temperature_c", "source", "timestamp"] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True, hide_index=True)
    st.caption("Protocolo: modo avión, brillo 0%, registro cada 5 min desde <5% hasta 100%.")
    t_m = np.linspace(0, max(float(df["t_min"].max()), 1), 200)
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
