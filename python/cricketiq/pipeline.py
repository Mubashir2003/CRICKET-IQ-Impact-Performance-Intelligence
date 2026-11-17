"""End-to-end pipeline: CSV -> clean -> reconstruct -> analytics -> validate -> JSON."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

import pandas as pd

from .analytics.facts import build_facts
from .analytics.impact import impact_indices, reliability
from .analytics.metrics import KEY, all_metrics, scope
from .analytics.positions import position_effectiveness, position_table
from .analytics.roles import infer_roles
from .config import Paths, load_settings
from .export.dashboard import export_dashboard
from .ingestion.loader import load_raw
from .processing.cleaning import clean, write_combined
from .processing.players import build_players
from .processing.reconstruct import build_core
from .validation.checks import run_checks, to_markdown

log = logging.getLogger("cricketiq")

COMP_FIELDS = [
    "matches_in_scope", "wins", "losses", "win_rate", "bat_innings", "runs", "balls", "outs", "average", "strike_rate", "highest", "fours", "sixes", "fifties", "hundreds",
    "team_run_contribution_pct", "boundary_pct", "dot_pct", "consistency_index", "impact_innings_pct", "runs_above_expected", "sr_above_avg",
    "powerplay_aggression_index", "middle_over_control_index", "death_finishing_index", "chase_contribution_pct", "chase_success_contribution_pct",
    "chase_failure_contribution_pct", "pressure_balls", "pressure_sr", "pressure_avg", "pressure_sr_delta",
    "bowl_innings", "legal_balls", "runs_conceded", "wickets", "bowling_average", "economy", "bowling_sr", "bowl_dot_pct", "wicket_contribution_pct",
    "dot_ball_share_pct", "boundary_prevention_rate", "runs_saved", "runs_saved_per_24", "economy_advantage", "boundary_suppression_index",
    "pressure_bowling_index", "pressure_economy", "pressure_economy_delta", "death_over_effectiveness", "bowling_consistency",
    "winning_run_share_pct", "winning_wicket_share_pct", "wins_significant", "wins_exceptional", "match_winning_pct", "runs_in_victories", "wickets_in_victories",
]


def run(paths: Paths | None = None, export: bool = True) -> dict[str, Any]:
    t0 = time.time()
    paths = paths or Paths()
    settings = load_settings(paths)
    log.info("Step 1/7  Reading input CSV files")
    raw = load_raw(paths, settings)
    log.info("Step 2/7  Cleaning and merging")
    cb = clean(raw, settings)
    write_combined(cb, paths.processed / "combined")
    log.info("Step 3/7  Reconstructing matches, innings and deliveries")
    core = build_core(cb.tables, settings)
    reg = build_players(core, cb.tables, settings)
    log.info("Step 4/7  Computing fact tables and expected-value baselines")
    facts = build_facts(core, settings)

    log.info("Step 5/7  Player analytics (batting, bowling, winning, pressure, roles, impact)")
    elig = reg.players[reg.players["eligible"]][KEY]
    sf_all = scope(facts, reg, core)
    met = all_metrics(sf_all, settings)
    met = elig.merge(met, on=KEY, how="left").copy()
    roles = infer_roles(met, facts.bat, facts.part, facts.deliveries, settings)
    imp = impact_indices(met, settings)
    full = reg.players[reg.players["eligible"]].merge(met, on=KEY, how="left").merge(roles, on=KEY, how="left").merge(imp, on=KEY, how="left").copy()

    by_comp_frames = []
    for comp, ids in core.matches.groupby("competition")["match_id"]:
        sm = all_metrics(scope(facts, reg, core, set(ids)), settings)
        sm = elig.merge(sm, on=KEY, how="inner")
        sm = sm[sm["matches_in_scope"].fillna(0) > 0]
        if sm.empty:
            continue
        sm = sm[[*KEY, *[c for c in COMP_FIELDS if c in sm.columns]]].copy()
        sm["competition"] = comp
        by_comp_frames.append(sm)
    by_comp = pd.concat(by_comp_frames, ignore_index=True) if by_comp_frames else pd.DataFrame(columns=[*KEY, "competition"])

    eb = facts.bat.merge(elig, on=KEY)
    pei, pei_rel = position_effectiveness(eb, settings)
    pos_tab = position_table(facts.bat)

    # split-half reliability of the experimental indices (odd/even matches by date)
    order = core.matches.sort_values("date")["match_id"].tolist()
    half_a, half_b = set(order[0::2]), set(order[1::2])
    ma = elig.merge(all_metrics(scope(facts, reg, core, half_a), settings), on=KEY)
    mb = elig.merge(all_metrics(scope(facts, reg, core, half_b), settings), on=KEY)
    imp_rel = reliability(ma, mb, settings)

    log.info("Step 6/7  Validating")
    checks = run_checks(cb.tables, core, facts)
    issues = [i.as_dict() for i in (*cb.issues, *core.issues, *reg.issues)]
    vdir = paths.processed
    vdir.mkdir(parents=True, exist_ok=True)
    report = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "checks": [c.as_dict() for c in checks],
        "issues": issues,
        "schema": raw.schema_report,
        "reliability": {"impact_split_half": imp_rel, "position_effectiveness_split_half": pei_rel},
        "eligibility": {g: {"eligible": int(s["eligible"].sum()), "total": int(len(s))} for g, s in reg.players.groupby("gender")},
    }
    (vdir / "validation_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (vdir / "validation_report.md").write_text(
        to_markdown(checks, {"generated": report["generated"], "Data-quality issues": "\n".join(f"[{i['severity']}] {i['gender']}/{i['table']}: {i['message']} ({i['count']})" for i in issues),
                             "Index reliability (split-half Spearman)": json.dumps(report["reliability"], indent=2), "Eligibility": json.dumps(report["eligibility"], indent=2)}),
        encoding="utf-8",
    )
    reg.audit.to_csv(vdir / "eligibility_audit.csv", index=False)
    cb.excluded_matches.to_csv(vdir / "excluded_matches.csv", index=False)
    an = vdir / "analytics"
    an.mkdir(exist_ok=True)
    core.matches.to_csv(an / "matches_enriched.csv", index=False)
    facts.bat.to_csv(an / "batting_innings_reconstructed.csv", index=False)
    facts.bowl.to_csv(an / "bowling_innings_reconstructed.csv", index=False)
    facts.part.to_csv(an / "partnerships_reconstructed.csv", index=False)
    facts.team_inn.to_csv(an / "team_innings.csv", index=False)
    facts.player_match.to_csv(an / "player_match_contributions.csv", index=False)
    full.to_csv(an / "player_metrics.csv", index=False)
    by_comp.to_csv(an / "player_metrics_by_competition.csv", index=False)
    pei.to_csv(an / "position_effectiveness.csv", index=False)

    failed = [c for c in checks if c.status == "fail"]
    sizes: dict[str, int] = {}
    if export:
        log.info("Step 7/7  Exporting dashboard JSON")
        ctx = {"core": core, "facts": facts, "registry": reg, "players_full": full, "by_comp": by_comp, "pei": pei, "position_table": pos_tab}
        sizes = export_dashboard(paths.dashboard_data, settings, ctx)
    summary = {
        "seconds": round(time.time() - t0, 1),
        "matches": core.matches.groupby("gender").size().to_dict(),
        "eligible": report["eligibility"],
        "checks": pd.Series([c.status for c in checks]).value_counts().to_dict(),
        "failed_checks": [c.name for c in failed],
        "json_bytes": sum(sizes.values()),
    }
    return summary
