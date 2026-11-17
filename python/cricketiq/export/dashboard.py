"""Write compact, dashboard-ready JSON.

Layout (per gender ``g``)::

    data/dashboard/manifest.json
    data/dashboard/definitions.json
    data/dashboard/<g>/core.json        dimensions + match table
    data/dashboard/<g>/bat.json         batting innings facts   (columnar)
    data/dashboard/<g>/bowl.json        bowling innings facts   (columnar)
    data/dashboard/<g>/part.json        partnerships            (columnar)
    data/dashboard/<g>/teaminn.json     team innings            (columnar)
    data/dashboard/<g>/players.json     eligible-player metrics, roles, impact
    data/dashboard/<g>/matches/<id>.json  match scorecards
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import Settings
from .definitions import METRICS, PRESSURE_TEXT

RES_CODE = {"W": "W", "L": "L", "T": "T", "N": "N"}
PHASE_IDX = {"powerplay": 0, "middle": 1, "death": 2}


def _clean(v: Any, nd: int = 3) -> Any:
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        r = round(f, nd)
        return int(r) if r.is_integer() else r
    if isinstance(v, (pd.Timestamp, date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (list, tuple)):
        return [_clean(x, nd) for x in v]
    if isinstance(v, np.ndarray):
        return [_clean(x, nd) for x in v.tolist()]
    if v is pd.NA:
        return None
    return v


def _col(series: pd.Series, nd: int = 3) -> list:
    return [_clean(x, nd) for x in series.tolist()]


def _dump(obj: Any, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    path.write_text(txt, encoding="utf-8")
    return len(txt)


class Dims:
    def __init__(self) -> None:
        self.maps: dict[str, dict[str, int]] = {}
        self.lists: dict[str, list[str]] = {}

    def idx(self, kind: str, values: pd.Series) -> list[int]:
        mp = self.maps.setdefault(kind, {})
        lst = self.lists.setdefault(kind, [])
        out = []
        for v in values.tolist():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                out.append(-1)
                continue
            if v not in mp:
                mp[v] = len(lst)
                lst.append(v)
            out.append(mp[v])
        return out


def _dismissal_text(kind: str | None, bowler: str | None) -> str:
    if not kind:
        return "not out"
    b = bowler or ""
    return {
        "bowled": f"b {b}", "caught": f"c ? b {b}", "caught and bowled": f"c & b {b}", "lbw": f"lbw b {b}",
        "stumped": f"st ? b {b}", "hit wicket": f"hit wicket b {b}", "run out": "run out",
    }.get(kind, kind)


def export_dashboard(out_dir: Path, settings: Settings, ctx: dict[str, Any]) -> dict[str, int]:
    """Write all JSON files. ``ctx`` carries the analytics results from the pipeline."""
    core, facts, reg = ctx["core"], ctx["facts"], ctx["registry"]
    players_all: pd.DataFrame = ctx["players_full"]
    by_comp: pd.DataFrame = ctx["by_comp"]
    pei: pd.DataFrame = ctx["pei"]
    pos_table: pd.DataFrame = ctx["position_table"]

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    sizes: dict[str, int] = {}
    manifest: dict[str, Any] = {
        "app": "CRICKET IQ",
        "updated": date.today().isoformat(),
        "season": "2026",
        "min_matches": settings["eligibility"]["min_distinct_matches"],
        "phases": {k: {"label": v["label"], "overs": f"{v['first_over']}-{v['last_over']}"} for k, v in settings.phases.items()},
        "pressure_definition": PRESSURE_TEXT,
        "genders": [],
    }
    sizes["definitions.json"] = _dump({k: {"label": a, "fmt": b, "desc": c, "hib": d} for k, (a, b, c, d) in METRICS.items()}, out_dir / "definitions.json")

    for g, gspec in settings.genders.items():
        m = core.matches[core.matches["gender"] == g].sort_values("date").reset_index(drop=True)
        if m.empty:
            continue
        gd = out_dir / g
        dims = Dims()
        mi = {mid: i for i, mid in enumerate(m["match_id"])}
        teams_all = pd.concat([m["team_1"], m["team_2"]])
        dims.idx("team", teams_all)
        comps = m.groupby("competition").agg(type=("comp_type", "first"), n=("match_id", "size"), start=("date", "min"), end=("date", "max")).reset_index().sort_values("n", ascending=False)
        dims.idx("comp", comps["competition"])

        def ti(s: pd.Series) -> list[int]:
            return dims.idx("team", s)

        bat = facts.bat[facts.bat["gender"] == g]
        bowl = facts.bowl[facts.bowl["gender"] == g]
        part = facts.part[facts.part["gender"] == g]
        tinn = facts.team_inn[facts.team_inn["gender"] == g]
        preg = reg.players[reg.players["gender"] == g]
        elig = preg[preg["eligible"]].sort_values("player")
        dims.idx("player", elig["player"])  # eligible players first -> index < n_eligible

        matches_json = {
            "id": m["match_id"].tolist(), "date": _col(m["date"]), "comp": dims.idx("comp", m["competition"]), "series": dims.idx("series", m["series"]),
            "venue": dims.idx("venue", m["venue"]), "city": dims.idx("city", m["city"]) if "city" in m else [], "t1": ti(m["team_1"]), "t2": ti(m["team_2"]),
            "winner": ti(m["effective_winner"]), "result": m["result"].map({"won": "W", "tie": "T", "no result": "N"}).tolist(),
            "so": [int(x) for x in m["has_super_over"]], "bat1": ti(m["bat1"]), "r1": _col(m["r1"]), "w1": _col(m["w1"]), "b1": _col(m["b1"]),
            "r2": _col(m["r2"]), "w2": _col(m["w2"]), "b2": _col(m["b2"]), "close": [int(x) for x in m["close_finish"]], "low": [int(x) for x in m["low_scoring"]],
            "red": [int(x) for x in m["reduced_or_revised"]], "mr": _col(m["margin_runs"]), "mw": _col(m["margin_wkts"]),
        }

        def facts_cols(df: pd.DataFrame, spec: dict[str, str], nd: int = 2) -> dict[str, list]:
            out: dict[str, list] = {"m": [mi[x] for x in df["match_id"]]}
            for k, c in spec.items():
                if c in ("player", "player_1", "player_2", "out_bowler", "broken_by"):
                    out[k] = dims.idx("player", df[c])
                elif c in ("team", "opponent"):
                    out[k] = ti(df[c])
                elif c == "result":
                    out[k] = df[c].tolist()
                else:
                    out[k] = _col(df[c], nd)
            return out

        bat_spec = {"i": "innings_number", "p": "player", "t": "team", "o": "opponent", "pos": "position", "r": "runs", "b": "balls", "f4": "fours", "f6": "sixes",
                    "d": "dots", "out": "out", "er": "exp_runs", "eo": "exp_outs", "tr": "team_runs", "res": "result", "ob": "out_bowler",
                    "pb": "p_balls", "pr": "p_runs", "po": "p_out", "per": "p_exp_runs"}
        for s in ("pp", "mid", "dth"):
            bat_spec.update({f"{s}_r": f"{s}_runs", f"{s}_b": f"{s}_balls", f"{s}_4": f"{s}_fours", f"{s}_6": f"{s}_sixes", f"{s}_d": f"{s}_dots", f"{s}_o": f"{s}_outs", f"{s}_er": f"{s}_exp_runs"})
        b_sorted = bat.assign(_mi=bat["match_id"].map(mi)).sort_values(["_mi", "innings_number", "position"])
        bj = facts_cols(b_sorted, bat_spec)
        bj["how"] = dims.idx("how", b_sorted["how_out"])

        bowl_spec = {"i": "innings_number", "p": "player", "t": "team", "o": "opponent", "bl": "balls", "dl": "deliveries", "r": "runs", "w": "wkts", "d": "dots",
                     "f4": "fours", "f6": "sixes", "wd": "wides", "nb": "no_balls", "md": "maidens", "er": "exp_runs", "ew": "exp_wkts", "eb": "exp_bnd", "ed": "exp_dots",
                     "tw": "team_bowl_wkts", "td": "team_dots", "res": "result", "pb": "p_balls", "pr": "p_runs", "pw": "p_wkts", "per": "p_exp_runs", "pew": "p_exp_wkts"}
        for s in ("pp", "mid", "dth"):
            bowl_spec.update({f"{s}_b": f"{s}_balls", f"{s}_r": f"{s}_runs", f"{s}_w": f"{s}_wkts", f"{s}_d": f"{s}_dots", f"{s}_bd": f"{s}_bnd", f"{s}_er": f"{s}_exp_runs"})
        o_sorted = bowl.assign(_mi=bowl["match_id"].map(mi)).sort_values(["_mi", "innings_number"])
        oj = facts_cols(o_sorted, bowl_spec)

        part_spec = {"i": "innings_number", "t": "team", "o": "opponent", "a": "player_1", "b": "player_2", "r": "runs", "bl": "balls", "ra": "p1_runs", "rb": "p2_runs",
                     "x": "extras", "wn": "wicket_no", "ub": "unbroken", "pr": "pressure", "bb": "broken_by", "res": "result", "n": "number"}
        p_sorted = part.assign(_mi=part["match_id"].map(mi)).sort_values(["_mi", "innings_number", "number"])
        pj = facts_cols(p_sorted, part_spec)
        pj["ub"] = [int(bool(x)) for x in pj["ub"]]
        pj["pr"] = [int(bool(x)) for x in pj["pr"]]
        pj["ph"] = [PHASE_IDX.get(x, 0) for x in p_sorted["start_phase"]]

        tspec = {"i": "innings_number", "t": "team", "o": "opponent", "r": "runs", "w": "wkts", "b": "legal_balls", "f4": "fours", "f6": "sixes", "x": "extras", "wd": "wides",
                 "nb": "no_balls", "d": "dots", "res": "result"}
        for s in ("pp", "mid", "dth"):
            tspec.update({f"{s}_r": f"{s}_runs", f"{s}_b": f"{s}_balls", f"{s}_w": f"{s}_wkts"})
        t_sorted = tinn.assign(_mi=tinn["match_id"].map(mi)).sort_values(["_mi", "innings_number"])
        tj = facts_cols(t_sorted, tspec)

        # ---------------- players (eligible only)
        pm = players_all[players_all["gender"] == g].copy().set_index("player").reindex(elig["player"]).reset_index()
        meta_cols = ["player", "country", "countries", "teams", "competitions", "matches", "primary_role", "batting_roles", "bowling_roles", "median_position", "first_match", "last_match"]
        metric_cols = [c for c in pm.columns if c not in meta_cols and c not in ("gender", "eligible", "distinct_matches", "appearances_upstream", "name_collisions")]
        rows = []
        for r in pm.itertuples(index=False):
            d = r._asdict()
            rows.append(
                {
                    "i": dims.maps["player"][d["player"]], "n": d["player"], "c": _clean(d["country"]) if isinstance(d["country"], str) else None, "cs": d["countries"] if isinstance(d["countries"], list) else [],
                    "tm": ti(pd.Series(d["teams"] or [])), "cp": dims.idx("comp", pd.Series(d["competitions"] or [])), "mt": _clean(d["matches"]),
                    "role": d["primary_role"] if isinstance(d["primary_role"], str) else None, "br": d["batting_roles"] if isinstance(d["batting_roles"], list) else [], "wr": d["bowling_roles"] if isinstance(d["bowling_roles"], list) else [], "fm": _clean(d["first_match"]), "lm": _clean(d["last_match"]),
                    "x": [_clean(d[c], 3) for c in metric_cols],
                }
            )
        bc = by_comp[by_comp["gender"] == g]
        comp_fields = [c for c in bc.columns if c not in ("gender", "player", "competition")]
        comp_rows: dict[str, list] = {}
        for cname, sub in bc.groupby("competition"):
            sub = sub[sub["player"].isin(dims.maps["player"])]
            ci = str(dims.maps["comp"][cname])
            comp_rows[ci] = [[dims.maps["player"][p], *[_clean(v, 3) for v in vals]] for p, *vals in sub[["player", *comp_fields]].itertuples(index=False)]
        pe = pei[pei["gender"] == g]
        pe = pe[pe["player"].isin(dims.maps["player"])]
        pei_rows = [[dims.maps["player"][r.player], r.pos_group, int(r.innings), _clean(r.runs), _clean(r.run_production, 2), _clean(r.team_contribution, 2), _clean(r.scoring_efficiency, 2), _clean(r.pressure_performance, 2), _clean(r.pei, 1)] for r in pe.itertuples()]
        pt = pos_table[pos_table["gender"] == g]
        players_json = {
            "fields": metric_cols, "rows": rows, "comp_fields": comp_fields, "by_comp": comp_rows,
            "pei_fields": ["p", "group", "innings", "runs", "run_production", "team_contribution", "scoring_efficiency", "pressure_performance", "pei"], "pei": pei_rows,
            "positions": {c: _col(pt[c], 2) for c in pt.columns if c != "gender"},
        }

        core_json = {
            "gender": g, "label": gspec["label"], "matches": matches_json,
            "comps": [{"name": r.competition, "type": r.type, "n": int(r.n), "start": _clean(r.start), "end": _clean(r.end)} for r in comps.itertuples()],
            "n_eligible": int(len(elig)), "players_total": int(len(preg)),
            "flags": {t: settings.countries.get(t) for t in dims.lists["team"] if t in settings.countries},
        }
        # dims last (after every idx call)
        sizes[f"{g}/bat.json"] = _dump(bj, gd / "bat.json")
        sizes[f"{g}/bowl.json"] = _dump(oj, gd / "bowl.json")
        sizes[f"{g}/part.json"] = _dump(pj, gd / "part.json")
        sizes[f"{g}/teaminn.json"] = _dump(tj, gd / "teaminn.json")
        sizes[f"{g}/players.json"] = _dump(players_json, gd / "players.json")
        n_md = _export_matches(gd / "matches", g, m, core, facts, ctx)
        core_json["dims"] = {k: v for k, v in dims.lists.items()}
        sizes[f"{g}/core.json"] = _dump(core_json, gd / "core.json")
        manifest["genders"].append({
            "key": g, "label": gspec["label"], "matches": int(len(m)), "from": _clean(m["date"].min()), "to": _clean(m["date"].max()),
            "eligible_players": int(len(elig)), "competitions": int(len(comps)), "match_files": n_md,
        })
    sizes["manifest.json"] = _dump(manifest, out_dir / "manifest.json")
    return sizes


def _export_matches(folder: Path, g: str, m: pd.DataFrame, core, facts, ctx) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    d = facts.deliveries
    d = d[d["gender"] == g]
    dall = core.deliveries[core.deliveries["gender"] == g]
    dis = core.dismissals[(core.dismissals["gender"] == g) & ~core.dismissals["super_over"] & core.dismissals["is_out"]]
    bat = facts.bat[facts.bat["gender"] == g]
    bowl = facts.bowl[facts.bowl["gender"] == g]
    part = facts.part[facts.part["gender"] == g]
    pm = facts.player_match[facts.player_match["gender"] == g]
    groups = {k: v for k, v in d.groupby("match_id")}
    so_groups = {k: v for k, v in dall[dall["super_over"]].groupby("match_id")}
    bat_g = {k: v for k, v in bat.groupby("match_id")}
    bowl_g = {k: v for k, v in bowl.groupby("match_id")}
    part_g = {k: v for k, v in part.groupby("match_id")}
    dis_g = {k: v for k, v in dis.groupby("match_id")}
    pm_g = {k: v for k, v in pm.groupby("match_id")}
    n = 0
    for r in m.itertuples(index=False):
        mid = r.match_id
        dd = groups.get(mid)
        innings = []
        if dd is not None:
            for inn_no, di in dd.groupby("innings_number"):
                di = di.sort_values("seq")
                di = di.assign(lio=di.groupby("over")["legal"].cumsum())
                b = bat_g.get(mid)
                b = b[b["innings_number"] == inn_no].sort_values("position") if b is not None else pd.DataFrame()
                o = bowl_g.get(mid)
                o = o[o["innings_number"] == inn_no] if o is not None else pd.DataFrame()
                if len(o):
                    first = di.groupby("bowler")["seq"].min()
                    o = o.assign(_f=o["player"].map(first)).sort_values("_f")
                pp = part_g.get(mid)
                pp = pp[pp["innings_number"] == inn_no] if pp is not None else pd.DataFrame()
                dz = dis_g.get(mid)
                dz = dz[dz["innings_number"] == inn_no].sort_values("seq") if dz is not None else pd.DataFrame()
                fow = []
                if len(dz):
                    ds = di.set_index("seq")
                    for k, x in enumerate(dz.itertuples(), 1):
                        row = ds.loc[x.seq]
                        fow.append({"w": k, "score": int(row["score_before"] + row["total_runs"]), "over": f"{int(row['over']) - 1}.{int(row['lio'])}", "p": x.player_out})
                overs = di.groupby("over").agg(r=("total_runs", "sum"), w=("team_wkts", "sum")).reset_index()
                phases = di.groupby("phase").agg(r=("total_runs", "sum"), w=("team_wkts", "sum"), b=("legal", "sum"))
                legal = int(di["legal"].sum())
                innings.append({
                    "n": int(inn_no), "team": di["batting_team"].iloc[0], "opp": di["bowling_team"].iloc[0], "runs": int(di["total_runs"].sum()),
                    "wkts": int(di["team_wkts"].sum()), "overs": f"{legal // 6}.{legal % 6}", "balls": legal,
                    "extras": {"total": int(di["extras"].sum()), "wides": int(di["wides"].sum()), "no_balls": int(di["no_balls"].sum()), "other": int(di["other_extras"].sum())},
                    "batting": [{"p": x.player, "pos": int(x.position), "r": int(x.runs), "b": int(x.balls), "f4": int(x.fours), "f6": int(x.sixes),
                                 "sr": _clean(x.runs / x.balls * 100 if x.balls else None, 1), "how": _dismissal_text(x.how_out, x.out_bowler) if x.out else "not out",
                                 "out": int(x.out)} for x in b.itertuples()] if len(b) else [],
                    "bowling": [{"p": x.player, "o": f"{int(x.balls) // 6}.{int(x.balls) % 6}", "m": int(x.maidens), "r": int(x.runs), "w": int(x.wkts),
                                 "econ": _clean(x.runs / x.balls * 6 if x.balls else None, 2), "d": int(x.dots), "wd": int(x.wides), "nb": int(x.no_balls)} for x in o.itertuples()] if len(o) else [],
                    "fow": fow,
                    "partnerships": [{"wn": int(x.wicket_no), "a": x.player_1, "b": x.player_2, "r": int(x.runs), "bl": int(x.balls), "ra": int(x.p1_runs), "rb": int(x.p2_runs), "x": int(x.extras), "ub": bool(x.unbroken)} for x in pp.itertuples()] if len(pp) else [],
                    "overs_prog": {"o": overs["over"].astype(int).tolist(), "r": overs["r"].astype(int).tolist(), "w": overs["w"].astype(int).tolist()},
                    "phases": {k: {"r": int(v.r), "w": int(v.w), "b": int(v.b)} for k, v in phases.iterrows()},
                })
        so = []
        sg = so_groups.get(mid)
        if sg is not None:
            for inn_no, s in sg.groupby("innings_number"):
                so.append({"n": int(inn_no), "team": s["batting_team"].iloc[0], "runs": int(s["total_runs"].sum()), "wkts": int(s["team_wkts"].sum())})
        contrib = []
        pz = pm_g.get(mid)
        if pz is not None:
            for x in pz.sort_values("match_score", ascending=False).head(8).itertuples():
                contrib.append({"p": x.player, "team": x.team, "runs": _clean(x.runs) if x.batted else None, "balls": _clean(x.balls) if x.batted else None, "wkts": _clean(x.wkts) if x.bowled else None, "conceded": _clean(x.conceded) if x.bowled else None,
                                "bat": _clean(x.bat_value, 1) if x.batted else None, "bowl": _clean(x.bowl_value, 1) if x.bowled else None, "score": _clean(x.match_score, 1),
                                "exceptional": bool(x.exceptional), "significant": bool(x.significant), "mwi": bool(x.match_winning_innings), "mwb": bool(x.match_winning_bowling)})
        if r.result == "won":
            if pd.notna(r.margin_runs):
                res_txt = f"{r.winner} won by {int(r.margin_runs)} runs"
            elif pd.notna(r.margin_wkts):
                res_txt = f"{r.winner} won by {int(r.margin_wkts)} wickets"
            else:
                res_txt = f"{r.winner} won"
            if r.reduced_or_revised:
                res_txt += " (reduced overs / revised target)"
        elif r.result == "tie":
            res_txt = "Match tied" + (f" - {r.super_over_winner} won the super over" if isinstance(r.super_over_winner, str) else "")
        else:
            res_txt = "No result"
        doc = {"id": mid, "date": _clean(r.date), "comp": r.competition, "series": r.series, "venue": r.venue, "city": r.city if isinstance(r.city, str) else None,
               "teams": [r.team_1, r.team_2], "winner": r.effective_winner if isinstance(r.effective_winner, str) else None, "result": res_txt,
               "close": bool(r.close_finish), "innings": innings, "super_over": so, "contributions": contrib}
        _dump(doc, folder / f"{mid}.json")
        n += 1
    return n
