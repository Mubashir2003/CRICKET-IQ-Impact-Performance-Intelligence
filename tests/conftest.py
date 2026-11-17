"""Shared fixtures: a tiny hand-built match whose correct answers are known."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from cricketiq.config import Paths, load_settings  # noqa: E402

DEL_COLS = ["match_id", "gender", "date", "competition", "innings_number", "batting_team", "bowling_team", "over", "delivery_in_over",
            "batter", "non_striker", "bowler", "batter_runs", "extras", "total_runs", "wides", "no_balls", "is_legal_delivery",
            "is_wicket", "dismissal_kinds", "players_out"]


class Builder:
    """Builds delivery rows; tracks the ball number within each over."""

    def __init__(self, match_id: str, gender: str = "men"):
        self.mid, self.gender, self.rows, self._ball = match_id, gender, [], {}

    def ball(self, inn, over, batter, ns, bowler, bat=0, wides=0, nb=0, other=0, kind=None, out=None, bt="A", wt="B"):
        k = (inn, over)
        self._ball[k] = self._ball.get(k, 0) + 1
        extras = wides + nb + other
        self.rows.append([self.mid, self.gender, "2026-05-01", "Test Cup", inn, bt, wt, over, self._ball[k], batter, ns, bowler,
                          bat, extras, bat + extras, wides, nb, wides == 0 and nb == 0, kind is not None, kind, out])
        return self

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=DEL_COLS)


@pytest.fixture(scope="session")
def settings():
    return load_settings(Paths())


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_row"] = range(len(df))
    df["date"] = pd.to_datetime(df["date"])
    df["is_legal_delivery"] = df["is_legal_delivery"].astype(bool)
    df["is_wicket"] = df["is_wicket"].astype(bool)
    return df


@pytest.fixture()
def tiny_tables():
    """Team A bats first (13 runs), team B chases and wins; then a tied match decided by a super over."""
    b = Builder("m1")
    # ---- innings 1, over 1 (bowler X): wide, no-ball+2, byes, four, retired hurt, dot, single, dot
    b.ball(1, 1, "A1", "A2", "X", wides=1)
    b.ball(1, 1, "A1", "A2", "X", nb=1, bat=2)
    b.ball(1, 1, "A1", "A2", "X", other=1)               # bye: faced, not charged to bowler
    b.ball(1, 1, "A2", "A1", "X", bat=4)
    b.ball(1, 1, "A2", "A1", "X", kind="retired hurt", out="A2")
    b.ball(1, 1, "A1", "A3", "X")
    b.ball(1, 1, "A1", "A3", "X", bat=1)
    # ---- over 2 (bowler Y): maiden with a wicket, then non-striker run out, timed out
    b.ball(1, 2, "A3", "A1", "Y")
    b.ball(1, 2, "A3", "A1", "Y", kind="bowled", out="A3")
    b.ball(1, 2, "A4", "A1", "Y")
    b.ball(1, 2, "A4", "A1", "Y", kind="run out", out="A1")
    b.ball(1, 2, "A4", "A5", "Y", kind="caught;timed out", out="A4;A6")
    b.ball(1, 2, "A5", "A7", "Y")
    # ---- innings 2 (bowler Z): B chases 14
    b.ball(2, 1, "B1", "B2", "Z", bat=6, bt="B", wt="A")
    b.ball(2, 1, "B1", "B2", "Z", bat=6, bt="B", wt="A")
    b.ball(2, 1, "B1", "B2", "Z", bat=2, bt="B", wt="A")
    d1 = b.frame()

    s = Builder("m2")
    s.ball(1, 1, "A1", "A2", "X", bat=4)
    s.ball(2, 1, "B1", "B2", "Z", bat=4, bt="B", wt="A")
    s.ball(3, 1, "A1", "A2", "X", bat=6)                  # super over A: 6
    s.ball(4, 1, "B1", "B2", "Z", bat=1, bt="B", wt="A")  # super over B: 1 -> A wins
    d2 = s.frame()
    deliveries = _prep(pd.concat([d1, d2], ignore_index=True))
    deliveries = deliveries.drop(columns=["date", "competition"])
    matches = pd.DataFrame({
        "gender": ["men", "men"], "match_id": ["m1", "m2"], "date": pd.to_datetime(["2026-05-01", "2026-05-02"]),
        "match_type": ["T20", "T20"], "competition": ["Test Cup", "Test Cup"], "season": ["2026", "2026"],
        "venue": ["Ground", "Ground"], "city": ["City", "City"], "team_1": ["A", "A"], "team_2": ["B", "B"],
        "winner": ["B", None], "result_type": [None, "tie"],
    })
    return {"matches": matches, "deliveries": deliveries}
