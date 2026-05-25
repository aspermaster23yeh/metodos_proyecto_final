"""Shared cyber theme for Battery Lab and Project Hub."""

from __future__ import annotations

import streamlit as st

BG = "#0E1117"
ACCENT_YELLOW = "#FFFF00"
ACCENT_CYAN = "#00F5FF"
TEXT_MUTED = "#9BA4B5"
GRID = "#262B36"

PROFILE_COLORS = {
    "Análisis": ACCENT_YELLOW,
    "Diseño UX": ACCENT_CYAN,
    "General": TEXT_MUTED,
}

def inject_global_style() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
        html, body, [class*="css"]  {{
            font-family: 'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Monaco, monospace !important;
            color: {TEXT_MUTED};
        }}
        .block-container {{
            padding-top: 1.2rem;
            max-width: 100%;
        }}
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'JetBrains Mono', monospace !important;
            color: {ACCENT_CYAN} !important;
            letter-spacing: 0.04em;
        }}
        [data-testid="stSidebar"] {{
            background-color: #161B22;
            border-right: 1px solid {GRID};
        }}
        div[data-testid="stMetricValue"] {{
            color: {ACCENT_YELLOW} !important;
            font-family: 'JetBrains Mono', monospace !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
        }}
        .task-card {{
            background: #161B22;
            border: 1px solid {GRID};
            border-radius: 6px;
            padding: 0.65rem 0.75rem;
            margin-bottom: 0.5rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
