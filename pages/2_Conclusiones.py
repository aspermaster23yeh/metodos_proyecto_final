"""
Conclusiones del proyecto — síntesis académica y técnica (ITT Tepic 5A).
"""
# Docstring del módulo: describe el propósito de la página dentro del proyecto.

from __future__ import annotations
# Habilita la evaluación diferida de anotaciones de tipo (compatibilidad con versiones futuras de Python).

import streamlit as st
# Importa la librería Streamlit con alias `st`; es el framework que dibuja la interfaz web.

from battery_models import report_fit_stats
# Importa la función que calcula estadísticas del ajuste (R², número de muestras, etc.) desde el módulo de modelos.
from report_data import (
    # Importa las constantes y datos del reporte académico desde `report_data.py`.
    CHARGE_TIME_REAL_MIN,   # Tiempo real medido de carga completa en minutos.
    DELIVERY_DATE,          # Fecha de entrega del proyecto.
    EFFICIENCY_PCT,         # Eficiencia útil aproximada del proceso de carga (%).
    ENERGY_WH,              # Energía total medida en Watt-hora.
    INSTITUTION,            # Nombre de la institución (ITT Tepic).
    K_RATE,                 # Parámetro k de la curva logística (velocidad de carga).
    NEWTON_80_ITER,         # Iteraciones que tomó Newton-Raphson para llegar al 80%.
    NEWTON_80_MIN,          # Tiempo en minutos al que se alcanza 80% según Newton-Raphson.
    T0_INFL,                # Tiempo de inflexión t₀ del modelo sigmoide.
    TEAM,                   # Lista de integrantes del equipo con su rol y aporte.
    TIME_IDEAL_MIN,         # Tiempo ideal teórico de carga en minutos.
    samples_dataframe,      # Función que devuelve las muestras del experimento como DataFrame.
)
from theme import ACCENT_CYAN, ACCENT_YELLOW, TEXT_MUTED, inject_global_style
# Importa colores y la función que inyecta CSS global para mantener una identidad visual coherente.

WIZARD_CONCLUSION_STEPS = [
    # Lista de pasos del asistente (wizard); cada tupla es (id_interno, etiqueta_visible, descripción).
    ("que", "Qué hicimos", "Objetivo del estudio y entregables del equipo."),
    ("como", "Cómo lo hicimos", "Experimento, métodos numéricos y organización."),
    ("codigo", "Programación", "Arquitectura del software y flujo de datos."),
    ("diseno", "Diseño", "Interfaz, experiencia de usuario y visualización."),
    ("final", "Conclusiones", "Hallazgos, límites y recomendaciones del reporte."),
]
# Define la estructura de navegación por pasos que verá el usuario.


def _step_header() -> int:
    # Función privada que dibuja el encabezado y el selector de pasos; devuelve el índice del paso activo.
    if "concl_step" not in st.session_state:
        # Si aún no existe el estado del paso actual en la sesión...
        st.session_state.concl_step = 0
        # ...lo inicializa en 0 (primer paso).
    n = len(WIZARD_CONCLUSION_STEPS)
    # Guarda el número total de pasos para los cálculos siguientes.
    idx = st.session_state.concl_step
    # Recupera el índice del paso actualmente seleccionado.

    st.markdown(
        # Renderiza el título principal usando HTML para aplicar el color del acento cian.
        f"<h1 style='color:{ACCENT_CYAN};'>Conclusiones del proyecto</h1>",
        unsafe_allow_html=True,
        # Permite HTML embebido en Markdown (necesario para el estilo en línea).
    )
    st.markdown(
        # Subtítulo en color amarillo con la institución; refuerza la identidad visual.
        f"<p style='color:{ACCENT_YELLOW};'>Síntesis del reporte y de la aplicación Streamlit · {INSTITUTION}</p>",
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / n, text=f"Sección {idx + 1} de {n}")
    # Barra de progreso proporcional al paso actual; ayuda al usuario a ubicarse.
    choice = st.radio(
        # Botones de radio horizontales para saltar directo a cualquier paso del wizard.
        "Secciones",
        options=list(range(n)),
        # Las opciones internamente son índices (0..n-1).
        format_func=lambda i: WIZARD_CONCLUSION_STEPS[i][1],
        # Pero se muestran con la etiqueta legible de cada paso.
        index=idx,
        # Selección actual coincide con el estado de sesión.
        horizontal=True,
        # Los botones se acomodan en una fila, no en columna.
        label_visibility="collapsed",
        # Oculta la etiqueta "Secciones" del radio (estética).
        key="concl_radio",
        # Clave única para que Streamlit identifique el widget entre renders.
    )
    if choice != idx:
        # Si el usuario cambió de paso con el radio...
        st.session_state.concl_step = choice
        # ...actualizamos el estado...
        st.rerun()
        # ...y forzamos un re-render de la página para reflejarlo.
    idx = st.session_state.concl_step
    # Releemos el índice por si cambió arriba.
    _id, label, desc = WIZARD_CONCLUSION_STEPS[idx]
    # Desempacamos la tupla del paso actual.
    st.info(f"**{label}** — {desc}")
    # Caja informativa azul con el título y la descripción del paso actual.
    st.markdown("---")
    # Línea separadora horizontal antes del contenido.
    return idx
    # Devuelve el índice activo para que `main()` sepa qué función de paso llamar.


def _nav(n: int) -> None:
    # Función privada que dibuja los botones "Anterior" y "Siguiente" al pie del wizard.
    idx = st.session_state.concl_step
    # Lee el paso actual desde la sesión.
    c1, c2, _ = st.columns([1, 1, 6])
    # Distribuye el espacio en 3 columnas: dos pequeñas para los botones y una grande vacía a la derecha.
    with c1:
        # Columna izquierda: botón "Anterior".
        if st.button("← Anterior", disabled=idx <= 0):
            # Se deshabilita si ya estamos en el primer paso.
            st.session_state.concl_step -= 1
            # Retrocede un paso.
            st.rerun()
            # Re-renderiza la página.
    with c2:
        # Columna central: botón "Siguiente".
        if st.button("Siguiente →", disabled=idx >= n - 1):
            # Se deshabilita si ya estamos en el último paso.
            st.session_state.concl_step += 1
            # Avanza un paso.
            st.rerun()
            # Re-renderiza la página.


def step_que() -> None:
    # Paso 1: explica QUÉ hicimos en el proyecto.
    st.subheader("Qué hicimos")
    # Subtítulo de la sección.
    st.markdown(
        # Bloque de texto en Markdown con la descripción general del estudio.
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
    # Encabezado de cuarto nivel para resaltar el objetivo.
    st.success(
        # Caja verde de "éxito" para destacar la meta principal.
        "Modelar matemáticamente el proceso de carga para **predecir el tiempo total** "
        "y explicar el comportamiento **no lineal** (rápido al inicio, lento al final)."
    )
    st.markdown("#### Equipo")
    # Encabezado de la sección del equipo.
    import pandas as pd
    # Importa pandas localmente (solo se usa aquí) para construir la tabla del equipo.

    st.table(pd.DataFrame(TEAM, columns=["Integrante", "Área", "Aporte"]))
    # Renderiza una tabla estática con los integrantes a partir de la constante TEAM.
    st.markdown("#### Entregables")
    # Encabezado de la sección de entregables.
    st.markdown(
        # Lista en Markdown con los productos entregados del proyecto.
        """
        - Reporte técnico (Word/PDF) con marco teórico **CC-CV**, datos, R² y conclusiones.
        - Prototipo visual (HTML/Figma) con gráfica sigmoide e iteraciones de Newton-Raphson.
        - **Aplicación Streamlit** multipágina: laboratorio, actividades y esta síntesis.
        - Bitácora de muestras (`data/charge_samples.json`) cuando se usa recolección en vivo.
        """
    )


def step_como() -> None:
    # Paso 2: explica CÓMO realizamos el estudio.
    st.subheader("Cómo lo hicimos")
    # Subtítulo de la sección.
    st.markdown("#### Protocolo electroquímico (CC-CV)")
    # Encabezado de la explicación del protocolo de carga.
    c1, c2 = st.columns(2)
    # Divide la pantalla en dos columnas iguales para mostrar las dos fases en paralelo.
    with c1:
        # Columna izquierda: descripción de la fase de corriente constante.
        st.markdown(
            """
            **Fase CC (corriente constante, ~0–80%)**
            El cargador inyecta la máxima corriente permitida; el porcentaje sube casi de forma lineal.
            """
        )
    with c2:
        # Columna derecha: descripción de la fase de voltaje constante.
        st.markdown(
            """
            **Fase CV (voltaje constante, ~80–100%)**
            El voltaje se mantiene y la corriente baja; la curva se **aplana** (carga lenta).
            """
        )

    st.markdown("#### Metodología en 6 pasos")
    # Encabezado para los 6 pasos del método experimental.
    for num, titulo, desc in [
        # Itera sobre una lista de tuplas (número, título, descripción) y los imprime uno por uno.
        ("1", "Descarga", "Dispositivo por debajo del 5%."),
        ("2", "Bitácora", "Registro cada 5 min hasta 100%."),
        ("3", "Gráfica", "Dispersión tiempo (min) vs carga (%)."),
        ("4", "Regresión", "Modelos lineal y logístico; comparar **R²**."),
        ("5", "Newton-Raphson", "Resolver **C(t) = objetivo** (problema escalar)."),
        ("6", "Evaluación", "Error, eficiencia y pérdidas por calor/BMS."),
    ]:
        st.markdown(f"**{num}. {titulo}** — {desc}")
        # Imprime cada paso con formato Markdown en negritas.

    df = samples_dataframe()
    # Obtiene el DataFrame con las muestras experimentales del reporte.
    stats = report_fit_stats(df)
    # Calcula estadísticas del ajuste (R², número de muestras, duración máxima).
    st.markdown("#### Datos del experimento principal")
    # Encabezado de la sección de métricas.
    m1, m2, m3, m4 = st.columns(4)
    # Cuatro columnas para mostrar 4 indicadores tipo "tarjeta".
    m1.metric("Muestras", int(stats["n_samples"]))
    # Métrica 1: cantidad total de muestras tomadas.
    m2.metric("Duración", f"{stats['t_max_min']:.0f} min")
    # Métrica 2: duración total del experimento en minutos.
    m3.metric("R² logístico", f"{stats['r2_logistic']:.4f}")
    # Métrica 3: coeficiente de determinación del ajuste logístico (qué tan bien encaja).
    m4.metric("Tiempo real a 100%", f"{CHARGE_TIME_REAL_MIN:.0f} min")
    # Métrica 4: tiempo real medido para alcanzar la carga completa.

    st.markdown("#### Organización del proyecto")
    # Encabezado para describir la división de tareas en el equipo.
    st.markdown(
        # Descripción de roles y cronograma general.
        """
        - **Análisis (Adán, Ángel, Sergio):** recolección, limpieza, regresiones, Newton-Raphson, redacción técnica.
        - **Diseño UX (Checho, Arath, Gustavo):** identidad visual, dashboard, infografía CC-CV, mockup predictivo.
        - **Cronograma:** 2 abr – 8 may 2026, 30 actividades en 5 fases (ver *Centro del proyecto*).
        """
    )


def step_codigo() -> None:
    # Paso 3: explica la arquitectura del software.
    st.subheader("Cómo está programado")
    # Subtítulo de la sección.
    st.markdown(
        # Descripción general del stack técnico (Python + Streamlit).
        """
        La aplicación es **Python 3** con **Streamlit** (interfaz web local). No hay servidor aparte:
        al ejecutar `streamlit run main.py` se levanta el laboratorio y las páginas en `pages/`.
        """
    )
    st.markdown(
        # Diagrama Mermaid con la arquitectura: UI, lógica, persistencia y hardware opcional.
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
    # Encabezado de la tabla con la descripción de cada archivo .py.
    st.markdown(
        # Tabla Markdown que documenta la responsabilidad de cada módulo del proyecto.
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
    # Encabezado de la sección de matemáticas usadas.
    st.latex(r"C(t)=\frac{L}{1+e^{-k(t-t_0)}},\quad L=100")
    # Renderiza la fórmula sigmoide en LaTeX (modelo logístico de carga).
    st.markdown(
        # Lista con los métodos y librerías concretas que se usan.
        f"""
        - **Parámetros del reporte:** k ≈ **{K_RATE}**, t₀ ≈ **{T0_INFL}** min.
        - **Spline cúbico** (`scipy.interpolate.UnivariateSpline`) sobre muestras observadas.
        - **Newton-Raphson** (`scipy.optimize.newton`) sobre **f(t) = C(t) − objetivo** con derivada analítica.
        - **ADB** (`subprocess`): parseo de `dumpsys battery` para nivel, voltaje, corriente y temperatura en Android.
        """
    )
    st.caption(
        # Texto pequeño al pie con las dependencias del proyecto.
        "Dependencias: streamlit, pandas, numpy, scipy, plotly (ver `requirements.txt`)."
    )


def step_diseno() -> None:
    # Paso 4: explica las decisiones de diseño y experiencia de usuario.
    st.subheader("Cómo está diseñado")
    # Subtítulo de la sección.
    st.markdown(
        # Introducción a la filosofía de diseño "wizard" (pocos pasos, claros).
        """
        La experiencia sigue un patrón **asistente (wizard)**: pocos pasos, texto breve en cada uno
        y métricas visibles de inmediato. El objetivo UX del reporte era **traducir datos complejos
        en gráficas claras** — por eso priorizamos:
        """
    )
    st.markdown(
        # Lista con las decisiones de diseño aplicadas a la app.
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
    # Encabezado sobre la paleta y tipografía del prototipo original.
    st.markdown(
        # Descripción de la identidad visual usada en HTML/Figma y su adaptación a Streamlit.
        """
        En el prototipo HTML del reporte se usó paleta **crema / rojo ladrillo / verde / azul**,
        tipografías **Bebas Neue**, **IBM Plex Mono** y **DM Sans**, y tarjetas con sombra plana.
        La app Streamlit retoma el espíritu técnico (mono + acentos neón) para alinearlo con el laboratorio digital.
        """
    )
    st.markdown("#### Páginas de la aplicación")
    # Encabezado que enumera las 3 páginas del proyecto Streamlit.
    st.markdown(
        # Lista numerada de las páginas con su propósito breve.
        """
        1. **Laboratorio** — Flujo del experimento y análisis numérico.
        2. **Centro del proyecto** — Gestión de tareas y cronograma del equipo.
        3. **Conclusiones** (esta página) — Documentación integral del proyecto.
        """
    )


def step_final() -> None:
    # Paso 5: muestra los hallazgos y conclusiones finales.
    st.subheader("A qué conclusión llegamos")
    # Subtítulo de la sección final.
    st.markdown(
        # Resumen del comportamiento observado (no lineal, encaja con sigmoide).
        """
        El comportamiento de carga observado **no es lineal**: encaja con un modelo **sigmoide**
        (saturación hacia 100%). La fase **CC** explica el tramo rápido; la **CV** el tramo final lento.
        """
    )

    c1, c2, c3, c4 = st.columns(4)
    # Crea 4 columnas para mostrar las métricas clave del experimento.
    c1.metric("Energía medida", f"{ENERGY_WH} Wh")
    # Métrica 1: energía total medida durante la carga.
    c2.metric("Carga real", f"{CHARGE_TIME_REAL_MIN:.0f} min")
    # Métrica 2: tiempo real observado para cargar al 100%.
    c3.metric("Ideal teórico", f"{TIME_IDEAL_MIN:.1f} min")
    # Métrica 3: tiempo ideal calculado teóricamente (sin pérdidas).
    c4.metric("Eficiencia útil", f"~{EFFICIENCY_PCT}%")
    # Métrica 4: porcentaje de energía aprovechado como carga útil.

    st.markdown("#### Sobre Newton-Raphson")
    # Encabezado de la sección sobre los resultados del método numérico.
    st.markdown(
        # Tabla que compara el éxito del Newton-Raphson escalar vs multivariable.
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
    # Encabezado para explicar a dónde se va la energía no aprovechada.
    st.markdown(
        # Lista de causas físicas de las pérdidas durante la carga.
        """
        Gran parte de la energía no se almacena como carga útil, sino que se disipa en:

        - **Calor (efecto Joule)** y resistencia interna.
        - Conversión y electrónica del cargador.
        - **Protección del BMS** y estrategia **CV** al acercarse al 100%.
        """
    )

    st.markdown("#### Conclusión general")
    # Encabezado de la conclusión final del estudio.
    st.success(
        # Caja verde con el cierre conceptual del trabajo.
        "La carga Li-ion sigue un modelo sigmoide coherente con la teoría CC-CV. "
        "Newton-Raphson es útil en la forma escalar para predicción de tiempos; "
        "para ajuste global de parámetros conviene métodos más robustos."
    )

    st.markdown("#### Recomendaciones (del reporte)")
    # Encabezado para las recomendaciones derivadas del análisis.
    st.markdown(
        # Lista de recomendaciones técnicas para trabajos futuros.
        """
        - Usar **Levenberg-Marquardt** o **gradiente descendente** para el ajuste de parámetros.
        - Tratar con cuidado los puntos extremos (0% y 100%) en el ajuste multivariable.
        - Validar con herramientas como Python/SciPy o MATLAB.
        - Seguir registrando cada **5 min** y comparar dispositivos (como el segundo juego de datos del reporte).
        """
    )

    st.markdown("#### Cierre del proyecto software")
    # Encabezado del cierre relacionado con la aplicación.
    st.info(
        # Caja azul informativa que conecta la app con el reporte y declara el proyecto como completado.
        "Esta aplicación materializa el reporte: mismos datos, mismos métodos y un camino guiado "
        "para repetir el experimento (Android por ADB o cualquier teléfono en modo manual). "
        "El cronograma del equipo quedó registrado como **100% completado** en el Gantt de abril–mayo 2026."
    )


def main() -> None:
    # Punto de entrada de la página: configura Streamlit y orquesta los pasos.
    st.set_page_config(
        # Configura los metadatos de la pestaña del navegador y el layout.
        page_title="Conclusiones — Li-ion",
        # Título que aparece en la pestaña del navegador.
        page_icon="📋",
        # Ícono (favicon) de la página.
        layout="wide",
        # Usa el ancho completo del navegador (no centrado).
        initial_sidebar_state="collapsed",
        # La barra lateral inicia colapsada para no distraer.
    )
    inject_global_style()
    # Inyecta el CSS global definido en `theme.py` (colores, fuentes, etc.).

    idx = _step_header()
    # Dibuja el encabezado + selector y obtiene el índice del paso activo.
    step_id = WIZARD_CONCLUSION_STEPS[idx][0]
    # Extrae el id interno (string) del paso, p. ej. "que", "como", "codigo"...

    if step_id == "que":
        # Si el paso activo es "qué hicimos", renderiza esa sección.
        step_que()
    elif step_id == "como":
        # Si es "cómo lo hicimos", renderiza la metodología.
        step_como()
    elif step_id == "codigo":
        # Si es "programación", renderiza la arquitectura del software.
        step_codigo()
    elif step_id == "diseno":
        # Si es "diseño", renderiza las decisiones de UX/UI.
        step_diseno()
    else:
        # Caso restante ("final"): renderiza las conclusiones generales.
        step_final()

    _nav(len(WIZARD_CONCLUSION_STEPS))
    # Dibuja la barra de navegación inferior con los botones Anterior/Siguiente.


main()
# Llama a `main()` al importar/ejecutar el archivo (Streamlit ejecuta el script de arriba abajo en cada render).
