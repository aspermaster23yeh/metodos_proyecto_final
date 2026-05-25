"""
Project Hub — Li-ion charge study: To-do, Kanban, Gantt (Apr 2 – May 8, 2026).
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tasks_store import (
    ASSIGNEES,
    CRONOGRAMA_8,
    PHASES,
    PROFILES,
    PROJECT_END,
    PROJECT_START,
    STATUSES,
    STATUS_LABELS,
    Task,
    load_tasks,
    new_task_id,
    redistribute_phase_dates,
    save_tasks,
    tasks_to_dataframe,
    validate_task,
)
from theme import (
    ACCENT_CYAN,
    ACCENT_YELLOW,
    BG,
    GRID,
    PROFILE_COLORS,
    TEXT_MUTED,
    inject_global_style,
)

STATUS_OPTIONS = list(STATUSES)
STATUS_DISPLAY = [STATUS_LABELS[s] for s in STATUS_OPTIONS]
STATUS_FROM_DISPLAY = dict(zip(STATUS_DISPLAY, STATUS_OPTIONS))


def _init_session() -> None:
    if "hub_tasks" not in st.session_state:
        st.session_state.hub_tasks = load_tasks()
    if "hub_dirty" not in st.session_state:
        st.session_state.hub_dirty = False


def _mark_dirty() -> None:
    st.session_state.hub_dirty = True


def _persist_if_dirty() -> None:
    if st.session_state.get("hub_dirty"):
        save_tasks(st.session_state.hub_tasks)
        st.session_state.hub_dirty = False


def _get_tasks() -> list[Task]:
    return st.session_state.hub_tasks


def _update_task(updated: Task) -> None:
    tasks = _get_tasks()
    for i, t in enumerate(tasks):
        if t.id == updated.id:
            tasks[i] = validate_task(updated)
            break
    st.session_state.hub_tasks = tasks
    _mark_dirty()


def _delete_task(task_id: str) -> None:
    st.session_state.hub_tasks = [t for t in _get_tasks() if t.id != task_id]
    _mark_dirty()


def _add_task(task: Task) -> None:
    st.session_state.hub_tasks = _get_tasks() + [validate_task(task)]
    _mark_dirty()


def _completion_stats(tasks: list[Task]) -> dict[str, float | int]:
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "done")
    return {
        "total": total,
        "done": done,
        "pct": (100.0 * done / total) if total else 0.0,
    }


def _filter_tasks(
    tasks: list[Task],
    phase: str | None,
    assignee: str | None,
    profile: str | None,
    status: str | None,
) -> list[Task]:
    out = tasks
    if phase and phase != "Todas":
        out = [t for t in out if t.phase == phase]
    if assignee and assignee != "Todos":
        out = [t for t in out if assignee in t.assignees]
    if profile and profile != "Todos":
        out = [t for t in out if t.profile == profile]
    if status and status != "Todos":
        out = [t for t in out if t.status == status]
    return out


def build_gantt_figure(tasks: list[Task], color_by: str) -> go.Figure:
    if not tasks:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG, height=420)
        return fig

    df = pd.DataFrame(
        [
            {
                "Task": t.title[:52] + ("…" if len(t.title) > 52 else ""),
                "Start": pd.Timestamp(t.start),
                "Finish": pd.Timestamp(t.end) + pd.Timedelta(days=1),
                "Phase": t.phase,
                "Profile": t.profile,
            }
            for t in tasks
        ]
    )
    color_col = "Phase" if color_by == "Fase" else "Profile"
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color=color_col,
        color_discrete_map={
            "Preparación": ACCENT_YELLOW,
            "Recolección": "#7CFF6B",
            "Modelación": ACCENT_CYAN,
            "Desarrollo UX": "#B388FF",
            "Cierre": TEXT_MUTED,
            "Análisis": ACCENT_YELLOW,
            "Diseño UX": ACCENT_CYAN,
            "General": "#6E7681",
        },
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
        font=dict(family="JetBrains Mono, monospace", color=TEXT_MUTED, size=11),
        title=dict(text="Cronograma Gantt — Proyecto Li-ion", font=dict(color=ACCENT_CYAN)),
        xaxis=dict(
            range=[PROJECT_START.isoformat(), PROJECT_END.isoformat()],
            title="Calendario",
            gridcolor=GRID,
        ),
        yaxis=dict(autorange="reversed", gridcolor=GRID),
        height=max(420, 28 * len(tasks)),
        margin=dict(l=200, r=24, t=56, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def render_sidebar() -> None:
    st.sidebar.markdown("### Proyecto Li-ion")
    st.sidebar.caption(f"Ventana: **{PROJECT_START}** → **{PROJECT_END}**")
    st.sidebar.markdown(
        "**Objetivo:** modelar matemáticamente la carga de un smartphone "
        "y predecir el tiempo total (comportamiento no lineal CC-CV)."
    )
    with st.sidebar.expander("Metodología CC-CV"):
        st.markdown(
            """
            **CC (corriente constante):** ~0–80%, crecimiento casi lineal.

            **CV (voltaje constante):** >80%, corriente decrece; curva se aplana.

            **Variables:** efecto Joule, uso del dispositivo durante medición.

            **Muestreo:** cada 5 min desde <5% hasta 100% (modo avión, brillo 0%).
            """
        )
    st.sidebar.markdown("---")
    if st.sidebar.button("Guardar cambios", type="primary"):
        save_tasks(_get_tasks())
        st.session_state.hub_dirty = False
        st.sidebar.success("Guardado en `data/project_tasks.json`")
    if st.sidebar.button("Repartir fechas por fase"):
        st.session_state.hub_tasks = redistribute_phase_dates(_get_tasks())
        _mark_dirty()
        st.sidebar.info("Fechas redistribuidas dentro de cada fase.")
        st.rerun()
    csv = tasks_to_dataframe(_get_tasks()).to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        "Exportar CSV",
        data=csv,
        file_name="project_tasks.csv",
        mime="text/csv",
    )
    st.sidebar.caption("Battery Lab: usa preset **Metodología (5 min)** en la página principal.")


def render_summary(tasks: list[Task]) -> None:
    stats = _completion_stats(tasks)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tareas", stats["total"])
    c2.metric("Completadas", stats["done"])
    c3.metric("Avance", f"{stats['pct']:.0f}%")
    c4.metric("Fases", len(PHASES))


def render_todo_tab(tasks: list[Task]) -> None:
    st.markdown("#### To-do y edición")
    with st.expander("Nueva tarea", expanded=False):
        with st.form("new_task_form", clear_on_submit=True):
            title = st.text_input("Título")
            phase = st.selectbox("Fase", PHASES)
            profile = st.selectbox("Perfil", PROFILES)
            assignees = st.multiselect("Responsables", ASSIGNEES, default=["Adán", "Ángel"])
            status_disp = st.selectbox("Estado", STATUS_DISPLAY, index=0)
            c1, c2 = st.columns(2)
            with c1:
                start = st.date_input("Inicio", PROJECT_START, min_value=PROJECT_START, max_value=PROJECT_END)
            with c2:
                end = st.date_input("Fin", PROJECT_END, min_value=PROJECT_START, max_value=PROJECT_END)
            deliverable = st.text_input("Entregable")
            notes = st.text_area("Notas", height=60)
            if st.form_submit_button("Agregar tarea"):
                if title.strip():
                    _add_task(
                        Task(
                            id=new_task_id(),
                            title=title.strip(),
                            phase=phase,
                            assignees=assignees or list(ASSIGNEES),
                            profile=profile,
                            status=STATUS_FROM_DISPLAY[status_disp],
                            start=start.isoformat(),
                            end=end.isoformat(),
                            deliverable=deliverable,
                            notes=notes,
                        )
                    )
                    st.rerun()
                else:
                    st.warning("El título es obligatorio.")

    for t in tasks:
        color = PROFILE_COLORS.get(t.profile, TEXT_MUTED)
        header = f"{'✅' if t.status == 'done' else '⬜'} {t.title}"
        with st.expander(header, expanded=False):
            st.markdown(
                f"<span style='color:{color};font-size:0.85rem;'>{t.phase} · {t.profile} · "
                f"{', '.join(t.assignees)}</span>",
                unsafe_allow_html=True,
            )
            if t.deliverable:
                st.caption(f"Entregable: {t.deliverable}")
            new_status = st.selectbox(
                "Estado",
                STATUS_DISPLAY,
                index=STATUS_OPTIONS.index(t.status) if t.status in STATUS_OPTIONS else 0,
                key=f"status_{t.id}",
            )
            nt = validate_task(
                Task(
                    id=t.id,
                    title=st.text_input("Título", t.title, key=f"title_{t.id}"),
                    phase=st.selectbox("Fase", PHASES, index=PHASES.index(t.phase), key=f"phase_{t.id}"),
                    profile=st.selectbox(
                        "Perfil", PROFILES, index=PROFILES.index(t.profile), key=f"prof_{t.id}"
                    ),
                    assignees=st.multiselect(
                        "Responsables",
                        ASSIGNEES,
                        default=t.assignees,
                        key=f"asg_{t.id}",
                    ),
                    status=STATUS_FROM_DISPLAY[new_status],
                    start=st.date_input(
                        "Inicio",
                        t.start_date(),
                        min_value=PROJECT_START,
                        max_value=PROJECT_END,
                        key=f"start_{t.id}",
                    ).isoformat(),
                    end=st.date_input(
                        "Fin",
                        t.end_date(),
                        min_value=PROJECT_START,
                        max_value=PROJECT_END,
                        key=f"end_{t.id}",
                    ).isoformat(),
                    deliverable=st.text_input("Entregable", t.deliverable, key=f"del_{t.id}"),
                    notes=st.text_area("Notas", t.notes, key=f"notes_{t.id}"),
                )
            )
            bc1, bc2 = st.columns(2)
            if bc1.button("Actualizar", key=f"upd_{t.id}"):
                _update_task(nt)
                st.rerun()
            if bc2.button("Eliminar", key=f"delbtn_{t.id}"):
                _delete_task(t.id)
                st.rerun()


def render_kanban_tab(tasks: list[Task]) -> None:
    st.markdown("#### Kanban")
    cols = st.columns(4)
    for col, status in zip(cols, STATUS_OPTIONS):
        with col:
            st.markdown(f"**{STATUS_LABELS[status]}**")
            column_tasks = [t for t in tasks if t.status == status]
            for t in column_tasks:
                color = PROFILE_COLORS.get(t.profile, TEXT_MUTED)
                st.markdown(
                    f"""<div class="task-card">
                    <div style="color:{ACCENT_CYAN};font-size:0.9rem;">{t.title}</div>
                    <div style="color:{color};font-size:0.75rem;margin-top:0.25rem;">
                    {t.phase} · {', '.join(t.assignees)}</div>
                    <div style="color:{TEXT_MUTED};font-size:0.7rem;">{t.start} → {t.end}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                new_disp = st.selectbox(
                    "Mover a",
                    STATUS_DISPLAY,
                    index=STATUS_OPTIONS.index(t.status),
                    key=f"kanban_{t.id}",
                    label_visibility="collapsed",
                )
                new_st = STATUS_FROM_DISPLAY[new_disp]
                if new_st != t.status:
                    t.status = new_st
                    _update_task(t)
                    st.rerun()


def render_gantt_tab(tasks: list[Task]) -> None:
    st.markdown("#### Gantt")
    color_by = st.radio("Color por", ["Fase", "Perfil"], horizontal=True)
    fig = build_gantt_figure(tasks, color_by)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("##### Referencia — cronograma de 8 actividades")
    st.dataframe(
        pd.DataFrame(
            CRONOGRAMA_8,
            columns=["Fase", "Actividad", "Responsables", "Entregable"],
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.dataframe(tasks_to_dataframe(tasks), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Project Hub — Li-ion", layout="wide", initial_sidebar_state="expanded")
    inject_global_style()
    _init_session()
    render_sidebar()

    st.markdown(
        f"<h1 style='color:{ACCENT_CYAN};margin-bottom:0.2rem;'>PROJECT HUB</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{ACCENT_YELLOW};font-size:0.95rem;margin-top:0;'>"
        "Gestión de tareas · Li-ion charge study · 02 abr – 08 may 2026"
        "</p>",
        unsafe_allow_html=True,
    )

    tasks_all = _get_tasks()
    render_summary(tasks_all)

    st.markdown("##### Filtros")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        f_phase = st.selectbox("Fase", ["Todas", *PHASES], key="filt_phase")
    with fc2:
        f_assignee = st.selectbox("Responsable", ["Todos", *ASSIGNEES], key="filt_asg")
    with fc3:
        f_profile = st.selectbox("Perfil", ["Todos", *PROFILES], key="filt_prof")
    with fc4:
        f_status = st.selectbox(
            "Estado",
            ["Todos", *STATUS_DISPLAY],
            key="filt_status",
        )
    status_key = None if f_status == "Todos" else STATUS_FROM_DISPLAY.get(f_status)
    filtered = _filter_tasks(tasks_all, f_phase, f_assignee, f_profile, status_key)

    tab_todo, tab_kanban, tab_gantt = st.tabs(["To-do", "Kanban", "Gantt"])
    with tab_todo:
        render_todo_tab(filtered)
    with tab_kanban:
        render_kanban_tab(filtered)
    with tab_gantt:
        render_gantt_tab(filtered)

    _persist_if_dirty()


main()
