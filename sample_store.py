"""Persistencia de bitácora de carga (muestras en vivo)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
SAMPLES_PATH = DATA_DIR / "charge_samples.json"


def _empty_payload() -> dict[str, Any]:
    return {
        "session_started": None,
        "device_label": "",
        "platform": "android",
        "updated_at": None,
        "rows": [],
    }


def load_session() -> dict[str, Any]:
    if not SAMPLES_PATH.exists():
        return _empty_payload()
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))


def rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["t_min", "t_h", "level", "voltage_mv", "current_ua", "temperature_c", "timestamp", "source"])
    df = pd.DataFrame(rows)
    for col in ("t_min", "t_h", "level"):
        if col not in df.columns:
            df[col] = []
    return df


def save_session(
    rows: list[dict[str, Any]],
    *,
    device_label: str = "",
    platform: str = "android",
    session_started: str | None = None,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = load_session() if SAMPLES_PATH.exists() else _empty_payload()
    payload["rows"] = rows
    payload["device_label"] = device_label
    payload["platform"] = platform
    if session_started:
        payload["session_started"] = session_started
    elif not payload.get("session_started") and rows:
        payload["session_started"] = rows[0].get("timestamp")
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    SAMPLES_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_session() -> None:
    save_session([], device_label="", platform="android", session_started=None)


def export_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    return rows_to_dataframe(rows).to_csv(index=False).encode("utf-8")
