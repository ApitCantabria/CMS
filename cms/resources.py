from __future__ import annotations

from datetime import date
import re

import pandas as pd

from .data import normalize_lookup

DIAS_ES = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}


def parse_date_list(value) -> set[date]:
    if pd.isna(value):
        return set()
    result = set()
    for part in re.split(r"[,;\n]+", str(value)):
        parsed = pd.to_datetime(part.strip(), dayfirst=True, errors="coerce")
        if pd.notna(parsed):
            result.add(parsed.date())
    return result


def annual_date_applies(
    selected_date: date,
    start,
    end,
) -> bool:
    """Compare an annual interval by month/day, including year-end spans."""
    selected_key = (selected_date.month, selected_date.day)
    start_key = (start.month, start.day) if pd.notna(start) else None
    end_key = (end.month, end.day) if pd.notna(end) else None

    if start_key and end_key:
        if start_key <= end_key:
            return start_key <= selected_key <= end_key
        return selected_key >= start_key or selected_key <= end_key
    if start_key:
        return selected_key >= start_key
    if end_key:
        return selected_key <= end_key
    return True


def row_applies_on(row: pd.Series, selected_date: date) -> bool:
    repetition = normalize_lookup(row.get("repeticion", ""))
    exclusions = parse_date_list(row.get("fechas_excluidas", ""))
    if repetition == "anual":
        selected_key = (selected_date.month, selected_date.day)
        if any((excluded.month, excluded.day) == selected_key for excluded in exclusions):
            return False
    elif selected_date in exclusions:
        return False

    start = row.get("fecha_inicio")
    end = row.get("fecha_fin")
    if repetition == "anual":
        if not annual_date_applies(selected_date, start, end):
            return False
    else:
        if pd.notna(start) and selected_date < start.date():
            return False
        if pd.notna(end) and selected_date > end.date():
            return False

    raw_days = row.get("dias_semana", "")
    days_text = "" if pd.isna(raw_days) else normalize_lookup(raw_days)
    if not days_text:
        return True

    days = {
        normalize_lookup(day)
        for day in re.split(r"\s*(?:-|,|;|/|\by\b)\s*", days_text)
        if day.strip()
    }
    if days & {"todos", "diario", "diaria", "todos los dias"}:
        return True
    return normalize_lookup(DIAS_ES[selected_date.weekday()]) in days


def related_rows(
    df: pd.DataFrame,
    *,
    id_column: str,
    entity_id,
    name_column: str,
    entity_name,
) -> pd.DataFrame:
    """Prefer a stable ID, while supporting legacy sheets during migration."""
    join_column = f"_{name_column}_join_key"
    if join_column in df.columns:
        join_key = (
            f"id:{str(entity_id).strip()}"
            if pd.notna(entity_id) and str(entity_id).strip()
            else f"name:{normalize_lookup(entity_name)}"
        )
        matches = df[df[join_column] == join_key]
        if not matches.empty:
            return matches.copy()

    if id_column in df.columns and pd.notna(entity_id) and str(entity_id).strip():
        matches = df[df[id_column].astype(str).str.strip() == str(entity_id).strip()]
        if not matches.empty:
            return matches.copy()

    key_column = f"_{name_column}_key"
    if key_column in df.columns:
        return df[df[key_column] == normalize_lookup(entity_name)].copy()
    if name_column in df.columns:
        return df[df[name_column].map(normalize_lookup) == normalize_lookup(entity_name)].copy()
    return pd.DataFrame(columns=df.columns)


def filter_resource_content(
    df: pd.DataFrame,
    *,
    resource_id,
    resource_name,
    selected_date: date,
) -> pd.DataFrame:
    rows = related_rows(
        df,
        id_column="recurso_id",
        entity_id=resource_id,
        name_column="recurso",
        entity_name=resource_name,
    )
    if rows.empty:
        return rows
    return rows[rows.apply(lambda row: row_applies_on(row, selected_date), axis=1)]


def latest_resource_confirmation(
    confirmations: pd.DataFrame,
    *,
    resource_id,
    resource_name,
):
    rows = related_rows(
        confirmations,
        id_column="recurso_id",
        entity_id=resource_id,
        name_column="recurso",
        entity_name=resource_name,
    )
    if rows.empty or "fecha" not in rows.columns:
        return None

    dates = pd.to_datetime(rows["fecha"], dayfirst=True, errors="coerce").dropna()
    return dates.max() if not dates.empty else None


def attach_restaurant_ratings(
    restaurants: pd.DataFrame,
    reviews: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate once, preferring IDs and filling migration gaps by name."""
    result = restaurants.copy()
    result["rating_medio"] = pd.NA
    result["n_resenas"] = 0
    if reviews.empty or "rating" not in reviews.columns:
        return result

    def apply_aggregate(column: str, *, only_missing: bool) -> None:
        if column not in result.columns or column not in reviews.columns:
            return
        source = reviews.dropna(subset=["rating"]).copy()
        if column.endswith("_id"):
            source = source[
                source[column].notna()
                & source[column].astype(str).str.strip().ne("")
            ]
        aggregates = (
            source
            .groupby(column)["rating"]
            .agg(rating_medio="mean", n_resenas="count")
        )
        ratings = result[column].map(aggregates["rating_medio"])
        counts = result[column].map(aggregates["n_resenas"])
        target = result["rating_medio"].isna() if only_missing else ratings.notna()
        result.loc[target & ratings.notna(), "rating_medio"] = ratings
        result.loc[target & counts.notna(), "n_resenas"] = counts

    apply_aggregate("restaurante_id", only_missing=False)
    apply_aggregate("_restaurante_key", only_missing=True)
    result["rating_medio"] = pd.to_numeric(result["rating_medio"], errors="coerce")
    result["n_resenas"] = pd.to_numeric(
        result["n_resenas"],
        errors="coerce",
    ).fillna(0).astype(int)
    return result
