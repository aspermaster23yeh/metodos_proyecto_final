"""
ADB Battery Lab — Streamlit desktop monitor + spline smoothing + Newton–Raphson ETA @ 100%.
Run: streamlit run main.py
Requires: Android platform-tools (adb) on PATH, USB debugging enabled on device.
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

from theme import ACCENT_CYAN, ACCENT_YELLOW, BG, GRID, TEXT_MUTED, inject_global_style


# ---------------------------------------------------------------------------
# ADB extraction module (subprocess + parse)
# ---------------------------------------------------------------------------
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
        raise RuntimeError(result.stderr.strip() or f"adb exit {result.returncode}")
    return result.stdout or ""


def parse_dumpsys_battery(text: str) -> BatteryReading:
    """Parse `dumpsys battery` for level, voltage, current, temperature."""
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
    return BatteryReading(
        level=level,
        voltage_mv=voltage,
        current_ua=current,
        temperature_c=temp_c,
        raw_text=text,
        error=None,
    )


def fetch_battery_reading(adb_bin: str) -> BatteryReading:
    try:
        text = run_dumpsys_battery(adb_bin=adb_bin)
        return parse_dumpsys_battery(text)
    except Exception as exc:  # noqa: BLE001 — surface to UI
        return BatteryReading(
            level=None,
            voltage_mv=None,
            current_ua=None,
            temperature_c=None,
            raw_text="",
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Numeric engine: spline smoothing + Newton–Raphson for t @ SoC=100%
# ---------------------------------------------------------------------------
class BatteryNumericEngine:
    """
    Fits a smoothing cubic spline SoC ≈ S(t) and uses Newton–Raphson on
    f(t) = S(t) - 100 to estimate time-to-full (hours from t=0 anchor).
    Goodness-of-fit vs samples: R² and SSR on smoothed vs observed levels.
    """

    def __init__(self, times_h: np.ndarray, levels: np.ndarray) -> None:
        self._t = np.asarray(times_h, dtype=float).ravel()
        self._y = np.asarray(levels, dtype=float).ravel()
        if self._t.size != self._y.size or self._t.size < 2:
            raise ValueError("times_h and levels must have equal length >= 2")
        order = np.argsort(self._t)
        self._t = self._t[order]
        self._y = self._y[order]
        ts: list[float] = []
        ys: list[float] = []
        for ti, yi in zip(self._t.tolist(), self._y.tolist()):
            if ts and abs(ti - ts[-1]) < 1e-9:
                ys[-1] = 0.5 * (ys[-1] + yi)
            else:
                ts.append(float(ti))
                ys.append(float(yi))
        self._t = np.asarray(ts, dtype=float)
        self._y = np.asarray(ys, dtype=float)
        self._spline: UnivariateSpline | None = None
        self._s_smooth: float = 0.0

    def fit_smoothing_spline(self, smoothing: float | None = None) -> UnivariateSpline:
        n = self._t.size
        k = int(min(3, max(1, n - 1)))
        if smoothing is None:
            s = max(0.0, (n * float(np.var(self._y))) * 0.05) if n >= 4 else 0.0
        else:
            s = float(smoothing)
        self._s_smooth = s
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
        y = self._y
        ss_res = float(np.sum((y - y_hat) ** 2))
        y_mean = float(np.mean(y))
        ss_tot = float(np.sum((y - y_mean) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
        return r2, ss_res

    def time_to_soc_newton(
        self,
        target: float = 100.0,
        tol: float = 1e-4,
        maxiter: int = 80,
    ) -> tuple[float | None, str]:
        """
        Solve S(t) - target = 0 with SciPy's scalar newton (Newton–Raphson + fallback).
        Returns (t_star_hours, status_message).
        """
        if self._spline is None:
            self.fit_smoothing_spline()
        assert self._spline is not None
        sp = self._spline
        d1 = sp.derivative(n=1)

        def f(tt: float) -> float:
            return float(sp(tt) - target)

        def fprime(tt: float) -> float:
            return float(d1(tt))

        t_last = float(self._t[-1])
        y_last = float(self._y[-1])
        if y_last >= target - 1e-6:
            return t_last, "already at or above target (within spline)"

        if self._t.size >= 2:
            dt = max(self._t[-1] - self._t[-2], 1e-6)
            slope = (self._y[-1] - self._y[-2]) / dt
        else:
            slope = 0.0

        if slope <= 1e-6:
            return None, "non-increasing series — cannot extrapolate charge ETA"

        t0 = t_last + max((target - y_last) / slope, 1e-3)

        try:
            root = newton(
                func=f,
                x0=t0,
                fprime=fprime,
                tol=tol,
                maxiter=maxiter,
            )
        except RuntimeError as exc:
            return None, f"Newton did not converge: {exc}"

        if not np.isfinite(root):
            return None, "non-finite root"

        if root < float(self._t[0]):
            return None, "root before first sample — check data"

        return float(root), "converged"


# ---------------------------------------------------------------------------
# Plotly figure
# ---------------------------------------------------------------------------
def build_experimental_figure(df: pd.DataFrame, t_smooth: np.ndarray, y_smooth: np.ndarray) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["t_h"],
            y=df["level"],
            mode="lines+markers",
            name="SoC samples",
            line=dict(color=ACCENT_YELLOW, width=1),
            marker=dict(size=7, color=ACCENT_YELLOW, line=dict(width=0)),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t_smooth,
            y=y_smooth,
            mode="lines",
            name="Spline model S(t)",
            line=dict(color=ACCENT_CYAN, width=2),
        )
    )
    fig.add_hline(y=100, line_dash="dash", line_color=TEXT_MUTED, annotation_text="100%")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="JetBrains Mono, monospace", color=TEXT_MUTED, size=12),
        title=dict(
            text="Experimental Visualization — State of Charge vs. time",
            font=dict(color=ACCENT_CYAN, size=16),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=48, r=24, t=64, b=48),
        xaxis=dict(
            title="t (h) — anchored at session start",
            gridcolor=GRID,
            zerolinecolor=GRID,
        ),
        yaxis=dict(
            title="SoC (%)",
            range=[0, 105],
            gridcolor=GRID,
            zerolinecolor=GRID,
        ),
        hovermode="x unified",
        height=520,
    )
    return fig


def _demo_series(n: int = 36) -> pd.DataFrame:
    """Synthetic monotonic charge curve for UI preview without adb."""
    t_h = np.linspace(0, 1.25, n)
    levels = 22 + 78 * (1 - np.exp(-1.4 * t_h))
    return pd.DataFrame({"t_h": t_h, "level": levels})


def main() -> None:
    st.set_page_config(page_title="ADB Battery Lab", layout="wide", initial_sidebar_state="expanded")
    inject_global_style()

    if "t0" not in st.session_state:
        st.session_state.t0 = time.time()
    if "rows" not in st.session_state:
        st.session_state.rows = []

    st.sidebar.markdown("### Acquisition")
    adb_bin = st.sidebar.text_input("adb binary", value="adb")
    demo = st.sidebar.checkbox("Demo mode (no adb)", value=False)
    poll_preset = st.sidebar.selectbox(
        "Sampling preset",
        ["Custom", "Metodología (5 min)", "Fast (8 s)"],
        index=2,
        help="Metodología alinea la recolección con intervalos de 5 min del protocolo.",
    )
    if poll_preset == "Metodología (5 min)":
        poll_default = 300
    elif poll_preset == "Fast (8 s)":
        poll_default = 8
    else:
        poll_default = 8
    poll_s = st.sidebar.slider("Auto-refresh (s)", 1, 600, poll_default)
    if st.sidebar.button("Reset time anchor"):
        st.session_state.t0 = time.time()
        st.session_state.rows = []
        st.rerun()
    if st.sidebar.button("Clear samples"):
        st.session_state.rows = []
        st.rerun()

    st.sidebar.markdown("### Newton–Raphson")
    nr_tol = st.sidebar.number_input("Tolerance", value=1e-4, format="%.6f", min_value=1e-12)
    nr_max = st.sidebar.number_input("Max iterations", min_value=5, max_value=500, value=80, step=5)

    st.sidebar.markdown("### Spline smoothing")
    smooth_override = st.sidebar.checkbox("Manual smoothing (s)", value=False)
    smooth_s = st.sidebar.number_input(
        "UnivariateSpline s",
        min_value=0.0,
        value=0.0,
        step=0.01,
        help="0 = let engine pick a small default when n≥4",
        disabled=not smooth_override,
    )

    st.markdown(
        f"<h1 style='color:{ACCENT_CYAN};margin-bottom:0.2rem;'>"
        "CYBER-PHYSICAL BATTERY LAB"
        "</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{ACCENT_YELLOW};font-size:0.95rem;margin-top:0;'>"
        "Experimental telemetry · spline synthesis · Newton–Raphson full-charge horizon"
        "</p>",
        unsafe_allow_html=True,
    )

    if demo:
        df = _demo_series()
    else:
        reading = fetch_battery_reading(adb_bin)
        if reading.error:
            st.warning(f"ADB error — showing last frame only. ({reading.error})")
        if reading.level is not None and not reading.error:
            now = time.time()
            st.session_state.rows.append(
                {
                    "t_h": (now - st.session_state.t0) / 3600.0,
                    "level": float(reading.level),
                    "voltage_mv": reading.voltage_mv,
                    "current_ua": reading.current_ua,
                    "temperature_c": reading.temperature_c,
                }
            )
        df = pd.DataFrame(st.session_state.rows)

    fig: go.Figure | None = None
    r2: float | None = None
    ssr: float | None = None
    t100: float | None = None
    nr_status = "awaiting data"
    t_obs_last: float | None = None

    if df.empty or "level" not in df.columns:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=BG,
            plot_bgcolor=BG,
            height=520,
            title=dict(text="Awaiting telemetry", font=dict(color=ACCENT_CYAN)),
        )
    elif len(df) < 2:
        nr_status = "need ≥ 2 samples"
        fig = build_experimental_figure(df, df["t_h"].to_numpy(), df["level"].to_numpy())
    else:
        t_obs = df["t_h"].to_numpy(dtype=float)
        y_obs = df["level"].to_numpy(dtype=float)
        t_obs_last = float(t_obs[-1])
        engine = BatteryNumericEngine(t_obs, y_obs)
        if smooth_override:
            engine.fit_smoothing_spline(smoothing=smooth_s if smooth_s > 0 else None)
        else:
            engine.fit_smoothing_spline(None)

        t_min, t_max = float(t_obs.min()), float(t_obs.max())
        span = max(0.05, t_max - t_min)
        t_smooth = np.linspace(t_min, t_max + 0.35 * span, 400)
        y_smooth = engine.evaluate(t_smooth)
        fig = build_experimental_figure(df, t_smooth, y_smooth)
        t100, nr_status = engine.time_to_soc_newton(target=100.0, tol=float(nr_tol), maxiter=int(nr_max))
        r2, ssr = engine.r2_and_ssr()

    col_viz, col_syn = st.columns([2.15, 1.0])

    with col_viz:
        st.markdown(
            f"#### <span style='color:{ACCENT_YELLOW}'>Experimental Visualization</span>",
            unsafe_allow_html=True,
        )
        st.latex(
            r"\text{Observed SoC: } y_i \approx S(t_i), \quad "
            r"S \in \mathcal{S}_k^{m} \ \text{(smoothing cubic spline)}"
        )

        if df.empty or "level" not in df.columns:
            st.info("Collecting samples… connect device with USB debugging or enable **Demo mode**.")
        elif len(df) < 2:
            st.info("Need ≥ 2 samples for spline + Newton analysis.")

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

        if not demo and not df.empty:
            last = df.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("SoC (%)", f"{last['level']:.0f}" if pd.notna(last.get("level")) else "—")
            c2.metric("Voltage (mV)", f"{int(last['voltage_mv'])}" if pd.notna(last.get("voltage_mv")) else "—")
            c3.metric("Current (µA)", f"{int(last['current_ua'])}" if pd.notna(last.get("current_ua")) else "—")
            c4.metric("Temp (°C)", f"{last['temperature_c']:.1f}" if pd.notna(last.get("temperature_c")) else "—")

    with col_syn:
        st.markdown(
            f"#### <span style='color:{ACCENT_CYAN}'>Model Synthesis</span>",
            unsafe_allow_html=True,
        )
        st.latex(r"f(t) = S(t) - 100 \quad\Rightarrow\quad t_{n+1} = t_n - \frac{f(t_n)}{f'(t_n)}")
        st.latex(
            r"R^2 = 1 - \frac{\sum_i (y_i - \hat{y}_i)^2}{\sum_i (y_i - \bar{y})^2}, \quad "
            r"\mathrm{SSR} = \sum_i (y_i - \hat{y}_i)^2"
        )
        st.metric("R² (spline vs samples)", f"{r2:.6f}" if r2 is not None else "—")
        st.metric("SSR", f"{ssr:.4f}" if ssr is not None else "—")
        if t100 is not None and t_obs_last is not None:
            remain = max(0.0, (t100 - t_obs_last) * 60.0)
            st.metric("t @ 100% (model horizon, h)", f"{t100:.4f}")
            st.metric("Δ from last sample (min)", f"{remain:.2f}")
        elif t100 is not None:
            st.metric("t @ 100% (model horizon, h)", f"{t100:.4f}")
        st.caption(nr_status)
        st.latex(r"\hat{y}_i = S(t_i), \quad S \ \text{fitted via SciPy UnivariateSpline}")

    if not demo:
        time.sleep(float(poll_s))
        st.rerun()


if __name__ == "__main__":
    main()
