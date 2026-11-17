"""Standardisation, season filtering, duplicate detection and referential checks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..config import Settings
from ..ingestion.loader import Issue, RawBundle

log = logging.getLogger(__name__)

STRING_COLS = {
    "matches": ["match_id", "competition", "venue", "city", "team_1", "team_2", "winner", "result_type", "season", "match_type"],
    "deliveries": ["match_id", "batting_team", "bowling_team", "batter", "non_striker", "bowler", "dismissal_kinds", "players_out", "competition"],
    "batting_innings": ["match_id", "team", "player"],
    "bowling_innings": ["match_id", "team", "player"],
    "partnerships": ["match_id", "batting_team", "player_1", "player_2"],
    "player_match": ["match_id", "team", "player"],
    "player_appearances": ["player"],
    "excluded_players": ["player"],
}

_WS = re.compile(r"\s+")


@dataclass
class CleanBundle:
    tables: dict[str, pd.DataFrame]
    issues: list[Issue] = field(default_factory=list)
    excluded_matches: pd.DataFrame = field(default_factory=pd.DataFrame)


def _norm_str(s: pd.Series) -> pd.Series:
    return s.map(lambda v: _WS.sub(" ", v).strip() if isinstance(v, str) else v)


def clean(bundle: RawBundle, settings: Settings) -> CleanBundle:
    """Return cleaned copies of all tables. Original input files are never modified."""
    t = {k: v.copy() for k, v in bundle.tables.items()}
    issues: list[Issue] = list(bundle.issues)

    for name, cols in STRING_COLS.items():
        if name in t:
            for c in cols:
                if c in t[name].columns:
                    t[name][c] = _norm_str(t[name][c])

    m = t["matches"]
    # gender consistency (source column like "mens"/"womens")
    for name, df in t.items():
        if "source_gender" in df.columns and len(df):
            src = df["source_gender"].fillna("").astype(str).str.lower()
            prefix = df["gender"].map({"men": "men", "women": "wom"}).fillna("")
            bad = (src != "") & ~pd.Series([s.startswith(p) for s, p in zip(src, prefix)], index=df.index)
            if bad.any():
                issues.append(Issue("*", name, "error", "Rows whose gender label disagrees with their folder", int(bad.sum())))

    # duplicate matches
    dup = m.duplicated(["gender", "match_id"], keep="first")
    if dup.any():
        issues.append(Issue("*", "matches", "warning", "Duplicate match_id rows found; first occurrence kept", int(dup.sum())))
        m = m[~dup]

    # season window & competition exclusions
    start = pd.Timestamp(settings["season"]["start_date"])
    end = settings["season"].get("end_date")
    keep = m["date"] >= start
    if end:
        keep &= m["date"] <= pd.Timestamp(end)
    keep &= m["date"].notna()
    for pat in settings["season"]["exclude_competition_patterns"]:
        keep &= ~m["competition"].fillna("").str.contains(pat, case=False, regex=True)
    excluded = m[~keep].copy()
    if len(excluded):
        issues.append(Issue("*", "matches", "info", "Matches outside the 2026 season window or in excluded competitions", len(excluded)))
    m = m[keep].copy()
    t["matches"] = m.reset_index(drop=True)

    valid = set(zip(m["gender"], m["match_id"]))
    for name in ("deliveries", "batting_innings", "bowling_innings", "partnerships", "player_match"):
        df = t.get(name)
        if df is None or df.empty:
            continue
        key = pd.Series(list(zip(df["gender"], df["match_id"])), index=df.index)
        orphan = ~key.isin(valid)
        if orphan.any():
            issues.append(Issue("*", name, "info", "Rows for matches not in the analysed match set (excluded or unknown) - not used", int(orphan.sum())))
        t[name] = df[~orphan].reset_index(drop=True)

    d = t["deliveries"]
    d["_row"] = range(len(d))
    keycols = ["gender", "match_id", "innings_number", "over", "delivery_in_over"]
    full_dup = d.duplicated([c for c in d.columns if c != "_row"], keep="first")
    if full_dup.any():
        issues.append(Issue("*", "deliveries", "warning", "Exact duplicate delivery rows removed", int(full_dup.sum())))
        d = d[~full_dup]
    key_dup = d.duplicated(keycols, keep=False)
    if key_dup.any():
        issues.append(Issue("*", "deliveries", "warning", "Deliveries sharing the same over/ball position but different content (kept)", int(key_dup.sum())))
    missing_matches = valid - set(zip(d["gender"], d["match_id"]))
    if missing_matches:
        issues.append(Issue("*", "matches", "warning", "Matches without any ball-by-ball data (kept for results only)", len(missing_matches)))
    t["deliveries"] = d.reset_index(drop=True)
    return CleanBundle(tables=t, issues=issues, excluded_matches=excluded)


def write_combined(clean_bundle: CleanBundle, out_dir: Path) -> list[Path]:
    """Write the 10 combined (gender-tagged) datasets to data/processed/combined."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in clean_bundle.tables.items():
        p = out_dir / f"{name}.csv"
        df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore").to_csv(p, index=False, date_format="%Y-%m-%d")
        written.append(p)
    return written
