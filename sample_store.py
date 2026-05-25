"""Persistencia de bitácora de carga (sesión actual + historial por archivo)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
SAMPLES_PATH = DATA_DIR / "charge_samples.json"

REFERENCE_LABEL = "Proyecto principal (reporte ITT)"


@dataclass
class SessionInfo:
    filename: str
    device_label: str
    session_date: str
    platform: str
    n_samples: int
    t_100_min: float
    final_level: float
    notes: str


def _empty_payload() -> dict[str, Any]:
    return {
        "session_id": None,
        "session_date": None,
        "device_label": "",
        "platform": "android",
        "notes": "",
        "session_started": None,
        "updated_at": None,
        "rows": [],
    }


def rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["t_min", "t_h", "level", "voltage_mv", "current_ua", "temperature_c", "timestamp", "source"]
        )
    df = pd.DataFrame(rows)
    for col in ("t_min", "t_h", "level"):
        if col not in df.columns:
            df[col] = []
    return df


def _rows_from_pairs(
    pairs: list[tuple[int, int]],
    *,
    device_label: str,
    session_date: str,
    notes: str = "",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, (t_min, level) in enumerate(pairs):
        charging = level < 95
        rows.append(
            {
                "timestamp": f"{session_date}T{10 + (i * 5) // 60:02d}:{(i * 5) % 60:02d}:00",
                "t_min": float(t_min),
                "t_h": round(t_min / 60.0, 4),
                "level": float(level),
                "voltage_mv": 3550 + int(level * 9),
                "current_ua": 750_000 if charging else 180_000,
                "temperature_c": round(27.5 + i * 0.35, 1),
                "source": "adb",
            }
        )
    return rows


def _build_payload(
    rows: list[dict[str, Any]],
    *,
    device_label: str,
    platform: str,
    session_date: str | None,
    notes: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    sid = session_id or _slug(device_label)
    sdate = session_date or (rows[0].get("timestamp", "")[:10] if rows else datetime.now().strftime("%Y-%m-%d"))
    return {
        "session_id": sid,
        "session_date": sdate,
        "device_label": device_label,
        "platform": platform,
        "notes": notes,
        "session_started": rows[0].get("timestamp") if rows else None,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows,
    }


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:48] or "sesion"


def _write_session_file(payload: dict[str, Any], filename: str | None = None) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        sdate = payload.get("session_date") or datetime.now().strftime("%Y%m%d")
        slug = _slug(str(payload.get("device_label", "android")))
        filename = f"charge_samples_{sdate}_{slug}.json"
    path = SESSIONS_DIR / filename
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def ensure_demo_sessions() -> None:
    """Crea sesiones de ejemplo si la carpeta está vacía."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(SESSIONS_DIR.glob("charge_samples_*.json"))
    if existing:
        return

    demos: list[tuple[str, str, str, list[tuple[int, int]]]] = [
        (
            "Samsung Galaxy A54",
            "2026-04-10",
            "Android gama media — protocolo idéntico al reporte (modo avión, 5 min).",
            [
                (0, 0), (5, 14), (10, 27), (15, 38), (20, 46), (25, 56),
                (30, 62), (35, 72), (40, 83), (45, 90), (50, 99), (52, 100),
            ],
        ),
        (
            "Xiaomi Redmi Note 12",
            "2026-04-12",
            "Carga más lenta en fase CV; 6000 mAh nominal.",
            [
                (0, 0), (5, 12), (10, 23), (15, 33), (20, 42), (25, 51),
                (30, 59), (35, 67), (40, 75), (45, 82), (50, 89), (55, 94),
                (58, 97), (60, 100),
            ],
        ),
        (
            "Motorola Edge 40",
            "2026-04-15",
            "CC más agresiva; alcanza 100% en ~50 min.",
            [
                (0, 0), (5, 16), (10, 30), (15, 41), (20, 52), (25, 61),
                (30, 70), (35, 79), (40, 87), (45, 93), (48, 98), (50, 100),
            ],
        ),
        (
            "OPPO A78 5G",
            "2026-04-18",
            "Segundo perfil del reporte: no llega al 100% en la ventana de 52 min.",
            [
                (0, 0), (5, 11), (10, 22), (15, 33), (20, 43), (25, 53),
                (30, 63), (35, 72), (40, 74), (45, 84), (50, 88), (52, 90),
            ],
        ),
        (
            "Google Pixel 7a",
            "2026-04-20",
            "Carga optimizada; temperatura estable vía ADB.",
            [
                (0, 0), (5, 15), (10, 28), (15, 39), (20, 49), (25, 58),
                (30, 66), (35, 75), (40, 84), (45, 91), (49, 98), (51, 100),
            ],
        ),
    ]
    for device, sdate, notes, pairs in demos:
        rows = _rows_from_pairs(pairs, device_label=device, session_date=sdate, notes=notes)
        payload = _build_payload(rows, device_label=device, platform="android", session_date=sdate, notes=notes)
        _write_session_file(payload)


def list_sessions() -> list[SessionInfo]:
    ensure_demo_sessions()
    out: list[SessionInfo] = []
    for path in sorted(SESSIONS_DIR.glob("charge_samples_*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("rows", [])
        df = rows_to_dataframe(rows)
        t100 = float(df["t_min"].max()) if not df.empty else 0.0
        final = float(df["level"].iloc[-1]) if not df.empty else 0.0
        out.append(
            SessionInfo(
                filename=path.name,
                device_label=str(raw.get("device_label", path.stem)),
                session_date=str(raw.get("session_date", "")),
                platform=str(raw.get("platform", "android")),
                n_samples=len(rows),
                t_100_min=t100,
                final_level=final,
                notes=str(raw.get("notes", "")),
            )
        )
    return out


def load_session_file(filename: str) -> dict[str, Any]:
    path = SESSIONS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(filename)
    return json.loads(path.read_text(encoding="utf-8"))


def load_current_session() -> dict[str, Any]:
    if not SAMPLES_PATH.exists():
        return _empty_payload()
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))


def save_current_session(
    rows: list[dict[str, Any]],
    *,
    device_label: str = "",
    platform: str = "android",
    session_started: str | None = None,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = load_current_session() if SAMPLES_PATH.exists() else _empty_payload()
    payload["rows"] = rows
    payload["device_label"] = device_label
    payload["platform"] = platform
    if session_started:
        payload["session_started"] = session_started
    elif not payload.get("session_started") and rows:
        payload["session_started"] = rows[0].get("timestamp")
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    SAMPLES_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def save_to_history(
    rows: list[dict[str, Any]],
    *,
    device_label: str,
    platform: str = "android",
    session_started: str | None = None,
    notes: str = "",
) -> Path:
    """Guarda una copia en data/sessions/ sin sobrescribir sesiones anteriores."""
    sdate = datetime.now().strftime("%Y-%m-%d")
    payload = _build_payload(
        rows,
        device_label=device_label or "Android",
        platform=platform,
        session_date=sdate,
        notes=notes or "Sesión guardada desde el Laboratorio.",
    )
    if session_started:
        payload["session_started"] = session_started
    return _write_session_file(payload)


def clear_current_session() -> None:
    save_current_session([], device_label="", platform="android", session_started=None)


def export_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    return rows_to_dataframe(rows).to_csv(index=False).encode("utf-8")


# Alias retrocompatibles
load_session = load_current_session
save_session = save_current_session
clear_session = clear_current_session
