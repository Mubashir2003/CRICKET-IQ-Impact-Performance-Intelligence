"""Read the 20 raw CSV files, validate schemas, type-coerce and merge by gender."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import Paths, Settings
from .schema import SCHEMAS, Column, TableSchema

log = logging.getLogger(__name__)

_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f"}


class IngestionError(RuntimeError):
    """Raised when required input files or columns are missing."""


@dataclass
class Issue:
    gender: str
    table: str
    severity: str  # "error" | "warning" | "info"
    message: str
    count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"gender": self.gender, "table": self.table, "severity": self.severity, "message": self.message, "count": self.count}


@dataclass
class RawBundle:
    """Combined (both genders) tables plus the schema inspection log."""

    tables: dict[str, pd.DataFrame]
    schema_report: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def _resolve_columns(df: pd.DataFrame, schema: TableSchema) -> tuple[dict[str, str], list[str]]:
    """Map actual column names onto canonical names. Returns (rename map, missing required)."""
    actual = {c.strip().lower(): c for c in df.columns}
    rename: dict[str, str] = {}
    missing: list[str] = []
    for col in schema.columns:
        found = None
        for cand in (col.name, *col.aliases):
            if cand.lower() in actual:
                found = actual[cand.lower()]
                break
        if found is None:
            if col.required:
                missing.append(col.name)
            continue
        rename[found] = col.name
    return rename, missing


def _coerce(series: pd.Series, col: Column) -> tuple[pd.Series, int]:
    """Coerce a string series to the declared type. Returns (series, n_unparseable)."""
    s = series.astype("object").where(series.notna(), None)
    s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    s = s.map(lambda v: None if (v is None or v == "") else v)
    present = s.notna()
    if col.type == "str":
        return s.astype("object"), 0
    if col.type in ("int", "float"):
        num = pd.to_numeric(s, errors="coerce")
        bad = int((present & num.isna()).sum())
        if col.type == "int":
            if num.notna().all() and np.allclose(num.fillna(0) % 1, 0):
                return num.astype("int64"), bad
            return num.astype("Float64").round().astype("Int64"), bad
        return num.astype("float64"), bad
    if col.type == "bool":
        low = s.map(lambda v: v.lower() if isinstance(v, str) else v)
        out = low.map(lambda v: True if v in _TRUE else (False if v in _FALSE else None))
        bad = int((present & out.isna()).sum())
        if out.notna().all():
            return out.astype(bool), bad
        return out.astype("boolean"), bad
    if col.type == "date":
        d = pd.to_datetime(s, errors="coerce", format="mixed")
        bad = int((present & d.isna()).sum())
        return d, bad
    raise ValueError(col.type)  # pragma: no cover


def read_table(path: Path, schema: TableSchema, gender: str) -> tuple[pd.DataFrame, dict[str, Any], list[Issue]]:
    """Read one CSV, resolve columns, coerce types and tag gender."""
    issues: list[Issue] = []
    df = pd.read_csv(path, dtype=str, keep_default_na=True, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    report: dict[str, Any] = {
        "gender": gender,
        "table": schema.name,
        "file": path.name,
        "rows": len(df),
        "columns": list(df.columns),
    }
    rename, missing = _resolve_columns(df, schema)
    if missing:
        raise IngestionError(
            f"{gender}/{path.name}: required column(s) not found: {', '.join(missing)}. "
            f"Columns present: {', '.join(df.columns)}"
        )
    df = df.rename(columns=rename)
    types: dict[str, str] = {}
    for col in schema.columns:
        if col.name not in df.columns:
            continue
        df[col.name], bad = _coerce(df[col.name], col)
        types[col.name] = col.type
        if bad:
            issues.append(Issue(gender, schema.name, "warning", f"Column '{col.name}': {bad} value(s) could not be parsed as {col.type} and were kept as missing", bad))
        nulls = int(df[col.name].isna().sum())
        if nulls and not col.nullable and col.required:
            issues.append(Issue(gender, schema.name, "warning", f"Column '{col.name}' has {nulls} missing value(s) (left missing, not zero-filled)", nulls))
    for col in schema.columns:  # optional columns that are absent are added as missing (never zero)
        if col.name not in df.columns and col.name != "gender":
            df[col.name] = pd.Series([None] * len(df), dtype="object")
    if "gender" in df.columns:
        df = df.rename(columns={"gender": "source_gender"})
    df.insert(0, "gender", gender)
    report["detected_types"] = types
    report["renamed"] = {k: v for k, v in rename.items() if k != v}
    report["extra_columns"] = [c for c in df.columns if c not in types and c not in ("gender", "source_gender")]
    return df, report, issues


def load_raw(paths: Paths, settings: Settings) -> RawBundle:
    """Load all raw files for every configured gender and merge into combined tables."""
    combined: dict[str, list[pd.DataFrame]] = {name: [] for name in SCHEMAS}
    schema_report: list[dict[str, Any]] = []
    issues: list[Issue] = []
    for gkey, gspec in settings.genders.items():
        folder = paths.raw / gspec["folder"]
        if not folder.exists() or not any(folder.glob("*.csv")):
            issues.append(Issue(gkey, "*", "warning", f"No input CSV files found for {gspec['label']} - skipped"))
            continue
        for name, schema in SCHEMAS.items():
            path = folder / f"{name}.csv"
            if not path.exists():
                if name in ("matches", "deliveries"):
                    raise IngestionError(f"Required file missing: {path}")
                issues.append(Issue(gkey, name, "warning", f"File {name}.csv not found - related cross-checks skipped"))
                continue
            df, rep, iss = read_table(path, schema, gkey)
            combined[name].append(df)
            schema_report.append(rep)
            issues.extend(iss)
            log.info("Loaded %-22s %-6s %8d rows", name, gkey, len(df))
    tables: dict[str, pd.DataFrame] = {}
    for name, frames in combined.items():
        if frames:
            tables[name] = pd.concat(frames, ignore_index=True)
        else:
            tables[name] = pd.DataFrame(columns=["gender", *[c.name for c in SCHEMAS[name].columns]])
    if tables["matches"].empty:
        raise IngestionError("No match data found. Place CSV files in data/raw/men and/or data/raw/women.")
    return RawBundle(tables=tables, schema_report=schema_report, issues=issues)
