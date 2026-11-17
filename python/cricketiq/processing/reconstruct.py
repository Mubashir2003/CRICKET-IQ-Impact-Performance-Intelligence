"""Match and delivery reconstruction.

Cricket rules applied (ball-by-ball source of truth):

* Legal ball  - not a wide and not a no-ball (counts toward the over).
* Ball faced  - every delivery except wides (no-balls ARE faced by the batter).
* Bowler runs - batter runs + wide runs + no-ball runs. Byes, leg-byes and penalty
  runs are never charged to the bowler. (The source combines byes/leg-byes/penalty
  into one "other extras" figure, which is kept separately.)
* Team wicket - any dismissal except "retired hurt" / "retired not out".
* Bowler wicket - bowled, caught, caught and bowled, lbw, stumped, hit wicket.
* Super overs (innings 3+) decide tied matches but are excluded from player
  statistics, phase analysis and innings totals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import Settings
from ..ingestion.loader import Issue

log = logging.getLogger(__name__)

INN = ["match_id", "innings_number"]


@dataclass
class Core:
    matches: pd.DataFrame
    deliveries: pd.DataFrame
    dismissals: pd.DataFrame
    innings: pd.DataFrame
    positions: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)


# --------------------------------------------------------------------------- matches
def classify_competitions(m: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Attach competition label, competition type and international flag."""
    cfg = settings["competitions"]
    countries = set(settings.countries)
    m = m.copy()
    m["series"] = m["competition"]
    m["is_international"] = m["team_1"].isin(countries) & m["team_2"].isin(countries)

    def short(name: str) -> str:
        import re

        for pat, label in cfg["short_names"]:
            if re.search(pat, name or "", flags=re.IGNORECASE):
                return label
        return name

    def ctype(row: pd.Series) -> str:
        import re

        if row["is_international"]:
            return "International"
        name = row["series"] or ""
        if any(re.search(p, name, flags=re.IGNORECASE) for p in cfg["franchise_patterns"]):
            return "Franchise league"
        return "Domestic"

    m["comp_type"] = m.apply(ctype, axis=1)
    m["competition"] = np.where(m["is_international"], cfg["international_label"], m["series"].map(short))
    return m


# --------------------------------------------------------------------------- deliveries
def _parse_dismissals(d: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    w = d.loc[d["dismissal_kinds"].notna(), ["gender", *INN, "seq", "over", "phase", "dismissal_kinds", "players_out", "batter", "non_striker", "bowler", "super_over"]]
    rows = []
    credited, not_out = settings.credited_kinds, settings.not_out_kinds
    for r in w.itertuples(index=False):
        kinds = [k.strip() for k in str(r.dismissal_kinds).split(";") if k.strip()]
        outs = [p.strip() for p in str(r.players_out or "").split(";") if p.strip()]
        for i, k in enumerate(kinds):
            p = outs[i] if i < len(outs) else (outs[-1] if outs else r.batter)
            kl = k.lower()
            rows.append(
                {
                    "gender": r.gender, "match_id": r.match_id, "innings_number": r.innings_number, "seq": r.seq,
                    "over": r.over, "phase": r.phase, "kind": kl, "player_out": p, "bowler": r.bowler,
                    "striker": r.batter, "non_striker": r.non_striker, "super_over": r.super_over,
                    "is_out": kl not in not_out, "bowler_credited": kl in credited,
                }
            )
    cols = ["gender", *INN, "seq", "over", "phase", "kind", "player_out", "bowler", "striker", "non_striker", "super_over", "is_out", "bowler_credited"]
    return pd.DataFrame(rows, columns=cols).astype({"is_out": bool, "bowler_credited": bool, "super_over": bool, "seq": "int64", "innings_number": "int64"})


def build_core(tables: dict[str, pd.DataFrame], settings: Settings) -> Core:
    issues: list[Issue] = []
    m = classify_competitions(tables["matches"], settings)
    d = tables["deliveries"].copy()

    if d["match_id"].duplicated().any():
        pass  # expected (many rows per match)
    dupe_ids = m.groupby("match_id")["gender"].nunique()
    if (dupe_ids > 1).any():
        raise ValueError("The same match_id appears in both genders; match ids must be unique.")

    # over numbering: convert to 1-based if the source is 0-based
    for g, sub in d.groupby("gender"):
        if sub["over"].min() == 0:
            d.loc[sub.index, "over"] = sub["over"] + 1
            issues.append(Issue(g, "deliveries", "info", "Over numbers were 0-based and have been converted to 1-based"))

    d = d.sort_values(["gender", "match_id", "innings_number", "over", "delivery_in_over", "_row"]).reset_index(drop=True)
    d["seq"] = d.groupby(INN).cumcount()
    d["super_over"] = d["innings_number"] > 2
    rule_legal = (d["wides"].fillna(0) == 0) & (d["no_balls"].fillna(0) == 0)
    src_legal = d["is_legal_delivery"].astype("boolean")
    mismatch = src_legal.notna() & (src_legal != rule_legal)
    if mismatch.any():
        issues.append(Issue("*", "deliveries", "warning", "Legal-delivery flag disagreed with wides/no-balls; cricket rule applied", int(mismatch.sum())))
    d["legal"] = rule_legal
    d["faced"] = d["wides"].fillna(0) == 0
    d["bowler_runs"] = d["batter_runs"] + d["wides"] + d["no_balls"]
    d["other_extras"] = d["extras"] - d["wides"] - d["no_balls"]
    neg = d["other_extras"] < 0
    if neg.any():
        issues.append(Issue("*", "deliveries", "warning", "Extras smaller than wides+no-balls (inconsistent rows)", int(neg.sum())))
    calc_total = d["batter_runs"] + d["extras"]
    if (calc_total != d["total_runs"]).any():
        issues.append(Issue("*", "deliveries", "warning", "total_runs differs from batter_runs + extras", int((calc_total != d["total_runs"]).sum())))
    d["four"] = d["faced"] & (d["batter_runs"] == 4)
    d["six"] = d["faced"] & (d["batter_runs"] == 6)
    d["boundary"] = d["four"] | d["six"]
    d["bat_dot"] = d["faced"] & (d["batter_runs"] == 0)
    d["bowl_dot"] = d["legal"] & (d["bowler_runs"] == 0)
    d["phase"] = d["over"].map(settings.phase_of_over)

    dis = _parse_dismissals(d, settings)
    team_w = dis[dis["is_out"]].groupby([*INN, "seq"]).size().rename("team_wkts")
    cred_w = dis[dis["bowler_credited"]].groupby([*INN, "seq"]).size().rename("bowler_wkts")
    striker_out = dis[dis["is_out"] & (dis["player_out"] == dis["striker"])].groupby([*INN, "seq"]).size().rename("striker_out")
    d = d.join(team_w, on=[*INN, "seq"]).join(cred_w, on=[*INN, "seq"]).join(striker_out, on=[*INN, "seq"])
    for c in ("team_wkts", "bowler_wkts", "striker_out"):
        d[c] = d[c].fillna(0).astype(int)

    g = d.groupby(INN, sort=False)
    d["legal_before"] = g["legal"].cumsum() - d["legal"].astype(int)
    d["score_before"] = g["total_runs"].cumsum() - d["total_runs"]
    d["wkts_before"] = g["team_wkts"].cumsum() - d["team_wkts"]

    # ---------------------------------------------------------------- innings
    reg = d[~d["super_over"]]
    inn = reg.groupby(INN).agg(
        gender=("gender", "first"), batting_team=("batting_team", "first"), bowling_team=("bowling_team", "first"),
        runs=("total_runs", "sum"), wkts=("team_wkts", "sum"), legal_balls=("legal", "sum"), deliveries=("seq", "size"),
        fours=("four", "sum"), sixes=("six", "sum"), extras=("extras", "sum"), wides=("wides", "sum"),
        no_balls=("no_balls", "sum"), other_extras=("other_extras", "sum"), batter_runs=("batter_runs", "sum"),
    ).reset_index()
    full = settings["match"]["full_innings_balls"]

    i1 = inn[inn["innings_number"] == 1].set_index("match_id")
    i2 = inn[inn["innings_number"] == 2].set_index("match_id")
    m = m.set_index("match_id")
    for k, src in (("1", i1), ("2", i2)):
        m[f"bat{k}"] = src["batting_team"]
        m[f"r{k}"] = src["runs"]
        m[f"w{k}"] = src["wkts"]
        m[f"b{k}"] = src["legal_balls"]

    # super-over winner (for tied matches)
    so = d[d["super_over"]].groupby(INN).agg(team=("batting_team", "first"), runs=("total_runs", "sum")).reset_index()
    so_winner: dict[str, str] = {}
    for mid, sub in so.groupby("match_id"):
        sub = sub.sort_values("innings_number")
        last = sub.tail(2)
        if len(last) == 2 and last["runs"].iloc[0] != last["runs"].iloc[1]:
            so_winner[mid] = last.loc[last["runs"].idxmax(), "team"]
    m["super_over_winner"] = pd.Series(so_winner)
    m["has_super_over"] = m.index.isin(so["match_id"].unique())

    rt = m["result_type"].fillna("").str.lower()
    m["result"] = np.select([rt.str.contains("no result") | rt.str.contains("abandon"), rt.str.contains("tie"), m["winner"].notna()], ["no result", "tie", "won"], default="no result")
    count_so = settings["match"]["count_super_over_winner_as_win"]
    m["effective_winner"] = m["winner"]
    if count_so:
        m["effective_winner"] = m["effective_winner"].fillna(m["super_over_winner"])
    # reduced-overs / revised target detection
    reduced = (m["b1"] < full) & (m["w1"] < 10)
    chase_won = m["winner"].notna() & (m["winner"] == m["bat2"])
    dls_suspect = (chase_won & (m["r2"] <= m["r1"])) | (m["winner"].notna() & (m["winner"] == m["bat1"]) & (m["r2"] > m["r1"]))
    m["reduced_or_revised"] = (reduced | dls_suspect).fillna(False)
    m["target"] = m["r1"] + 1
    m["chase_won"] = chase_won.fillna(False)
    # margins
    m["margin_runs"] = np.where(m["result"].eq("won") & (m["winner"] == m["bat1"]), m["r1"] - m["r2"], np.nan)
    m["margin_wkts"] = np.where(m["result"].eq("won") & chase_won, 10 - m["w2"], np.nan)
    m["balls_remaining"] = np.where(m["result"].eq("won") & chase_won & ~m["reduced_or_revised"], full - m["b2"], np.nan)
    cf = settings["match"]["close_finish"]
    m["close_finish"] = (
        (m["result"] == "tie")
        | (m["margin_runs"] <= cf["max_run_margin"])
        | (m["balls_remaining"] <= cf["max_balls_remaining"])
        | (m["margin_wkts"] <= cf["max_wickets_in_hand"])
    ).fillna(False)
    q = settings["match"]["low_scoring_first_innings_quantile"]
    ok = m["r1"].notna() & ~m["reduced_or_revised"]
    thresholds = m[ok].groupby("gender")["r1"].quantile(q)
    m["low_scoring"] = (m["r1"] < m["gender"].map(thresholds)) & ok
    m["low_score_threshold"] = m["gender"].map(thresholds)
    m = m.reset_index()

    # ---------------------------------------------------------------- chase state & pressure
    mm = m.set_index("match_id")
    d["target"] = d["match_id"].map(mm["target"])
    d["chase_reduced"] = d["match_id"].map(mm["reduced_or_revised"]).fillna(True).astype(bool)
    is_chase = (d["innings_number"] == 2) & ~d["chase_reduced"]
    d["runs_needed"] = np.where(is_chase, d["target"] - d["score_before"], np.nan)
    d["balls_left"] = np.where(is_chase, full - d["legal_before"], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        d["req_rate"] = np.where(is_chase & (d["balls_left"] > 0), d["runs_needed"] * 6 / d["balls_left"], np.nan)
    p = settings["pressure"]
    live = is_chase & (d["runs_needed"] > 0)
    chase_p = live & (
        ((d["req_rate"] >= p["chase_min_required_rate"]) & (d["req_rate"] <= p["chase_max_required_rate"]))
        | ((d["balls_left"] <= p["chase_late_balls_remaining"]) & (d["req_rate"] <= p["chase_late_max_required_rate"]))
    )
    collapse = pd.Series(False, index=d.index)
    for rule in p["collapse_rules"]:
        collapse |= (d["wkts_before"] >= rule["min_wickets_down"]) & (d["legal_before"] < rule["max_legal_balls_bowled"])
    d["pressure_chase"] = chase_p.fillna(False) & ~d["super_over"]
    d["pressure_collapse"] = collapse & ~d["super_over"]
    d["pressure"] = d["pressure_chase"] | d["pressure_collapse"]

    # ---------------------------------------------------------------- batting positions
    a = d.loc[~d["super_over"], [*INN, "seq", "batter", "non_striker"]]
    st = a[[*INN, "seq", "batter"]].rename(columns={"batter": "player"}).assign(o=a["seq"] * 2)
    ns = a[[*INN, "seq", "non_striker"]].rename(columns={"non_striker": "player"}).assign(o=a["seq"] * 2 + 1)
    # batters dismissed without reaching the crease (e.g. "timed out") still have an innings
    gone = dis.loc[~dis["super_over"], [*INN, "seq", "player_out"]].rename(columns={"player_out": "player"})
    gone = gone.assign(o=gone["seq"] * 2 + 1.5)
    pos = pd.concat([st, ns, gone]).sort_values([*INN, "o"]).drop_duplicates([*INN, "player"])
    pos["position"] = pos.groupby(INN).cumcount() + 1
    pos = pos[[*INN, "player", "position", "seq"]].rename(columns={"seq": "first_seq"})
    d = d.merge(pos[[*INN, "player", "position"]].rename(columns={"player": "batter", "position": "striker_pos"}), on=[*INN, "batter"], how="left")
    d["pos_group"] = d["striker_pos"].fillna(11).astype(int).map(settings.position_group)

    # attach match context
    ctx = m[["match_id", "competition", "comp_type", "date", "venue"]]
    d = d.drop(columns=[c for c in ("competition", "date") if c in d.columns]).merge(ctx, on="match_id", how="left")
    d = d.sort_values(["gender", "match_id", "innings_number", "seq"]).reset_index(drop=True)
    inn = inn.merge(m[["match_id", "competition", "comp_type", "date"]], on="match_id", how="left")
    return Core(matches=m, deliveries=d, dismissals=dis, innings=inn, positions=pos, issues=issues)
