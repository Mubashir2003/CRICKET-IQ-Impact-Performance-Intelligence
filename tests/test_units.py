"""Unit tests for ingestion, baselines, metrics helpers, impact and export."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from cricketiq.analytics.baselines import hier_expect
from cricketiq.analytics.impact import impact_indices
from cricketiq.analytics.metrics import div
from cricketiq.export.dashboard import _clean
from cricketiq.ingestion.loader import IngestionError, read_table
from cricketiq.ingestion.schema import SCHEMAS


def test_loader_resolves_aliases_and_keeps_missing(tmp_path):
    p = tmp_path / "matches.csv"
    p.write_text("﻿match_id,start_date,event_name,team1,team2,winner,result\nx1,2026-02-01,Cup,A,B,,no result\nx2,2026-02-02,Cup,A,B,A,\n", encoding="utf-8")
    df, rep, issues = read_table(p, SCHEMAS["matches"], "men")
    assert {"date", "competition", "team_1", "team_2"} <= set(df.columns)
    assert df["winner"].isna().sum() == 1          # missing stays missing
    assert df["gender"].eq("men").all()
    assert rep["renamed"]


def test_loader_reports_missing_required_columns(tmp_path):
    p = tmp_path / "matches.csv"
    p.write_text("match_id,date\n1,2026-01-01\n", encoding="utf-8")
    with pytest.raises(IngestionError):
        read_table(p, SCHEMAS["matches"], "men")


def test_numeric_coercion_flags_bad_values_without_zero_fill(tmp_path):
    p = tmp_path / "player_appearances.csv"
    p.write_text("player,matches_played\nA,12\nB,abc\n", encoding="utf-8")
    df, _, issues = read_table(p, SCHEMAS["player_appearances"], "women")
    assert pd.isna(df.loc[1, "matches_played"])
    assert any("could not be parsed" in i.message for i in issues)


def test_hier_expect_backs_off_to_broader_level():
    rows = pd.DataFrame({"g": ["a"] * 10 + ["b"] * 2, "v": [1.0] * 10 + [0.0] * 2, "all": ["x"] * 12})
    e = hier_expect(rows, ["v"], [["g"], ["all"]], min_n=5)
    assert e.loc[0, "v"] == 1.0                         # bucket a has 10 rows -> own mean
    assert e.loc[11, "v"] == pytest.approx(10 / 12)     # bucket b too small -> overall mean


def test_div_returns_nan_not_zero():
    out = div([5, 3], [0, 2])
    assert math.isnan(out[0]) and out[1] == 1.5


def test_impact_does_not_score_non_bowler_as_zero(settings):
    n = 40
    rng = np.random.default_rng(0)
    met = pd.DataFrame({
        "gender": ["men"] * n, "player": [f"p{i}" for i in range(n)],
        "balls": rng.integers(100, 600, n), "bat_innings": 20, "runs_above_expected": rng.normal(0, 30, n),
        "sr_above_avg": rng.normal(0, 10, n), "runs": 400, "outs": 15, "expected_runs": 380, "expected_outs": 16,
        "team_run_contribution_pct": rng.normal(15, 4, n), "consistency_index": rng.normal(55, 8, n),
        "legal_balls": [0] * 20 + list(rng.integers(150, 400, 20)), "runs_saved_per_24": rng.normal(0, 3, n),
        "wkts_above_exp_per_24": rng.normal(0, .3, n), "dot_ball_index": 100, "boundary_suppression_index": 100,
        "bowling_consistency": 50, "pressure_balls": 50, "pressure_balls_bowled": 0, "pressure_runs_above_expected": rng.normal(0, 5, n),
        "pressure_runs_saved": 0, "matches_in_scope": 20, "winning_run_share_pct": 20, "winning_wicket_share_pct": np.nan,
        "match_winning_pct": 5, "avg_match_score_in_wins": 3,
    })
    imp = impact_indices(met, settings)
    assert imp.loc[:19, "bowling_impact"].isna().all()       # did not bowl -> n/a, not 0
    assert imp.loc[20:, "bowling_impact"].notna().all()
    assert imp["overall_impact"].between(0, 100).all()


def test_export_clean_handles_nan_and_numpy():
    assert _clean(float("nan")) is None
    assert _clean(np.int64(3)) == 3
    assert _clean(2.0) == 2
    assert _clean(np.float64(1.23456), 2) == 1.23
    assert _clean([np.nan, 1.5]) == [None, 1.5]
