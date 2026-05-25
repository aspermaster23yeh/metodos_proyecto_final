"""
Conclusiones del proyecto — síntesis académica y técnica (ITT Tepic 5A).
"""

from __future__ import annotations

import streamlit as st

from battery_models import report_fit_stats
from report_data import (
    CHARGE_TIME_REAL_MIN,
    DELIVERY_DATE,
    EFFICIENCY_PCT,
    ENERGY_WH,
    INSTITUTION,
    K_RATE,
    NEWTON_80_ITER,
    NEWTON_80_MIN,
    T0_INFL,
    TEAM,
    TIME_IDEAL_MIN,
    samples_dataframe,
)
from theme import ACCENT_CYAN, ACCENT_YELLOW, TEXT_MUTED, inject_global_style

WIZARD_CONCLUSION_STEPS = [
    ("que", "Qué hicimos", "Objetivo del estudio y entregables del equipo."),
    ("como", "Cómo lo hicimos", "Experimento, métodos numéricos y organización."),
    ("codigo", "Programación", "Arquitectura del software y flujo de datos."),
    ("diseno", "Diseño", "Interfaz, experiencia de usuario y visualización."),
    ("final", "Conclusiones", "Hallazgos, límites y recomendaciones del reporte."),
]


def _step_header() -> int:
    if "concl_step" not in st.session_state:
        st.session_state.concl_step = 0
    n = len(WIZARD_CONCLUSION_STEPS)
    idx = st.session_state.concl_step

    st.markdown(
        f"<h1 style='color:{ACCENT_CYAN};'>Conclusiones del proyecto</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{ACCENT_YELLOW};'>Síntesis del reporte y de la aplicación Streamlit · {INSTITUTION}</p>",
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / n, text=f"Sección {idx + 1} de {n}")
    choice = st.radio(
        "Secciones",
        options=list(range(n)),
        format_func=lambda i: WIZARD_CONCLUSION_STEPS[i][1],
        index=idx,
        horizontal=True,
        label_visibility="collapsed",
        key="concl_radio",
    )
    if choice != idx:
        st.session_state.concl_step = choice
        st.rerun()
    idx = st.session_state.concl_step
    _id, label, desc = WIZARD_CONCLUSION_STEPS[idx]
    st.info(f"**{label}** — {desc}")
    st.markdown("---")
    return idx


def _nav(n: int) -> None:
    idx = st.session_state.concl_step
    c1, c2, _ = st.columns([1, 1, 6])
    with c1:
        if st.button("← Anterior", disabled=idx <= 0):
            st.session_state.concl_step -= 1
            st.rerun()
    with c2:
        if st.button("Siguiente →", disabled=idx >= n - 1):
            st.session_state.concl_step += 1
            st.rerun()


def step_que() -> None:
    st.subheader("Qué hicimos")
    st.markdown(
        f"""
        Desarrollamos un **estudio de métodos numéricos** sobre la carga de una batería **Li-ion**
        en un smartphone, con entrega el **{DELIVERY_DATE}**.

        El trabajo combinó tres frentes:

        1. **Experimento** — Medir el porcentaje de carga cada **5 minutos** desde ~0% hasta **100%**
           bajo condiciones controladas (modo avión, brillo bajo, sin uso intensivo).
        2. **Modelación** — Ajustar una curva **sigmoide (logística)** y aplicar **Newton-Raphson**
           para estimar en qué instante se alcanza un nivel de carga dado (por ejemplo 80%).
        3. **Software y diseño** — Esta aplicación **Streamlit** (laboratorio + centro de proyecto)
           para visualizar datos, repetir el análisis y documentar el cronograma del equipo.
        """
    )
    st.markdown("#### Objetivo general")
    st.success(
        "Modelar matemáticamente el proceso de carga para **predecir el tiempo total** "
        "y explicar el comportamiento **no lineal** (rápido al inicio, lento al final)."
    )
    st.markdown("#### Equipo")
    import pandas as pd

    st.table(pd.DataFrame(TEAM, columns=["Integrante", "Área", "Aporte"]))
    st.markdown("#### Entregables")
    st.markdown(
        """
        - Reporte técnico (Word/PDF) con marco teórico **CC-CV**, datos, R² y conclusiones.
        - Prototipo visual (HTML/Figma) con gráfica sigmoide e iteraciones de Newton-Raphson.
        - **Aplicación Streamlit** multipágina: laboratorio, actividades y esta síntesis.
        - Bitácora de muestras (`data/charge_samples.json`) cuando se usa recolección en vivo.
        """
    )


def step_como() -> None:
    st.subheader("Cómo lo hicimos")
    st.markdown("#### Protocolo electroquímico (CC-CV)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            **Fase CC (corriente constante, ~0–80%)**  
            El cargador inyecta la máxima corriente permitida; el porcentaje sube casi de forma lineal.
            """
        )
    with c2:
        st.markdown(
            """
            **Fase CV (voltaje constante, ~80–100%)**  
            El voltaje se mantiene y la corriente baja; la curva se **aplana** (carga lenta).
            """
        )

    st.markdown("#### Metodología en 6 pasos")
    for num, titulo, desc in [
        ("1", "Descarga", "Dispositivo por debajo del 5%."),
        ("2", "Bitácora", "Registro cada 5 min hasta 100%."),
        ("3", "Gráfica", "Dispersión tiempo (min) vs carga (%)."),
        ("4", "Regresión", "Modelos lineal y logístico; comparar **R²**."),
        ("5", "Newton-Raphson", "Resolver **C(t) = objetivo** (problema escalar)."),
        ("6", "Evaluación", "Error, eficiencia y pérdidas por calor/BMS."),
    ]:
        st.markdown(f"**{num}. {titulo}** — {desc}")

    df = samples_dataframe()
    stats = report_fit_stats(df)
    st.markdown("#### Datos del experimento principal")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Muestras", int(stats["n_samples"]))
    m2.metric("Duración", f"{stats['t_max_min']:.0f} min")
    m3.metric("R² logístico", f"{stats['r2_logistic']:.4f}")
    m4.metric("Tiempo real a 100%", f"{CHARGE_TIME_REAL_MIN:.0f} min")

    st.markdown("#### Organización del proyecto")
    st.markdown(
        """
        - **Análisis (Adán, Ángel, Sergio):** recolección, limpieza, regresiones, Newton-Raphson, redacción técnica.
        - **Diseño UX (Checho, Arath, Gustavo):** identidad visual, dashboard, infografía CC-CV, mockup predictivo.
        - **Cronograma:** 2 abr – 8 may 2026, 30 actividades en 5 fases (ver *Centro del proyecto*).
        """
    )


def step_codigo() -> None:
    st.subheader("Cómo está programado")
    st.markdown(
        """
        La aplicación es **Python 3** con **Streamlit** (interfaz web local). No hay servidor aparte:
        al ejecutar `streamlit run main.py` se levanta el laboratorio y las páginas en `pages/`.
        """
    )
    st.markdown(
        """
        ```mermaid
        flowchart TB
          subgraph ui [Interfaz Streamlit]
            Lab[main.py Laboratorio]
            Centro[Centro del Proyecto]
            Concl[Conclusiones]
          end
          subgraph logica [Lógica]
            Models[battery_models.py]
            Report[report_data.py]
            Samples[sample_store.py]
            Tasks[tasks_store.py]
          end
          subgraph persist [Datos locales]
            JSON1[charge_samples.json]
            JSON2[project_tasks.json]
          end
          subgraph externo [Hardware opcional]
            ADB[adb dumpsys battery]
          end
          Lab --> Models
          Lab --> Report
          Lab --> Samples
          Lab --> ADB
          Centro --> Tasks
          Samples --> JSON1
          Tasks --> JSON2
        ```
        """
    )
    st.markdown("#### Módulos principales")
    st.markdown(
        """
        | Archivo | Responsabilidad |
        |---------|-----------------|
        | `main.py` | Asistente del laboratorio: metodología, gráficas Plotly, ADB, Newton-Raphson |
        | `battery_models.py` | Curva logística **C(t)**, R², iteraciones de Newton |
        | `report_data.py` | Constantes y 12 muestras del reporte |
        | `sample_store.py` | Guardar/cargar bitácora en vivo (`charge_samples.json`) |
        | `tasks_store.py` | Tareas del equipo y cronograma (`project_tasks.json`) |
        | `theme.py` | Estilos compartidos (tema oscuro, tipografía mono) |
        | `wizard_ui.py` | Barra de progreso y navegación por pasos |
        """
    )
    st.markdown("#### Métodos numéricos implementados")
    st.latex(r"C(t)=\frac{L}{1+e^{-k(t-t_0)}},\quad L=100")
    st.markdown(
        f"""
        - **Parámetros del reporte:** k ≈ **{K_RATE}**, t₀ ≈ **{T0_INFL}** min.
        - **Spline cúbico** (`scipy.interpolate.UnivariateSpline`) sobre muestras observadas.
        - **Newton-Raphson** (`scipy.optimize.newton`) sobre **f(t) = C(t) − objetivo** con derivada analítica.
        - **ADB** (`subprocess`): parseo de `dumpsys battery` para nivel, voltaje, corriente y temperatura en Android.
        """
    )
    st.caption(
        "Dependencias: streamlit, pandas, numpy, scipy, plotly (ver `requirements.txt`)."
    )


def step_diseno() -> None:
    st.subheader("Cómo está diseñado")
    st.markdown(
        """
        La experiencia sigue un patrón **asistente (wizard)**: pocos pasos, texto breve en cada uno
        y métricas visibles de inmediato. El objetivo UX del reporte era **traducir datos complejos
        en gráficas claras** — por eso priorizamos:
        """
    )
    st.markdown(
        """
        - **Navegación por pasos** con barra de progreso (Laboratorio, Centro del proyecto, Conclusiones).
        - **Tema oscuro** con acentos cian/amarillo (`theme.py`), tipografía monoespaciada legible.
        - **Gráficas Plotly** interactivas: puntos medidos + curva sigmoide + spline.
        - **Centro del proyecto:** resumen de avance, actividades por fase y **Gantt** con color por fase.
        - **Recolección en vivo:** botones claros (Iniciar / Detener / Muestra ahora / Guardar) y aviso
          Android vs iPhone (manual).
        """
    )
    st.markdown("#### Identidad visual (equipo UX)")
    st.markdown(
        """
        En el prototipo HTML del reporte se usó paleta **crema / rojo ladrillo / verde / azul**,
        tipografías **Bebas Neue**, **IBM Plex Mono** y **DM Sans**, y tarjetas con sombra plana.
        La app Streamlit retoma el espíritu técnico (mono + acentos neón) para alinearlo con el laboratorio digital.
        """
    )
    st.markdown("#### Páginas de la aplicación")
    st.markdown(
        """
        1. **Laboratorio** — Flujo del experimento y análisis numérico.  
        2. **Centro del proyecto** — Gestión de tareas y cronograma del equipo.  
        3. **Conclusiones** (esta página) — Documentación integral del proyecto.
        """
    )


def step_final() -> None:
    st.subheader("A qué conclusión llegamos")
    st.markdown(
        """
        El comportamiento de carga observado **no es lineal**: encaja con un modelo **sigmoide**
        (saturación hacia 100%). La fase **CC** explica el tramo rápido; la **CV** el tramo final lento.
        """
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Energía medida", f"{ENERGY_WH} Wh")
    c2.metric("Carga real", f"{CHARGE_TIME_REAL_MIN:.0f} min")
    c3.metric("Ideal teórico", f"{TIME_IDEAL_MIN:.1f} min")
    c4.metric("Eficiencia útil", f"~{EFFICIENCY_PCT}%")

    st.markdown("#### Sobre Newton-Raphson")
    st.markdown(
        f"""
        | Enfoque | Resultado |
        |---------|-----------|
        | **Escalar** (¿en qué *t* se alcanza 80%?) | **Funciona** — ≈ **{NEWTON_80_MIN} min** en **{NEWTON_80_ITER}** iteraciones |
        | **Multivariable** (ajustar *k* y *t₀* simultáneamente) | **Falló** — parámetros **NaN** por inestabilidad numérica |

        **Interpretación:** el método es adecuado para **despejar tiempo** dado un modelo fijo; no siempre
        converge cuando se estiman varios parámetros a la vez con datos en 0% y 100% y Jacobianos mal condicionados.
        """
    )

    st.markdown("#### Pérdidas energéticas (~71.5%)")
    st.markdown(
        """
        Gran parte de la energía no se almacena como carga útil, sino que se disipa en:

        - **Calor (efecto Joule)** y resistencia interna.  
        - Conversión y electrónica del cargador.  
        - **Protección del BMS** y estrategia **CV** al acercarse al 100%.
        """
    )

    st.markdown("#### Conclusión general")
    st.success(
        "La carga Li-ion sigue un modelo sigmoide coherente con la teoría CC-CV. "
        "Newton-Raphson es útil en la forma escalar para predicción de tiempos; "
        "para ajuste global de parámetros conviene métodos más robustos."
    )

    st.markdown("#### Recomendaciones (del reporte)")
    st.markdown(
        """
        - Usar **Levenberg-Marquardt** o **gradiente descendente** para el ajuste de parámetros.  
        - Tratar con cuidado los puntos extremos (0% y 100%) en el ajuste multivariable.  
        - Validar con herramientas como Python/SciPy o MATLAB.  
        - Seguir registrando cada **5 min** y comparar dispositivos (como el segundo juego de datos del reporte).
        """
    )

    st.markdown("#### Cierre del proyecto software")
    st.info(
        "Esta aplicación materializa el reporte: mismos datos, mismos métodos y un camino guiado "
        "para repetir el experimento (Android por ADB o cualquier teléfono en modo manual). "
        "El cronograma del equipo quedó registrado como **100% completado** en el Gantt de abril–mayo 2026."
    )


def main() -> None:
    st.set_page_config(
        page_title="Conclusiones — Li-ion",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_style()

    idx = _step_header()
    step_id = WIZARD_CONCLUSION_STEPS[idx][0]

    if step_id == "que":
        step_que()
    elif step_id == "como":
        step_como()
    elif step_id == "codigo":
        step_codigo()
    elif step_id == "diseno":
        step_diseno()
    else:
        step_final()

    _nav(len(WIZARD_CONCLUSION_STEPS))


main()
