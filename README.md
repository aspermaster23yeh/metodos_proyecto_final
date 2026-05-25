# Proyecto Li-ion — Métodos Numéricos (ITT Tepic 5A)

Monitor de carga Li-ion alineado al reporte técnico + centro de actividades del equipo.

## Requisitos

- Python 3.11+
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (`adb` en PATH) para el Battery Lab
- Teléfono con depuración USB (o modo demo sin dispositivo)

## Instalación

```bash
cd battery_streamlit_monitor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run main.py
```

Navegación (asistente por pasos en español):

| Página | Archivo | Descripción |
|--------|---------|-------------|
| **Laboratorio** | `main.py` | Metodología, datos del reporte (12×5 min), sigmoide, Newton-Raphson |
| **Centro del proyecto** | `pages/1_Centro_Proyecto.py` | Resumen, actividades y Gantt (02 abr – 08 may 2026) |

## Project Hub

- Tareas editables persistidas en `data/project_tasks.json`
- 30 tareas iniciales (5 fases × 6) con fechas dentro del rango del proyecto
- Exportar CSV desde el sidebar
- Metodología CC-CV y cronograma de 8 actividades de referencia

## Battery Lab — muestreo

En el sidebar, el preset **Metodología (5 min)** fija el auto-refresh a 300 s, alineado con la bitácora cada 5 minutos del protocolo experimental.

## Estructura

```
main.py              # Battery Lab (home)
theme.py             # Estilos compartidos
tasks_store.py       # Modelo y persistencia de tareas
pages/
  2_Project_Hub.py   # Dashboard de proyecto
data/
  project_tasks.json # Fuente de verdad (generado al primer arranque)
```

## Próximos pasos (fuera del alcance actual)

- Comparativa de regresión lineal vs logarítmica en el Lab (hoy: spline + Newton)
