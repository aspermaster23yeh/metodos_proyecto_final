"""
Centro del proyecto — actividades y cronograma (asistente simplificado).
"""
# Docstring del módulo: página de gestión de actividades del equipo (tareas, fases y cronograma Gantt).

from __future__ import annotations
# Anotaciones modernas de tipo.

from datetime import date, datetime
# `date` y `datetime` para trabajar con las fechas del proyecto.

import pandas as pd
# Pandas para construir DataFrames a partir de las tareas.
import plotly.express as px
# Plotly Express (API de alto nivel) — se usa para el diagrama Gantt.
import plotly.graph_objects as go
# Plotly graph_objects (API de bajo nivel) para crear figuras vacías cuando no hay datos.
import streamlit as st
# Framework de la UI.

from report_data import DELIVERY_DATE, INSTITUTION, WIZARD_HUB_STEPS
# Importa fecha de entrega, institución y los pasos del wizard del hub.
from tasks_store import (
    # Importa todo lo relacionado con tareas: datos, constantes, modelo y funciones de IO.
    CRONOGRAMA_8,           # Lista de 8 hitos principales.
    PHASE_COLORS,           # Colores de cada fase para el Gantt.
    PHASES,                 # Lista ordenada de fases.
    PROJECT_END,            # Fecha fin del proyecto.
    PROJECT_START,          # Fecha inicio del proyecto.
    STATUS_LABELS,          # Mapeo de estados internos a etiquetas en español.
    Task,                   # Clase dataclass de tarea.
    load_tasks,             # Lee tareas del JSON.
    save_tasks,             # Guarda tareas al JSON.
    tasks_to_dataframe,     # Convierte lista de Task a DataFrame.
)
from theme import ACCENT_CYAN, ACCENT_YELLOW, BG, GRID, PROFILE_COLORS, TEXT_MUTED, inject_global_style
# Colores y estilos del tema.
from wizard_ui import render_step_header, step_nav_buttons
# Helpers para el asistente por pasos.


def _init() -> None:
    # Inicializa el estado de la sesión con las tareas (las carga del JSON solo la primera vez).
    if "hub_tasks" not in st.session_state:
        st.session_state.hub_tasks = load_tasks()


def _stats(tasks: list[Task]) -> dict:
    # Calcula estadísticas globales y por fase para el resumen.
    total = len(tasks)
    # Total de tareas.
    done = sum(1 for t in tasks if t.status == "done")
    # Cuenta cuántas están en estado "done".
    by_phase = {p: sum(1 for t in tasks if t.phase == p) for p in PHASES}
    # Conteo total de tareas por fase.
    by_phase_done = {p: sum(1 for t in tasks if t.phase == p and t.status == "done") for p in PHASES}
    # Conteo de tareas hechas por fase.
    return {
        "total": total,
        "done": done,
        "pct": 100.0 * done / total if total else 0,
        # Porcentaje global de avance (con guarda para evitar división por cero).
        "by_phase": by_phase,
        "by_phase_done": by_phase_done,
    }


def build_gantt(tasks: list[Task]) -> go.Figure:
    # Construye el diagrama Gantt (línea de tiempo) con todas las tareas.
    if not tasks:
        return go.Figure()
        # Si no hay tareas, devuelve una figura vacía.
    df = pd.DataFrame(
        # Construye un DataFrame con las columnas que Plotly Express necesita para timeline.
        [
            {
                "Tarea": t.title[:48] + ("…" if len(t.title) > 48 else ""),
                # Trunca títulos largos a 48 caracteres + "…" para que no rompan el eje Y.
                "Inicio": pd.Timestamp(t.start),
                # Fecha de inicio como Timestamp de pandas.
                "Fin": pd.Timestamp(t.end) + pd.Timedelta(days=1),
                # Fecha de fin + 1 día (Plotly usa intervalo abierto en el extremo).
                "Fase": t.phase,
                "Estado": STATUS_LABELS.get(t.status, t.status),
            }
            for t in tasks
        ]
    )
    fig = px.timeline(
        # `px.timeline` crea un diagrama Gantt a partir del DataFrame.
        df,
        x_start="Inicio",
        x_end="Fin",
        y="Tarea",
        color="Fase",
        # Cada fase aparece con su propio color.
        color_discrete_map=PHASE_COLORS,
        # Mapeo explícito fase→color para que sean consistentes con el resto de la app.
        hover_data=["Estado"],
        # Al pasar el cursor por una barra se ve el estado.
    )
    today = date.today()
    # Fecha actual del sistema.
    if PROJECT_START <= today <= PROJECT_END:
        # Si hoy cae dentro del rango del proyecto, dibuja una línea vertical "Hoy".
        fig.add_vline(
            x=datetime.combine(today, datetime.min.time()),
            # Convierte `date` a `datetime` (Plotly requiere datetime).
            line_dash="dot",
            line_color=ACCENT_YELLOW,
            annotation_text="Hoy",
        )
    fig.update_layout(
        # Estética general del Gantt.
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Cronograma del proyecto (abril–mayo 2026)", font=dict(color=ACCENT_CYAN)),
        xaxis=dict(range=[PROJECT_START.isoformat(), PROJECT_END.isoformat()], title="Fecha"),
        # Eje X limitado al rango del proyecto.
        yaxis=dict(autorange="reversed"),
        # Invierte el eje Y para que la primera tarea aparezca arriba.
        height=max(450, 26 * len(tasks)),
        # Altura adaptativa: ~26 px por tarea, mínimo 450 px.
        font=dict(family="JetBrains Mono, monospace", color=TEXT_MUTED),
        legend=dict(orientation="h", y=1.02),
    )
    return fig


def step_resumen(tasks: list[Task]) -> None:
    # PASO 1 del wizard del hub: resumen de avance del equipo.
    s = _stats(tasks)
    # Calcula las estadísticas.
    st.subheader("Estadísticas del equipo")
    c1, c2, c3 = st.columns(3)
    # Tres métricas globales.
    c1.metric("Tareas totales", s["total"])
    c2.metric("Completadas", s["done"])
    c3.metric("Avance global", f"{s['pct']:.0f}%")
    st.progress(s["pct"] / 100.0)
    # Barra de progreso global (0..1).

    st.markdown("#### Avance por fase")
    rows = []
    # Acumulador para la tabla de avance por fase.
    for p in PHASES:
        tot = s["by_phase"][p]
        # Total de tareas en la fase.
        ok = s["by_phase_done"][p]
        # Hechas en la fase.
        rows.append({"Fase": p, "Hechas": ok, "Total": tot, "%": f"{100 * ok / tot:.0f}%" if tot else "—"})
        # Construye la fila con el porcentaje (o "—" si la fase no tiene tareas).
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    # Renderiza la tabla.

    st.markdown("#### Cronograma oficial (8 hitos)")
    st.dataframe(
        # Tabla con los 8 hitos principales (cronograma resumido).
        pd.DataFrame(CRONOGRAMA_8, columns=["Fase", "Actividad", "Responsables", "Entregable"]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{INSTITUTION} · Entrega: {DELIVERY_DATE}")
    # Caption con la institución y la fecha de entrega.


def step_actividades(tasks: list[Task]) -> None:
    # PASO 2 del wizard: lista detallada de actividades por fase.
    st.subheader("Actividades por fase")
    fase = st.selectbox("Ver fase", PHASES)
    # Selector para filtrar por fase.
    subset = [t for t in tasks if t.phase == fase]
    # Filtra las tareas de la fase elegida.
    for t in subset:
        # Renderiza cada tarea como una tarjeta HTML estilizada.
        color = PROFILE_COLORS.get(t.profile, TEXT_MUTED)
        # Color asociado al perfil del responsable.
        st.markdown(
            # HTML personalizado con la clase `task-card` definida en theme.py.
            f"""
            <div class="task-card">
            <div style="color:{ACCENT_CYAN};font-weight:600;">✅ {t.title}</div>
            <div style="color:{color};font-size:0.8rem;margin-top:0.3rem;">
            {t.start} · {', '.join(t.assignees)} · {t.profile}
            </div>
            <div style="color:{TEXT_MUTED};font-size:0.75rem;margin-top:0.25rem;">
            {t.description or 'Sin descripción.'}
            </div>
            <div style="color:{ACCENT_YELLOW};font-size:0.75rem;">Entregable: {t.deliverable or '—'}</div>
            </div>
            """,
            unsafe_allow_html=True,
            # Permite HTML embebido (necesario para la tarjeta personalizada).
        )


def step_gantt(tasks: list[Task]) -> None:
    # PASO 3 del wizard: cronograma Gantt visual.
    st.subheader("Línea de tiempo")
    st.caption(f"Proyecto del **{PROJECT_START.strftime('%d/%m/%Y')}** al **{PROJECT_END.strftime('%d/%m/%Y')}** — barras por día.")
    # Caption con el rango del proyecto formateado en DD/MM/AAAA.
    st.plotly_chart(build_gantt(tasks), use_container_width=True)
    # Renderiza el Gantt.
    with st.expander("Tabla de fechas"):
        # Bloque colapsable con la tabla completa de tareas (alternativa textual al Gantt).
        st.dataframe(tasks_to_dataframe(tasks), use_container_width=True, hide_index=True)


def main() -> None:
    # Punto de entrada de la página: configura, inicializa y enruta los pasos.
    st.set_page_config(page_title="Centro del proyecto", layout="wide", initial_sidebar_state="collapsed")
    # Configura metadatos y layout.
    inject_global_style()
    # Aplica el CSS global del tema.
    _init()
    # Inicializa el estado de sesión (carga tareas si es necesario).
    tasks = st.session_state.hub_tasks
    # Atajo a la lista de tareas en sesión.

    with st.sidebar:
        # Barra lateral con acciones secundarias.
        st.markdown("### Centro del proyecto")
        if st.button("Recargar datos del JSON"):
            # Botón para volver a leer el JSON desde disco (descarta cambios en sesión).
            st.session_state.hub_tasks = load_tasks()
            st.rerun()
        csv = tasks_to_dataframe(tasks).to_csv(index=False).encode("utf-8")
        # Convierte las tareas a CSV en bytes para descarga.
        st.download_button("Descargar CSV", csv, "actividades.csv", "text/csv")
        # Botón de descarga del CSV.

    idx = render_step_header(
        # Dibuja el encabezado del wizard del hub.
        WIZARD_HUB_STEPS,
        "hub_step",
        "Centro del proyecto",
        "Seguimiento de actividades — todas completadas según el reporte",
    )
    step_id = WIZARD_HUB_STEPS[idx][0]
    # Identificador interno del paso activo.

    if step_id == "resumen":
        step_resumen(tasks)
    elif step_id == "actividades":
        step_actividades(tasks)
    else:
        step_gantt(tasks)
    # Enruta al paso correspondiente.

    step_nav_buttons("hub_step", len(WIZARD_HUB_STEPS))
    # Botones Anterior/Siguiente al pie.


main()
# Llamada al main: Streamlit ejecuta el archivo de arriba abajo en cada render.
