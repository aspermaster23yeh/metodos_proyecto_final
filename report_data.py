"""Datos y constantes del reporte técnico (ITT Tepic, Grupo 5A)."""

from __future__ import annotations

import pandas as pd

# Equipo (reporte)
TEAM = [
    ("Adán", "Análisis", "Recolección y modelación"),
    ("Ángel", "Análisis", "Procesamiento de datos"),
    ("Checho", "Diseño UX", "Identidad visual"),
    ("Arath", "Diseño UX", "Interfaz"),
    ("Gustavo", "Diseño UX", "Prototipo"),
    ("Sergio", "Análisis", "Apoyo en experimentación"),
]

INSTITUTION = "Instituto Tecnológico de Tepic — Métodos Numéricos, Grupo 5A"
DELIVERY_DATE = "Miércoles 6 de mayo de 2026"

# Muestras experimentales (dispositivo principal), cada 5 min
SAMPLES_MAIN = [
    (0, 0),
    (5, 14),
    (10, 27),
    (15, 38),
    (20, 46),
    (25, 56),
    (30, 62),
    (35, 72),
    (40, 83),
    (45, 90),
    (50, 99),
    (52, 100),
]

# Segundo dispositivo (comparativa en reporte)
SAMPLES_ALT = [
    (0, 0),
    (5, 11),
    (10, 22),
    (15, 33),
    (20, 43),
    (25, 53),
    (30, 63),
    (35, 72),
    (40, 74),
    (45, 84),
    (50, 88),
    (52, 90),
]

# Modelo logístico ajustado (reporte / prototipo HTML)
L_MAX = 100.0
K_RATE = 0.11850
T0_INFL = 23.85

# Semilla logit del reporte
K_SEED = 0.1139
T0_SEED = 21.71

# Resultados físicos y Newton escalar
CHARGE_TIME_REAL_MIN = 52.0
ENERGY_WH = 22.2
TIME_IDEAL_MIN = 14.8
EFFICIENCY_PCT = 28.5  # útil ≈ 100 - 71.5 pérdidas
NEWTON_80_MIN = 35.55
NEWTON_80_ITER = 5

NEWTON_BATCH_TARGETS = [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 99]

DEVICE_MAIN_LABEL = "Dispositivo principal (reporte)"
DEVICE_ALT_LABEL = "Dispositivo alternativo (reporte)"

METHODOLOGY_STEPS = [
    ("1", "Descarga", "Llevar el dispositivo por debajo del 5% con uso controlado."),
    ("2", "Bitácora", "Registrar porcentaje cada 5 minutos hasta el 100%."),
    ("3", "Gráfica", "Construir dispersión tiempo vs carga (%)"),
    ("4", "Regresión", "Ajustar modelos lineal, logístico y exponencial; comparar R²."),
    ("5", "Newton-Raphson", "Resolver C(t)=objetivo para estimar tiempos (p. ej. 80%)."),
    ("6", "Evaluación", "Analizar error, eficiencia energética y fases CC-CV."),
]

WIZARD_LAB_STEPS = [
    ("inicio", "Inicio", "Contexto del proyecto y objetivos."),
    ("metodo", "Metodología", "Protocolo CC-CV y pasos del experimento."),
    ("datos", "Recolección", "Muestras cada 5 min (reporte o ADB en vivo)."),
    ("modelo", "Modelo", "Comparativa lineal/logística/spline, CC-CV y dos dispositivos."),
    ("newton", "Newton-Raphson", "Tiempo para alcanzar un % de carga."),
    ("stats", "Resultados", "Estadísticas del reporte y conclusiones."),
]

WIZARD_HUB_STEPS = [
    ("resumen", "Resumen", "Avance del equipo y estadísticas globales."),
    ("actividades", "Actividades", "Tareas por fase con entregables."),
    ("gantt", "Cronograma", "Línea de tiempo 2 abr – 8 may 2026."),
]


def samples_dataframe(pairs: list[tuple[int, int]] | None = None) -> pd.DataFrame:
    pairs = pairs or SAMPLES_MAIN
    return pd.DataFrame(
        {"t_min": [p[0] for p in pairs], "level": [float(p[1]) for p in pairs]}
    ).assign(t_h=lambda d: d["t_min"] / 60.0)
