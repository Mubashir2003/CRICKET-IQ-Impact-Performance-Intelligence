"""Player identification, participation and the 11-match eligibility rule.

Identity: the source has no player IDs, so a player is identified by name *within
a gender*. Possible name collisions (the same name appearing for both sides of
one match) are flagged in the audit.

Participation (distinct match IDs) is the union of:
* every match where the player batted, was at the non-striker's end, bowled or was dismissed;
* every match in ``player_match`` (playing-XI level records, includes fielding-only games).
The upstream ``player_appearances`` count (playing-XI based) is used as a
cross-check and, when enabled in settings, as a lower bound.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config import Settings
from ..ingestion.loader import Issue
from .reconstruct import Core


@dataclass
class PlayerRegistry:
    participation: pd.DataFrame  # gender, match_id, player, team
    players: pd.DataFrame  # one row per gender+player
    audit: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)


def build_players(core: Core, tables: dict[str, pd.DataFrame], settings: Settings) -> PlayerRegistry:
    issues: list[Issue] = []
    d = core.deliveries
    parts = [
        d[["gender", "match_id", "batter", "batting_team"]].set_axis(["gender", "match_id", "player", "team"], axis=1),
        d[["gender", "match_id", "non_striker", "batting_team"]].set_axis(["gender", "match_id", "player", "team"], axis=1),
        d[["gender", "match_id", "bowler", "bowling_team"]].set_axis(["gender", "match_id", "player", "team"], axis=1),
    ]
    pm = tables.get("player_match")
    if pm is not None and not pm.empty:
        parts.append(pm[["gender", "match_id", "player", "team"]])
    part = pd.concat(parts, ignore_index=True).dropna(subset=["player"]).drop_duplicates(["gender", "match_id", "player", "team"])

    # name collisions: one name on both sides of a match
    sides = part.groupby(["gender", "match_id", "player"])["team"].nunique()
    coll = sides[sides > 1].reset_index()[["gender", "player", "match_id"]]
    if len(coll):
        issues.append(Issue("*", "players", "warning", "Same player name appears for both teams in a match (possible name collision)", len(coll)))
    part = part.drop_duplicates(["gender", "match_id", "player"])

    m = core.matches.set_index("match_id")
    part["competition"] = part["match_id"].map(m["competition"])
    part["is_international"] = part["match_id"].map(m["is_international"]).fillna(False).astype(bool)
    part["date"] = part["match_id"].map(m["date"])

    g = part.groupby(["gender", "player"])
    players = g.agg(distinct_matches=("match_id", "nunique"), first_match=("date", "min"), last_match=("date", "max")).reset_index()
    teams = part.groupby(["gender", "player"])["team"].agg(lambda s: s.value_counts().index.tolist())
    players["teams"] = players.set_index(["gender", "player"]).index.map(teams)
    comps = part.groupby(["gender", "player"])["competition"].agg(lambda s: s.value_counts().index.tolist())
    players["competitions"] = players.set_index(["gender", "player"]).index.map(comps)
    intl = part[part["is_international"] & part["team"].isin(settings.countries)]
    countries = intl.groupby(["gender", "player"])["team"].agg(lambda s: s.value_counts().index.tolist())
    players["countries"] = players.set_index(["gender", "player"]).index.map(countries)
    players["countries"] = players["countries"].apply(lambda v: v if isinstance(v, list) else [])
    players["country"] = players["countries"].apply(lambda v: v[0] if v else None)

    pa = tables.get("player_appearances")
    if pa is not None and not pa.empty:
        players = players.merge(pa[["gender", "player", "matches_played"]].rename(columns={"matches_played": "appearances_upstream"}), on=["gender", "player"], how="left")
    else:
        players["appearances_upstream"] = pd.NA
    use_up = settings["eligibility"]["use_upstream_appearance_counts"]
    up = pd.to_numeric(players["appearances_upstream"], errors="coerce")
    players["matches"] = players["distinct_matches"]
    if use_up:
        players["matches"] = pd.concat([players["distinct_matches"], up], axis=1).max(axis=1).astype(int)
    thr = settings["eligibility"]["min_distinct_matches"]
    players["eligible"] = players["matches"] >= thr
    over = up.notna() & (players["distinct_matches"] > up)
    if over.any():
        issues.append(Issue("*", "players", "info", "Players with more distinct matches in ball-by-ball data than the upstream appearance count", int(over.sum())))

    audit = players[["gender", "player", "distinct_matches", "appearances_upstream", "matches", "eligible"]].copy()
    audit["reason"] = audit["eligible"].map({True: f"{thr}+ distinct matches", False: f"fewer than {thr} distinct matches"})
    ex = tables.get("excluded_players")
    if ex is not None and not ex.empty and "eligible" in ex.columns:
        up_el = ex.set_index(["gender", "player"])["eligible"]
        audit["upstream_eligible"] = audit.set_index(["gender", "player"]).index.map(up_el)
        pa_el = pa.set_index(["gender", "player"])["eligible"] if pa is not None and "eligible" in pa.columns else None
        if pa_el is not None:
            audit["upstream_eligible"] = audit["upstream_eligible"].fillna(pd.Series(audit.set_index(["gender", "player"]).index.map(pa_el), index=audit.index))
    players = players.merge(coll.groupby(["gender", "player"]).size().rename("name_collisions").reset_index(), on=["gender", "player"], how="left")
    players["name_collisions"] = players["name_collisions"].fillna(0).astype(int)
    for gk, sub in players.groupby("gender"):
        issues.append(Issue(gk, "players", "info", f"Eligible players ({thr}+ matches): {int(sub['eligible'].sum())} of {len(sub)}"))
    return PlayerRegistry(participation=part, players=players, audit=audit, issues=issues)
