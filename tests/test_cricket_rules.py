"""Cricket-rule correctness on a hand-built match with known answers."""

from __future__ import annotations

import pytest

from cricketiq.analytics.facts import build_facts
from cricketiq.processing.reconstruct import build_core


@pytest.fixture()
def built(tiny_tables, settings):
    core = build_core(tiny_tables, settings)
    return core, build_facts(core, settings)


def _bat(facts, mid, inn, player):
    b = facts.bat
    return b[(b.match_id == mid) & (b.innings_number == inn) & (b.player == player)].iloc[0]


def _bowl(facts, mid, inn, player):
    o = facts.bowl
    return o[(o.match_id == mid) & (o.innings_number == inn) & (o.player == player)].iloc[0]


def test_innings_total_includes_all_extras(built):
    core, _ = built
    inn = core.innings.set_index(["match_id", "innings_number"])
    # wide 1 + nb(1+2) + bye 1 + 4 + 1 = 10
    assert inn.loc[("m1", 1), "runs"] == 10
    assert inn.loc[("m1", 1), "extras"] == 3


def test_wides_not_faced_noballs_faced(built):
    _, f = built
    a1 = _bat(f, "m1", 1, "A1")
    # A1 faced: nb(2 runs), bye, dot, single -> 4 balls (wide excluded), runs 3
    assert a1["balls"] == 4
    assert a1["runs"] == 3


def test_bowler_charged_wides_and_noballs_not_byes(built):
    _, f = built
    x = _bowl(f, "m1", 1, "X")
    # wide 1 + nb 1 + bat 2 + 4 + 1 = 9 (bye excluded)
    assert x["runs"] == 9
    assert x["balls"] == 5          # 7 deliveries - wide - no-ball
    assert x["wides"] == 1 and x["no_balls"] == 1


def test_retired_hurt_is_not_out_and_not_team_wicket(built):
    core, f = built
    assert _bat(f, "m1", 1, "A2")["out"] == 0
    # wickets: bowled, run out, caught, timed out = 4 (retired hurt excluded)
    assert core.innings.set_index(["match_id", "innings_number"]).loc[("m1", 1), "wkts"] == 4


def test_bowler_credited_wickets_exclude_run_out_and_timed_out(built):
    _, f = built
    y = _bowl(f, "m1", 1, "Y")
    assert y["wkts"] == 2           # bowled + caught


def test_non_striker_run_out_counts_for_that_batter(built):
    _, f = built
    a1 = _bat(f, "m1", 1, "A1")
    assert a1["out"] == 1 and a1["how_out"] == "run out"


def test_timed_out_batter_has_an_innings(built):
    _, f = built
    a6 = _bat(f, "m1", 1, "A6")
    assert a6["balls"] == 0 and a6["out"] == 1


def test_maiden_requires_six_legal_balls_no_runs(built):
    _, f = built
    assert _bowl(f, "m1", 1, "Y")["maidens"] == 1
    assert _bowl(f, "m1", 1, "X")["maidens"] == 0


def test_batting_position_by_arrival(built):
    _, f = built
    pos = {p: _bat(f, "m1", 1, p)["position"] for p in ("A1", "A2", "A3", "A4", "A5")}
    assert pos == {"A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5}


def test_partnerships_sum_to_innings_and_split_correctly(built):
    core, f = built
    p = f.part[(f.part.match_id == "m1") & (f.part.innings_number == 1)]
    assert p["runs"].sum() == 10
    assert ((p["p1_runs"] + p["p2_runs"] + p["extras"]) == p["runs"]).all()
    first = p.iloc[0]
    assert {first.player_1, first.player_2} == {"A1", "A2"} and first.runs == 9


def test_super_over_excluded_from_stats_but_decides_winner(built):
    core, f = built
    m = core.matches.set_index("match_id")
    assert m.loc["m2", "result"] == "tie"
    assert m.loc["m2", "super_over_winner"] == "A"
    assert m.loc["m2", "effective_winner"] == "A"
    assert _bat(f, "m2", 1, "A1")["runs"] == 4    # super-over 6 not added
    assert not ((f.bat.match_id == "m2") & (f.bat.innings_number > 2)).any()


def test_chase_result_and_margin(built):
    core, f = built
    m = core.matches.set_index("match_id")
    assert m.loc["m1", "result"] == "won" and m.loc["m1", "winner"] == "B"
    assert m.loc["m1", "margin_wkts"] == 10
    assert _bat(f, "m1", 2, "B1")["result"] == "W"
    assert _bat(f, "m1", 1, "A1")["result"] == "L"


def test_expected_values_present_and_positive(built):
    _, f = built
    assert (f.bat["exp_runs"] >= 0).all()
    assert f.bowl["exp_runs"].notna().all()
