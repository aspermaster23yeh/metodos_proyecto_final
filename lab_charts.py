"""Gráficas Plotly del Laboratorio."""
# Docstring: define las gráficas interactivas (Plotly) usadas en main.py para visualizar la carga.

from __future__ import annotations
# Anotaciones modernas de tipo.

import numpy as np
# Para generar arrays densos de tiempos (np.linspace).
import pandas as pd
# Para manejar las muestras como DataFrame.
import plotly.graph_objects as go
# API "low-level" de Plotly para construir figuras personalizadas.

from battery_models import ModelComparison, logistic_c
# Importa la estructura de comparación y la función de la sigmoide.
from theme import ACCENT_CYAN, ACCENT_YELLOW, BG, TEXT_MUTED
# Colores del tema para mantener la identidad visual.


def fig_model_comparison(df: pd.DataFrame, cmp: ModelComparison) -> go.Figure:
    # Construye la gráfica que compara los 3 modelos (lineal, logístico, spline) contra las mediciones.
    fig = go.Figure()
    # Crea una figura vacía a la que se irán añadiendo trazas.
    fig.add_trace(
        # Traza 1: puntos medidos.
        go.Scatter(
            x=df["t_min"],
            # Eje X: tiempo en minutos.
            y=df["level"],
            # Eje Y: % de carga.
            mode="markers+lines",
            # Dibuja puntos y los une con líneas finas.
            name="Medido",
            # Nombre que aparece en la leyenda.
            line=dict(color=ACCENT_YELLOW, width=1),
            # Línea fina amarilla.
            marker=dict(size=8, color=ACCENT_YELLOW),
            # Marcadores amarillos más grandes.
        )
    )
    fig.add_trace(
        # Traza 2: modelo lineal (recta de regresión).
        go.Scatter(
            x=cmp.t_grid,
            # Grid denso de tiempos para una curva suave.
            y=cmp.y_linear,
            # Predicciones del modelo lineal.
            mode="lines",
            # Solo línea, sin puntos.
            name="Lineal",
            line=dict(color="#7CFF6B", width=2, dash="dash"),
            # Verde claro punteado (estilo "dash").
        )
    )
    fig.add_trace(
        # Traza 3: modelo logístico (sigmoide).
        go.Scatter(
            x=cmp.t_grid,
            y=cmp.y_logistic,
            mode="lines",
            name="Logístico C(t)",
            line=dict(color=ACCENT_CYAN, width=2),
            # Línea cian sólida (resalta como el modelo principal).
        )
    )
    fig.add_trace(
        # Traza 4: spline.
        go.Scatter(
            x=cmp.t_grid,
            y=cmp.y_spline,
            mode="lines",
            name="Spline",
            line=dict(color="#B388FF", width=2, dash="dot"),
            # Lila punteado (estilo "dot" para diferenciarlo de la recta).
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED, annotation_text="80%")
    # Línea horizontal de referencia en 80% (inicio aproximado de la fase CV).
    fig.add_hline(y=100, line_dash="dash", line_color=TEXT_MUTED, annotation_text="100%")
    # Línea horizontal de referencia en 100% (carga máxima).
    if cmp.t_cv_min is not None:
        # Solo dibuja la línea vertical si se detectó el cruce del 80%.
        fig.add_vline(
            x=cmp.t_cv_min,
            line_dash="dot",
            line_color="#FF6B6B",
            # Rojo punteado para destacar la transición CC→CV.
            annotation_text="Inicio CV (~80%)",
            annotation_position="top",
        )
    fig.update_layout(
        # Configuración estética general de la figura.
        template="plotly_dark",
        # Tema oscuro base.
        paper_bgcolor=BG,
        # Fondo del lienzo.
        plot_bgcolor=BG,
        # Fondo del área de gráfica.
        title=dict(text="Comparativa de modelos + fases CC-CV", font=dict(color=ACCENT_CYAN)),
        # Título cian.
        xaxis_title="t (min)",
        yaxis_title="C (%)",
        # Títulos de los ejes.
        yaxis=dict(range=[0, 105]),
        # Rango fijo del eje Y (0–105% para que entren las líneas de referencia).
        height=520,
        # Altura del gráfico en píxeles.
        legend=dict(orientation="h", y=1.08),
        # Leyenda horizontal encima de la gráfica.
    )
    return fig
    # Devuelve la figura lista para `st.plotly_chart`.


def fig_dual_devices(
    # Gráfica comparativa entre dos dispositivos (el principal y el alternativo del reporte).
    df_main: pd.DataFrame,
    # Datos del primer dispositivo.
    df_alt: pd.DataFrame,
    # Datos del segundo dispositivo.
    label_main: str,
    # Etiqueta visible del primer dispositivo.
    label_alt: str,
    # Etiqueta visible del segundo dispositivo.
) -> go.Figure:
    t_grid = np.linspace(0, 52, 200)
    # Grid de 200 puntos entre 0 y 52 min para dibujar la sigmoide de referencia.
    fig = go.Figure()
    fig.add_trace(
        # Mediciones del primer dispositivo (amarillo).
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
        # Sigmoide de referencia para el primer dispositivo (línea cian punteada).
        go.Scatter(
            x=t_grid,
            y=logistic_c(t_grid),
            mode="lines",
            name=f"{label_main} (sigmoide ref.)",
            line=dict(color=ACCENT_CYAN, width=1, dash="dash"),
        )
    )
    fig.add_trace(
        # Mediciones del segundo dispositivo (verde claro).
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
        # Sigmoide de referencia para el segundo dispositivo (línea lila, oculta de la leyenda).
        go.Scatter(
            x=t_grid,
            y=logistic_c(t_grid),
            mode="lines",
            name=f"{label_alt} (sigmoide ref.)",
            line=dict(color="#B388FF", width=1, dash="dot"),
            showlegend=False,
            # No se muestra en la leyenda para no duplicar visualmente con la del primer dispositivo.
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED)
    # Línea horizontal de referencia en 80%.
    fig.update_layout(
        # Estética general (igual al patrón del gráfico anterior).
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


def fig_session_vs_reference(
    df_session: pd.DataFrame,
    df_ref: pd.DataFrame,
    label_session: str,
    label_ref: str,
) -> go.Figure:
    """Comparación visual sesión del historial vs proyecto principal."""
    t_max = max(float(df_session["t_min"].max()), float(df_ref["t_min"].max()), 52)
    t_grid = np.linspace(0, t_max, 200)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_ref["t_min"],
            y=df_ref["level"],
            mode="markers+lines",
            name=f"{label_ref} (medido)",
            line=dict(color=ACCENT_CYAN, width=2),
            marker=dict(size=8, color=ACCENT_CYAN),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_session["t_min"],
            y=df_session["level"],
            mode="markers+lines",
            name=f"{label_session} (medido)",
            line=dict(color=ACCENT_YELLOW, width=2),
            marker=dict(size=8, color=ACCENT_YELLOW),
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED, annotation_text="80% CC→CV")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        title=dict(text="Sesión vs proyecto principal", font=dict(color=ACCENT_CYAN)),
        xaxis_title="t (min)",
        yaxis_title="C (%)",
        yaxis=dict(range=[0, 105]),
        height=520,
        legend=dict(orientation="h", y=1.08),
    )
    return fig


def fig_charge_simple(df: pd.DataFrame, t_cv_min: float | None = None) -> go.Figure:
    """Gráfica de recolección con marca CC-CV opcional."""
    # Docstring: gráfica simple (medidos + sigmoide de referencia) usada en el paso "Recolección".
    t_m = np.linspace(0, max(float(df["t_min"].max()), 1), 200)
    # Grid denso desde 0 hasta el máximo observado (al menos 1 min para evitar grid degenerado).
    fig = go.Figure()
    fig.add_trace(
        # Mediciones del experimento (amarillo).
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
        # Sigmoide de referencia (cian) — modelo del reporte.
        go.Scatter(x=t_m, y=logistic_c(t_m), mode="lines", name="Referencia sigmoide", line=dict(color=ACCENT_CYAN))
    )
    fig.add_hline(y=80, line_dash="dash", line_color=TEXT_MUTED, annotation_text="80%")
    # Línea de referencia en 80%.
    if t_cv_min is not None:
        # Si se pasó el tiempo de inicio de CV, lo marca con una línea vertical roja.
        fig.add_vline(x=t_cv_min, line_dash="dot", line_color="#FF6B6B", annotation_text="Inicio CV (~80%)")
    fig.update_layout(
        # Configuración estética.
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
