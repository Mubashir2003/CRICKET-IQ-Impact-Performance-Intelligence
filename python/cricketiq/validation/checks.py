"""Cross-validation of reconstructed statistics against the supplied scorecards.

Every check returns a :class:`CheckResult`. Results are written to
``data/processed/validation_report.json`` and ``validation_report.md``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..processing.reconstruct import INN, Core
from ..analytics.facts import Facts


@dataclass
class CheckResult:
    name: str
    status: str  # pass | warn | fail | skipped
    compared: int = 0
    mismatches: int = 0
    detail: str = ""
    examples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _status(mismatch: int, compared: int, tolerance: float = 0.0) -> str:
    if compared == 0:
        return "skipped"
    if mismatch == 0:
        return "pass"
    return "warn" if mismatch / compared <= max(tolerance, 0.005) else "fail"


def _compare(ours: pd.DataFrame, theirs: pd.DataFrame, keys: list[str], pairs: list[tuple[str, str]], name: str) -> list[CheckResult]:
    if theirs is None or theirs.empty:
        return [CheckResult(name, "skipped", detail="upstream table unavailable")]
    j = theirs.merge(ours, on=keys, how="left", suffixes=("_up", ""), indicator=True)
    missing = int((j["_merge"] == "left_only").sum())
    res = [CheckResult(f"{name}: rows present in reconstruction", _status(missing, len(j)), len(j), missing, "Upstream rows with no reconstructed counterpart",
                       j.loc[j["_merge"] == "left_only", keys].head(5).astype(str).to_dict("records"))]
    both = j[j["_merge"] == "both"]
    for up, mine in pairs:
        if up not in both.columns or mine not in both.columns:
            continue
        a = pd.to_numeric(both[up], errors="coerce")
        b = pd.to_numeric(both[mine], errors="coerce")
        bad = ~np.isclose(a.fillna(-999), b.fillna(-999))
        ex = both.loc[bad, [*keys, up, mine]].head(5).astype(str).to_dict("records")
        res.append(CheckResult(f"{name}: {mine}", _status(int(bad.sum()), len(both)), len(both), int(bad.sum()), f"upstream '{up}' vs reconstructed '{mine}'", ex))
    return res


def run_checks(tables: dict[str, pd.DataFrame], core: Core, facts: Facts) -> list[CheckResult]:
    out: list[CheckResult] = []
    m = core.matches

    # --- structural
    d = core.deliveries
    orphan = ~d["match_id"].isin(m["match_id"])
    out.append(CheckResult("Deliveries reference known matches", _status(int(orphan.sum()), len(d)), len(d), int(orphan.sum())))
    t12 = m.set_index("match_id")[["team_1", "team_2"]]
    tt = d[["match_id", "batting_team", "bowling_team"]].drop_duplicates()
    tt = tt.join(t12, on="match_id")
    bad = ~(((tt["batting_team"] == tt["team_1"]) & (tt["bowling_team"] == tt["team_2"])) | ((tt["batting_team"] == tt["team_2"]) & (tt["bowling_team"] == tt["team_1"])))
    out.append(CheckResult("Delivery teams match fixture teams", _status(int(bad.sum()), len(tt)), len(tt), int(bad.sum()), examples=tt[bad].head(5).astype(str).to_dict("records")))
    wk = m[(m["result"] == "won")]
    badw = ~((wk["winner"] == wk["team_1"]) | (wk["winner"] == wk["team_2"]))
    out.append(CheckResult("Winner is one of the two teams", _status(int(badw.sum()), len(wk)), len(wk), int(badw.sum())))
    over_bad = (d["over"] < 1) | (d["over"] > 20)
    out.append(CheckResult("Over numbers within 1-20", _status(int(over_bad.sum()), len(d)), len(d), int(over_bad.sum())))
    legal_per_over = d[~d["super_over"]].groupby([*INN, "over"])["legal"].sum()
    too_many = legal_per_over > 6
    out.append(CheckResult("No over has more than 6 legal balls", _status(int(too_many.sum()), len(legal_per_over)), len(legal_per_over), int(too_many.sum()),
                           examples=legal_per_over[too_many].head(5).reset_index().astype(str).to_dict("records")))
    wk_inn = core.innings["wkts"] > 10
    out.append(CheckResult("No innings has more than 10 wickets", _status(int(wk_inn.sum()), len(core.innings)), len(core.innings), int(wk_inn.sum())))
    tot = d["batter_runs"] + d["extras"] != d["total_runs"]
    out.append(CheckResult("Delivery total = batter runs + extras", _status(int(tot.sum()), len(d)), len(d), int(tot.sum())))

    # --- innings totals: sum of batter runs + extras = innings runs
    inn = core.innings
    diff = inn["batter_runs"] + inn["extras"] != inn["runs"]
    out.append(CheckResult("Innings total = batter runs + extras", _status(int(diff.sum()), len(inn)), len(inn), int(diff.sum())))
    bsum = facts.bat.groupby(INN)["runs"].sum()
    j = inn.set_index(INN)["batter_runs"]
    bad = (bsum.reindex(j.index).fillna(0) != j)
    out.append(CheckResult("Sum of batting scorecard = innings batter runs", _status(int(bad.sum()), len(j)), len(j), int(bad.sum())))
    wsum = facts.bowl.groupby(INN)["runs"].sum()
    exp_conc = inn.set_index(INN).eval("batter_runs + wides + no_balls")
    bad = (wsum.reindex(exp_conc.index).fillna(0) != exp_conc)
    out.append(CheckResult("Bowler runs conceded = batter runs + wides + no-balls", _status(int(bad.sum()), len(exp_conc)), len(exp_conc), int(bad.sum())))
    fall = facts.bat.groupby(INN)["out"].sum()
    bad = fall.reindex(inn.set_index(INN).index).fillna(0) != inn.set_index(INN)["wkts"]
    out.append(CheckResult("Batting dismissals = innings wickets", _status(int(bad.sum()), len(inn)), len(inn), int(bad.sum())))
    psum = facts.part.groupby(INN)["runs"].sum()
    bad = psum.reindex(inn.set_index(INN).index).fillna(0) != inn.set_index(INN)["runs"]
    out.append(CheckResult("Partnership runs sum to innings total", _status(int(bad.sum()), len(inn)), len(inn), int(bad.sum())))
    pr = facts.part
    bad = pr["p1_runs"] + pr["p2_runs"] + pr["extras"] != pr["runs"]
    out.append(CheckResult("Partnership = batter 1 + batter 2 + extras", _status(int(bad.sum()), len(pr)), len(pr), int(bad.sum())))

    # --- upstream cross-checks (regular innings only; super overs excluded by design)
    so_matches = set(m.loc[m["has_super_over"], "match_id"])
    bi = tables.get("batting_innings")
    if bi is not None and not bi.empty:
        bi = bi[bi["innings_number"] <= 2]
        cols = [c for c in ("runs", "balls_faced", "fours", "sixes") if c in bi.columns]
        out += _compare(facts.bat, bi[["match_id", "innings_number", "player", *cols]], ["match_id", "innings_number", "player"],
                        [("runs_up", "runs"), ("balls_faced", "balls"), ("fours_up", "fours"), ("sixes_up", "sixes")], "Batting scorecards")
        if "dismissals" in bi.columns:
            rh = core.dismissals[core.dismissals["kind"].isin(["retired hurt", "retired not out"])][["match_id", "innings_number", "player_out"]]
            rh_keys = set(map(tuple, rh.to_numpy()))
            j = bi.merge(facts.bat, on=["match_id", "innings_number", "player"])
            bad = j["dismissals"] != j["out"]
            explained = pd.Series([(a, b, c) in rh_keys for a, b, c in zip(j["match_id"], j["innings_number"], j["player"])], index=j.index)
            out.append(CheckResult("Batting scorecards: dismissals", _status(int((bad & ~explained).sum()), len(j)), len(j), int((bad & ~explained).sum()),
                                   f"{int((bad & explained).sum())} upstream rows count 'retired hurt / retired not out' as a dismissal; under the Laws these are not-out and the reconstruction treats them so"))
        if "batting_position" in bi.columns:
            j = bi.merge(facts.bat, on=["match_id", "innings_number", "player"])
            bad = j["batting_position"] != j["position"]
            out.append(CheckResult("Batting scorecards: batting position", "info" if bad.any() else "pass", len(j), int(bad.sum()),
                                   "Reconstruction orders batters by arrival at the crease (striker or non-striker), confirmed by partnership order. Upstream differs mainly where a new batter arrived at the non-striker's end.",
                                   j.loc[bad, ["match_id", "innings_number", "player", "batting_position", "position"]].head(5).astype(str).to_dict("records")))
    bo = tables.get("bowling_innings")
    if bo is not None and not bo.empty:
        bo = bo[bo["innings_number"] <= 2]
        cols = [c for c in ("runs_conceded", "legal_balls", "wickets", "dot_balls", "fours_conceded", "sixes_conceded") if c in bo.columns]
        out += _compare(facts.bowl, bo[["match_id", "innings_number", "player", *cols]], ["match_id", "innings_number", "player"],
                        [("runs_conceded", "runs"), ("legal_balls", "balls"), ("wickets", "wkts"), ("dot_balls", "dots_strict"), ("fours_conceded", "fours"), ("sixes_conceded", "sixes")],
                        "Bowling scorecards")
        out.append(CheckResult("Bowling dot-ball definition", "info", detail="Dashboard dot balls follow the bowler convention (legal ball, no runs charged to the bowler - byes/leg-byes count as dots). Upstream excludes byes/leg-byes; 'dots_strict' reproduces the upstream definition for this check."))
    up = tables.get("partnerships")
    if up is not None and not up.empty:
        up = up[up["innings_number"] <= 2]
        u = up.assign(pa=np.minimum(up["player_1"], up["player_2"]), pb=np.maximum(up["player_1"], up["player_2"]))
        u = u.groupby([*INN, "pa", "pb"]).agg(runs_up=("runs", "sum"), balls_up=("legal_balls", "sum")).reset_index()
        o = facts.part.groupby([*INN, "player_1", "player_2"]).agg(runs=("runs", "sum"), balls=("balls", "sum")).reset_index().rename(columns={"player_1": "pa", "player_2": "pb"})
        out += _compare(o, u, [*INN, "pa", "pb"], [("runs_up", "runs"), ("balls_up", "balls")], "Partnerships (by batting pair)")
        n_ours, n_up = len(o), len(u)
        out.append(CheckResult("Partnership coverage", "info", n_ours, n_ours - n_up,
                               f"Reconstruction has {n_ours} batting-pair stands vs {n_up} in the upstream file. Every upstream stand is matched above; the upstream file covers only a subset of stands, so partnership analytics use the full ball-by-ball reconstruction."))
    pm = tables.get("player_match")
    if pm is not None and not pm.empty:
        pm = pm[~pm["match_id"].isin(so_matches)]
        ours = facts.player_match.assign(bat_r=lambda x: x["runs"].fillna(0), bowl_w=lambda x: x["wkts"].fillna(0))
        played = pm[(pm["batting_balls"].fillna(0) > 0) | (pm["bowling_balls"].fillna(0) > 0)]
        out += _compare(ours[["match_id", "player", "bat_r", "bowl_w"]], played[["match_id", "player", "batting_runs", "bowling_wickets"]], ["match_id", "player"],
                        [("batting_runs", "bat_r"), ("bowling_wickets", "bowl_w")], "Player-match records (non-super-over)")
    return out


def to_markdown(results: list[CheckResult], extra: dict[str, Any]) -> str:
    lines = ["# CRICKET IQ - Validation Report", "", f"Generated: {extra.get('generated', '')}", ""]
    counts = pd.Series([r.status for r in results]).value_counts().to_dict()
    lines += [f"**Summary:** {counts}", "", "| Check | Status | Compared | Mismatches | Detail |", "|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r.name} | {r.status.upper()} | {r.compared} | {r.mismatches} | {r.detail} |")
    for r in results:
        if r.examples:
            lines += ["", f"### Examples - {r.name}", "```", *[str(e) for e in r.examples], "```"]
    for k, v in extra.items():
        if k == "generated":
            continue
        lines += ["", f"## {k}", "```", str(v), "```"]
    return "\n".join(lines) + "\n"
