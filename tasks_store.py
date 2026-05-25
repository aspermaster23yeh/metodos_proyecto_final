"""Task persistence and seed data for Li-ion project hub."""
# Docstring: gestiona las tareas (actividades) del proyecto: definición, fechas, persistencia JSON.

from __future__ import annotations
# Anotaciones de tipo modernas.

import json
# Para guardar/leer las tareas en formato JSON.
import uuid
# Para generar IDs únicos cuando se crean tareas nuevas.
from dataclasses import asdict, dataclass
# `dataclass` para definir la clase Task; `asdict` para convertir instancias a diccionarios.
from datetime import date, datetime, timedelta
# Manejo de fechas (date), instantes (datetime) y diferencias (timedelta).
from pathlib import Path
# Rutas multiplataforma.
from typing import Any
# Tipos genéricos.

PROJECT_START = date(2026, 4, 2)
# Fecha de inicio del proyecto (2 de abril de 2026).
PROJECT_END = date(2026, 5, 8)
# Fecha de fin del proyecto (8 de mayo de 2026).

PHASES = [
    # Lista ordenada de las 5 fases en que se divide el proyecto.
    "Preparación",
    "Recolección",
    "Modelación",
    "Desarrollo UX",
    "Cierre",
]

STATUSES = ("todo", "in_progress", "review", "done")
# Estados posibles de una tarea (orden: pendiente → en progreso → revisión → hecho).
STATUS_LABELS = {
    # Etiquetas legibles en español para mostrar cada estado en la UI.
    "todo": "Por hacer",
    "in_progress": "En progreso",
    "review": "Revisión",
    "done": "Hecho",
}
PROFILES = ("Análisis", "Diseño UX", "General")
# Perfiles posibles del responsable (área de trabajo).
ASSIGNEES = ("Adán", "Ángel", "Checho", "Arath", "Gustavo", "Sergio")
# Lista de integrantes del equipo a quienes se pueden asignar tareas.

PHASE_COLORS = {
    # Colores asignados a cada fase para el cronograma Gantt (visualmente distinguibles).
    "Preparación": "#E8B923",
    # Amarillo oro.
    "Recolección": "#5FD38D",
    # Verde claro.
    "Modelación": "#00F5FF",
    # Cian neón.
    "Desarrollo UX": "#B388FF",
    # Lila.
    "Cierre": "#9BA4B5",
    # Gris azulado.
}

DATA_DIR = Path(__file__).resolve().parent / "data"
# Carpeta `data/` junto a este archivo.
TASKS_PATH = DATA_DIR / "project_tasks.json"
# Archivo JSON donde se guardan las tareas.

PHASE_RANGES: dict[str, tuple[date, date]] = {
    # Rango de fechas (inicio, fin) que ocupa cada fase del proyecto.
    "Preparación": (date(2026, 4, 2), date(2026, 4, 8)),
    "Recolección": (date(2026, 4, 9), date(2026, 4, 18)),
    "Modelación": (date(2026, 4, 19), date(2026, 4, 28)),
    "Desarrollo UX": (date(2026, 4, 22), date(2026, 5, 4)),
    # Nota: Desarrollo UX se traslapa con Modelación (trabajo en paralelo).
    "Cierre": (date(2026, 5, 5), date(2026, 5, 8)),
}

CRONOGRAMA_8 = [
    # 8 hitos principales del cronograma resumido (fase, actividad, responsables, entregable).
    ("Preparación", "Definir dispositivo y protocolo de control", "Adán & Ángel", "Protocolo de control"),
    ("Recolección", "Registro cada 5 min (<5% → 100%)", "Adán & Ángel", "Bitácora CSV/Excel"),
    ("Procesamiento", "Limpieza y gráfica de dispersión", "Adán & Ángel", "Gráfico (x,y)"),
    ("Diseño Visual", "Identidad visual y layout del reporte", "Checho, Arath & Gustavo", "Plantilla UX"),
    ("Modelación", "Regresiones lineal vs logarítmica + R²", "Adán & Ángel", "Ecuación predictiva"),
    ("Infografía", "Diagrama CC-CV", "Checho, Arath & Gustavo", "Diagrama de flujo"),
    ("Análisis Final", "Comparativa de error y conclusiones", "Todo el equipo", "Reporte de resultados"),
    ("Prototipado", "Mockup UI predictivo", "Checho, Arath & Gustavo", "Prototipo Figma"),
]


@dataclass
class Task:
    # Clase de datos (dataclass) que representa una tarea del proyecto.
    id: str
    # Identificador único.
    title: str
    # Título corto de la actividad.
    phase: str
    # Fase a la que pertenece (una de PHASES).
    assignees: list[str]
    # Lista de integrantes asignados.
    profile: str
    # Perfil predominante de la tarea (Análisis / Diseño UX / General).
    status: str
    # Estado actual (todo / in_progress / review / done).
    start: str
    # Fecha de inicio en formato ISO ("YYYY-MM-DD").
    end: str
    # Fecha de fin en formato ISO.
    deliverable: str = ""
    # Entregable concreto (opcional).
    description: str = ""
    # Descripción larga (opcional).
    notes: str = ""
    # Notas adicionales (opcional).

    def start_date(self) -> date:
        # Helper: convierte la cadena `start` a un objeto `date`.
        return date.fromisoformat(self.start)

    def end_date(self) -> date:
        # Helper: convierte la cadena `end` a un objeto `date`.
        return date.fromisoformat(self.end)


def _parse_assignees(raw: str) -> list[str]:
    # Convierte una cadena tipo "Adán & Ángel" o "Todo el equipo" en una lista de nombres válidos.
    if "Todo el equipo" in raw:
        return list(ASSIGNEES)
        # Caso especial: asigna a todos los integrantes.
    parts = raw.replace("&", ",").split(",")
    # Normaliza separadores: "&" → "," y luego divide por coma.
    names: list[str] = []
    for p in parts:
        p = p.strip()
        # Quita espacios sobrantes alrededor de cada nombre.
        if p in ASSIGNEES and p not in names:
            # Solo acepta nombres válidos y sin duplicados.
            names.append(p)
    return names or list(ASSIGNEES)
    # Si no detectó ningún nombre válido, devuelve el equipo completo como fallback.


def _profile_from_assignees(raw: str, explicit: str | None = None) -> str:
    # Determina el perfil predominante de la tarea a partir de los responsables.
    if explicit:
        return explicit
        # Si se pasó perfil explícito, lo respeta.
    if "Todo el equipo" in raw:
        return "General"
        # "Todo el equipo" → perfil General.
    if any(n in raw for n in ("Checho", "Arath", "Gustavo")):
        # Si hay al menos un integrante de UX...
        if any(n in raw for n in ("Adán", "Ángel")):
            return "General"
            # ...y también alguien de análisis → tarea mixta (General).
        return "Diseño UX"
        # ...si solo hay UX → perfil Diseño UX.
    return "Análisis"
    # Caso restante: solo análisis.


def _stagger_dates(phase: str, index: int, count: int) -> tuple[str, str]:
    # Reparte fechas dentro del rango de una fase, dividiéndolo en `count` "slots" para `count` tareas.
    p_start, p_end = PHASE_RANGES[phase]
    # Lee inicio y fin de la fase.
    total_days = (p_end - p_start).days + 1
    # Días totales que dura la fase (inclusive).
    if count <= 1:
        return p_start.isoformat(), p_end.isoformat()
        # Si solo hay una tarea, ocupa todo el rango.
    slot = max(1, total_days // count)
    # Tamaño aproximado de cada slot (mínimo 1 día).
    start = p_start + timedelta(days=min(index * slot, total_days - 1))
    # Inicio = p_start + offset según el índice, sin pasarse del último día.
    end = min(p_start + timedelta(days=min((index + 1) * slot, total_days) - 1), p_end)
    # Fin = inicio + slot - 1, recortado al final de la fase.
    if end < start:
        end = start
        # Salvaguarda: si el cálculo da fin antes que inicio, los iguala.
    return start.isoformat(), end.isoformat()
    # Devuelve las fechas como cadenas ISO.


def apply_progressive_completed(tasks: list[Task]) -> list[Task]:
    """Marca todas las tareas como hechas, repartidas día a día entre inicio y fin del proyecto."""
    # Docstring: simula que el proyecto se completó al 100%, repartiendo cada tarea en un día distinto.
    span_days = (PROJECT_END - PROJECT_START).days
    # Duración total del proyecto en días.
    n = len(tasks)
    # Número total de tareas.
    out: list[Task] = []
    # Lista resultado.
    for i, t in enumerate(tasks):
        # Itera con índice y tarea.
        offset = round(i * span_days / max(n - 1, 1))
        # Reparte uniformemente el día de finalización (de 0 a span_days).
        day = PROJECT_START + timedelta(days=offset)
        # Día concreto en el que se da por completada esta tarea.
        t.status = "done"
        # Marca como hecha.
        t.start = day.isoformat()
        # Inicio = ese día.
        t.end = day.isoformat()
        # Fin = mismo día (tarea puntual de un día).
        out.append(validate_task(t))
        # Valida y añade la tarea actualizada.
    return out


TASK_DESCRIPTIONS: dict[str, str] = {
    # Diccionario título → descripción detallada. Sirve como "ayuda" al ver cada tarea.
    "Definir dispositivo de prueba y documentar capacidad (mAh)": "Documentar mAh y condiciones del smartphone usado en el experimento.",
    "Establecer protocolo de control (modo avión, brillo 0%)": "Controlar variables: modo avión, brillo mínimo, sin uso durante la carga.",
    "Crear moodboard de inspiración visual": "Referencias visuales para el reporte y dashboard.",
    "Diseñar bitácora digital de captura (Google Sheets)": "Plantilla para registro cada 5 minutos.",
    "Definir paleta de colores y tipografía": "Identidad del reporte (crema, acento rojo, mono técnico).",
    "Investigar curva teórica de carga del fabricante": "Benchmark del fabricante vs datos medidos.",
    "Descarga controlada del equipo hasta 1–5%": "Paso 1 de la metodología: descarga hasta <5%.",
    "Registro sistemático cada 5 min (cronómetro)": "12 muestras POCO X 7 Pro (0–52 min) — bitácora principal del reporte.",
    "Documentar cambios térmicos durante la carga": "Observar efecto Joule y calentamiento.",
    "Bocetos (wireframes) para presentación de resultados": "Estructura de diapositivas y dashboard.",
    "Iconos personalizados (batería, rayo, calor, reloj)": "Iconografía del equipo UX.",
    "Validar transferencia digital sin pérdida de datos": "Verificar CSV/Excel vs mediciones.",
    "Gráfica de dispersión y detección de anomalías": "Dispersión t vs C(%) del experimento.",
    "Regresión lineal y límite de precisión": "Ajuste lineal; comparar limitaciones vs sigmoide.",
    "Regresión logarítmica/polinómica fase CV": "Modelo logístico C(t)=L/(1+e^{-k(t-t0)}).",
    "Gráficos estéticos de fórmulas matemáticas": "Visualización publicable de ecuaciones.",
    "Coeficiente R² para cada modelo": "Evaluar bondad de ajuste (objetivo R²→1).",
    "Infografía fases CC vs CV": "Explicar 0–80% CC y 80–100% CV.",
    "Dashboard visual de hallazgos": "Esta aplicación Streamlit + gráficas Plotly.",
    "Comparativa: modelo matemático vs realidad": "Curva sigmoide vs puntos medidos.",
    "Sustento teórico (efecto Joule, BMS)": "Capítulo teórico del reporte.",
    "Mockup de app con modelo predictivo": "Prototipo Figma / HTML Newton-Raphson.",
    "Pruebas de usabilidad en diapositivas": "Validar lectura de gráficas y métricas.",
    "Jerarquía visual de datos clave": "Resaltar R², tiempo 80%, eficiencia.",
    "Análisis de error y desviaciones del modelo": "Incluir fallo NaN en ajuste multivariable.",
    "Conclusiones técnicas de la experimentación": "Sigmoide adecuada; Newton escalar sí converge.",
    "Ensamblar reporte/presentación final": "Entrega 6 may 2026 — documento Word/PDF.",
    "Revisión ortográfica y consistencia visual": "Revisión final UX.",
    "Pitch verbal del modelo matemático": "Exposición del método y resultados.",
    "Exportar PDF y prototipo Figma alta resolución": "Entregables finales de diseño.",
}


def build_seed_tasks() -> list[Task]:
    """30 tasks from project breakdown (5 phases × 6)."""
    # Docstring: construye las 30 tareas iniciales (5 fases × 6 actividades).
    rows: list[tuple[str, str, str, str | None]] = [
        # Cada tupla: (fase, título, responsables, perfil). Lista completa de actividades del reporte.
        # Preparación
        ("Preparación", "Definir dispositivo de prueba y documentar capacidad (mAh)", "Adán & Ángel", "Análisis"),
        ("Preparación", "Establecer protocolo de control (modo avión, brillo 0%)", "Adán & Ángel", "Análisis"),
        ("Preparación", "Crear moodboard de inspiración visual", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Preparación", "Diseñar bitácora digital de captura (Google Sheets)", "Adán & Ángel", "Análisis"),
        ("Preparación", "Definir paleta de colores y tipografía", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Preparación", "Investigar curva teórica de carga del fabricante", "Adán & Ángel", "Análisis"),
        # Recolección
        ("Recolección", "Descarga controlada del equipo hasta 1–5%", "Adán & Ángel", "Análisis"),
        ("Recolección", "Registro sistemático cada 5 min (cronómetro)", "Adán & Ángel", "Análisis"),
        ("Recolección", "Documentar cambios térmicos durante la carga", "Adán & Ángel", "Análisis"),
        ("Recolección", "Bocetos (wireframes) para presentación de resultados", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Recolección", "Iconos personalizados (batería, rayo, calor, reloj)", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Recolección", "Validar transferencia digital sin pérdida de datos", "Adán & Ángel", "Análisis"),
        # Modelación
        ("Modelación", "Gráfica de dispersión y detección de anomalías", "Adán & Ángel", "Análisis"),
        ("Modelación", "Regresión lineal y límite de precisión", "Adán & Ángel", "Análisis"),
        ("Modelación", "Regresión logarítmica/polinómica fase CV", "Adán & Ángel", "Análisis"),
        ("Modelación", "Gráficos estéticos de fórmulas matemáticas", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Modelación", "Coeficiente R² para cada modelo", "Adán & Ángel", "Análisis"),
        ("Modelación", "Infografía fases CC vs CV", "Checho, Arath & Gustavo", "Diseño UX"),
        # Desarrollo UX
        ("Desarrollo UX", "Dashboard visual de hallazgos", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Desarrollo UX", "Comparativa: modelo matemático vs realidad", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Desarrollo UX", "Sustento teórico (efecto Joule, BMS)", "Adán & Ángel", "Análisis"),
        ("Desarrollo UX", "Mockup de app con modelo predictivo", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Desarrollo UX", "Pruebas de usabilidad en diapositivas", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Desarrollo UX", "Jerarquía visual de datos clave", "Checho, Arath & Gustavo", "Diseño UX"),
        # Cierre
        ("Cierre", "Análisis de error y desviaciones del modelo", "Adán & Ángel", "Análisis"),
        ("Cierre", "Conclusiones técnicas de la experimentación", "Adán & Ángel", "Análisis"),
        ("Cierre", "Ensamblar reporte/presentación final", "Todo el equipo", "General"),
        ("Cierre", "Revisión ortográfica y consistencia visual", "Checho, Arath & Gustavo", "Diseño UX"),
        ("Cierre", "Pitch verbal del modelo matemático", "Todo el equipo", "General"),
        ("Cierre", "Exportar PDF y prototipo Figma alta resolución", "Checho, Arath & Gustavo", "Diseño UX"),
    ]

    deliverables_by_phase: dict[str, list[str]] = {
        # Entregables específicos por fase (alineados al orden de aparición en `rows`).
        "Preparación": ["Protocolo de control", "", "", "Bitácora digital", "Guía de estilo", "Benchmark fabricante"],
        "Recolección": ["Ciclo descarga", "Bitácora 5 min", "Log térmico", "Wireframes", "Set de iconos", "CSV validado"],
        "Modelación": ["Scatter limpio", "Modelo lineal", "Modelo log/polinómico", "Gráficos publicación", "Tabla R²", "Infografía CC-CV"],
        "Desarrollo UX": ["Dashboard", "Comparativa visual", "Capítulo teórico", "Mockup Figma", "Informe usabilidad", "Checklist jerarquía"],
        "Cierre": ["Informe de error", "Conclusiones", "Reporte final", "Documento revisado", "Guión pitch", "Entregables export"],
    }

    phase_counts: dict[str, int] = {p: 0 for p in PHASES}
    # Contador por fase para llevar el índice de cada tarea dentro de su fase.
    tasks: list[Task] = []
    # Lista resultado.
    for phase, title, assignees_raw, profile in rows:
        # Itera sobre las 30 filas para construir cada Task.
        idx = phase_counts[phase]
        # Índice de la tarea dentro de su fase (0..5).
        phase_counts[phase] += 1
        # Incrementa el contador para la siguiente tarea de la misma fase.
        start, end = _stagger_dates(phase, idx, 6)
        # Asigna fechas escalonadas dentro del rango de la fase.
        dels = deliverables_by_phase.get(phase, [])
        # Entregables de la fase.
        deliverable = dels[idx] if idx < len(dels) else ""
        # Entregable concreto para esta tarea (vacío si no hay).
        tasks.append(
            # Crea y agrega el objeto Task.
            Task(
                id=f"task-{phase.lower().replace(' ', '-')}-{idx + 1}",
                # ID derivado de la fase y el índice (legible y único).
                title=title,
                phase=phase,
                assignees=_parse_assignees(assignees_raw),
                # Convierte la cadena de responsables en lista.
                profile=profile or _profile_from_assignees(assignees_raw),
                # Usa el perfil explícito o lo infiere desde los responsables.
                status="todo",
                # Estado inicial: por hacer (luego se sobreescribe a "done").
                start=start,
                end=end,
                deliverable=deliverable,
                description=TASK_DESCRIPTIONS.get(title, ""),
                # Descripción extra si está registrada.
                notes="Completada según cronograma del reporte.",
                # Nota por defecto.
            )
        )
    return apply_progressive_completed(tasks)
    # Marca todas como completadas (el proyecto ya se entregó al cargar la app).


def clamp_date(d: date) -> date:
    # Recorta una fecha para que quede dentro del rango del proyecto.
    if d < PROJECT_START:
        return PROJECT_START
        # Si está antes del inicio, devuelve el inicio.
    if d > PROJECT_END:
        return PROJECT_END
        # Si está después del fin, devuelve el fin.
    return d
    # En otro caso, devuelve la fecha original.


def validate_task(task: Task) -> Task:
    # Valida los campos de una tarea: estados, fases, perfiles y fechas; corrige si son inválidos.
    if task.status not in STATUSES:
        task.status = "todo"
        # Si el estado no es válido, lo resetea a "por hacer".
    if task.phase not in PHASES:
        task.phase = PHASES[0]
        # Si la fase no es válida, usa la primera (Preparación).
    if task.profile not in PROFILES:
        task.profile = "General"
        # Perfil inválido → General.
    try:
        s = clamp_date(date.fromisoformat(task.start))
        # Convierte y recorta la fecha de inicio.
        e = clamp_date(date.fromisoformat(task.end))
        # Convierte y recorta la fecha de fin.
    except ValueError:
        # Si las fechas no son ISO válidas...
        s, e = PROJECT_START, PROJECT_END
        # ...usa el rango completo del proyecto como fallback.
    if e < s:
        e = s
        # Asegura que la fecha de fin no sea anterior a la de inicio.
    task.start = s.isoformat()
    # Guarda la fecha como cadena ISO.
    task.end = e.isoformat()
    return task


def task_from_dict(d: dict[str, Any]) -> Task:
    # Construye una instancia Task a partir de un diccionario (típicamente leído del JSON).
    return validate_task(
        Task(
            id=str(d.get("id", uuid.uuid4().hex[:8])),
            # ID del JSON, o uno nuevo aleatorio de 8 chars si falta.
            title=str(d.get("title", "Sin título")),
            phase=str(d.get("phase", PHASES[0])),
            assignees=list(d.get("assignees", [])),
            profile=str(d.get("profile", "General")),
            status=str(d.get("status", "todo")),
            start=str(d.get("start", PROJECT_START.isoformat())),
            end=str(d.get("end", PROJECT_END.isoformat())),
            deliverable=str(d.get("deliverable", "")),
            description=str(d.get("description", "")),
            notes=str(d.get("notes", "")),
        )
    )
    # `validate_task` filtra estados/fases inválidos y recorta fechas.


def tasks_to_dicts(tasks: list[Task]) -> list[dict[str, Any]]:
    # Convierte una lista de objetos Task en una lista de diccionarios, validando antes.
    return [asdict(validate_task(t)) for t in tasks]
    # `asdict` de dataclasses serializa los campos a un dict.


def save_tasks(tasks: list[Task]) -> None:
    # Guarda las tareas en el JSON con metadatos del proyecto.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Garantiza la carpeta `data/`.
    payload = {
        "project_start": PROJECT_START.isoformat(),
        "project_end": PROJECT_END.isoformat(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        # Fecha de la última actualización.
        "tasks": tasks_to_dicts(tasks),
        # Lista serializada de tareas.
    }
    TASKS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # Escribe el JSON formateado, manteniendo acentos.


def load_tasks() -> list[Task]:
    # Carga las tareas desde el JSON; si no existe, crea las iniciales y las guarda.
    if not TASKS_PATH.exists():
        tasks = build_seed_tasks()
        # Primera ejecución: genera el dataset semilla.
        save_tasks(tasks)
        # Y lo persiste a disco.
        return tasks
    raw = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    # Lee el JSON existente.
    items = raw.get("tasks", raw) if isinstance(raw, dict) else raw
    # Acepta dos formatos: dict con clave "tasks" o lista directa.
    return [task_from_dict(item) for item in items]
    # Convierte cada item a objeto Task validado.


def new_task_id() -> str:
    # Genera un ID único para una tarea nueva (8 caracteres aleatorios).
    return f"task-{uuid.uuid4().hex[:8]}"


def redistribute_phase_dates(tasks: list[Task]) -> list[Task]:
    """Re-assign dates within each phase range (keeps titles/status)."""
    # Docstring: reparte de nuevo las fechas dentro de cada fase (útil si se agregan/eliminan tareas).
    by_phase: dict[str, list[Task]] = {p: [] for p in PHASES}
    # Inicializa un dict con listas vacías por cada fase.
    for t in tasks:
        by_phase.setdefault(t.phase, []).append(t)
        # Agrupa las tareas por su fase.
    out: list[Task] = []
    # Lista resultado.
    for phase in PHASES:
        # Recorre las fases en su orden oficial.
        phase_tasks = by_phase.get(phase, [])
        # Tareas de esta fase.
        for i, t in enumerate(phase_tasks):
            # Itera con índice para repartir las fechas.
            start, end = _stagger_dates(phase, i, len(phase_tasks) or 1)
            # Calcula nuevas fechas escalonadas dentro de la fase.
            t.start, t.end = start, end
            # Aplica las fechas a la tarea.
            out.append(validate_task(t))
            # Agrega la tarea validada.
    # preserve tasks in unknown phases
    known_ids = {t.id for t in out}
    # IDs ya procesados.
    for t in tasks:
        if t.id not in known_ids:
            out.append(validate_task(t))
            # Conserva tareas cuyas fases no estén en PHASES (sin tocar sus fechas).
    return out


def tasks_to_dataframe(tasks: list[Task]):
    # Convierte una lista de Task en un DataFrame de pandas para mostrar en tablas o exportar a CSV.
    import pandas as pd
    # Import local (solo se usa aquí, no encarece el módulo al importarlo).

    rows = []
    # Filas que se irán acumulando.
    for t in tasks:
        rows.append(
            # Construye un diccionario por tarea con las columnas que verá el usuario.
            {
                "id": t.id,
                "title": t.title,
                "phase": t.phase,
                "assignees": ", ".join(t.assignees),
                # Junta los nombres separados por coma para visualización.
                "profile": t.profile,
                "status": STATUS_LABELS.get(t.status, t.status),
                # Estado traducido al español.
                "start": t.start,
                "end": t.end,
                "deliverable": t.deliverable,
                "description": t.description,
                "notes": t.notes,
            }
        )
    return pd.DataFrame(rows)
    # Convierte la lista de dicts en DataFrame.
