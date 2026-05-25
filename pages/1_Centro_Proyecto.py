"""
Centro del proyecto — actividades y cronograma (asistente simplificado).
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from report_data import DELIVERY_DATE, INSTITUTION, WIZARD_HUB_STEPS
from tasks_store import (
    CRONOGRAMA_8,
    PHASE_COLORS,
    PHASES,
    PROJECT_END,
    PROJECT_START,
    STATUS_LABELS,
    Task,
    load_tasks,
    save_tasks,
    tasks_to_dataframe,
)
from theme import ACCENT_CYAN, ACCENT_YELLOW, BG, GRID, PROFILE_COLORS, TEXT_MUTED, inject_global_style
from wizard_ui import render_step_header, step_nav_buttons


def _init() -> None:
    if "hub_tasks" not in st.session_state:
        st.session_state.hub_tasks = load_tasks()


def _stats(tasks: list[Task]) -> dict:
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "done")
    by_phase = {p: sum(1 for t in tasks if t.phase == p) for p in PHASES}
    by_phase_done = {p: sum(1 for t in tasks if t.phase == p and t.status == "done") for p in PHASES}
    return {
        "total": total,
        "done": done,
        "pct": 100.0 * done / total if total else 0,
        "by_phase": by_phase,
        "by_phase_done": by_phase_done,
    }


def build_gantt(tasks: list[Task]) -> go.Figure:
    if not tasks:
        return go.Figure()
    df = pd.DataFrame(
        [
            {
                "Tarea": t.title[:48] + ("…" if len(t.title) > 48 else ""),
                "Inicio": pd.Timestamp(t.start),
                "Fin": pd.Timestamp(t.end) + pd.Timedelta(days=1),
                "Fase": t.phase,
                "Estado": STATUS_LABELS.get(t.status, t.status),
            }
            for t in tasks
        ]
    )
    fig = px.timeline(
        df,
        x_start="Inicio",
        x_end="Fin",
        y="Tarea",
        color="Fase",
        color_discrete_map=PHASE_COLORS,
        hover_data=["Estado"],
    )
    today = date.today()
    if PROJECT_START <= today <= PROJECT_END:
        fig.add_vline(
            x=datetime.combine(today, datetime.min.time()),
            line_dash="dot",
            line_color=ACCENT_YELLOW,
            annotation_text="Hoy",
        )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Cronograma del proyecto (abril–mayo 2026)", font=dict(color=ACCENT_CYAN)),
        xaxis=dict(range=[PROJECT_START.isoformat(), PROJECT_END.isoformat()], title="Fecha"),
        yaxis=dict(autorange="reversed"),
        height=max(450, 26 * len(tasks)),
        font=dict(family="JetBrains Mono, monospace", color=TEXT_MUTED),
        legend=dict(orientation="h", y=1.02),
    )
    return fig


def step_resumen(tasks: list[Task]) -> None:
    s = _stats(tasks)
    st.subheader("Estadísticas del equipo")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tareas totales", s["total"])
    c2.metric("Completadas", s["done"])
    c3.metric("Avance global", f"{s['pct']:.0f}%")
    st.progress(s["pct"] / 100.0)

    st.markdown("#### Avance por fase")
    rows = []
    for p in PHASES:
        tot = s["by_phase"][p]
        ok = s["by_phase_done"][p]
        rows.append({"Fase": p, "Hechas": ok, "Total": tot, "%": f"{100 * ok / tot:.0f}%" if tot else "—"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Cronograma oficial (8 hitos)")
    st.dataframe(
        pd.DataFrame(CRONOGRAMA_8, columns=["Fase", "Actividad", "Responsables", "Entregable"]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{INSTITUTION} · Entrega: {DELIVERY_DATE}")


def step_actividades(tasks: list[Task]) -> None:
    st.subheader("Actividades por fase")
    fase = st.selectbox("Ver fase", PHASES)
    subset = [t for t in tasks if t.phase == fase]
    for t in subset:
        color = PROFILE_COLORS.get(t.profile, TEXT_MUTED)
        st.markdown(
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
        )


def step_gantt(tasks: list[Task]) -> None:
    st.subheader("Línea de tiempo")
    st.caption(f"Proyecto del **{PROJECT_START.strftime('%d/%m/%Y')}** al **{PROJECT_END.strftime('%d/%m/%Y')}** — barras por día.")
    st.plotly_chart(build_gantt(tasks), use_container_width=True)
    with st.expander("Tabla de fechas"):
        st.dataframe(tasks_to_dataframe(tasks), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Centro del proyecto", layout="wide", initial_sidebar_state="collapsed")
    inject_global_style()
    _init()
    tasks = st.session_state.hub_tasks

    with st.sidebar:
        st.markdown("### Centro del proyecto")
        if st.button("Recargar datos del JSON"):
            st.session_state.hub_tasks = load_tasks()
            st.rerun()
        csv = tasks_to_dataframe(tasks).to_csv(index=False).encode("utf-8")
        st.download_button("Descargar CSV", csv, "actividades.csv", "text/csv")

    idx = render_step_header(
        WIZARD_HUB_STEPS,
        "hub_step",
        "Centro del proyecto",
        "Seguimiento de actividades — todas completadas según el reporte",
    )
    step_id = WIZARD_HUB_STEPS[idx][0]

    if step_id == "resumen":
        step_resumen(tasks)
    elif step_id == "actividades":
        step_actividades(tasks)
    else:
        step_gantt(tasks)

    step_nav_buttons("hub_step", len(WIZARD_HUB_STEPS))


main()
