"""Per-innings fact tables (batting, bowling, partnerships, team innings).

Every fact row carries actual AND expected values (from :mod:`baselines`), so any
filtered aggregation (sum of actual minus sum of expected) stays opportunity- and
competition-adjusted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import Settings
from ..processing.reconstruct import INN, Core
from .baselines import hier_expect

PHASES = ("powerplay", "middle", "death")
PH_SHORT = {"powerplay": "pp", "middle": "mid", "death": "dth"}


@dataclass
class Facts:
    bat: pd.DataFrame
    bowl: pd.DataFrame
    part: pd.DataFrame
    team_inn: pd.DataFrame
    player_match: pd.DataFrame
    deliveries: pd.DataFrame


def _result_for(df: pd.DataFrame, matches: pd.DataFrame, team_col: str) -> pd.Series:
    """Result letter (W/L/T/N) for the team in ``team_col`` in each row's match."""
    mm = matches.set_index("match_id")
    res = df["match_id"].map(mm["result"])
    ew = df["match_id"].map(mm["effective_winner"])
    out = np.select(
        [res.eq("no result"), ew.notna() & (ew == df[team_col]), ew.notna() & (ew != df[team_col]), res.eq("tie")],
        ["N", "W", "L", "T"],
        default="N",
    )
    return pd.Series(out, index=df.index)


def _pivot_phase(rows: pd.DataFrame, keys: list[str], cols: dict[str, str]) -> pd.DataFrame:
    """Sum ``cols`` per key and phase -> wide columns like ``pp_runs``."""
    if rows.empty:
        return pd.DataFrame(columns=keys)
    agg = rows.groupby([*keys, "phase"])[list(cols)].sum()
    wide = agg.unstack("phase", fill_value=0)
    wide.columns = [f"{PH_SHORT.get(ph, ph)}_{cols[c]}" for c, ph in wide.columns]
    for ph in PHASES:
        for c in cols.values():
            name = f"{PH_SHORT[ph]}_{c}"
            if name not in wide.columns:
                wide[name] = 0
    return wide.reset_index()


def build_facts(core: Core, settings: Settings) -> Facts:
    d = core.deliveries
    reg = d[~d["super_over"]].copy()
    m = core.matches
    bmin = settings["baselines"]["min_balls"]
    pmin = settings["baselines"]["min_balls_pressure"]

    # ------------------------------------------------------------ batting expectations
    faced = reg[reg["faced"]]
    reg[["exp_r", "exp_out", "exp_4", "exp_6", "exp_dot"]] = np.nan
    e = hier_expect(
        faced, ["batter_runs", "striker_out", "four", "six", "bat_dot"],
        [["gender", "competition", "phase", "pos_group"], ["gender", "competition", "phase"], ["gender", "comp_type", "phase", "pos_group"], ["gender", "phase"]],
        bmin,
    )
    reg.loc[faced.index, ["exp_r", "exp_out", "exp_4", "exp_6", "exp_dot"]] = e.to_numpy()
    pf = faced[faced["pressure"]]
    reg[["exp_pr", "exp_pout"]] = 0.0
    if len(pf):
        ep = hier_expect(pf, ["batter_runs", "striker_out"], [["gender", "comp_type", "phase"], ["gender", "phase"]], pmin)
        reg.loc[pf.index, ["exp_pr", "exp_pout"]] = ep.to_numpy()

    # ------------------------------------------------------------ bowling expectations
    e2 = hier_expect(
        reg, ["bowler_runs", "bowler_wkts", "boundary"],
        [["gender", "competition", "phase"], ["gender", "comp_type", "phase"], ["gender", "phase"]], bmin,
    )
    reg[["exp_conc", "exp_wk", "exp_bnd"]] = e2.to_numpy()
    legal = reg[reg["legal"]]
    reg["exp_bdot"] = 0.0
    e3 = hier_expect(legal, ["bowl_dot"], [["gender", "competition", "phase"], ["gender", "comp_type", "phase"], ["gender", "phase"]], bmin)
    reg.loc[legal.index, "exp_bdot"] = e3["bowl_dot"].to_numpy()
    pr = reg[reg["pressure"]]
    reg[["exp_pconc", "exp_pwk"]] = 0.0
    if len(pr):
        e4 = hier_expect(pr, ["bowler_runs", "bowler_wkts"], [["gender", "comp_type", "phase"], ["gender", "phase"]], pmin)
        reg.loc[pr.index, ["exp_pconc", "exp_pwk"]] = e4.to_numpy()

    bat = _batting(reg, core, settings)
    bowl = _bowling(reg, core, settings)
    part = _partnerships(reg, core, settings)
    team_inn = _team_innings(reg, core)
    pm = _player_match(bat, bowl, m, settings)
    return Facts(bat=bat, bowl=bowl, part=part, team_inn=team_inn, player_match=pm, deliveries=reg)


# ---------------------------------------------------------------------------- batting
def _batting(reg: pd.DataFrame, core: Core, settings: Settings) -> pd.DataFrame:
    keys = [*INN, "batter"]
    f = reg[reg["faced"]].copy()
    f["one"] = 1
    tot = f.groupby(keys).agg(
        balls=("one", "sum"), runs=("batter_runs", "sum"), fours=("four", "sum"), sixes=("six", "sum"), dots=("bat_dot", "sum"),
        exp_runs=("exp_r", "sum"), exp_outs=("exp_out", "sum"), exp_fours=("exp_4", "sum"), exp_sixes=("exp_6", "sum"), exp_dots=("exp_dot", "sum"),
    ).reset_index()
    f["bnd"] = f["boundary"].astype(int)
    f["exp_bnd_"] = f["exp_4"] + f["exp_6"]
    ph = _pivot_phase(f, keys, {"one": "balls", "batter_runs": "runs", "four": "fours", "six": "sixes", "bat_dot": "dots",
                                "exp_r": "exp_runs", "exp_out": "exp_outs", "exp_bnd_": "exp_bnd", "exp_dot": "exp_dots"})
    pf = f[f["pressure"]]
    pres = pf.groupby(keys).agg(p_balls=("one", "sum"), p_runs=("batter_runs", "sum"), p_exp_runs=("exp_pr", "sum"), p_exp_outs=("exp_pout", "sum")).reset_index()

    # dismissals (any batter, including non-striker run outs)
    dis = core.dismissals
    dis = dis[~dis["super_over"] & dis["is_out"]].copy()
    dseq = reg.set_index([*INN, "seq"])["pressure"]
    dis["pressure"] = pd.Series(list(zip(dis["match_id"], dis["innings_number"], dis["seq"]))).map(dseq.to_dict()).fillna(False).to_numpy()
    outs = dis.groupby([*INN, "player_out"]).agg(out=("kind", "size"), how_out=("kind", "first"), out_bowler=("bowler", "first"), out_phase=("phase", "first"), p_out=("pressure", "sum")).reset_index().rename(columns={"player_out": "batter"})
    outs["out"] = outs["out"].clip(upper=1)

    base = core.positions.rename(columns={"player": "batter"})[[*INN, "batter", "position"]]
    bat = base.merge(tot, on=keys, how="left").merge(ph, on=keys, how="left").merge(pres, on=keys, how="left").merge(outs, on=keys, how="left")
    num = [c for c in bat.columns if c not in (*keys, "position", "how_out", "out_bowler", "out_phase")]
    bat[num] = bat[num].fillna(0)
    for ph_ in PHASES:
        bat[f"{PH_SHORT[ph_]}_outs"] = ((bat["out_phase"] == ph_) & (bat["out"] > 0)).astype(int)
    inn = core.innings.set_index(INN)
    idx = pd.MultiIndex.from_frame(bat[INN])
    bat["team"] = inn["batting_team"].reindex(idx).to_numpy()
    bat["opponent"] = inn["bowling_team"].reindex(idx).to_numpy()
    bat["team_runs"] = inn["runs"].reindex(idx).to_numpy()
    bat["team_bat_runs"] = inn["batter_runs"].reindex(idx).to_numpy()
    bat["gender"] = inn["gender"].reindex(idx).to_numpy()
    bat = bat.rename(columns={"batter": "player"})
    bat["result"] = _result_for(bat, core.matches, "team")
    bat["is_chase"] = bat["innings_number"] == 2
    bat["pos_group"] = bat["position"].map(settings.position_group)
    int_cols = ["balls", "runs", "fours", "sixes", "dots", "out", "p_balls", "p_runs", "p_out"] + [c for c in bat.columns if c[:3] in ("pp_", "mid", "dth") and "exp_" not in c]
    for c in int_cols:
        bat[c] = bat[c].astype(int)
    return bat


# ---------------------------------------------------------------------------- bowling
def _bowling(reg: pd.DataFrame, core: Core, settings: Settings) -> pd.DataFrame:
    keys = [*INN, "bowler"]
    r = reg.copy()
    r["one"] = 1
    r["wide_ball"] = r["wides"] > 0
    r["nb_ball"] = r["no_balls"] > 0
    r["strict_dot"] = r["legal"] & (r["total_runs"] == 0)
    tot = r.groupby(keys).agg(
        deliveries=("one", "sum"), balls=("legal", "sum"), runs=("bowler_runs", "sum"), wkts=("bowler_wkts", "sum"), dots=("bowl_dot", "sum"), dots_strict=("strict_dot", "sum"),
        fours=("four", "sum"), sixes=("six", "sum"), wides=("wide_ball", "sum"), no_balls=("nb_ball", "sum"), wide_runs=("wides", "sum"), nb_runs=("no_balls", "sum"),
        exp_runs=("exp_conc", "sum"), exp_wkts=("exp_wk", "sum"), exp_bnd=("exp_bnd", "sum"), exp_dots=("exp_bdot", "sum"),
    ).reset_index()
    r["bnd"] = r["boundary"].astype(int)
    ph = _pivot_phase(r, keys, {"legal": "balls", "bowler_runs": "runs", "bowler_wkts": "wkts", "bowl_dot": "dots", "bnd": "bnd",
                                 "exp_conc": "exp_runs", "exp_wk": "exp_wkts", "exp_bdot": "exp_dots", "exp_bnd": "exp_bnd"})
    pr = r[r["pressure"]]
    pres = pr.groupby(keys).agg(p_balls=("legal", "sum"), p_del=("one", "sum"), p_runs=("bowler_runs", "sum"), p_wkts=("bowler_wkts", "sum"), p_exp_runs=("exp_pconc", "sum"), p_exp_wkts=("exp_pwk", "sum")).reset_index()
    ov = r.groupby([*INN, "over"]).agg(nb=("bowler", "nunique"), bowler=("bowler", "first"), legal=("legal", "sum"), runs=("bowler_runs", "sum")).reset_index()
    maid = ov[(ov["nb"] == 1) & (ov["legal"] >= 6) & (ov["runs"] == 0)].groupby(keys).size().rename("maidens").reset_index()
    bowl = tot.merge(ph, on=keys, how="left").merge(pres, on=keys, how="left").merge(maid, on=keys, how="left")
    num = [c for c in bowl.columns if c not in keys]
    bowl[num] = bowl[num].fillna(0)
    inn = core.innings.set_index(INN)
    idx = pd.MultiIndex.from_frame(bowl[INN])
    bowl["team"] = inn["bowling_team"].reindex(idx).to_numpy()
    bowl["opponent"] = inn["batting_team"].reindex(idx).to_numpy()
    bowl["team_conceded"] = inn["runs"].reindex(idx).to_numpy()
    bowl["gender"] = inn["gender"].reindex(idx).to_numpy()
    bowl = bowl.rename(columns={"bowler": "player"})
    bowl["result"] = _result_for(bowl, core.matches, "team")
    bowl["defending"] = bowl["innings_number"] == 2
    tw = bowl.groupby(INN)[["wkts", "dots"]].transform("sum")
    bowl["team_bowl_wkts"] = tw["wkts"]
    bowl["team_dots"] = tw["dots"]
    ints = [c for c in bowl.columns if not c.startswith(("exp_", "p_exp")) and c.endswith(("balls", "runs", "wkts", "dots", "dots_strict", "bnd", "fours", "sixes", "wides", "no_balls", "deliveries", "maidens", "p_del"))]
    for c in ints:
        if c in ("team_conceded",) or "exp_" in c:
            continue
        bowl[c] = bowl[c].astype(int)
    return bowl


# ---------------------------------------------------------------------------- partnerships
def _partnerships(reg: pd.DataFrame, core: Core, settings: Settings) -> pd.DataFrame:
    r = reg[[*INN, "seq", "gender", "batting_team", "bowling_team", "batter", "non_striker", "bowler", "batter_runs", "extras", "total_runs", "legal", "team_wkts", "wkts_before", "score_before", "legal_before", "pressure", "phase"]].copy()
    a = np.where(r["batter"] < r["non_striker"], r["batter"], r["non_striker"])
    b = np.where(r["batter"] < r["non_striker"], r["non_striker"], r["batter"])
    r["p1"], r["p2"] = a, b
    new_inn = (r["match_id"] != r["match_id"].shift()) | (r["innings_number"] != r["innings_number"].shift())
    changed = (r["p1"] != r["p1"].shift()) | (r["p2"] != r["p2"].shift())
    r["seg"] = (new_inn | changed).cumsum()
    r["r1"] = np.where(r["batter"] == r["p1"], r["batter_runs"], 0)
    r["r2"] = np.where(r["batter"] == r["p2"], r["batter_runs"], 0)
    g = r.groupby("seg")
    part = g.agg(
        match_id=("match_id", "first"), innings_number=("innings_number", "first"), gender=("gender", "first"), team=("batting_team", "first"),
        opponent=("bowling_team", "first"), player_1=("p1", "first"), player_2=("p2", "first"), runs=("total_runs", "sum"),
        balls=("legal", "sum"), p1_runs=("r1", "sum"), p2_runs=("r2", "sum"), extras=("extras", "sum"), wkt_end=("team_wkts", "last"),
        wkts_before=("wkts_before", "first"), start_score=("score_before", "first"), start_ball=("legal_before", "first"),
        pressure_start=("pressure", "first"), pressure_balls=("pressure", "sum"), start_phase=("phase", "first"), last_seq=("seq", "last"), end_bowler=("bowler", "last"),
    ).reset_index(drop=True)
    part["wicket_no"] = part["wkts_before"] + 1
    part["unbroken"] = part["wkt_end"] == 0
    part["number"] = part.groupby(INN).cumcount() + 1
    # bowler credited with breaking the partnership
    dis = core.dismissals
    cred = dis[dis["bowler_credited"] & ~dis["super_over"]].drop_duplicates([*INN, "seq"]).set_index([*INN, "seq"])["bowler"]
    part["broken_by"] = pd.Series(list(zip(part["match_id"], part["innings_number"], part["last_seq"]))).map(cred.to_dict()).to_numpy()
    part["pressure"] = part["pressure_start"] | (part["pressure_balls"] > 0)
    part["result"] = _result_for(part, core.matches, "team")
    part = part.drop(columns=["wkt_end", "wkts_before", "pressure_start"])
    return part


# ---------------------------------------------------------------------------- team innings
def _team_innings(reg: pd.DataFrame, core: Core) -> pd.DataFrame:
    keys = list(INN)
    r = reg.copy()
    r["dot_ball"] = r["legal"] & (r["total_runs"] == 0)
    ph = _pivot_phase(r, keys, {"total_runs": "runs", "legal": "balls", "team_wkts": "wkts", "boundary": "bnd"})
    dots = r.groupby(keys)["dot_ball"].sum().rename("dots").reset_index()
    t = core.innings.merge(ph, on=keys, how="left").merge(dots, on=keys, how="left")
    t = t.rename(columns={"batting_team": "team", "bowling_team": "opponent"})
    t["result"] = _result_for(t, core.matches, "team")
    t["is_chase"] = t["innings_number"] == 2
    t["boundary_runs"] = t["fours"] * 4 + t["sixes"] * 6
    return t


# ---------------------------------------------------------------------------- player-match
def _player_match(bat: pd.DataFrame, bowl: pd.DataFrame, m: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    w = settings["winning"]
    wv = w["wicket_value_runs"]
    b = bat.groupby(["gender", "match_id", "team", "player"]).agg(
        runs=("runs", "sum"), balls=("balls", "sum"), out=("out", "sum"), exp_runs=("exp_runs", "sum"), team_runs=("team_runs", "first"), position=("position", "first"),
    ).reset_index()
    o = bowl.groupby(["gender", "match_id", "team", "player"]).agg(
        bowl_balls=("balls", "sum"), conceded=("runs", "sum"), wkts=("wkts", "sum"), exp_conc=("exp_runs", "sum"), exp_wkts=("exp_wkts", "sum"), team_bowl_wkts=("team_bowl_wkts", "first"),
    ).reset_index()
    pm = b.merge(o, on=["gender", "match_id", "team", "player"], how="outer")
    pm["batted"] = pm["balls"].notna()
    pm["bowled"] = pm["bowl_balls"].notna()
    pm["bat_value"] = (pm["runs"] - pm["exp_runs"]).where(pm["batted"], 0.0)
    pm["runs_saved"] = (pm["exp_conc"] - pm["conceded"]).where(pm["bowled"], 0.0)
    pm["bowl_value"] = (pm["runs_saved"] + wv * (pm["wkts"] - pm["exp_wkts"])).where(pm["bowled"], 0.0)
    pm["match_score"] = pm["bat_value"].fillna(0) + pm["bowl_value"].fillna(0)
    pm["result"] = _result_for(pm, m, "team")
    pm["run_share"] = np.where(pm["team_runs"] > 0, pm["runs"] / pm["team_runs"] * 100, np.nan)
    won = pm["result"] == "W"
    s = w["significant"]
    sig_bat = pm["batted"] & (pm["runs"] >= s["min_runs"]) & (pm["run_share"] >= s["min_run_share_pct"])
    sig_bowl = pm["bowled"] & ((pm["wkts"] >= s["min_wickets"]) | ((pm["bowl_balls"] >= s["min_balls_bowled"]) & (pm["runs_saved"] >= s["min_runs_saved"])))
    pm["significant"] = (sig_bat | sig_bowl | (pm["match_score"] >= s["min_match_score"])).fillna(False)
    # exceptional = best match score in the winning XI and above threshold
    best = pm.groupby(["match_id", "team"])["match_score"].transform("max")
    pm["exceptional"] = won & (pm["match_score"] == best) & (pm["match_score"] >= w["exceptional_min_match_score"])
    mi = w["match_winning_innings"]
    best_bat = pm.groupby(["match_id", "team"])["bat_value"].transform("max")
    pm["match_winning_innings"] = won & pm["batted"] & (pm["bat_value"] == best_bat) & (pm["runs"] >= mi["min_runs"]) & (pm["bat_value"] >= mi["min_runs_above_expected"])
    mb = w["match_winning_bowling"]
    best_bowl = pm.groupby(["match_id", "team"])["bowl_value"].transform("max")
    pm["match_winning_bowling"] = won & pm["bowled"] & (pm["bowl_value"] == best_bowl) & (pm["bowl_value"] >= mb["min_value"]) & ((pm["wkts"] >= mb["min_wickets"]) | (pm["runs_saved"] >= mb["alt_min_runs_saved"]))
    pm["date"] = pm["match_id"].map(m.set_index("match_id")["date"])
    return pm
