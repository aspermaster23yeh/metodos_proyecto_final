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

import pandas as pd
import streamlit as st

from battery_models import (
    compare_models,
    compare_to_reference,
    comparison_verdict_es,
    device_summary,
    estimate_cv_start_min,
    format_newton_steps,
    multivar_fit_note,
    newton_batch_table,
    newton_time_for_target,
    try_logistic_curve_fit,
)
from lab_charts import (
    fig_charge_simple,
    fig_dual_devices,
    fig_model_comparison,
    fig_session_vs_reference,
)
from report_data import (
    CHARGE_TIME_REAL_MIN,
    DELIVERY_DATE,
    DEVICE_ALT_LABEL,
    DEVICE_MAIN_LABEL,
    EFFICIENCY_PCT,
    ENERGY_WH,
    INSTITUTION,
    K_RATE,
    MAIN_DEVICE_NAME,
    MAIN_SESSION_FILENAME,
    METHODOLOGY_STEPS,
    NEWTON_80_ITER,
    NEWTON_80_MIN,
    NEWTON_BATCH_TARGETS,
    REFERENCE_LABEL,
    SAMPLES_ALT,
    SAMPLES_MAIN,
    T0_INFL,
    TEAM,
    TIME_IDEAL_MIN,
    WIZARD_LAB_STEPS,
    samples_dataframe,
)
from sample_store import (
    SessionInfo,
    clear_session,
    ensure_demo_sessions,
    export_csv_bytes,
    list_sessions,
    load_session,
    load_session_file,
    rows_to_dataframe,
    save_session,
    save_to_history,
)
from theme import ACCENT_CYAN, ACCENT_YELLOW, inject_global_style
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
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dispositivo principal", MAIN_DEVICE_NAME)
    c2.metric("Muestras del reporte", "12")
    c3.metric("Intervalo", "5 min")
    c4.metric("Duración real", f"{CHARGE_TIME_REAL_MIN:.0f} min")


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


def _render_historial_sesiones() -> None:
    """Historial en data/sessions/*.json — comparar con el proyecto principal."""
    ensure_demo_sessions()
    sessions = list_sessions()
    if not sessions:
        st.warning("No hay sesiones en el historial.")
        return

    def _fmt_session(s: SessionInfo) -> str:
        tag = " ★ principal" if s.is_main else ""
        return f"{s.device_label} — {s.session_date} ({s.n_samples} muestras, {s.final_level:.0f}%){tag}"

    keys = [s.filename for s in sessions]
    default_ix = keys.index(MAIN_SESSION_FILENAME) if MAIN_SESSION_FILENAME in keys else 0
    elegido = st.selectbox(
        "Seleccionar sesión Android",
        keys,
        index=default_ix,
        format_func=lambda k: _fmt_session(next(s for s in sessions if s.filename == k)),
    )
    info = next(s for s in sessions if s.filename == elegido)
    if info.is_main:
        st.success(f"**{MAIN_DEVICE_NAME}** — dispositivo principal del proyecto (bitácora del reporte).")
    raw = load_session_file(elegido)
    df_sess = rows_to_dataframe(raw["rows"])
    df_ref = samples_dataframe(SAMPLES_MAIN)

    if info.notes:
        st.caption(info.notes)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Muestras", info.n_samples)
    c2.metric("Tiempo registro (min)", f"{info.t_100_min:.0f}")
    c3.metric("Carga final", f"{info.final_level:.0f} %")
    c4.metric("Plataforma", info.platform)

    summ = device_summary(df_sess)
    cmp_sess = compare_models(df_sess)
    st.markdown("#### Estadísticas de la prueba")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("R² logístico", f"{summ['r2_logistic']:.4f}")
    m2.metric("R² lineal", f"{summ['r2_linear']:.4f}")
    m3.metric("Inicio CV (~80%)", f"{cmp_sess.t_cv_min:.1f} min" if cmp_sess.t_cv_min else "—")
    if summ["initial_slope_pct_per_min"] is not None:
        m4.metric("Pendiente 0–5 min", f"{summ['initial_slope_pct_per_min']:.2f} %/min")

    diff = compare_to_reference(df_sess, df_ref, REFERENCE_LABEL)
    st.markdown(f"#### Comparación vs {MAIN_DEVICE_NAME}")
    st.dataframe(
        pd.DataFrame(
            [
                {"Métrica": "Tiempo hasta última muestra (min)", "Sesión": summ["t_100_min"], "Referencia": diff["reference"]["t_100_min"], "Δ": diff["delta_t100_min"]},
                {"Métrica": "Carga final (%)", "Sesión": summ["final_level"], "Referencia": diff["reference"]["final_level"], "Δ": diff["delta_final_level"]},
                {"Métrica": "R² logístico", "Sesión": f"{summ['r2_logistic']:.4f}", "Referencia": f"{diff['reference']['r2_logistic']:.4f}", "Δ": f"{diff['delta_r2_logistic']:+.4f}"},
                {
                    "Métrica": "Pendiente inicial (%/min)",
                    "Sesión": summ["initial_slope_pct_per_min"],
                    "Referencia": diff["reference"]["initial_slope_pct_per_min"],
                    "Δ": diff["delta_slope"],
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if diff["delta_t100_min"] > 0:
        st.info(f"Esta sesión tardó **{diff['delta_t100_min']:.0f} min más** que **{MAIN_DEVICE_NAME}** en llegar al tramo final.")
    elif diff["delta_t100_min"] < 0:
        st.success(f"Esta sesión fue **{abs(diff['delta_t100_min']):.0f} min más rápida** que **{MAIN_DEVICE_NAME}**.")
    if diff["delta_final_level"] < 0:
        st.warning("No alcanzó el mismo porcentaje final que el experimento de referencia (100%).")

    st.plotly_chart(
        fig_session_vs_reference(df_sess, df_ref, info.device_label, REFERENCE_LABEL),
        use_container_width=True,
    )

    with st.expander("Modelos ajustados en esta sesión"):
        st.dataframe(
            pd.DataFrame(
                [
                    {"Modelo": "Lineal", "R²": f"{cmp_sess.r2_linear:.4f}"},
                    {"Modelo": "Logístico", "R²": f"{cmp_sess.r2_logistic:.4f}"},
                    {"Modelo": "Spline", "R²": f"{cmp_sess.r2_spline:.4f}"},
                ]
            ),
            hide_index=True,
        )
        st.markdown(comparison_verdict_es(cmp_sess))
        st.plotly_chart(fig_model_comparison(df_sess, cmp_sess), use_container_width=True)

    st.markdown("#### Bitácora de la sesión")
    st.dataframe(df_sess[["t_min", "level", "voltage_mv", "temperature_c", "timestamp"]], use_container_width=True, hide_index=True)

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Usar en el Laboratorio", type="primary"):
            st.session_state.lab_df = df_sess
            st.session_state.live_monitoring = False
            st.success(f"Cargado: {info.device_label}")
            st.rerun()
    with b2:
        st.download_button(
            "Descargar CSV de sesión",
            data=export_csv_bytes(raw["rows"]),
            file_name=elegido.replace(".json", ".csv"),
            mime="text/csv",
        )
    with b3:
        st.caption(f"Archivo: `data/sessions/{elegido}`")


def step_recoleccion() -> None:
    st.subheader("Recolección de muestras")
    st.info(
        "**Android:** lectura automática con USB y depuración USB activada (`adb`). "
        "**iPhone:** Apple no permite ADB; usa **entrada manual** cada 5 min. "
        "**Historial:** sesiones guardadas en `data/sessions/`."
    )

    fuente = st.radio(
        "Fuente de datos",
        [
            "Historial de sesiones Android",
            "Tiempo real (guardar bitácora)",
            "Reporte (12 mediciones)",
            "Comparar 2º dispositivo (reporte)",
        ],
        horizontal=True,
    )

    if fuente == "Historial de sesiones Android":
        _render_historial_sesiones()
        st.session_state.live_monitoring = False
        if "lab_df" not in st.session_state:
            st.session_state.lab_df = samples_dataframe()
        df = st.session_state.lab_df
        if not df.empty:
            st.markdown("---")
            st.caption("Vista previa de los datos activos en el Laboratorio (usa **Usar en el Laboratorio** arriba para cambiar).")
            t_cv = estimate_cv_start_min(df)
            st.plotly_chart(fig_charge_simple(df, t_cv), use_container_width=True)
        return

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
            placeholder="Ej. POCO X 7 Pro, iPhone 13",
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
            if st.button("💾 Guardar"):
                save_session(
                    st.session_state.live_rows,
                    device_label=st.session_state.get("device_label", ""),
                    platform=st.session_state.get("platform", "android"),
                    session_started=st.session_state.get("session_started"),
                )
                st.success(f"Bitácora actual: `data/charge_samples.json` ({len(st.session_state.live_rows)} filas)")

        st.markdown("##### Historial (no sobrescribe)")
        h1, h2 = st.columns(2)
        with h1:
            if st.button("📁 Guardar copia en historial"):
                if not st.session_state.live_rows:
                    st.warning("No hay muestras para guardar.")
                else:
                    path = save_to_history(
                        st.session_state.live_rows,
                        device_label=st.session_state.get("device_label", "") or "Android",
                        platform=st.session_state.get("platform", "android"),
                        session_started=st.session_state.get("session_started"),
                        notes="Copia desde monitoreo en vivo del Laboratorio.",
                    )
                    st.success(f"Guardado: `{path.name}`")
        with h2:
            ensure_demo_sessions()
            st.caption(f"{len(list_sessions())} sesión(es) en `data/sessions/`.")

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
    t_cv = estimate_cv_start_min(df)
    st.plotly_chart(fig_charge_simple(df, t_cv), use_container_width=True)


def step_modelo() -> None:
    st.subheader("Modelación y comparativa de modelos")
    df = _ensure_data()
    if len(df) < 2:
        st.warning("Se necesitan al menos 2 muestras. Vuelve a **Recolección** o carga el reporte.")
        return

    cmp = compare_models(df)
    st.markdown("#### Tabla R²")
    tabla = pd.DataFrame(
        [
            {"Modelo": "Lineal", "R²": f"{cmp.r2_linear:.4f}", "Nota": "Una recta; no satura en 100%."},
            {"Modelo": "Logístico", "R²": f"{cmp.r2_logistic:.4f}", "Nota": "Sigmoide CC-CV del reporte."},
            {"Modelo": "Spline", "R²": f"{cmp.r2_spline:.4f}", "Nota": "Ajuste flexible punto a punto."},
        ]
    )
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.markdown(comparison_verdict_es(cmp))
    if cmp.t_cv_min is not None:
        st.caption(f"Transición estimada a fase **CV** (~80%): ≈ **{cmp.t_cv_min:.1f} min**.")
    st.plotly_chart(fig_model_comparison(df, cmp), use_container_width=True)
    st.caption(f"Sigmoide de referencia: k={K_RATE}, t₀={T0_INFL} min.")

    with st.expander("¿Por qué falló el ajuste simultáneo de k y t₀?"):
        st.markdown(multivar_fit_note())
        fit = try_logistic_curve_fit(df)
        if fit["ok"]:
            st.success(fit["message"])
        else:
            st.warning(fit["message"])
        st.markdown(
            "**Próximo paso recomendado:** **Levenberg-Marquardt** "
            "(`scipy.optimize.curve_fit` / `least_squares`) con semilla estable y, si hace falta, "
            "excluir los extremos 0% y 100% del ajuste global."
        )

    st.markdown("---")
    st.markdown(f"#### {MAIN_DEVICE_NAME} vs dispositivo alternativo")
    df_main = samples_dataframe(SAMPLES_MAIN)
    df_alt = samples_dataframe(SAMPLES_ALT)
    s_main = device_summary(df_main)
    s_alt = device_summary(df_alt)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{DEVICE_MAIN_LABEL}**")
        st.metric("Tiempo a 100%", f"{s_main['t_100_min']:.0f} min")
        st.metric("R² logístico", f"{s_main['r2_logistic']:.4f}")
        if s_main["initial_slope_pct_per_min"] is not None:
            st.metric("Pendiente inicial", f"{s_main['initial_slope_pct_per_min']:.2f} %/min")
        st.metric("Carga final", f"{s_main['final_level']:.0f} %")
    with c2:
        st.markdown(f"**{DEVICE_ALT_LABEL}**")
        st.metric("Tiempo a 100%", f"{s_alt['t_100_min']:.0f} min")
        st.metric("R² logístico", f"{s_alt['r2_logistic']:.4f}")
        if s_alt["initial_slope_pct_per_min"] is not None:
            st.metric("Pendiente inicial", f"{s_alt['initial_slope_pct_per_min']:.2f} %/min")
        st.metric("Carga final", f"{s_alt['final_level']:.0f} %")

    st.plotly_chart(fig_dual_devices(df_main, df_alt, DEVICE_MAIN_LABEL, DEVICE_ALT_LABEL), use_container_width=True)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Dispositivo": DEVICE_MAIN_LABEL,
                    "t@100% (min)": s_main["t_100_min"],
                    "R² log.": s_main["r2_logistic"],
                    "Pendiente 0–5 min (%/min)": s_main["initial_slope_pct_per_min"],
                },
                {
                    "Dispositivo": DEVICE_ALT_LABEL,
                    "t@100% (min)": s_alt["t_100_min"],
                    "R² log.": s_alt["r2_logistic"],
                    "Pendiente 0–5 min (%/min)": s_alt["initial_slope_pct_per_min"],
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def step_newton() -> None:
    st.subheader("Newton-Raphson")
    st.markdown("Resolver **C(t) − objetivo = 0** con el modelo logístico del reporte.")

    st.markdown("#### Una meta (con iteraciones)")
    objetivo = st.slider("Porcentaje objetivo (%)", 10, 99, 80)
    t_star, msg, steps = newton_time_for_target(float(objetivo))
    if t_star is not None:
        mm = int(t_star)
        ss = int(round((t_star - mm) * 60))
        st.success(f"Tiempo estimado: **{mm} min {ss} s** — {msg}")
    else:
        st.error(msg)

    df_steps = format_newton_steps(steps)
    if not df_steps.empty:
        st.dataframe(df_steps, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar iteraciones (CSV)",
            data=df_steps.to_csv(index=False).encode("utf-8"),
            file_name="newton_iteraciones.csv",
            mime="text/csv",
        )

    st.markdown("#### Tabla completa (10% … 99%)")
    if st.button("Calcular 10%, 20%, … 99%", type="primary"):
        st.session_state.newton_batch = newton_batch_table(NEWTON_BATCH_TARGETS)

    if "newton_batch" in st.session_state:
        batch = st.session_state.newton_batch
        st.dataframe(batch, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar soluciones (CSV)",
            data=batch.to_csv(index=False).encode("utf-8"),
            file_name="newton_soluciones.csv",
            mime="text/csv",
        )
        row80 = batch[batch["% objetivo"] == 80]
        if not row80.empty:
            t80 = row80["t* (min)"].iloc[0]
            st.info(
                f"**80%:** modelo ≈ **{t80} min** · reporte ≈ **{NEWTON_80_MIN} min** "
                f"({NEWTON_80_ITER} iteraciones en el documento)."
            )

    st.caption(
        "Newton **escalar** (tiempo para un %) converge; el ajuste **multivariable** de k y t₀ "
        "del reporte dio NaN — ver expander en el paso Modelo."
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
