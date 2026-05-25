"""Datos y constantes del reporte técnico (ITT Tepic, Grupo 5A)."""
# Docstring del módulo: centraliza todos los datos fijos del reporte (mediciones, parámetros, equipo).

from __future__ import annotations
# Habilita anotaciones modernas de tipo.

import pandas as pd
# Importa pandas para construir DataFrames a partir de las muestras.

# Equipo (reporte)
TEAM = [
    # Lista de tuplas con los integrantes del proyecto: (nombre, área, aporte principal).
    ("Adán", "Análisis", "Recolección y modelación"),
    ("Ángel", "Análisis", "Procesamiento de datos"),
    ("Checho", "Diseño UX", "Identidad visual"),
    ("Arath", "Diseño UX", "Interfaz"),
    ("Gustavo", "Diseño UX", "Prototipo"),
    ("Sergio", "Análisis", "Apoyo en experimentación"),
]

INSTITUTION = "Instituto Tecnológico de Tepic — Métodos Numéricos, Grupo 5A"
# Nombre de la institución y materia (se muestra en encabezados de las páginas).
DELIVERY_DATE = "Miércoles 6 de mayo de 2026"
# Fecha de entrega oficial del reporte.

# Muestras experimentales (dispositivo principal), cada 5 min
SAMPLES_MAIN = [
    # Lista de tuplas (tiempo_en_minutos, porcentaje_de_carga) — datos del primer dispositivo.
    (0, 0),     # Inicio del experimento: 0 min, 0% de carga.
    (5, 14),    # A los 5 min, el dispositivo está al 14%.
    (10, 27),
    (15, 38),
    (20, 46),
    (25, 56),
    (30, 62),
    (35, 72),
    (40, 83),
    (45, 90),
    (50, 99),
    (52, 100),  # A los 52 min se alcanza la carga completa.
]

# Segundo dispositivo (comparativa en reporte)
SAMPLES_ALT = [
    # Muestras del dispositivo alternativo (mismo protocolo, cargador o teléfono distinto).
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
    (52, 90),   # Este dispositivo no llegó a 100% en el mismo tiempo (carga más lenta).
]

# Modelo logístico ajustado (reporte / prototipo HTML)
L_MAX = 100.0
# Asíntota superior del modelo sigmoide: 100% es la carga máxima.
K_RATE = 0.11850
# Parámetro k que controla la pendiente/velocidad de la curva logística.
T0_INFL = 23.85
# Punto de inflexión t₀ en minutos (donde la curva sigmoide está al 50%).

# Semilla logit del reporte
K_SEED = 0.1139
# Valor inicial de k usado como "semilla" en los algoritmos de ajuste (curve_fit, Newton).
T0_SEED = 21.71
# Valor inicial de t₀ usado como semilla del ajuste.

# Resultados físicos y Newton escalar
CHARGE_TIME_REAL_MIN = 52.0
# Tiempo real medido para alcanzar el 100% (en minutos).
ENERGY_WH = 22.2
# Energía total medida durante la carga, en Watt-hora.
TIME_IDEAL_MIN = 14.8
# Tiempo ideal teórico de carga (sin pérdidas) — comparativa contra el tiempo real.
EFFICIENCY_PCT = 28.5  # útil ≈ 100 - 71.5 pérdidas
# Eficiencia útil de la carga: solo ~28.5% de la energía llega como carga útil (el resto se disipa).
NEWTON_80_MIN = 35.55
# Tiempo en minutos al que se alcanza 80% según Newton-Raphson (resultado del reporte).
NEWTON_80_ITER = 5
# Número de iteraciones que tomó Newton-Raphson para converger al 80%.

NEWTON_BATCH_TARGETS = [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 99]
# Lista de porcentajes objetivo para correr Newton-Raphson en lote y mostrar una tabla completa.

DEVICE_MAIN_LABEL = "Dispositivo principal (reporte)"
# Etiqueta visible para el primer dispositivo en gráficas y tablas.
DEVICE_ALT_LABEL = "Dispositivo alternativo (reporte)"
# Etiqueta para el segundo dispositivo (comparativa).

METHODOLOGY_STEPS = [
    # Lista de los 6 pasos de la metodología experimental — (número, nombre, descripción).
    ("1", "Descarga", "Llevar el dispositivo por debajo del 5% con uso controlado."),
    ("2", "Bitácora", "Registrar porcentaje cada 5 minutos hasta el 100%."),
    ("3", "Gráfica", "Construir dispersión tiempo vs carga (%)"),
    ("4", "Regresión", "Ajustar modelos lineal, logístico y exponencial; comparar R²."),
    ("5", "Newton-Raphson", "Resolver C(t)=objetivo para estimar tiempos (p. ej. 80%)."),
    ("6", "Evaluación", "Analizar error, eficiencia energética y fases CC-CV."),
]

WIZARD_LAB_STEPS = [
    # Pasos del wizard del Laboratorio (main.py) — cada tupla es (id, etiqueta, descripción).
    ("inicio", "Inicio", "Contexto del proyecto y objetivos."),
    ("metodo", "Metodología", "Protocolo CC-CV y pasos del experimento."),
    ("datos", "Recolección", "Muestras cada 5 min (reporte o ADB en vivo)."),
    ("modelo", "Modelo", "Comparativa lineal/logística/spline, CC-CV y dos dispositivos."),
    ("newton", "Newton-Raphson", "Tiempo para alcanzar un % de carga."),
    ("stats", "Resultados", "Estadísticas del reporte y conclusiones."),
]

WIZARD_HUB_STEPS = [
    # Pasos del wizard del Centro del Proyecto (1_Centro_Proyecto.py).
    ("resumen", "Resumen", "Avance del equipo y estadísticas globales."),
    ("actividades", "Actividades", "Tareas por fase con entregables."),
    ("gantt", "Cronograma", "Línea de tiempo 2 abr – 8 may 2026."),
]


def samples_dataframe(pairs: list[tuple[int, int]] | None = None) -> pd.DataFrame:
    # Convierte la lista de pares (tiempo, porcentaje) en un DataFrame de pandas.
    pairs = pairs or SAMPLES_MAIN
    # Si no se pasa lista, usa por defecto las muestras del dispositivo principal.
    return pd.DataFrame(
        # Crea un DataFrame con dos columnas iniciales: t_min y level.
        {"t_min": [p[0] for p in pairs], "level": [float(p[1]) for p in pairs]}
        # `t_min` es el tiempo en minutos; `level` es el porcentaje convertido a float.
    ).assign(t_h=lambda d: d["t_min"] / 60.0)
    # Añade una tercera columna `t_h` (tiempo en horas) calculada a partir de t_min.
