"""Batting-position analysis and the (experimental) Position Effectiveness Index.

PEI for a player at a position group =
    w1*z(runs per innings) + w2*z(team run share) + w3*z(strike rate vs expected)
  + w4*z(pressure runs above expected per pressure ball, shrunk)
z-scores are computed within gender and position group across players with at
least ``min_innings`` innings there; the composite is shrunk toward 0 with
n/(n + k) and converted to a 0-100 percentile. Split-half reliability (odd vs even
innings) is reported in the validation output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Settings
from .metrics import div


def _z(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and np.isfinite(sd) and sd > 0 else s * 0


def position_table(bat: pd.DataFrame) -> pd.DataFrame:
    """League-wide stats by gender and batting position 1-11."""
    b = bat.copy()
    b["bnd_runs"] = b["fours"] * 4 + b["sixes"] * 6
    b["w_runs"] = np.where(b["result"] == "W", b["runs"], 0)
    b["w_team"] = np.where(b["result"] == "W", b["team_runs"], 0)
    g = b.groupby(["gender", "position"])
    a = g[["runs", "balls", "out", "dots", "bnd_runs", "team_runs", "w_runs", "w_team", "pp_runs", "mid_runs", "dth_runs", "pp_balls", "mid_balls", "dth_balls"]].sum()
    a["innings"] = g.size()
    a = a.reset_index()
    a["average"] = div(a["runs"], a["out"])
    a["strike_rate"] = div(a["runs"], a["balls"], 100)
    a["boundary_pct"] = div(a["bnd_runs"], a["runs"], 100)
    a["dot_pct"] = div(a["dots"], a["balls"], 100)
    a["team_contribution_pct"] = div(a["runs"], a["team_runs"], 100)
    a["win_contribution_pct"] = div(a["w_runs"], a["w_team"], 100)
    return a


def _pei_raw(b: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    cfg = settings["position_effectiveness"]
    g = b.groupby(["gender", "pos_group", "player"])
    a = g[["runs", "balls", "exp_runs", "team_runs", "p_runs", "p_exp_runs", "p_balls"]].sum()
    a["innings"] = g.size()
    a = a.reset_index()
    a = a[a["innings"] >= cfg["min_innings"]].copy()
    if a.empty:
        return a
    a["run_production"] = a["runs"] / a["innings"]
    a["team_contribution"] = div(a["runs"], a["team_runs"], 100)
    a["scoring_efficiency"] = div(a["runs"] - a["exp_runs"], a["balls"], 100)
    pr = div(a["p_runs"] - a["p_exp_runs"], a["p_balls"], 100)
    a["pressure_performance"] = np.nan_to_num(pr) * (a["p_balls"] / (a["p_balls"] + 30))
    w = cfg["weights"]
    comp = np.zeros(len(a))
    for k, wt in w.items():
        comp += wt * a.groupby(["gender", "pos_group"])[k].transform(_z).fillna(0).to_numpy()
    k = cfg["shrinkage_innings"]
    a["pei_raw"] = comp * a["innings"] / (a["innings"] + k)
    return a


def position_effectiveness(bat: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, dict]:
    a = _pei_raw(bat, settings)
    if a.empty:
        return a, {}
    a["pei"] = a.groupby(["gender", "pos_group"])["pei_raw"].rank(pct=True) * 100
    # split-half reliability
    b = bat.sort_values("match_id").copy()
    b["half"] = b.groupby(["gender", "player", "pos_group"]).cumcount() % 2
    h0 = _pei_raw(b[b["half"] == 0], settings)
    h1 = _pei_raw(b[b["half"] == 1], settings)
    rel = {}
    if not h0.empty and not h1.empty:
        j = h0.merge(h1, on=["gender", "pos_group", "player"], suffixes=("_a", "_b"))
        for (g, pg), sub in j.groupby(["gender", "pos_group"]):
            if len(sub) >= 10:
                rel[f"{g}/{pg}"] = {"players": int(len(sub)), "spearman": round(float(sub["pei_raw_a"].rank().corr(sub["pei_raw_b"].rank())), 3)}
    keep = ["gender", "pos_group", "player", "innings", "runs", "balls", "run_production", "team_contribution", "scoring_efficiency", "pressure_performance", "pei"]
    return a[keep], rel
