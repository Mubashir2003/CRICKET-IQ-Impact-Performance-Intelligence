"""The 11-distinct-match eligibility rule."""

from __future__ import annotations

import pandas as pd

from cricketiq.processing.players import build_players
from cricketiq.processing.reconstruct import build_core

from .conftest import Builder, _prep


def _season(n_matches: int, extra_player_matches: int, settings):
    frames, rows = [], []
    for i in range(n_matches):
        b = Builder(f"g{i}")
        b.ball(1, 1, "Regular", "Partner", "Bowler1")
        b.ball(1, 1, "Regular", "Partner", "Bowler1")          # same match twice -> counts once
        if i < extra_player_matches:
            b.ball(1, 1, "Occasional", "Partner", "Bowler1")
        b.ball(2, 1, "Opp1", "Opp2", "Bowler2", bt="B", wt="A")
        frames.append(b.frame())
        rows.append({"gender": "men", "match_id": f"g{i}", "date": pd.Timestamp("2026-03-01") + pd.Timedelta(days=i), "match_type": "T20",
                     "competition": "Cup", "season": "2026", "venue": "V", "city": "C", "team_1": "A", "team_2": "B", "winner": "A", "result_type": None})
    d = _prep(pd.concat(frames, ignore_index=True)).drop(columns=["date", "competition"])
    return {"matches": pd.DataFrame(rows), "deliveries": d}


def test_threshold_counts_distinct_matches(settings):
    t = _season(11, 10, settings)
    core = build_core(t, settings)
    reg = build_players(core, t, settings)
    p = reg.players.set_index("player")
    assert p.loc["Regular", "distinct_matches"] == 11 and p.loc["Regular", "eligible"]
    assert p.loc["Occasional", "distinct_matches"] == 10 and not p.loc["Occasional", "eligible"]
    # audit keeps everybody, nothing is discarded
    assert set(reg.audit["player"]) >= {"Regular", "Occasional"}


def test_upstream_appearances_act_as_lower_bound(settings):
    t = _season(3, 0, settings)
    t["player_appearances"] = pd.DataFrame({"gender": ["men"], "player": ["Regular"], "matches_played": [12]})
    core = build_core(t, settings)
    reg = build_players(core, t, settings)
    assert bool(reg.players.set_index("player").loc["Regular", "eligible"])


def test_countries_only_from_internationals(settings):
    t = _season(2, 0, settings)
    t["matches"].loc[0, ["team_1", "team_2"]] = ["India", "Nepal"]
    t["deliveries"].loc[t["deliveries"].match_id == "g0", "batting_team"] = t["deliveries"].loc[t["deliveries"].match_id == "g0", "batting_team"].map({"A": "India", "B": "Nepal"})
    t["deliveries"].loc[t["deliveries"].match_id == "g0", "bowling_team"] = t["deliveries"].loc[t["deliveries"].match_id == "g0", "bowling_team"].map({"A": "India", "B": "Nepal"})
    core = build_core(t, settings)
    reg = build_players(core, t, settings)
    p = reg.players.set_index("player")
    assert p.loc["Regular", "countries"] == ["India"]       # franchise team "A" not treated as a country
