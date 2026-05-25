"""Componentes UI compartidos: asistente por pasos."""

from __future__ import annotations

import streamlit as st

from theme import ACCENT_CYAN, ACCENT_YELLOW, TEXT_MUTED


def init_step(key: str, default: int = 0) -> None:
    if key not in st.session_state:
        st.session_state[key] = default


def render_step_header(
    steps: list[tuple[str, str, str]],
    session_key: str,
    title: str,
    subtitle: str,
) -> int:
    """Barra de progreso y navegación. Devuelve índice del paso actual."""
    init_step(session_key, 0)
    idx = st.session_state[session_key]
    n = len(steps)

    st.markdown(
        f"<h1 style='color:{ACCENT_CYAN};margin-bottom:0.1rem;'>{title}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{ACCENT_YELLOW};font-size:0.9rem;margin-top:0;'>{subtitle}</p>",
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / n, text=f"Paso {idx + 1} de {n}")

    choice = st.radio(
        "Ir al paso",
        options=list(range(n)),
        format_func=lambda i: steps[i][1],
        index=idx,
        horizontal=True,
        key=f"{session_key}_radio",
        label_visibility="collapsed",
    )
    if choice != idx:
        st.session_state[session_key] = choice
        st.rerun()
    idx = st.session_state[session_key]

    st.markdown("---")
    _id, label, desc = steps[idx]
    st.info(f"**{label}** — {desc}")
    return idx


def step_nav_buttons(session_key: str, n_steps: int, col_ratio: tuple[int, int] = (1, 1, 6)) -> None:
    idx = st.session_state[session_key]
    c1, c2, _ = st.columns(col_ratio)
    with c1:
        if st.button("← Anterior", disabled=idx <= 0):
            st.session_state[session_key] = max(0, idx - 1)
            st.rerun()
    with c2:
        if st.button("Siguiente →", disabled=idx >= n_steps - 1):
            st.session_state[session_key] = min(n_steps - 1, idx + 1)
            st.rerun()
