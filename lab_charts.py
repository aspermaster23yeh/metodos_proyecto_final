"""Gráficas Plotly del Laboratorio."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from battery_models import ModelComparison, logistic_c
from theme import ACCENT_CYAN, ACCENT_YELLOW, BG, TEXT_MUTED


def fig_model_comparison(df: pd.DataFrame, cmp: ModelComparison) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["t_min"],
            y=df["level"],
            mode="markers+lines",
            name="Medido",
            line=dict(color=ACCENT_YELLOW, width=1),
            marker=dict(size=8, color=ACCENT_YELLOW),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cmp.t_grid,
            y=cmp.y_linear,
            mode="lines",
            name="Lineal",
            line=dict(color="#7CFF6B", width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cmp.t_grid,
            y=cmp.y_logistic,
            mode="lines",
            name="Logístico C(t)",
            line=dict(color=ACCENT_CYAN, width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cmp.t_grid,
            y=cmp.y_spline,
            mode="lines",
            name="Spline",
            line=dict(color="#B388FF", width=2, dash="dot"),
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED, annotation_text="80%")
    fig.add_hline(y=100, line_dash="dash", line_color=TEXT_MUTED, annotation_text="100%")
    if cmp.t_cv_min is not None:
        fig.add_vline(
            x=cmp.t_cv_min,
            line_dash="dot",
            line_color="#FF6B6B",
            annotation_text="Inicio CV (~80%)",
            annotation_position="top",
        )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Comparativa de modelos + fases CC-CV", font=dict(color=ACCENT_CYAN)),
        xaxis_title="t (min)",
        yaxis_title="C (%)",
        yaxis=dict(range=[0, 105]),
        height=520,
        legend=dict(orientation="h", y=1.08),
    )
    return fig


def fig_dual_devices(
    df_main: pd.DataFrame,
    df_alt: pd.DataFrame,
    label_main: str,
    label_alt: str,
) -> go.Figure:
    t_grid = np.linspace(0, 52, 200)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_main["t_min"],
            y=df_main["level"],
            mode="markers+lines",
            name=f"{label_main} (medido)",
            line=dict(color=ACCENT_YELLOW, width=1),
            marker=dict(size=7),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t_grid,
            y=logistic_c(t_grid),
            mode="lines",
            name=f"{label_main} (sigmoide ref.)",
            line=dict(color=ACCENT_CYAN, width=1, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_alt["t_min"],
            y=df_alt["level"],
            mode="markers+lines",
            name=f"{label_alt} (medido)",
            line=dict(color="#7CFF6B", width=1),
            marker=dict(size=7),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t_grid,
            y=logistic_c(t_grid),
            mode="lines",
            name=f"{label_alt} (sigmoide ref.)",
            line=dict(color="#B388FF", width=1, dash="dot"),
            showlegend=False,
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Dos dispositivos del reporte", font=dict(color=ACCENT_CYAN)),
        xaxis_title="t (min)",
        yaxis_title="C (%)",
        yaxis=dict(range=[0, 105]),
        height=520,
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def fig_charge_simple(df: pd.DataFrame, t_cv_min: float | None = None) -> go.Figure:
    """Gráfica de recolección con marca CC-CV opcional."""
    t_m = np.linspace(0, max(float(df["t_min"].max()), 1), 200)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["t_min"],
            y=df["level"],
            mode="markers+lines",
            name="Medido",
            line=dict(color=ACCENT_YELLOW, width=1),
            marker=dict(size=8, color=ACCENT_YELLOW),
        )
    )
    fig.add_trace(
        go.Scatter(x=t_m, y=logistic_c(t_m), mode="lines", name="Referencia sigmoide", line=dict(color=ACCENT_CYAN))
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED, annotation_text="80%")
    if t_cv_min is not None:
        fig.add_vline(x=t_cv_min, line_dash="dot", line_color="#FF6B6B", annotation_text="Inicio CV (~80%)")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Carga (%) vs tiempo (min)", font=dict(color=ACCENT_CYAN)),
        xaxis_title="t (min)",
        yaxis_title="C (%)",
        yaxis=dict(range=[0, 105]),
        height=480,
    )
    return fig
