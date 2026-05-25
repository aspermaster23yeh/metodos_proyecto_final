"""Shared cyber theme for Battery Lab and Project Hub."""
# Docstring del módulo: define el tema visual (colores, fuentes, estilos) compartido por todas las páginas.

from __future__ import annotations
# Permite usar anotaciones de tipo modernas en versiones anteriores de Python.

import streamlit as st
# Importa Streamlit para poder inyectar CSS al renderizado de la app.

BG = "#0E1117"
# Color de fondo principal (gris/negro muy oscuro) usado en gráficas y contenedores.
ACCENT_YELLOW = "#FFFF00"
# Color de acento amarillo intenso (usado para datos y métricas destacadas).
ACCENT_CYAN = "#00F5FF"
# Color de acento cian/neón (usado en títulos y elementos importantes).
TEXT_MUTED = "#9BA4B5"
# Color gris azulado para texto secundario (etiquetas, captions, descripciones).
GRID = "#262B36"
# Color de líneas de cuadrícula y bordes (gris oscuro discreto).

PROFILE_COLORS = {
    # Diccionario que asigna un color a cada "perfil" del equipo para identificar roles visualmente.
    "Análisis": ACCENT_YELLOW,
    # Los miembros de análisis se muestran en amarillo.
    "Diseño UX": ACCENT_CYAN,
    # Los de diseño UX en cian.
    "General": TEXT_MUTED,
    # Tareas compartidas en color neutro.
}

def inject_global_style() -> None:
    # Función que inyecta un bloque <style> CSS global en la página Streamlit.
    st.markdown(
        # Renderiza un bloque Markdown que en realidad contiene HTML/CSS.
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
        /* Importa la fuente JetBrains Mono desde Google Fonts (tipografía técnica y monoespaciada). */
        html, body, [class*="css"]  {{
            font-family: 'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Monaco, monospace !important;
            /* Aplica la fuente monoespaciada a TODO el documento, con fallbacks por si no carga la principal. */
            color: {TEXT_MUTED};
            /* Color de texto por defecto: gris azulado. */
        }}
        .block-container {{
            padding-top: 1.2rem;
            /* Reduce el espacio superior para aprovechar más la pantalla. */
            max-width: 100%;
            /* Permite que el contenido ocupe todo el ancho del navegador. */
        }}
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'JetBrains Mono', monospace !important;
            /* Fuerza la fuente mono también en todos los encabezados. */
            color: {ACCENT_CYAN} !important;
            /* Los encabezados se ven en cian neón. */
            letter-spacing: 0.04em;
            /* Espacio extra entre letras para estilo "tech". */
        }}
        [data-testid="stSidebar"] {{
            background-color: #161B22;
            /* Fondo ligeramente más claro para la barra lateral, para contraste. */
            border-right: 1px solid {GRID};
            /* Borde derecho sutil que separa sidebar del contenido. */
        }}
        div[data-testid="stMetricValue"] {{
            color: {ACCENT_YELLOW} !important;
            /* Los valores numéricos de las métricas (st.metric) se ven en amarillo. */
            font-family: 'JetBrains Mono', monospace !important;
            /* Y siempre con la fuente monoespaciada. */
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            /* Pequeña separación entre pestañas (st.tabs) para legibilidad. */
        }}
        .task-card {{
            background: #161B22;
            /* Fondo oscuro de las tarjetas de tareas en el Centro del Proyecto. */
            border: 1px solid {GRID};
            /* Borde sutil. */
            border-radius: 6px;
            /* Esquinas ligeramente redondeadas. */
            padding: 0.65rem 0.75rem;
            /* Margen interno cómodo. */
            margin-bottom: 0.5rem;
            /* Separación entre tarjetas. */
        }}
        </style>
        """,
        unsafe_allow_html=True,
        # Necesario para permitir HTML/CSS embebido (Streamlit lo bloquea por defecto).
    )
