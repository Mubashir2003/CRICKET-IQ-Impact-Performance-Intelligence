"""EXPERIMENTAL composite impact indices.

Method (fully configurable in settings.json -> impact):
1. Each component metric is z-scored within gender across players to whom the
   index applies (enough balls faced / bowled / under pressure).
2. The weighted sum of z-scores is shrunk toward the average by n / (n + k),
   where n is the relevant ball count, so small samples cannot top the rankings.
3. The shrunk score is converted to a 0-100 percentile within gender.
4. Overall Impact = weighted mean of the APPLICABLE component percentiles,
   weights renormalised (a batter who does not bowl gets no bowling component
   rather than a zero). Fielding is disabled: the source data has no fielder names.

The weights are an initial, transparent starting point - not established
science. Split-half reliability is reported in the validation output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Settings
from .metrics import KEY, div


def _z(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std(ddof=0)
    if not (sd and np.isfinite(sd) and sd > 0):
        return s * 0
    return ((s - s.mean()) / sd).clip(-4, 4)


def _composite(df: pd.DataFrame, mask: pd.Series, comps: dict[str, pd.Series], weights: dict[str, float], n: pd.Series, k: float) -> pd.Series:
    """Weighted z-score composite over players in ``mask``, shrunk by n/(n+k)."""
    total = pd.Series(0.0, index=df.index)
    for name, w in weights.items():
        z = comps[name].where(mask).groupby(df["gender"]).transform(_z)
        total += w * z.fillna(0)  # missing component (e.g. too few innings for consistency) -> average
    return (total * n / (n + k)).where(mask)


def _pct(df: pd.DataFrame, raw: pd.Series) -> pd.Series:
    return raw.groupby(df["gender"]).rank(pct=True) * 100


def raw_scores(met: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Unscaled composite scores (used for both the index and reliability checks)."""
    c = settings["impact"]
    df = met.copy().reset_index(drop=True)
    f = lambda col: pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=df.index)  # noqa: E731
    balls, bballs = f("balls").fillna(0), f("legal_balls").fillna(0)
    bat_ok = balls >= c["min_balls"]["batting"]
    bowl_ok = bballs >= c["min_balls"]["bowling"]
    bat_comps = {
        "runs_above_expected_per_innings": pd.Series(div(f("runs_above_expected"), f("bat_innings")), index=df.index),
        "strike_rate_vs_expected": f("sr_above_avg"),
        "average_vs_expected": pd.Series(np.log(np.clip(div(div(f("runs"), f("outs") + 1), div(f("expected_runs"), f("expected_outs") + 1)), 0.2, 5)), index=df.index),
        "team_run_share": f("team_run_contribution_pct"),
        "consistency": f("consistency_index"),
    }
    bowl_comps = {
        "runs_saved_per_24": f("runs_saved_per_24"),
        "wickets_above_expected_per_24": f("wkts_above_exp_per_24"),
        "dot_ball_vs_expected": f("dot_ball_index"),
        "boundary_suppression": f("boundary_suppression_index"),
        "consistency": f("bowling_consistency"),
    }
    df["bat_raw"] = _composite(df, bat_ok, bat_comps, c["batting_weights"], balls, c["shrinkage_balls"]["batting"])
    df["bowl_raw"] = _composite(df, bowl_ok, bowl_comps, c["bowling_weights"], bballs, c["shrinkage_balls"]["bowling"])
    pb, pbb = f("pressure_balls").fillna(0), f("pressure_balls_bowled").fillna(0)
    p_bat = pd.Series(div(f("pressure_runs_above_expected"), pb, 100), index=df.index)
    p_bowl = pd.Series(div(f("pressure_runs_saved"), pbb, 24), index=df.index)
    tot = pb + pbb
    p_ok = tot >= c["min_balls"]["pressure"]
    zb = p_bat.where(pb >= 12).groupby(df["gender"]).transform(_z).fillna(0)
    zo = p_bowl.where(pbb >= 12).groupby(df["gender"]).transform(_z).fillna(0)
    comb = div(zb * pb + zo * pbb, tot)
    df["pressure_raw"] = np.where(p_ok, comb * tot / (tot + c["shrinkage_balls"]["pressure"]), np.nan)
    # winning contribution: only components the player has an opportunity for
    win_ok = f("matches_in_scope").fillna(0) >= c["min_matches_winning"]
    ww = c["winning_weights"]
    zr = f("winning_run_share_pct").where(bat_ok).groupby(df["gender"]).transform(_z)
    zw = f("winning_wicket_share_pct").where(bowl_ok).groupby(df["gender"]).transform(_z)
    zm = f("match_winning_pct").groupby(df["gender"]).transform(_z)
    za = f("avg_match_score_in_wins").groupby(df["gender"]).transform(_z)
    num = ww["winning_run_share"] * zr.fillna(0) * bat_ok + ww["winning_wicket_share"] * zw.fillna(0) * bowl_ok + ww["match_winning_frequency"] * zm.fillna(0) + ww["avg_score_in_wins"] * za.fillna(0)
    den = ww["winning_run_share"] * bat_ok + ww["winning_wicket_share"] * bowl_ok + ww["match_winning_frequency"] + ww["avg_score_in_wins"]
    m = f("matches_in_scope").fillna(0)
    df["winning_raw"] = np.where(win_ok, div(num, den) * m / (m + 10), np.nan)
    df["bat_applicable"], df["bowl_applicable"], df["pressure_applicable"] = bat_ok, bowl_ok, p_ok
    return df


def impact_indices(met: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    c = settings["impact"]
    df = raw_scores(met, settings)
    out = df[KEY].copy()
    for name in ("bat", "bowl", "pressure", "winning"):
        raw = df[f"{name}_raw"]
        out[f"{name}_impact"] = _pct(df, raw).where(raw.notna())
    out = out.rename(columns={"bat_impact": "batting_impact", "bowl_impact": "bowling_impact", "winning_impact": "winning_contribution"})
    w = c["overall_weights"]
    parts = {"batting": out["batting_impact"], "bowling": out["bowling_impact"], "pressure": out["pressure_impact"]}
    num = sum(w[k] * v.fillna(0) for k, v in parts.items())
    den = sum(w[k] * v.notna() for k, v in parts.items())
    out["overall_impact"] = pd.Series(div(num, den), index=out.index).where(den > 0)
    out["impact_rank"] = out.groupby("gender")["overall_impact"].rank(ascending=False, method="min")
    out["fielding_impact"] = np.nan  # not available in source data
    return out


def reliability(met_a: pd.DataFrame, met_b: pd.DataFrame, settings: Settings) -> dict:
    """Spearman correlation of raw component scores computed on two disjoint match halves."""
    a, b = raw_scores(met_a, settings), raw_scores(met_b, settings)
    j = a.merge(b, on=KEY, suffixes=("_a", "_b"))
    res: dict = {}
    for g, sub in j.groupby("gender"):
        for comp in ("bat_raw", "bowl_raw", "pressure_raw", "winning_raw"):
            s = sub[[f"{comp}_a", f"{comp}_b"]].dropna()
            if len(s) >= 15:
                res[f"{g}/{comp.replace('_raw', '')}"] = {"players": int(len(s)), "spearman": round(float(s.iloc[:, 0].rank().corr(s.iloc[:, 1].rank())), 3)}
    return res
