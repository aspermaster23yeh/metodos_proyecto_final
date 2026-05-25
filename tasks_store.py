"""Task persistence and seed data for Li-ion project hub."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_START = date(2026, 4, 2)
PROJECT_END = date(2026, 5, 8)

PHASES = [
    "Preparación",
    "Recolección",
    "Modelación",
    "Desarrollo UX",
    "Cierre",
]

STATUSES = ("todo", "in_progress", "review", "done")
STATUS_LABELS = {
    "todo": "Por hacer",
    "in_progress": "En progreso",
    "review": "Revisión",
    "done": "Hecho",
}
PROFILES = ("Análisis", "Diseño UX", "General")
ASSIGNEES = ("Adán", "Ángel", "Checho", "Arath", "Gustavo")

DATA_DIR = Path(__file__).resolve().parent / "data"
TASKS_PATH = DATA_DIR / "project_tasks.json"

PHASE_RANGES: dict[str, tuple[date, date]] = {
    "Preparación": (date(2026, 4, 2), date(2026, 4, 8)),
    "Recolección": (date(2026, 4, 9), date(2026, 4, 18)),
    "Modelación": (date(2026, 4, 19), date(2026, 4, 28)),
    "Desarrollo UX": (date(2026, 4, 22), date(2026, 5, 4)),
    "Cierre": (date(2026, 5, 5), date(2026, 5, 8)),
}

CRONOGRAMA_8 = [
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
    id: str
    title: str
    phase: str
    assignees: list[str]
    profile: str
    status: str
    start: str
    end: str
    deliverable: str = ""
    notes: str = ""

    def start_date(self) -> date:
        return date.fromisoformat(self.start)

    def end_date(self) -> date:
        return date.fromisoformat(self.end)


def _parse_assignees(raw: str) -> list[str]:
    if "Todo el equipo" in raw:
        return list(ASSIGNEES)
    parts = raw.replace("&", ",").split(",")
    names: list[str] = []
    for p in parts:
        p = p.strip()
        if p in ASSIGNEES and p not in names:
            names.append(p)
    return names or list(ASSIGNEES)


def _profile_from_assignees(raw: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    if "Todo el equipo" in raw:
        return "General"
    if any(n in raw for n in ("Checho", "Arath", "Gustavo")):
        if any(n in raw for n in ("Adán", "Ángel")):
            return "General"
        return "Diseño UX"
    return "Análisis"


def _stagger_dates(phase: str, index: int, count: int) -> tuple[str, str]:
    p_start, p_end = PHASE_RANGES[phase]
    total_days = (p_end - p_start).days + 1
    if count <= 1:
        return p_start.isoformat(), p_end.isoformat()
    slot = max(1, total_days // count)
    start = p_start + timedelta(days=min(index * slot, total_days - 1))
    end = min(p_start + timedelta(days=min((index + 1) * slot, total_days) - 1), p_end)
    if end < start:
        end = start
    return start.isoformat(), end.isoformat()


def build_seed_tasks() -> list[Task]:
    """30 tasks from project breakdown (5 phases × 6)."""
    rows: list[tuple[str, str, str, str | None]] = [
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
        "Preparación": ["Protocolo de control", "", "", "Bitácora digital", "Guía de estilo", "Benchmark fabricante"],
        "Recolección": ["Ciclo descarga", "Bitácora 5 min", "Log térmico", "Wireframes", "Set de iconos", "CSV validado"],
        "Modelación": ["Scatter limpio", "Modelo lineal", "Modelo log/polinómico", "Gráficos publicación", "Tabla R²", "Infografía CC-CV"],
        "Desarrollo UX": ["Dashboard", "Comparativa visual", "Capítulo teórico", "Mockup Figma", "Informe usabilidad", "Checklist jerarquía"],
        "Cierre": ["Informe de error", "Conclusiones", "Reporte final", "Documento revisado", "Guión pitch", "Entregables export"],
    }

    phase_counts: dict[str, int] = {p: 0 for p in PHASES}
    tasks: list[Task] = []
    for phase, title, assignees_raw, profile in rows:
        idx = phase_counts[phase]
        phase_counts[phase] += 1
        start, end = _stagger_dates(phase, idx, 6)
        dels = deliverables_by_phase.get(phase, [])
        deliverable = dels[idx] if idx < len(dels) else ""
        tasks.append(
            Task(
                id=f"task-{phase.lower().replace(' ', '-')}-{idx + 1}",
                title=title,
                phase=phase,
                assignees=_parse_assignees(assignees_raw),
                profile=profile or _profile_from_assignees(assignees_raw),
                status="todo",
                start=start,
                end=end,
                deliverable=deliverable,
                notes="",
            )
        )
    return tasks


def clamp_date(d: date) -> date:
    if d < PROJECT_START:
        return PROJECT_START
    if d > PROJECT_END:
        return PROJECT_END
    return d


def validate_task(task: Task) -> Task:
    if task.status not in STATUSES:
        task.status = "todo"
    if task.phase not in PHASES:
        task.phase = PHASES[0]
    if task.profile not in PROFILES:
        task.profile = "General"
    try:
        s = clamp_date(date.fromisoformat(task.start))
        e = clamp_date(date.fromisoformat(task.end))
    except ValueError:
        s, e = PROJECT_START, PROJECT_END
    if e < s:
        e = s
    task.start = s.isoformat()
    task.end = e.isoformat()
    return task


def task_from_dict(d: dict[str, Any]) -> Task:
    return validate_task(
        Task(
            id=str(d.get("id", uuid.uuid4().hex[:8])),
            title=str(d.get("title", "Sin título")),
            phase=str(d.get("phase", PHASES[0])),
            assignees=list(d.get("assignees", [])),
            profile=str(d.get("profile", "General")),
            status=str(d.get("status", "todo")),
            start=str(d.get("start", PROJECT_START.isoformat())),
            end=str(d.get("end", PROJECT_END.isoformat())),
            deliverable=str(d.get("deliverable", "")),
            notes=str(d.get("notes", "")),
        )
    )


def tasks_to_dicts(tasks: list[Task]) -> list[dict[str, Any]]:
    return [asdict(validate_task(t)) for t in tasks]


def save_tasks(tasks: list[Task]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_start": PROJECT_START.isoformat(),
        "project_end": PROJECT_END.isoformat(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "tasks": tasks_to_dicts(tasks),
    }
    TASKS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_tasks() -> list[Task]:
    if not TASKS_PATH.exists():
        tasks = build_seed_tasks()
        save_tasks(tasks)
        return tasks
    raw = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    items = raw.get("tasks", raw) if isinstance(raw, dict) else raw
    return [task_from_dict(item) for item in items]


def new_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:8]}"


def redistribute_phase_dates(tasks: list[Task]) -> list[Task]:
    """Re-assign dates within each phase range (keeps titles/status)."""
    by_phase: dict[str, list[Task]] = {p: [] for p in PHASES}
    for t in tasks:
        by_phase.setdefault(t.phase, []).append(t)
    out: list[Task] = []
    for phase in PHASES:
        phase_tasks = by_phase.get(phase, [])
        for i, t in enumerate(phase_tasks):
            start, end = _stagger_dates(phase, i, len(phase_tasks) or 1)
            t.start, t.end = start, end
            out.append(validate_task(t))
    # preserve tasks in unknown phases
    known_ids = {t.id for t in out}
    for t in tasks:
        if t.id not in known_ids:
            out.append(validate_task(t))
    return out


def tasks_to_dataframe(tasks: list[Task]):
    import pandas as pd

    rows = []
    for t in tasks:
        rows.append(
            {
                "id": t.id,
                "title": t.title,
                "phase": t.phase,
                "assignees": ", ".join(t.assignees),
                "profile": t.profile,
                "status": STATUS_LABELS.get(t.status, t.status),
                "start": t.start,
                "end": t.end,
                "deliverable": t.deliverable,
                "notes": t.notes,
            }
        )
    return pd.DataFrame(rows)
