"""
Laboratorio de carga Li-ion — asistente por pasos (Streamlit).
Ejecutar: streamlit run main.py
"""
# Docstring del módulo: archivo principal del laboratorio. Se ejecuta con `streamlit run main.py`.

from __future__ import annotations
# Habilita anotaciones modernas de tipo.

import re
# Expresiones regulares (parseo del texto de `adb dumpsys battery`).
import subprocess
# Para ejecutar comandos del sistema (en este caso `adb`).
import time
# Temporizador para el monitoreo en vivo (intervalos entre muestras).
from dataclasses import dataclass
# Para definir la clase de datos `BatteryReading`.
from datetime import datetime
# Marcas de tiempo para registrar las muestras.

import pandas as pd
# DataFrames de pandas para manipular las muestras y tablas.
import streamlit as st
# Framework de la interfaz web local.

from battery_models import (
    # Importa los modelos y métodos numéricos.
    compare_models,             # Comparativa lineal/logística/spline.
    comparison_verdict_es,      # Texto en español con el veredicto del mejor modelo.
    device_summary,             # Resumen estadístico por dispositivo.
    estimate_cv_start_min,      # Tiempo donde se cruza el 80% (inicio CV).
    format_newton_steps,        # Convierte iteraciones de Newton en tabla legible.
    multivar_fit_note,          # Nota sobre por qué falló el ajuste multivariable.
    newton_batch_table,         # Tabla de Newton para varias metas.
    newton_time_for_target,     # Newton para una sola meta.
    try_logistic_curve_fit,     # Reintento con curve_fit (Levenberg-Marquardt).
)
from lab_charts import fig_charge_simple, fig_dual_devices, fig_model_comparison
# Importa las funciones que construyen las gráficas Plotly.
from report_data import (
    # Importa todas las constantes y datos del reporte.
    CHARGE_TIME_REAL_MIN,
    DELIVERY_DATE,
    DEVICE_ALT_LABEL,
    DEVICE_MAIN_LABEL,
    EFFICIENCY_PCT,
    ENERGY_WH,
    INSTITUTION,
    K_RATE,
    METHODOLOGY_STEPS,
    NEWTON_80_ITER,
    NEWTON_80_MIN,
    NEWTON_BATCH_TARGETS,
    SAMPLES_ALT,
    SAMPLES_MAIN,
    T0_INFL,
    TEAM,
    TIME_IDEAL_MIN,
    WIZARD_LAB_STEPS,
    samples_dataframe,
)
from sample_store import clear_session, export_csv_bytes, load_session, rows_to_dataframe, save_session
# Funciones para persistir/leer la bitácora de muestras en JSON.
from theme import ACCENT_CYAN, ACCENT_YELLOW, inject_global_style
# Colores y estilos compartidos.
from wizard_ui import render_step_header, step_nav_buttons
# Helpers del asistente por pasos.


@dataclass
class BatteryReading:
    # Estructura para una lectura individual de la batería (vía ADB).
    level: int | None
    # Nivel de carga en % (0-100), o None si no se pudo leer.
    voltage_mv: int | None
    # Voltaje en milivoltios.
    current_ua: int | None
    # Corriente en microamperios (puede ser negativa durante carga).
    temperature_c: float | None
    # Temperatura en grados Celsius.
    raw_text: str
    # Texto crudo devuelto por `dumpsys battery` (para debug).
    error: str | None = None
    # Mensaje de error si la lectura falló.


def run_dumpsys_battery(adb_bin: str = "adb", timeout_s: float = 12.0) -> str:
    # Ejecuta el comando `adb shell dumpsys battery` y devuelve su salida en texto.
    result = subprocess.run(
        [adb_bin, "shell", "dumpsys", "battery"],
        # Comando: adb shell dumpsys battery.
        capture_output=True,
        # Captura stdout y stderr en lugar de imprimirlos.
        text=True,
        # Devuelve strings en lugar de bytes.
        timeout=timeout_s,
        # Tiempo máximo de espera para evitar bloqueos.
    )
    if result.returncode != 0:
        # Si adb falló (código distinto de 0)...
        raise RuntimeError(result.stderr.strip() or f"adb salió con código {result.returncode}")
        # ...lanza una excepción con el mensaje de error.
    return result.stdout or ""
    # Devuelve la salida estándar (o cadena vacía).


def parse_dumpsys_battery(text: str) -> BatteryReading:
    # Parsea el texto de salida de `dumpsys battery` y extrae los campos relevantes.
    level = voltage = current = None
    # Variables iniciales en None por si no se encuentran las líneas.
    temp_raw: int | None = None
    # Temperatura cruda (en décimas de grado).
    for line in text.splitlines():
        # Recorre cada línea de la salida.
        m = re.match(r"^\s*level:\s*(\d+)\s*$", line, re.I)
        # Regex para "level: <número>".
        if m:
            level = int(m.group(1))
            # Extrae el nivel de batería.
            continue
        m = re.match(r"^\s*voltage:\s*(\d+)\s*$", line, re.I)
        # Regex para "voltage: <número>" (en mV).
        if m:
            voltage = int(m.group(1))
            continue
        m = re.match(r"^\s*temperature:\s*(\d+)\s*$", line, re.I)
        # Regex para "temperature: <número>" (décimas de °C).
        if m:
            temp_raw = int(m.group(1))
            continue
        m = re.match(r"^\s*current now:\s*(-?\d+)\s*$", line, re.I)
        # Regex para "current now: <±número>" (en µA; admite signo negativo).
        if m:
            current = int(m.group(1))
            continue
    temp_c = (temp_raw / 10.0) if temp_raw is not None else None
    # Convierte la temperatura cruda (ej. 305) a grados Celsius (30.5°C).
    return BatteryReading(level, voltage, current, temp_c, text, None)
    # Devuelve la lectura estructurada.


def fetch_battery_reading(adb_bin: str) -> BatteryReading:
    # Función conveniente que combina ejecución + parseo y maneja errores.
    try:
        return parse_dumpsys_battery(run_dumpsys_battery(adb_bin))
        # Llama a las dos funciones anteriores en cadena.
    except Exception as exc:  # noqa: BLE001
        # Si algo falla (adb no instalado, sin permisos, etc.)...
        return BatteryReading(None, None, None, None, "", str(exc))
        # ...devuelve una lectura vacía con el mensaje de error.


def list_adb_devices(adb_bin: str = "adb") -> tuple[list[str], str | None]:
    """Lista dispositivos Android conectados por USB/Wi‑Fi debugging."""
    # Docstring: ejecuta `adb devices -l` y devuelve la lista de seriales conectados.
    try:
        result = subprocess.run(
            [adb_bin, "devices", "-l"],
            # `-l` añade detalles legibles a cada dispositivo.
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return [], result.stderr.strip() or "Error al ejecutar adb devices"
            # Devuelve lista vacía y un mensaje de error.
        devices: list[str] = []
        # Acumulador.
        for line in result.stdout.splitlines():
            line = line.strip()
            # Limpia espacios.
            if not line or line.startswith("List of"):
                # Salta líneas vacías o el encabezado "List of devices attached".
                continue
            parts = line.split()
            # Divide por espacios: primer token = serial, segundo = estado.
            if len(parts) >= 2 and parts[1] == "device":
                # Solo cuenta los que están en estado "device" (no "unauthorized" ni "offline").
                devices.append(parts[0])
                # Agrega el serial.
        return devices, None
        # Devuelve la lista y None como error (todo OK).
    except FileNotFoundError:
        # Si `adb` no está instalado en el sistema...
        return [], "No se encontró `adb`. Instala Android platform-tools."
    except Exception as exc:  # noqa: BLE001
        # Cualquier otro error.
        return [], str(exc)


def _init_live_state() -> None:
    # Inicializa el estado de la sesión Streamlit para el monitoreo en vivo.
    if "live_rows" not in st.session_state:
        # Si aún no hay filas guardadas en sesión...
        data = load_session()
        # ...lee del JSON las muestras previas (si las hay).
        st.session_state.live_rows = list(data.get("rows", []))
        # Carga las filas en sesión.
    if "live_t0" not in st.session_state:
        st.session_state.live_t0 = time.time()
        # Marca el tiempo de inicio de la sesión actual.
    if "live_monitoring" not in st.session_state:
        st.session_state.live_monitoring = False
        # Flag: ¿está corriendo el monitoreo automático?
    if "last_sample_ts" not in st.session_state:
        st.session_state.last_sample_ts = 0.0
        # Última vez que se tomó una muestra (epoch).


def _elapsed_min() -> float:
    # Devuelve el tiempo transcurrido desde `live_t0` en minutos.
    return (time.time() - st.session_state.live_t0) / 60.0


def _append_live_row(
    # Agrega una nueva fila al log de muestras en vivo y la guarda en disco.
    level: float,
    # Porcentaje de carga (obligatorio).
    *,
    source: str,
    # Origen de la muestra: "adb" o "manual".
    voltage_mv: int | None = None,
    current_ua: int | None = None,
    temperature_c: float | None = None,
    # Datos físicos opcionales (solo presentes si vienen de ADB).
) -> None:
    t_min = _elapsed_min()
    # Calcula los minutos transcurridos.
    row = {
        # Construye el diccionario con todos los campos de la muestra.
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        # Marca de tiempo en formato ISO.
        "t_min": round(t_min, 2),
        # Tiempo desde el inicio en minutos (2 decimales).
        "t_h": round(t_min / 60.0, 4),
        # Mismo tiempo en horas (4 decimales).
        "level": float(level),
        "voltage_mv": voltage_mv,
        "current_ua": current_ua,
        "temperature_c": temperature_c,
        "source": source,
    }
    st.session_state.live_rows.append(row)
    # Agrega la fila al log en sesión.
    st.session_state.last_sample_ts = time.time()
    # Actualiza el timestamp de la última muestra.
    save_session(
        # Persiste el log actualizado a JSON.
        st.session_state.live_rows,
        device_label=st.session_state.get("device_label", ""),
        platform=st.session_state.get("platform", "android"),
        session_started=st.session_state.get("session_started"),
    )


def _capture_adb_sample(adb_bin: str) -> bool:
    # Captura una muestra desde el dispositivo Android conectado por ADB.
    reading = fetch_battery_reading(adb_bin)
    # Lee la batería.
    if reading.error:
        # Si hubo error de ADB...
        st.error(f"ADB: {reading.error}")
        # ...muestra mensaje rojo en la UI.
        return False
    if reading.level is None:
        # Si el comando funcionó pero no se pudo extraer el nivel...
        st.error("No se pudo leer el nivel de batería.")
        return False
    _append_live_row(
        # Guarda la muestra con todos los datos físicos.
        reading.level,
        source="adb",
        voltage_mv=reading.voltage_mv,
        current_ua=reading.current_ua,
        temperature_c=reading.temperature_c,
    )
    return True
    # Indica éxito.


def _ensure_data() -> pd.DataFrame:
    # Garantiza que exista un DataFrame de datos en sesión; si no, lo inicializa con las muestras del reporte.
    if "lab_df" not in st.session_state:
        st.session_state.lab_df = samples_dataframe()
    return st.session_state.lab_df


def step_inicio() -> None:
    # PASO 1 del wizard: presentación del proyecto y equipo.
    st.subheader("Proyecto: ajuste de curva Li-ion")
    # Subtítulo.
    st.caption(INSTITUTION)
    # Texto pequeño con el nombre de la institución.
    st.markdown(
        # Descripción general del objetivo.
        """
        Modelar matemáticamente la **carga de una batería** para predecir el tiempo total
        y explicar por qué los primeros minutos son más rápidos que el tramo final (protocolo **CC-CV**).
        """
    )
    st.markdown(f"**Entrega:** {DELIVERY_DATE}")
    # Resalta la fecha de entrega.
    st.markdown("#### Integrantes")
    # Encabezado de la tabla del equipo.
    st.table(pd.DataFrame(TEAM, columns=["Nombre", "Rol", "Responsabilidad"]))
    # Tabla estática con el equipo.
    c1, c2, c3 = st.columns(3)
    # Tres columnas para mostrar 3 métricas resumen.
    c1.metric("Muestras del reporte", "12")
    c2.metric("Intervalo", "5 min")
    c3.metric("Duración real", f"{CHARGE_TIME_REAL_MIN:.0f} min")


def step_metodologia() -> None:
    # PASO 2 del wizard: metodología experimental (CC-CV y los 6 pasos).
    st.subheader("Metodología experimental")
    for num, titulo, desc in METHODOLOGY_STEPS:
        # Itera sobre los 6 pasos definidos en report_data.
        st.markdown(f"**{num}. {titulo}** — {desc}")
        # Imprime cada paso como ítem en Markdown.
    st.markdown("#### Fases CC-CV")
    c1, c2 = st.columns(2)
    # Dos columnas para mostrar las fases en paralelo.
    with c1:
        st.success("**CC (0–80%)** — corriente casi constante; crecimiento rápido.")
        # Caja verde para la fase CC.
    with c2:
        st.warning("**CV (80–100%)** — voltaje fijo; corriente baja; curva se aplana.")
        # Caja amarilla para la fase CV.
    st.latex(r"C(t)=\frac{L}{1+e^{-k(t-t_0)}},\quad L=100\%")
    # Renderiza la fórmula sigmoide en LaTeX.


def step_recoleccion() -> None:
    # PASO 3 del wizard: recolección de muestras (3 modos: tiempo real, reporte, dispositivo alternativo).
    st.subheader("Recolección de muestras")
    st.info(
        # Caja informativa con el aviso Android vs iPhone.
        "**Android:** lectura automática con USB y depuración USB activada (`adb`). "
        "**iPhone:** Apple no permite ADB; usa **entrada manual** cada 5 min (mismo protocolo del reporte)."
    )

    fuente = st.radio(
        # Selector horizontal de fuente de datos.
        "Fuente de datos",
        ["Tiempo real (guardar bitácora)", "Reporte (12 mediciones)", "Comparar 2º dispositivo (reporte)"],
        horizontal=True,
    )

    if fuente == "Reporte (12 mediciones)":
        # Modo: cargar las 12 muestras estáticas del reporte (dispositivo principal).
        st.session_state.lab_df = samples_dataframe()
        st.session_state.live_monitoring = False
        # Detiene cualquier monitoreo en curso.
    elif fuente == "Comparar 2º dispositivo (reporte)":
        # Modo: cargar las muestras del dispositivo alternativo.
        st.session_state.lab_df = samples_dataframe(SAMPLES_ALT)
        st.session_state.live_monitoring = False
    else:
        # Modo: recolección en vivo.
        _init_live_state()
        # Inicializa el estado de sesión.
        plataforma = st.radio(
            # Selecciona si el dispositivo es Android (ADB) o manual.
            "Tipo de dispositivo",
            ["Android (ADB automático)", "Manual — iPhone u otro (tú ingresas el %)"],
            horizontal=True,
        )
        es_android = plataforma.startswith("Android")
        # Booleano que indica si usaremos ADB.
        st.session_state.platform = "android" if es_android else "manual"
        # Guarda la plataforma elegida.
        st.session_state.device_label = st.text_input(
            # Campo para nombrar el dispositivo (etiqueta legible).
            "Nombre del dispositivo (opcional)",
            value=st.session_state.get("device_label", ""),
            placeholder="Ej. Samsung A54, iPhone 13",
        )

        intervalo_s = st.slider(
            # Slider para elegir cada cuántos segundos se toma una muestra automática.
            "Intervalo entre muestras automáticas (segundos)",
            min_value=30,
            max_value=600,
            value=300,
            # Valor por defecto: 5 min (300 s) como en el reporte.
            step=30,
            help="El reporte usa 5 min (300 s). En pruebas puedes bajar a 30 s.",
        )

        adb_bin = "adb"
        # Ruta del binario adb (por defecto se asume en PATH).
        if es_android:
            adb_bin = st.text_input("Ruta de adb", value="adb", key="adb_path")
            # Permite cambiar la ruta si adb está en otra ubicación.
            if st.button("Buscar dispositivos conectados"):
                # Botón para listar Androids conectados.
                devices, err = list_adb_devices(adb_bin)
                if err:
                    st.error(err)
                elif not devices:
                    # Si no hay ningún dispositivo, da instrucciones.
                    st.warning(
                        "No hay dispositivos. Conecta el Android por USB, activa "
                        "**Opciones de desarrollador → Depuración USB** y acepta la llave RSA."
                    )
                else:
                    st.success("Conectados: " + ", ".join(devices))
                    # Lista los seriales encontrados.
        else:
            # Modo manual (iPhone u otro): el usuario teclea el %.
            st.caption(
                "En cada intervalo actualiza el % que ves en Ajustes → Batería y pulsa **Muestra ahora**, "
                "o deja el valor actualizado antes del auto-muestreo."
            )
            manual_pct = st.number_input("Porcentaje actual (%)", 0, 100, 50, key="manual_pct")
            # Campo numérico de 0 a 100 con valor inicial 50.

        st.markdown("#### Control en tiempo real")
        c1, c2, c3, c4 = st.columns(4)
        # Cuatro columnas para los botones de control.
        with c1:
            # Botón "Iniciar": arranca el monitoreo automático.
            if st.button("▶ Iniciar monitoreo", type="primary", disabled=st.session_state.live_monitoring):
                st.session_state.live_monitoring = True
                # Activa la bandera de monitoreo.
                st.session_state.live_t0 = time.time()
                # Marca el tiempo de inicio.
                st.session_state.last_sample_ts = 0.0
                # Resetea el timestamp para forzar primera muestra.
                st.session_state.session_started = datetime.now().isoformat(timespec="seconds")
                # Guarda el inicio de la sesión.
                if es_android:
                    _capture_adb_sample(adb_bin)
                    # Toma una primera muestra inmediata vía ADB.
                else:
                    _append_live_row(float(manual_pct), source="manual")
                    # Toma una muestra manual con el valor ingresado.
                st.rerun()
        with c2:
            # Botón "Detener": pausa el monitoreo.
            if st.button("⏹ Detener", disabled=not st.session_state.live_monitoring):
                st.session_state.live_monitoring = False
                st.rerun()
        with c3:
            # Botón "Muestra ahora": toma una sola muestra puntual.
            if st.button("📸 Muestra ahora"):
                if es_android:
                    if _capture_adb_sample(adb_bin):
                        st.toast("Muestra guardada")
                        # Pequeña notificación tipo toast.
                else:
                    _append_live_row(float(manual_pct), source="manual")
                    st.toast("Muestra guardada")
                st.rerun()
        with c4:
            # Botón "Guardar bitácora": fuerza el guardado actual en JSON.
            if st.button("💾 Guardar bitácora"):
                save_session(
                    st.session_state.live_rows,
                    device_label=st.session_state.get("device_label", ""),
                    platform=st.session_state.get("platform", "android"),
                    session_started=st.session_state.get("session_started"),
                )
                st.success(f"Guardado en `data/charge_samples.json` ({len(st.session_state.live_rows)} filas)")

        acc1, acc2, acc3 = st.columns(3)
        # Tres columnas con acciones secundarias.
        with acc1:
            # Botón para recargar el JSON guardado (descarta cambios en sesión).
            if st.button("Cargar bitácora guardada"):
                data = load_session()
                st.session_state.live_rows = list(data.get("rows", []))
                st.session_state.device_label = data.get("device_label", "")
                st.rerun()
        with acc2:
            # Botón para reiniciar la bitácora (borra todas las muestras).
            if st.button("Reiniciar bitácora"):
                st.session_state.live_rows = []
                st.session_state.live_monitoring = False
                clear_session()
                # Limpia también el JSON.
                st.rerun()
        with acc3:
            # Botón para descargar las muestras como CSV.
            st.download_button(
                "Descargar CSV",
                data=export_csv_bytes(st.session_state.live_rows),
                file_name="bitacora_carga.csv",
                mime="text/csv",
                disabled=len(st.session_state.live_rows) == 0,
                # Deshabilitado si no hay muestras.
            )

        if st.session_state.live_monitoring:
            # Si está activo el monitoreo, muestra un indicador visible.
            st.markdown(
                f"<p style='color:{ACCENT_YELLOW};font-weight:600;'>● EN VIVO — "
                f"próxima muestra automática cada {intervalo_s}s</p>",
                unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            # Tres métricas: muestras, tiempo y último %.
            m1.metric("Muestras", len(st.session_state.live_rows))
            m2.metric("Tiempo transcurrido (min)", f"{_elapsed_min():.1f}")
            if st.session_state.live_rows:
                m3.metric("Último %", f"{st.session_state.live_rows[-1]['level']:.0f}")

        if st.session_state.live_rows:
            # Si hay muestras, actualiza el DataFrame de trabajo.
            st.session_state.lab_df = rows_to_dataframe(st.session_state.live_rows)
        else:
            # Si no hay muestras, advierte al usuario.
            st.warning("Sin muestras aún. Pulsa **Iniciar monitoreo** o **Muestra ahora**.")

        # Bucle en vivo: toma muestra y recarga cuando pasa el intervalo
        if st.session_state.live_monitoring:
            now = time.time()
            if now - st.session_state.last_sample_ts >= intervalo_s:
                # Si pasó el intervalo configurado desde la última muestra...
                if es_android:
                    _capture_adb_sample(adb_bin)
                    # ...captura por ADB.
                else:
                    _append_live_row(float(manual_pct), source="manual")
                    # ...o usa el valor manual actual.
            time.sleep(2)
            # Espera 2 s para no saturar el bucle.
            st.rerun()
            # Re-renderiza para mantener el "tiempo real" (Streamlit re-ejecuta todo el script).

    df = _ensure_data()
    # Obtiene el DataFrame actual (sea del reporte o en vivo).
    if df.empty:
        st.stop()
        # Si está vacío, detiene la ejecución de esta función.
    cols_show = [c for c in ["t_min", "level", "voltage_mv", "temperature_c", "source", "timestamp"] if c in df.columns]
    # Columnas a mostrar (solo las que existan en el DataFrame).
    st.dataframe(df[cols_show], use_container_width=True, hide_index=True)
    # Renderiza la tabla de muestras.
    st.caption("Protocolo: modo avión, brillo 0%, registro cada 5 min desde <5% hasta 100%.")
    # Aclaración del protocolo experimental.
    t_cv = estimate_cv_start_min(df)
    # Calcula el cruce del 80% (inicio CV).
    st.plotly_chart(fig_charge_simple(df, t_cv), use_container_width=True)
    # Renderiza la gráfica de carga simple.


def step_modelo() -> None:
    # PASO 4 del wizard: comparación de modelos y análisis estadístico.
    st.subheader("Modelación y comparativa de modelos")
    df = _ensure_data()
    if len(df) < 2:
        # Se necesitan al menos 2 muestras para hacer cualquier regresión.
        st.warning("Se necesitan al menos 2 muestras. Vuelve a **Recolección** o carga el reporte.")
        return

    cmp = compare_models(df)
    # Ejecuta la comparación de los 3 modelos.
    st.markdown("#### Tabla R²")
    tabla = pd.DataFrame(
        # Construye una tabla resumen con R² de cada modelo y una nota.
        [
            {"Modelo": "Lineal", "R²": f"{cmp.r2_linear:.4f}", "Nota": "Una recta; no satura en 100%."},
            {"Modelo": "Logístico", "R²": f"{cmp.r2_logistic:.4f}", "Nota": "Sigmoide CC-CV del reporte."},
            {"Modelo": "Spline", "R²": f"{cmp.r2_spline:.4f}", "Nota": "Ajuste flexible punto a punto."},
        ]
    )
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    # Muestra la tabla.
    st.markdown(comparison_verdict_es(cmp))
    # Imprime el veredicto en español.
    if cmp.t_cv_min is not None:
        st.caption(f"Transición estimada a fase **CV** (~80%): ≈ **{cmp.t_cv_min:.1f} min**.")
        # Caption con el tiempo de cruce.
    st.plotly_chart(fig_model_comparison(df, cmp), use_container_width=True)
    # Gráfica con los 3 modelos superpuestos.
    st.caption(f"Sigmoide de referencia: k={K_RATE}, t₀={T0_INFL} min.")
    # Recordatorio de los parámetros del modelo logístico.

    with st.expander("¿Por qué falló el ajuste simultáneo de k y t₀?"):
        # Bloque colapsable con la explicación del fallo del ajuste multivariable.
        st.markdown(multivar_fit_note())
        # Texto explicativo.
        fit = try_logistic_curve_fit(df)
        # Intenta el ajuste con curve_fit (más robusto que Newton multivariable).
        if fit["ok"]:
            st.success(fit["message"])
            # Si convergió, muestra los parámetros encontrados.
        else:
            st.warning(fit["message"])
            # Si no, muestra el error.
        st.markdown(
            # Recomendación final.
            "**Próximo paso recomendado:** **Levenberg-Marquardt** "
            "(`scipy.optimize.curve_fit` / `least_squares`) con semilla estable y, si hace falta, "
            "excluir los extremos 0% y 100% del ajuste global."
        )

    st.markdown("---")
    # Separador antes de la sección de dos dispositivos.
    st.markdown("#### Dos dispositivos del reporte")
    df_main = samples_dataframe(SAMPLES_MAIN)
    # DataFrame del dispositivo principal.
    df_alt = samples_dataframe(SAMPLES_ALT)
    # DataFrame del dispositivo alternativo.
    s_main = device_summary(df_main)
    # Estadísticas del dispositivo principal.
    s_alt = device_summary(df_alt)
    # Estadísticas del alternativo.
    c1, c2 = st.columns(2)
    # Dos columnas paralelas (una por dispositivo).
    with c1:
        # Columna izquierda: dispositivo principal.
        st.markdown(f"**{DEVICE_MAIN_LABEL}**")
        st.metric("Tiempo a 100%", f"{s_main['t_100_min']:.0f} min")
        st.metric("R² logístico", f"{s_main['r2_logistic']:.4f}")
        if s_main["initial_slope_pct_per_min"] is not None:
            st.metric("Pendiente inicial", f"{s_main['initial_slope_pct_per_min']:.2f} %/min")
        st.metric("Carga final", f"{s_main['final_level']:.0f} %")
    with c2:
        # Columna derecha: dispositivo alternativo (mismas métricas).
        st.markdown(f"**{DEVICE_ALT_LABEL}**")
        st.metric("Tiempo a 100%", f"{s_alt['t_100_min']:.0f} min")
        st.metric("R² logístico", f"{s_alt['r2_logistic']:.4f}")
        if s_alt["initial_slope_pct_per_min"] is not None:
            st.metric("Pendiente inicial", f"{s_alt['initial_slope_pct_per_min']:.2f} %/min")
        st.metric("Carga final", f"{s_alt['final_level']:.0f} %")

    st.plotly_chart(fig_dual_devices(df_main, df_alt, DEVICE_MAIN_LABEL, DEVICE_ALT_LABEL), use_container_width=True)
    # Gráfica comparativa entre los dos dispositivos.
    st.dataframe(
        # Tabla resumen con métricas de ambos dispositivos lado a lado.
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
    # PASO 5 del wizard: cálculos de Newton-Raphson (escalar y por lote).
    st.subheader("Newton-Raphson")
    st.markdown("Resolver **C(t) − objetivo = 0** con el modelo logístico del reporte.")
    # Recordatorio del problema que resolvemos.

    st.markdown("#### Una meta (con iteraciones)")
    objetivo = st.slider("Porcentaje objetivo (%)", 10, 99, 80)
    # Slider para elegir el % objetivo (entre 10 y 99, default 80).
    t_star, msg, steps = newton_time_for_target(float(objetivo))
    # Resuelve Newton para ese %.
    if t_star is not None:
        # Si convergió...
        mm = int(t_star)
        ss = int(round((t_star - mm) * 60))
        # Convierte a minutos y segundos.
        st.success(f"Tiempo estimado: **{mm} min {ss} s** — {msg}")
        # Muestra el resultado en una caja verde.
    else:
        st.error(msg)
        # Si falló, muestra el error.

    df_steps = format_newton_steps(steps)
    # Convierte las iteraciones a DataFrame legible.
    if not df_steps.empty:
        st.dataframe(df_steps, use_container_width=True, hide_index=True)
        # Tabla con cada iteración.
        st.download_button(
            # Botón para descargar las iteraciones como CSV.
            "Descargar iteraciones (CSV)",
            data=df_steps.to_csv(index=False).encode("utf-8"),
            file_name="newton_iteraciones.csv",
            mime="text/csv",
        )

    st.markdown("#### Tabla completa (10% … 99%)")
    if st.button("Calcular 10%, 20%, … 99%", type="primary"):
        # Botón para correr Newton sobre todas las metas predefinidas.
        st.session_state.newton_batch = newton_batch_table(NEWTON_BATCH_TARGETS)
        # Guarda el resultado en sesión.

    if "newton_batch" in st.session_state:
        # Si ya se calculó la tabla en alguna ejecución previa de la sesión...
        batch = st.session_state.newton_batch
        st.dataframe(batch, use_container_width=True, hide_index=True)
        # Muestra la tabla completa.
        st.download_button(
            "Descargar soluciones (CSV)",
            data=batch.to_csv(index=False).encode("utf-8"),
            file_name="newton_soluciones.csv",
            mime="text/csv",
        )
        row80 = batch[batch["% objetivo"] == 80]
        # Busca la fila correspondiente a 80% para comparar con el reporte.
        if not row80.empty:
            t80 = row80["t* (min)"].iloc[0]
            st.info(
                f"**80%:** modelo ≈ **{t80} min** · reporte ≈ **{NEWTON_80_MIN} min** "
                f"({NEWTON_80_ITER} iteraciones en el documento)."
            )
            # Compara el valor calculado vs el valor reportado oficialmente.

    st.caption(
        # Nota final sobre el alcance del método.
        "Newton **escalar** (tiempo para un %) converge; el ajuste **multivariable** de k y t₀ "
        "del reporte dio NaN — ver expander en el paso Modelo."
    )


def step_stats() -> None:
    # PASO 6 del wizard: resultados finales y conclusiones del reporte.
    st.subheader("Resultados del reporte")
    c1, c2, c3, c4 = st.columns(4)
    # Cuatro métricas clave del reporte.
    c1.metric("Energía", f"{ENERGY_WH} Wh")
    c2.metric("Tiempo real", f"{CHARGE_TIME_REAL_MIN:.0f} min")
    c3.metric("Tiempo ideal", f"{TIME_IDEAL_MIN:.1f} min")
    c4.metric("Eficiencia útil", f"~{EFFICIENCY_PCT}%")
    st.markdown(
        # Lista resumida de conclusiones.
        """
        **Conclusiones (reporte):**
        - La carga sigue un comportamiento **sigmoide** (no lineal).
        - Newton-Raphson **funciona** en el problema escalar (tiempo para un %).
        - El ajuste simultáneo de parámetros puede **diverger** (NaN) — usar semillas estables o Levenberg-Marquardt.
        """
    )
    st.markdown("**Recomendaciones:** gradiente descendente, eliminar extremos 0%/100% del ajuste global, validar con Python/MATLAB.")
    # Recomendaciones del reporte para trabajos futuros.


def main() -> None:
    # Punto de entrada del Laboratorio: configura la página y orquesta el wizard.
    st.set_page_config(
        # Configura metadatos y layout de la página.
        page_title="Laboratorio Li-ion",
        page_icon="🔋",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_style()
    # Inyecta el CSS global del tema.

    idx = render_step_header(
        # Dibuja el encabezado del wizard y obtiene el paso activo.
        WIZARD_LAB_STEPS,
        "lab_step",
        "Laboratorio de batería",
        "Asistente del proyecto de Métodos Numéricos — carga Li-ion",
    )
    step_id = WIZARD_LAB_STEPS[idx][0]
    # Identificador interno del paso activo.

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
    # Enruta al paso correspondiente según el id.

    step_nav_buttons("lab_step", len(WIZARD_LAB_STEPS))
    # Dibuja los botones Anterior/Siguiente al pie.


if __name__ == "__main__":
    # Solo ejecuta main() si el archivo se corre directamente (no como import).
    main()
