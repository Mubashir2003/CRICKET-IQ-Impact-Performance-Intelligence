"""Player-level traditional and advanced metrics.

All functions operate on (optionally scope-filtered) fact tables and return one
row per ``gender + player``. Undefined values (e.g. batting average with no
dismissals) are NaN - never zero - and are shown as "-" in the dashboard.

Index conventions: a value of 100 means "exactly the average of comparable
deliveries" (same gender, competition, phase and - for batters - position group);
above 100 is better.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import Settings
from ..processing.players import PlayerRegistry
from ..processing.reconstruct import Core
from .facts import PH_SHORT, PHASES, Facts

KEY = ["gender", "player"]


def div(a, b, scale: float = 1.0):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b > 0, a / b * scale, np.nan)


@dataclass
class ScopeFacts:
    bat: pd.DataFrame
    bowl: pd.DataFrame
    part: pd.DataFrame
    pm: pd.DataFrame
    team_inn: pd.DataFrame
    participation: pd.DataFrame
    matches: pd.DataFrame


def scope(facts: Facts, reg: PlayerRegistry, core: Core, match_ids: set[str] | None = None) -> ScopeFacts:
    def f(df: pd.DataFrame) -> pd.DataFrame:
        return df if match_ids is None else df[df["match_id"].isin(match_ids)]

    return ScopeFacts(f(facts.bat), f(facts.bowl), f(facts.part), f(facts.player_match), f(facts.team_inn), f(reg.participation), f(core.matches))


# ----------------------------------------------------------------------------- batting
def batting_metrics(sf: ScopeFacts, settings: Settings) -> pd.DataFrame:
    b = sf.bat.copy()
    if b.empty:
        return pd.DataFrame(columns=KEY)
    cfg = settings["batting"]
    sum_cols = ["runs", "balls", "fours", "sixes", "dots", "out", "exp_runs", "exp_outs", "exp_fours", "exp_sixes", "exp_dots", "team_runs",
                "p_balls", "p_runs", "p_out", "p_exp_runs", "p_exp_outs"]
    sum_cols += [c for c in b.columns if c.split("_")[0] in PH_SHORT.values()]
    b["bnd_runs"] = b["fours"] * 4 + b["sixes"] * 6
    b["f30"] = ((b["runs"] >= 30) & (b["runs"] < 50)).astype(int)
    b["f50"] = ((b["runs"] >= 50) & (b["runs"] < 100)).astype(int)
    b["f100"] = (b["runs"] >= 100).astype(int)
    mi = cfg["meaningful_innings"]
    sr = div(b["runs"], b["balls"], 100)
    b["meaningful"] = ((b["runs"] >= mi["min_runs"]) | ((b["runs"] >= mi["alt_min_runs"]) & (np.nan_to_num(sr) >= mi["alt_min_strike_rate"]))).astype(int)
    ii = cfg["impact_innings"]
    b["impact_inn"] = ((b["runs"] >= ii["min_runs"]) & ((b["runs"] - b["exp_runs"]) >= ii["min_runs_above_expected"])).astype(int)
    b["faced_any"] = (b["balls"] > 0).astype(int)
    for res, tag in (("W", "win"), ("L", "loss")):
        sel = b["is_chase"] & (b["result"] == res)
        b[f"chase_{tag}_runs"] = np.where(sel, b["runs"], 0)
        b[f"chase_{tag}_team"] = np.where(sel, b["team_runs"], 0)
        b[f"chase_{tag}_balls"] = np.where(sel, b["balls"], 0)
    b["chase_runs"] = np.where(b["is_chase"], b["runs"], 0)
    b["chase_balls"] = np.where(b["is_chase"], b["balls"], 0)
    b["chase_team"] = np.where(b["is_chase"], b["team_runs"], 0)
    b["chase_out"] = np.where(b["is_chase"], b["out"], 0)
    w = b["result"] == "W"
    for c in ("runs", "balls", "out"):
        b[f"win_{c}"] = np.where(w, b[c], 0)

    g = b.groupby(KEY)
    agg = g[[*sum_cols, "bnd_runs", "f30", "f50", "f100", "meaningful", "impact_inn", "faced_any",
             "chase_win_runs", "chase_win_team", "chase_win_balls", "chase_loss_runs", "chase_loss_team", "chase_loss_balls",
             "chase_runs", "chase_balls", "chase_team", "chase_out", "win_runs", "win_balls", "win_out"]].sum()
    agg["innings"] = g.size()
    agg["bat_matches"] = g["match_id"].nunique()
    idx = b.groupby(KEY)["runs"].idxmax()
    hs = b.loc[idx, [*KEY, "runs", "out"]].set_index(KEY)
    agg["highest"] = hs["runs"]
    agg["highest_not_out"] = hs["out"] == 0
    # consistency (innings where at least one ball faced)
    fb = b[b["balls"] > 0]
    st = fb.groupby(KEY)["runs"].agg(["mean", "std", "size"])
    cv = div(st["std"], st["mean"])
    mrate = fb.groupby(KEY)["meaningful"].mean()
    ci = 100 * (0.5 * mrate + 0.5 * (1 - np.minimum(np.nan_to_num(cv, nan=2.0), 2.0) / 2))
    ci[st["size"] < cfg["consistency_min_innings"]] = np.nan
    agg["consistency_index"] = ci
    a = agg.reset_index()

    out = a[KEY].copy()
    out["bat_innings"] = a["innings"]
    out["bat_matches"] = a["bat_matches"]
    out["not_outs"] = a["innings"] - a["out"]
    out["runs"] = a["runs"]
    out["balls"] = a["balls"]
    out["outs"] = a["out"]
    out["average"] = div(a["runs"], a["out"])
    out["strike_rate"] = div(a["runs"], a["balls"], 100)
    out["highest"] = a["highest"]
    out["highest_not_out"] = a["highest_not_out"]
    out["fours"] = a["fours"]
    out["sixes"] = a["sixes"]
    out["boundary_runs"] = a["bnd_runs"]
    out["boundary_pct"] = div(a["bnd_runs"], a["runs"], 100)
    out["dot_pct"] = div(a["dots"], a["balls"], 100)
    out["balls_per_boundary"] = div(a["balls"], a["fours"] + a["sixes"])
    out["scores_30"] = a["f30"]
    out["fifties"] = a["f50"]
    out["hundreds"] = a["f100"]
    out["balls_per_dismissal"] = div(a["balls"], a["out"])
    # advanced
    out["team_run_contribution_pct"] = div(a["runs"], a["team_runs"], 100)
    out["boundary_dependency_pct"] = out["boundary_pct"]
    out["non_boundary_pct"] = div(a["runs"] - a["bnd_runs"], a["runs"], 100)
    out["runs_per_ball"] = div(a["runs"], a["balls"])
    out["consistency_index"] = a["consistency_index"]
    out["impact_innings_pct"] = div(a["impact_inn"], a["faced_any"], 100)
    out["impact_innings"] = a["impact_inn"]
    out["runs_per_dismissal"] = out["average"]
    out["expected_runs"] = a["exp_runs"]
    out["expected_outs"] = a["exp_outs"]
    out["runs_above_expected"] = a["runs"] - a["exp_runs"]
    out["expected_sr"] = div(a["exp_runs"], a["balls"], 100)
    out["sr_above_avg"] = out["strike_rate"] - out["expected_sr"]
    out["expected_average"] = div(a["exp_runs"], a["exp_outs"])
    out["average_ratio"] = div(out["average"], out["expected_average"])
    for ph in PHASES:
        s = PH_SHORT[ph]
        r, bl, f4, f6, dt, o = (a[f"{s}_{k}"] for k in ("runs", "balls", "fours", "sixes", "dots", "outs"))
        er, eo, eb, ed = (a[f"{s}_{k}"] for k in ("exp_runs", "exp_outs", "exp_bnd", "exp_dots"))
        out[f"{s}_runs"], out[f"{s}_balls"], out[f"{s}_outs"] = r, bl, o
        out[f"{s}_sr"] = div(r, bl, 100)
        out[f"{s}_avg"] = div(r, o)
        out[f"{s}_bnd_pct"] = div(f4 + f6, bl, 100)
        out[f"{s}_dot_pct"] = div(dt, bl, 100)
        out[f"{s}_ball_share"] = div(bl, a["balls"])
        out[f"{s}_run_share_of_player"] = div(r, a["runs"], 100)
        sr_ratio = div(r, er)
        bnd_ratio = div(f4 + f6 + 0.5, eb + 0.5)
        risk = np.clip(div(eo + 1, o + 1), 0.5, 1.5)
        dot_ratio = div(ed + 0.5, dt + 0.5)
        if s == "pp":
            idx_ = 100 * (0.5 * sr_ratio + 0.3 * bnd_ratio + 0.2 * risk)
            name = "powerplay_aggression_index"
        elif s == "mid":
            idx_ = 100 * (0.4 * sr_ratio + 0.35 * dot_ratio + 0.25 * bnd_ratio)
            name = "middle_over_control_index"
        else:
            idx_ = 100 * (0.5 * sr_ratio + 0.3 * bnd_ratio + 0.2 * risk)
            name = "death_finishing_index"
        out[name] = np.where(bl >= 30, idx_, np.nan)
        out[f"{s}_sr_index"] = sr_ratio
        out[f"{s}_dot_index"] = div(dt + 0.5, ed + 0.5)
    # chases
    out["chase_runs"] = a["chase_runs"]
    out["chase_sr"] = div(a["chase_runs"], a["chase_balls"], 100)
    out["chase_avg"] = div(a["chase_runs"], a["chase_out"])
    out["chase_contribution_pct"] = div(a["chase_runs"], a["chase_team"], 100)
    out["chase_success_contribution_pct"] = div(a["chase_win_runs"], a["chase_win_team"], 100)
    out["chase_failure_contribution_pct"] = div(a["chase_loss_runs"], a["chase_loss_team"], 100)
    out["chase_success_runs"] = a["chase_win_runs"]
    out["chase_success_sr"] = div(a["chase_win_runs"], a["chase_win_balls"], 100)
    # pressure
    out["pressure_balls"] = a["p_balls"]
    out["pressure_runs"] = a["p_runs"]
    out["pressure_outs"] = a["p_out"]
    out["pressure_sr"] = div(a["p_runs"], a["p_balls"], 100)
    out["pressure_avg"] = div(a["p_runs"], a["p_out"])
    out["pressure_expected_sr"] = div(a["p_exp_runs"], a["p_balls"], 100)
    out["pressure_sr_delta"] = out["pressure_sr"] - out["pressure_expected_sr"]
    out["pressure_runs_above_expected"] = a["p_runs"] - a["p_exp_runs"]
    out["pressure_expected_avg"] = div(a["p_exp_runs"], a["p_exp_outs"])
    out["late_over_scoring_efficiency"] = 100 * div(a["dth_runs"], a["dth_exp_runs"])
    # wins
    out["bat_avg_in_wins"] = div(a["win_runs"], a["win_out"])
    out["bat_sr_in_wins"] = div(a["win_runs"], a["win_balls"], 100)
    out["runs_in_wins"] = a["win_runs"]
    return out


# ----------------------------------------------------------------------------- bowling
def bowling_metrics(sf: ScopeFacts, settings: Settings) -> pd.DataFrame:
    o = sf.bowl.copy()
    if o.empty:
        return pd.DataFrame(columns=KEY)
    cfg = settings["bowling"]
    o["w4"] = (o["wkts"] == 4).astype(int)
    o["w5"] = (o["wkts"] >= 5).astype(int)
    o["bnd"] = o["fours"] + o["sixes"]
    for res, tag in (("W", "win"), ("L", "loss")):
        sel = o["result"] == res
        for c in ("balls", "runs", "wkts"):
            o[f"{tag}_{c}"] = np.where(sel, o[c], 0)
    o["n_win"] = (o["result"] == "W").astype(int)
    o["n_loss"] = (o["result"] == "L").astype(int)
    sum_cols = ["deliveries", "balls", "runs", "wkts", "dots", "fours", "sixes", "bnd", "wides", "no_balls", "maidens", "exp_runs", "exp_wkts", "exp_bnd", "exp_dots",
                "team_bowl_wkts", "team_dots", "p_balls", "p_del", "p_runs", "p_wkts", "p_exp_runs", "p_exp_wkts", "w4", "w5",
                "win_balls", "win_runs", "win_wkts", "loss_balls", "loss_runs", "loss_wkts", "n_win", "n_loss"]
    sum_cols += [c for c in o.columns if c.split("_")[0] in PH_SHORT.values()]
    g = o.groupby(KEY)
    a = g[sum_cols].sum()
    a["innings"] = g.size()
    a["bowl_matches"] = g["match_id"].nunique()
    best = o.sort_values(["wkts", "runs"], ascending=[False, True]).drop_duplicates(KEY).set_index(KEY)
    a["best_wkts"] = best["wkts"]
    a["best_runs"] = best["runs"]
    # consistency
    q = o[o["balls"] >= cfg["consistency_min_balls_per_innings"]].copy()
    q["econ"] = q["runs"] / q["balls"] * 6
    q["good"] = ((q["runs"] <= q["exp_runs"]) | (q["wkts"] >= cfg["good_spell_min_wickets"])).astype(int)
    st = q.groupby(KEY).agg(m=("econ", "mean"), s=("econ", "std"), n=("econ", "size"), good=("good", "mean"))
    cons = 100 * (0.5 * st["good"] + 0.5 * (1 - np.minimum(np.nan_to_num(div(st["s"], st["m"]), nan=1.0), 1.0)))
    cons[st["n"] < cfg["consistency_min_innings"]] = np.nan
    a["consistency"] = cons
    a = a.reset_index()

    out = a[KEY].copy()
    out["bowl_innings"] = a["innings"]
    out["bowl_matches"] = a["bowl_matches"]
    out["legal_balls"] = a["balls"]
    out["overs"] = (a["balls"] // 6).astype(int).astype(str) + "." + (a["balls"] % 6).astype(int).astype(str)
    out["runs_conceded"] = a["runs"]
    out["wickets"] = a["wkts"]
    out["bowling_average"] = div(a["runs"], a["wkts"])
    out["economy"] = div(a["runs"], a["balls"], 6)
    out["bowling_sr"] = div(a["balls"], a["wkts"])
    out["best_figures"] = a["best_wkts"].astype(int).astype(str) + "/" + a["best_runs"].astype(int).astype(str)
    out["best_wkts"], out["best_runs"] = a["best_wkts"], a["best_runs"]
    out["maidens"] = a["maidens"]
    out["dot_balls"] = a["dots"]
    out["bowl_dot_pct"] = div(a["dots"], a["balls"], 100)
    out["boundary_balls"] = a["bnd"]
    out["fours_conceded"], out["sixes_conceded"] = a["fours"], a["sixes"]
    out["wides"] = a["wides"]
    out["no_balls"] = a["no_balls"]
    out["four_wkt_hauls"] = a["w4"]
    out["five_wkt_hauls"] = a["w5"]
    # advanced
    out["wicket_contribution_pct"] = div(a["wkts"], a["team_bowl_wkts"], 100)
    out["dot_ball_share_pct"] = div(a["dots"], a["team_dots"], 100)
    out["boundary_prevention_rate"] = 100 - div(a["bnd"], a["balls"], 100)
    out["expected_runs_conceded"] = a["exp_runs"]
    out["runs_saved"] = a["exp_runs"] - a["runs"]
    out["runs_saved_per_24"] = div(out["runs_saved"], a["balls"], 24)
    out["wickets_above_expected"] = a["wkts"] - a["exp_wkts"]
    out["wkts_above_exp_per_24"] = div(out["wickets_above_expected"], a["balls"], 24)
    out["expected_economy"] = div(a["exp_runs"], a["balls"], 6)
    out["economy_advantage"] = out["expected_economy"] - out["economy"]
    out["boundary_suppression_index"] = 100 * div(a["exp_bnd"] + 1, a["bnd"] + 1)
    out["dot_ball_index"] = 100 * div(a["dots"] + 1, a["exp_dots"] + 1)
    out["bowling_consistency"] = a["consistency"]
    out["wicket_frequency"] = out["bowling_sr"]
    for ph in PHASES:
        s = PH_SHORT[ph]
        bl, r, w, dt, bd = (a[f"{s}_{k}"] for k in ("balls", "runs", "wkts", "dots", "bnd"))
        er, ew, ed, eb = (a[f"{s}_{k}"] for k in ("exp_runs", "exp_wkts", "exp_dots", "exp_bnd"))
        out[f"b{s}_balls"], out[f"b{s}_runs"], out[f"b{s}_wkts"] = bl, r, w
        out[f"b{s}_economy"] = div(r, bl, 6)
        out[f"b{s}_expected_economy"] = div(er, bl, 6)
        out[f"b{s}_wkt_contribution_pct"] = div(w, a["wkts"], 100)
        out[f"b{s}_dot_pct"] = div(dt, bl, 100)
        out[f"b{s}_ball_share"] = div(bl, a["balls"])
        out[f"b{s}_economy_index"] = div(r, er)
        out[f"b{s}_wicket_index"] = div(w + 0.5, ew + 0.5)
        out[f"b{s}_runs_saved"] = er - r
        if s == "dth":
            econ_r = div(er + 1, r + 1)
            out["death_over_effectiveness"] = np.where(bl >= 24, 100 * (0.4 * econ_r + 0.3 * div(w + 0.5, ew + 0.5) + 0.15 * div(dt + 0.5, ed + 0.5) + 0.15 * div(eb + 0.5, bd + 0.5)), np.nan)
    out["economy_index"] = div(a["runs"], a["exp_runs"])
    out["boundary_index"] = div(a["bnd"] + 0.5, a["exp_bnd"] + 0.5)
    out["dot_index"] = div(a["dots"] + 0.5, a["exp_dots"] + 0.5)
    out["wicket_index"] = div(a["wkts"] + 0.5, a["exp_wkts"] + 0.5)
    # pressure
    out["pressure_balls_bowled"] = a["p_balls"]
    out["pressure_economy"] = div(a["p_runs"], a["p_balls"], 6)
    out["pressure_expected_economy"] = div(a["p_exp_runs"], a["p_balls"], 6)
    out["pressure_economy_delta"] = out["pressure_expected_economy"] - out["pressure_economy"]
    out["pressure_wickets"] = a["p_wkts"]
    out["pressure_wicket_frequency"] = div(a["p_balls"], a["p_wkts"])
    out["pressure_runs_saved"] = a["p_exp_runs"] - a["p_runs"]
    out["pressure_bowling_index"] = np.where(a["p_balls"] >= 24, 100 * (0.6 * div(a["p_exp_runs"] + 1, a["p_runs"] + 1) + 0.4 * div(a["p_wkts"] + 0.5, a["p_exp_wkts"] + 0.5)), np.nan)
    # wins vs losses
    out["economy_in_wins"] = div(a["win_runs"], a["win_balls"], 6)
    out["economy_in_losses"] = div(a["loss_runs"], a["loss_balls"], 6)
    out["bowl_avg_in_wins"] = div(a["win_runs"], a["win_wkts"])
    out["bowl_avg_in_losses"] = div(a["loss_runs"], a["loss_wkts"])
    out["wkts_in_wins"] = a["win_wkts"]
    out["wkts_per_match_wins"] = div(a["win_wkts"], a["n_win"])
    out["wkts_per_match_losses"] = div(a["loss_wkts"], a["n_loss"])
    return out


# ----------------------------------------------------------------------------- winning / match context
def winning_metrics(sf: ScopeFacts, settings: Settings) -> pd.DataFrame:
    part = sf.participation[["gender", "match_id", "player", "team"]].copy()
    if part.empty:
        return pd.DataFrame(columns=KEY)
    m = sf.matches.set_index("match_id")
    res = part["match_id"].map(m["result"])
    ew = part["match_id"].map(m["effective_winner"])
    part["res"] = np.select([res.eq("no result"), ew.notna() & (ew == part["team"]), ew.notna(), res.eq("tie")], ["N", "W", "L", "T"], default="N")
    part["close"] = part["match_id"].map(m["close_finish"]).fillna(False).astype(bool)
    part["low"] = part["match_id"].map(m["low_scoring"]).fillna(False).astype(bool)
    ti = sf.team_inn
    team_runs = ti.groupby(["match_id", "team"])["runs"].sum()
    bw = sf.bowl.groupby(["match_id", "team"])["wkts"].sum()
    keys = list(zip(part["match_id"], part["team"]))
    part["team_runs"] = pd.Series(keys).map(team_runs.to_dict()).to_numpy()
    part["team_wkts"] = pd.Series(keys).map(bw.to_dict()).to_numpy()
    pm = sf.pm.set_index(["match_id", "player"])
    pk = list(zip(part["match_id"], part["player"]))
    for c in ("runs", "balls", "out", "wkts", "conceded", "bowl_balls", "match_score", "significant", "exceptional", "match_winning_innings", "match_winning_bowling", "bat_value", "bowl_value"):
        part[c] = pd.Series(pk).map(pm[c].to_dict()).to_numpy() if c in pm.columns else np.nan
    for c in ("runs", "balls", "out", "wkts", "conceded", "bowl_balls", "match_score", "bat_value", "bowl_value"):
        part[c] = pd.to_numeric(part[c], errors="coerce").fillna(0.0)
    for c in ("significant", "exceptional", "match_winning_innings", "match_winning_bowling"):
        part[c] = part[c].fillna(False).astype(bool)
    W = part["res"] == "W"
    part["w"] = W.astype(int)
    part["l"] = (part["res"] == "L").astype(int)
    part["t"] = (part["res"] == "T").astype(int)
    part["n"] = (part["res"] == "N").astype(int)
    for c in ("runs", "wkts", "team_runs", "team_wkts", "match_score"):
        part[f"w_{c}"] = np.where(W, part[c].fillna(0), 0)
    part["w_sig"] = (W & part["significant"]).astype(int)
    part["w_exc"] = (W & part["exceptional"]).astype(int)
    part["mwi"] = part["match_winning_innings"].astype(int)
    part["mwb"] = part["match_winning_bowling"].astype(int)
    for flag in ("close", "low"):
        sel = part[flag]
        part[f"{flag}_m"] = sel.astype(int)
        part[f"{flag}_w"] = (sel & W).astype(int)
        for c in ("runs", "balls", "out", "wkts", "conceded", "bowl_balls"):
            part[f"{flag}_{c}"] = np.where(sel, part[c], 0)
    g = part.groupby(KEY)
    s = g[[c for c in part.columns if c not in ("gender", "match_id", "player", "team", "res", "close", "low", "significant", "exceptional", "match_winning_innings", "match_winning_bowling")]].sum()
    s["matches_in_scope"] = g["match_id"].nunique()
    a = s.reset_index()
    out = a[KEY].copy()
    out["matches_in_scope"] = a["matches_in_scope"]
    out["wins"], out["losses"], out["ties"], out["no_results"] = a["w"], a["l"], a["t"], a["n"]
    out["win_rate"] = div(a["w"] + 0.5 * a["t"], a["w"] + a["l"] + a["t"], 100)
    out["runs_in_victories"] = a["w_runs"]
    out["wickets_in_victories"] = np.where(a["bowl_balls"] > 0, a["w_wkts"], np.nan)
    # shares only where the player actually batted / bowled in the scope (never a structural zero)
    out["winning_run_share_pct"] = np.where(a["balls"] > 0, div(a["w_runs"], a["w_team_runs"], 100), np.nan)
    out["winning_wicket_share_pct"] = np.where(a["bowl_balls"] > 0, div(a["w_wkts"], a["w_team_wkts"], 100), np.nan)
    out["wins_present"] = a["w"]
    out["wins_significant"] = a["w_sig"]
    out["wins_exceptional"] = a["w_exc"]
    out["significant_win_pct"] = div(a["w_sig"], a["w"], 100)
    out["match_winning_innings"] = a["mwi"]
    out["match_winning_bowling"] = a["mwb"]
    out["match_winning_innings_pct"] = div(a["mwi"], a["matches_in_scope"], 100)
    out["match_winning_bowling_pct"] = div(a["mwb"], a["matches_in_scope"], 100)
    out["match_winning_pct"] = div(a["w_exc"], a["matches_in_scope"], 100)
    out["avg_match_score_in_wins"] = div(a["w_match_score"], a["w"])
    out["avg_match_score"] = div(a["match_score"], a["matches_in_scope"])
    for flag, lbl in (("close", "close"), ("low", "low_scoring")):
        out[f"{lbl}_matches"] = a[f"{flag}_m"]
        out[f"{lbl}_wins"] = a[f"{flag}_w"]
        out[f"{lbl}_runs"] = a[f"{flag}_runs"]
        out[f"{lbl}_bat_sr"] = div(a[f"{flag}_runs"], a[f"{flag}_balls"], 100)
        out[f"{lbl}_bat_avg"] = div(a[f"{flag}_runs"], a[f"{flag}_out"])
        out[f"{lbl}_wkts"] = a[f"{flag}_wkts"]
        out[f"{lbl}_economy"] = div(a[f"{flag}_conceded"], a[f"{flag}_bowl_balls"], 6)
    # pressure partnerships
    pp = sf.part[sf.part["pressure"]]
    rows = pd.concat([
        pp[["gender", "player_1", "p1_runs", "runs"]].set_axis(["gender", "player", "pr", "tot"], axis=1),
        pp[["gender", "player_2", "p2_runs", "runs"]].set_axis(["gender", "player", "pr", "tot"], axis=1),
    ])
    ppa = rows.groupby(KEY).agg(pr=("pr", "sum"), tot=("tot", "sum"), n=("tot", "size")).reset_index()
    out = out.merge(ppa, on=KEY, how="left")
    out["pressure_partnerships"] = out.pop("n").fillna(0).astype(int)
    out["pressure_partnership_contribution_pct"] = div(out.pop("pr"), out.pop("tot"), 100)
    return out


def all_metrics(sf: ScopeFacts, settings: Settings) -> pd.DataFrame:
    """Combine batting, bowling and winning metrics into one frame."""
    bm = batting_metrics(sf, settings)
    om = bowling_metrics(sf, settings)
    wm = winning_metrics(sf, settings)
    out = wm.merge(bm, on=KEY, how="outer").merge(om, on=KEY, how="outer")
    return out
