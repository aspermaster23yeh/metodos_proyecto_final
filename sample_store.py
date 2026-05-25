"""Persistencia de bitácora de carga (muestras en vivo)."""
# Docstring: gestiona el guardado y la carga de las muestras tomadas en tiempo real
# (vía ADB o entrada manual) en un archivo JSON local.

from __future__ import annotations
# Anotaciones de tipo modernas.

import json
# Módulo estándar para serializar/deserializar JSON.
from datetime import datetime
# Para registrar marcas de tiempo (timestamps).
from pathlib import Path
# Manejo de rutas multiplataforma orientado a objetos.
from typing import Any
# Tipo genérico (usado en dicts con valores heterogéneos).

import pandas as pd
# Pandas para convertir las muestras en un DataFrame.

DATA_DIR = Path(__file__).resolve().parent / "data"
# Carpeta `data/` ubicada junto a este archivo (para guardar el JSON).
SAMPLES_PATH = DATA_DIR / "charge_samples.json"
# Ruta completa del archivo JSON de la bitácora de muestras.


def _empty_payload() -> dict[str, Any]:
    # Devuelve un diccionario "vacío" con la estructura esperada del JSON.
    return {
        "session_started": None,
        # Cuándo arrancó la sesión actual (ISO 8601 o None).
        "device_label": "",
        # Nombre/etiqueta del dispositivo medido.
        "platform": "android",
        # Plataforma: "android" (ADB automático) o "manual" (iPhone u otro).
        "updated_at": None,
        # Última actualización del archivo.
        "rows": [],
        # Lista de filas (cada muestra con sus campos).
    }


def load_session() -> dict[str, Any]:
    # Lee la bitácora desde disco; si no existe, devuelve la estructura vacía.
    if not SAMPLES_PATH.exists():
        return _empty_payload()
        # Archivo aún no creado → estructura vacía por defecto.
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    # Lee el JSON con codificación UTF-8 y lo deserializa a un diccionario.


def rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    # Convierte la lista de muestras (dicts) en un DataFrame de pandas con columnas esperadas.
    if not rows:
        # Caso sin muestras: devuelve un DataFrame vacío con las columnas correctas.
        return pd.DataFrame(columns=["t_min", "t_h", "level", "voltage_mv", "current_ua", "temperature_c", "timestamp", "source"])
    df = pd.DataFrame(rows)
    # Construye el DataFrame a partir de la lista de dicts.
    for col in ("t_min", "t_h", "level"):
        # Verifica que existan las columnas mínimas indispensables.
        if col not in df.columns:
            df[col] = []
            # Si falta alguna, la crea vacía para evitar errores aguas abajo.
    return df


def save_session(
    # Guarda la lista de muestras (y metadatos) en el JSON, fusionando con el contenido previo.
    rows: list[dict[str, Any]],
    *,
    # `*` obliga a usar los siguientes argumentos por nombre (keyword-only).
    device_label: str = "",
    # Etiqueta del dispositivo (opcional).
    platform: str = "android",
    # Plataforma usada para la sesión.
    session_started: str | None = None,
    # Marca de tiempo en que se inició la sesión (opcional).
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Garantiza que la carpeta `data/` exista (crea padres si hace falta, sin error si ya existe).
    payload = load_session() if SAMPLES_PATH.exists() else _empty_payload()
    # Lee el JSON previo (si existe) para no perder metadatos antiguos.
    payload["rows"] = rows
    # Reemplaza las muestras con la lista actual.
    payload["device_label"] = device_label
    # Actualiza la etiqueta del dispositivo.
    payload["platform"] = platform
    # Actualiza la plataforma.
    if session_started:
        # Si se pasó una marca de inicio explícita...
        payload["session_started"] = session_started
        # ...la usa.
    elif not payload.get("session_started") and rows:
        # Si no había una y hay al menos una muestra...
        payload["session_started"] = rows[0].get("timestamp")
        # ...usa el timestamp de la primera muestra como inicio de sesión.
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    # Marca el momento de la última actualización (formato ISO sin microsegundos).
    SAMPLES_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # Escribe el JSON con indentación y caracteres no-ASCII tal cual (acentos legibles).


def clear_session() -> None:
    # Reinicia la bitácora a un estado vacío (sin borrar el archivo).
    save_session([], device_label="", platform="android", session_started=None)


def export_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    # Convierte las muestras a CSV en memoria (bytes), listo para descargar desde la app.
    return rows_to_dataframe(rows).to_csv(index=False).encode("utf-8")
    # `to_csv(index=False)`: omite el índice. `.encode("utf-8")`: convierte string a bytes.
