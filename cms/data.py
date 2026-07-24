from __future__ import annotations

import logging
from dataclasses import dataclass
from io import StringIO
from typing import Callable
import unicodedata

import pandas as pd
import requests

from .config import DATE_COLUMNS, SHEET_SCHEMAS, SHEET_URLS

logger = logging.getLogger(__name__)

TRUE_VALUES = {"true", "verdadero", "si", "sí", "yes", "1", "x"}


class DataSourceError(RuntimeError):
    """A sheet could not be downloaded or validated."""

    def __init__(self, sheet: str, message: str):
        super().__init__(f"{sheet}: {message}")
        self.sheet = sheet


@dataclass(frozen=True)
class DataLoadResult:
    frames: dict[str, pd.DataFrame]
    errors: dict[str, str]
    warnings: tuple[str, ...]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = (
        result.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )
    return result


def normalize_lookup(value) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip().casefold())
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char)).split()
    )


def normalize_bool(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return normalize_lookup(value) in TRUE_VALUES


def validate_schema(name: str, df: pd.DataFrame) -> tuple[str, ...]:
    schema = SHEET_SCHEMAS[name]
    missing = schema["required"] - set(df.columns)
    if missing:
        columns = ", ".join(sorted(missing))
        raise DataSourceError(name, f"faltan columnas obligatorias: {columns}")

    missing_recommended = schema["recommended"] - set(df.columns)
    return tuple(
        f"La hoja '{name}' todavía no incluye la columna recomendada '{column}'."
        for column in sorted(missing_recommended)
    )


def read_remote_csv(
    url: str,
    *,
    http_get: Callable = requests.get,
    timeout: int = 10,
) -> pd.DataFrame:
    response = http_get(url, timeout=timeout)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def prepare_frame(name: str, df: pd.DataFrame) -> tuple[pd.DataFrame, tuple[str, ...]]:
    result = normalize_columns(df)
    warnings = validate_schema(name, result)

    for column in DATE_COLUMNS & set(result.columns):
        result[column] = pd.to_datetime(
            result[column],
            dayfirst=True,
            errors="coerce",
        )

    if "activo" in result.columns:
        result["activo"] = result["activo"].apply(normalize_bool)
    if "rating" in result.columns:
        result["rating"] = pd.to_numeric(result["rating"], errors="coerce")
    if "prioridad" in result.columns:
        result["prioridad"] = pd.to_numeric(result["prioridad"], errors="coerce")

    for column in ("recurso", "restaurante", "municipio"):
        if column in result.columns:
            result[f"_{column}_key"] = result[column].map(normalize_lookup)

    for entity in ("recurso", "restaurante"):
        name_key = f"_{entity}_key"
        id_column = f"{entity}_id"
        if name_key in result.columns:
            if id_column in result.columns:
                ids = result[id_column].fillna("").astype(str).str.strip()
                result[f"_{entity}_join_key"] = [
                    f"id:{entity_id}" if entity_id else f"name:{name}"
                    for entity_id, name in zip(ids, result[name_key])
                ]
            else:
                result[f"_{entity}_join_key"] = "name:" + result[name_key]

    return result, warnings


def load_all_sheets(
    urls: dict[str, str] = SHEET_URLS,
    *,
    reader: Callable[[str], pd.DataFrame] = read_remote_csv,
) -> DataLoadResult:
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    warnings: list[str] = []

    for name, url in urls.items():
        try:
            frames[name], sheet_warnings = prepare_frame(name, reader(url))
            warnings.extend(sheet_warnings)
        except Exception as exc:
            logger.exception("No se pudo cargar la hoja '%s'", name)
            errors[name] = str(exc)

    return DataLoadResult(frames, errors, tuple(warnings))
