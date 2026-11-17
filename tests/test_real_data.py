"""Integration checks against the real supplied data (skipped if it is absent)."""

from __future__ import annotations

import json

import pytest

from cricketiq.config import Paths

P = Paths()
HAS_DATA = (P.raw / "men" / "deliveries.csv").exists() or (P.raw / "women" / "deliveries.csv").exists()
HAS_REPORT = (P.processed / "validation_report.json").exists()
HAS_JSON = (P.dashboard_data / "manifest.json").exists()


@pytest.mark.skipif(not HAS_REPORT, reason="run `python run.py` first")
def test_no_failed_validation_checks():
    rep = json.loads((P.processed / "validation_report.json").read_text())
    failed = [c["name"] for c in rep["checks"] if c["status"] == "fail"]
    assert not failed, failed


@pytest.mark.skipif(not HAS_REPORT, reason="run `python run.py` first")
def test_scorecards_match_upstream_exactly():
    rep = json.loads((P.processed / "validation_report.json").read_text())
    by = {c["name"]: c for c in rep["checks"]}
    for name in ("Batting scorecards: runs", "Batting scorecards: balls", "Bowling scorecards: runs", "Bowling scorecards: wkts", "Bowling scorecards: balls"):
        if name in by:
            assert by[name]["mismatches"] == 0, name


@pytest.mark.skipif(not HAS_JSON, reason="run `python run.py` first")
def test_dashboard_json_is_complete_and_gender_separated():
    man = json.loads((P.dashboard_data / "manifest.json").read_text())
    assert man["genders"]
    for g in man["genders"]:
        d = P.dashboard_data / g["key"]
        for f in ("core.json", "bat.json", "bowl.json", "part.json", "teaminn.json", "players.json"):
            assert (d / f).exists(), f
        core = json.loads((d / "core.json").read_text())
        players = json.loads((d / "players.json").read_text())
        assert core["gender"] == g["key"]
        assert len(players["rows"]) == core["n_eligible"] == g["eligible_players"]
        assert all(r["i"] < core["n_eligible"] for r in players["rows"])
        assert len(list((d / "matches").glob("*.json"))) == g["matches"]
        bat = json.loads((d / "bat.json").read_text())
        n = len(bat["m"])
        assert all(len(v) == n for v in bat.values())


@pytest.mark.skipif(not HAS_JSON, reason="run `python run.py` first")
def test_dashboard_json_contains_no_technical_leaks():
    text = (P.dashboard_data / "manifest.json").read_text() + (P.dashboard_data / "definitions.json").read_text()
    for word in (".csv", "pandas", "python", "json", "traceback"):
        assert word not in text.lower(), word
