"""Expected schemas for the 10 input CSV files.

Each table declares its columns with a logical type, whether the column is
required, and accepted aliases (so slightly different exports still load).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ColType = Literal["str", "int", "float", "bool", "date"]


@dataclass(frozen=True)
class Column:
    name: str
    type: ColType
    required: bool = True
    nullable: bool = False
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[Column, ...]
    key: tuple[str, ...] = ()
    optional_file: bool = False
    description: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def required(self) -> list[str]:
        return [c.name for c in self.columns if c.required]


C = Column

SCHEMAS: dict[str, TableSchema] = {
    "matches": TableSchema(
        "matches",
        (
            C("match_id", "str"),
            C("gender", "str", required=False),
            C("date", "date", aliases=("start_date", "match_date")),
            C("match_type", "str", required=False),
            C("competition", "str", aliases=("event_name", "event", "tournament")),
            C("season", "str", required=False),
            C("venue", "str", required=False, nullable=True, aliases=("ground",)),
            C("city", "str", required=False, nullable=True),
            C("team_1", "str", aliases=("team1", "home_team")),
            C("team_2", "str", aliases=("team2", "away_team")),
            C("winner", "str", nullable=True, aliases=("winning_team",)),
            C("result_type", "str", nullable=True, required=False, aliases=("result",)),
        ),
        key=("match_id",),
        description="One row per match",
    ),
    "deliveries": TableSchema(
        "deliveries",
        (
            C("match_id", "str"),
            C("gender", "str", required=False),
            C("date", "date", required=False),
            C("competition", "str", required=False),
            C("innings_number", "int", aliases=("innings",)),
            C("batting_team", "str"),
            C("bowling_team", "str"),
            C("over", "int", aliases=("over_number",)),
            C("delivery_in_over", "int", aliases=("ball", "ball_in_over")),
            C("batter", "str", aliases=("striker", "batsman")),
            C("non_striker", "str"),
            C("bowler", "str"),
            C("batter_runs", "int", aliases=("runs_off_bat", "runs_batter")),
            C("extras", "int", aliases=("extra_runs", "runs_extras")),
            C("total_runs", "int", aliases=("runs_total",)),
            C("wides", "int", aliases=("wide_runs",)),
            C("no_balls", "int", aliases=("noballs", "noball_runs")),
            C("is_legal_delivery", "bool", aliases=("legal_ball", "is_legal")),
            C("is_wicket", "bool", aliases=("wicket",)),
            C("dismissal_kinds", "str", nullable=True, aliases=("wicket_type", "dismissal_kind")),
            C("players_out", "str", nullable=True, aliases=("player_dismissed", "player_out")),
        ),
        description="One row per delivery (ball-by-ball)",
    ),
    "batting_innings": TableSchema(
        "batting_innings",
        (
            C("match_id", "str"),
            C("innings_number", "int"),
            C("team", "str"),
            C("player", "str"),
            C("batting_position", "int", required=False),
            C("runs", "int"),
            C("balls_faced", "int"),
            C("fours", "int", required=False),
            C("sixes", "int", required=False),
            C("dismissals", "int", required=False),
            C("not_out", "bool", required=False),
            C("team_innings_runs", "int", required=False),
        ),
        key=("match_id", "innings_number", "player"),
        description="Upstream batting scorecards (used for cross-validation)",
    ),
    "bowling_innings": TableSchema(
        "bowling_innings",
        (
            C("match_id", "str"),
            C("innings_number", "int"),
            C("team", "str"),
            C("player", "str"),
            C("runs_conceded", "int"),
            C("legal_balls", "int"),
            C("wickets", "int"),
            C("dot_balls", "int", required=False),
            C("fours_conceded", "int", required=False),
            C("sixes_conceded", "int", required=False),
        ),
        key=("match_id", "innings_number", "player"),
        description="Upstream bowling scorecards (used for cross-validation)",
    ),
    "partnerships": TableSchema(
        "partnerships",
        (
            C("match_id", "str"),
            C("innings_number", "int"),
            C("batting_team", "str"),
            C("partnership_number", "int"),
            C("player_1", "str"),
            C("player_2", "str"),
            C("runs", "int"),
            C("legal_balls", "int"),
            C("wickets", "int", required=False),
        ),
        key=("match_id", "innings_number", "partnership_number"),
        description="Upstream partnerships (used for cross-validation)",
    ),
    "player_match": TableSchema(
        "player_match",
        (
            C("match_id", "str"),
            C("team", "str"),
            C("player", "str"),
            C("batting_runs", "float", required=False, nullable=True),
            C("batting_balls", "float", required=False, nullable=True),
            C("bowling_wickets", "float", required=False, nullable=True),
            C("bowling_runs_conceded", "float", required=False, nullable=True),
            C("bowling_balls", "float", required=False, nullable=True),
        ),
        key=("match_id", "player"),
        description="Player-match participation records",
    ),
    "player_appearances": TableSchema(
        "player_appearances",
        (C("player", "str"), C("matches_played", "int"), C("eligible", "bool", required=False)),
        key=("player",),
        description="Playing-XI appearance counts per player",
    ),
    "excluded_players": TableSchema(
        "excluded_players",
        (C("player", "str"), C("matches_played", "int", required=False), C("eligible", "bool", required=False)),
        description="Upstream exclusion audit",
    ),
    "invalid_files": TableSchema(
        "invalid_files",
        (C("file", "str", required=False, nullable=True), C("error", "str", required=False, nullable=True)),
        description="Upstream invalid source files",
    ),
    "data_quality_report": TableSchema(
        "data_quality_report",
        (C("metric", "str"), C("value", "str", nullable=True)),
        description="Upstream data-quality summary",
    ),
}

TABLE_NAMES: tuple[str, ...] = tuple(SCHEMAS)
