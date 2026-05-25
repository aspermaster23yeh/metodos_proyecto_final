"""Componentes UI compartidos: asistente por pasos."""
# Docstring: define helpers reutilizables para crear interfaces tipo "wizard" (asistente por pasos)
# usados por el Laboratorio y el Centro del Proyecto.

from __future__ import annotations
# Habilita evaluación diferida de anotaciones (compatibilidad con tipos modernos).

import streamlit as st
# Importa Streamlit para los widgets (botones, radio, progress, etc.).

from theme import ACCENT_CYAN, ACCENT_YELLOW, TEXT_MUTED
# Importa los colores del tema para mantener una identidad visual consistente.


def init_step(key: str, default: int = 0) -> None:
    # Inicializa el índice del paso actual dentro de `st.session_state` si aún no existe.
    if key not in st.session_state:
        # Si la clave no está en el estado de la sesión...
        st.session_state[key] = default
        # ...la crea con el valor por defecto (paso 0 = inicio).


def render_step_header(
    # Función que dibuja el encabezado del wizard: título, subtítulo, progreso y selector de pasos.
    steps: list[tuple[str, str, str]],
    # Lista de pasos donde cada tupla es (id, etiqueta, descripción).
    session_key: str,
    # Clave única para guardar el paso actual en el estado (permite varios wizards en la app).
    title: str,
    # Título grande de la página (ej. "Laboratorio de batería").
    subtitle: str,
    # Subtítulo debajo del título (descripción corta).
) -> int:
    """Barra de progreso y navegación. Devuelve índice del paso actual."""
    # Docstring: explica el propósito y el valor de retorno.
    init_step(session_key, 0)
    # Garantiza que exista el estado del paso (lo inicializa en 0 si es la primera vez).
    idx = st.session_state[session_key]
    # Lee el índice del paso activo desde el estado.
    n = len(steps)
    # Total de pasos del wizard.

    st.markdown(
        # Renderiza el título principal con HTML para aplicar color cian del tema.
        f"<h1 style='color:{ACCENT_CYAN};margin-bottom:0.1rem;'>{title}</h1>",
        unsafe_allow_html=True,
        # Permite HTML embebido (necesario para estilizar el título).
    )
    st.markdown(
        # Subtítulo amarillo, más pequeño, debajo del título.
        f"<p style='color:{ACCENT_YELLOW};font-size:0.9rem;margin-top:0;'>{subtitle}</p>",
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / n, text=f"Paso {idx + 1} de {n}")
    # Barra de progreso proporcional (de 0 a 1) con texto descriptivo.

    choice = st.radio(
        # Botones de radio horizontales como navegador rápido entre pasos.
        "Ir al paso",
        # Etiqueta del widget (oculta luego con label_visibility).
        options=list(range(n)),
        # Las opciones internas son índices numéricos 0..n-1.
        format_func=lambda i: steps[i][1],
        # Pero al usuario se le muestra la etiqueta (segundo elemento de la tupla).
        index=idx,
        # Selecciona por defecto el paso activo.
        horizontal=True,
        # Acomoda los botones en una fila horizontal.
        key=f"{session_key}_radio",
        # Clave única del widget para que Streamlit lo identifique entre renders.
        label_visibility="collapsed",
        # Oculta visualmente la etiqueta "Ir al paso".
    )
    if choice != idx:
        # Si el usuario seleccionó un paso distinto al actual...
        st.session_state[session_key] = choice
        # ...actualiza el estado al nuevo paso...
        st.rerun()
        # ...y fuerza un re-renderizado de la app para reflejar el cambio.
    idx = st.session_state[session_key]
    # Vuelve a leer el índice (por si cambió en el bloque anterior).

    st.markdown("---")
    # Línea horizontal separadora antes del contenido específico del paso.
    _id, label, desc = steps[idx]
    # Desempaqueta la tupla del paso activo: id interno, etiqueta visible y descripción.
    st.info(f"**{label}** — {desc}")
    # Caja informativa azul con el nombre y descripción del paso actual.
    return idx
    # Devuelve el índice para que el script principal sepa qué función de paso ejecutar.


def step_nav_buttons(session_key: str, n_steps: int, col_ratio: tuple[int, int] = (1, 1, 6)) -> None:
    # Dibuja los botones "Anterior" y "Siguiente" al pie de la página del wizard.
    idx = st.session_state[session_key]
    # Lee el paso actual desde el estado de sesión.
    c1, c2, _ = st.columns(col_ratio)
    # Crea tres columnas con proporciones dadas (1:1:6) — los botones a la izquierda y espacio vacío a la derecha.
    with c1:
        # Primera columna: botón "Anterior".
        if st.button("← Anterior", disabled=idx <= 0):
            # Deshabilitado cuando ya estamos en el primer paso.
            st.session_state[session_key] = max(0, idx - 1)
            # Retrocede un paso (nunca por debajo de 0).
            st.rerun()
            # Vuelve a renderizar la página con el nuevo paso.
    with c2:
        # Segunda columna: botón "Siguiente".
        if st.button("Siguiente →", disabled=idx >= n_steps - 1):
            # Deshabilitado cuando ya estamos en el último paso.
            st.session_state[session_key] = min(n_steps - 1, idx + 1)
            # Avanza un paso (nunca por encima del último).
            st.rerun()
            # Re-renderiza la página.
