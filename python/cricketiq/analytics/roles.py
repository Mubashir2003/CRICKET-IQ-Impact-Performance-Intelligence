"""Rule-based role inference from performance patterns and opportunities.

Roles are never guessed from names or reputation: every rule uses where a player
actually batted/bowled (ball shares by phase, batting position) and how they
performed relative to comparable deliveries. A player can hold several roles.
Spin-specific roles need bowler-type data; supply it in ``config/bowler_types.csv``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Settings
from .metrics import KEY, div

BATTER_ROLES = ["Powerplay Aggressor", "Top-order Stabilizer", "Middle-order Controller", "Spin Attacker", "Finisher", "Pressure Specialist", "Flexible Batter"]
BOWLER_ROLES = ["Powerplay Wicket-taker", "Middle-over Controller", "Spin Pressure Specialist", "Death-over Specialist", "Boundary Suppressor", "Partnership Breaker"]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=df.index)


def infer_roles(met: pd.DataFrame, bat: pd.DataFrame, part: pd.DataFrame, deliveries: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    r = settings["roles"]
    out = met[KEY].copy()
    pos = bat.groupby(KEY)["position"].median().rename("median_position")
    out = out.join(pos, on=KEY)
    dist = bat.groupby([*KEY, "position"]).size().reset_index(name="n")
    fx = r["batter"]["flexible_batter"]
    flex = dist[dist["n"] >= fx["min_innings_per_position"]].groupby(KEY)["position"].nunique().rename("distinct_positions")
    out = out.join(flex, on=KEY)

    # primary role
    pr = r["primary"]
    bat_bpi = div(_num(met, "balls"), _num(met, "bat_innings"))
    bowl_share = div(_num(met, "bowl_innings"), _num(met, "matches_in_scope"))
    bowl_bpi = div(_num(met, "legal_balls"), _num(met, "bowl_innings"))
    is_bat = (np.nan_to_num(bat_bpi) >= pr["batter_min_balls_per_innings"]) & (out["median_position"].fillna(11) <= pr["batter_max_median_position"])
    is_bowl = (np.nan_to_num(bowl_share) >= pr["bowler_min_innings_share"]) & (np.nan_to_num(bowl_bpi) >= pr["bowler_min_balls_per_innings"])
    fallback = np.where(_num(met, "legal_balls").fillna(0) > _num(met, "balls").fillna(0), "Bowler", "Batter")
    out["primary_role"] = np.select([is_bat & is_bowl, is_bowl, is_bat], ["All-Rounder", "Bowler", "Batter"], default=fallback)

    # spin data (optional)
    bt = settings.bowler_types
    spin_ok = bool(bt)
    spin_bat = pd.DataFrame(columns=[*KEY, "sp_balls", "sp_runs", "sp_exp"])
    if spin_ok:
        d = deliveries[deliveries["faced"]].copy()
        d["btype"] = [bt.get((g, b)) for g, b in zip(d["gender"], d["bowler"])]
        sp = d[d["btype"] == "spin"]
        spin_bat = sp.groupby(["gender", "batter"]).agg(sp_balls=("faced", "size"), sp_runs=("batter_runs", "sum"), sp_exp=("exp_r", "sum")).reset_index().rename(columns={"batter": "player"})
    out = out.merge(spin_bat, on=KEY, how="left")

    b = r["batter"]
    roles_bat: list[list[str]] = [[] for _ in range(len(out))]

    def add(mask, name, bucket):
        for i in np.flatnonzero(np.asarray(mask, dtype=bool)):
            bucket[i].append(name)

    m = met.copy().set_index(KEY).reindex(pd.MultiIndex.from_frame(out[KEY])).reset_index()
    c = b["powerplay_aggressor"]
    add((_num(m, "pp_ball_share") >= c["min_phase_ball_share"]) & (_num(m, "pp_balls") >= c["min_phase_balls"]) & (_num(m, "pp_sr_index") >= c["min_sr_index"]), "Powerplay Aggressor", roles_bat)
    c = b["top_order_stabilizer"]
    add((out["median_position"] <= c["max_median_position"]) & (_num(m, "average_ratio") >= c["min_avg_index"]) & (_num(m, "bat_innings") >= c["min_innings"]), "Top-order Stabilizer", roles_bat)
    c = b["middle_order_controller"]
    add((_num(m, "mid_ball_share") >= c["min_phase_ball_share"]) & (_num(m, "mid_balls") >= c["min_phase_balls"]) & (_num(m, "mid_sr_index") >= c["min_sr_index"]) & (_num(m, "mid_dot_index") <= c["max_dot_index"]), "Middle-order Controller", roles_bat)
    if spin_ok:
        c = b["spin_attacker"]
        add((out["sp_balls"] >= c["min_balls_vs_spin"]) & (div(out["sp_runs"], out["sp_exp"]) >= c["min_sr_index_vs_spin"]), "Spin Attacker", roles_bat)
    c = b["finisher"]
    add((_num(m, "dth_ball_share") >= c["min_phase_ball_share"]) & (_num(m, "dth_balls") >= c["min_phase_balls"]) & (out["median_position"] >= c["min_median_position"]) & (_num(m, "dth_sr_index") >= c["min_sr_index"]), "Finisher", roles_bat)
    c = b["pressure_specialist"]
    add((_num(m, "pressure_balls") >= c["min_pressure_balls"]) & (_num(m, "pressure_sr_delta") >= c["min_pressure_sr_delta"]), "Pressure Specialist", roles_bat)
    c = b["flexible_batter"]
    add(out["distinct_positions"].fillna(0) >= c["min_distinct_positions"], "Flexible Batter", roles_bat)

    o = r["bowler"]
    roles_bowl: list[list[str]] = [[] for _ in range(len(out))]
    c = o["powerplay_wicket_taker"]
    add((_bowl_share(m, "pp") >= c["min_phase_ball_share"]) & (_num(m, "bpp_balls") >= c["min_phase_balls"]) & (_num(m, "bpp_wicket_index") >= c["min_wicket_index"]), "Powerplay Wicket-taker", roles_bowl)
    c = o["middle_over_controller"]
    add((_bowl_share(m, "mid") >= c["min_phase_ball_share"]) & (_num(m, "bmid_balls") >= c["min_phase_balls"]) & (_num(m, "bmid_economy_index") <= c["max_economy_index"]), "Middle-over Controller", roles_bowl)
    if spin_ok:
        c = o["spin_pressure_specialist"]
        spinner = pd.Series([bt.get((g, p)) == "spin" for g, p in zip(out["gender"], out["player"])], index=out.index)
        add(spinner & (_num(m, "legal_balls") >= c["min_balls"]) & (_num(m, "dot_index") >= c["min_dot_index"]) & (_num(m, "economy_index") <= c["max_economy_index"]), "Spin Pressure Specialist", roles_bowl)
    c = o["death_over_specialist"]
    add((_bowl_share(m, "dth") >= c["min_phase_ball_share"]) & (_num(m, "bdth_balls") >= c["min_phase_balls"]) & (_num(m, "bdth_economy_index") <= c["max_economy_index"]), "Death-over Specialist", roles_bowl)
    c = o["boundary_suppressor"]
    add((_num(m, "legal_balls") >= c["min_balls"]) & (_num(m, "boundary_index") <= c["max_boundary_index"]), "Boundary Suppressor", roles_bowl)
    c = o["partnership_breaker"]
    br = part[part["broken_by"].notna() & (part["runs"] >= c["min_partnership_runs"])].groupby(["gender", "broken_by"]).size()
    breaks = pd.Series([br.get((g, p), 0) for g, p in zip(out["gender"], out["player"])], index=out.index)
    out["big_partnerships_broken"] = breaks
    add(breaks >= c["min_breaks"], "Partnership Breaker", roles_bowl)

    out["batting_roles"] = roles_bat
    out["bowling_roles"] = roles_bowl
    out["spin_roles_available"] = spin_ok
    return out[[*KEY, "primary_role", "median_position", "distinct_positions", "batting_roles", "bowling_roles", "big_partnerships_broken", "spin_roles_available"]]


def _bowl_share(m: pd.DataFrame, ph: str) -> pd.Series:
    """Share of a bowler's legal balls delivered in phase ``ph``."""
    return pd.Series(div(_num(m, f"b{ph}_balls"), _num(m, "legal_balls")), index=m.index)
