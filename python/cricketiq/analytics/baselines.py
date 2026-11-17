"""Hierarchical expected-value baselines.

For every delivery the expected outcome (runs, dismissals, boundaries, dots,
bowler wickets) is the average outcome of comparable deliveries: same gender,
competition and phase (and batting-position group for batters). When a bucket
has too few deliveries the next broader level is used, ending at gender + phase.
Summing these per-ball expectations gives each player an opportunity-adjusted
"expected" figure that the actual figure is compared against.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def hier_expect(rows: pd.DataFrame, values: Sequence[str], levels: Sequence[Sequence[str]], min_n: int) -> pd.DataFrame:
    """Return per-row expected rates for ``values`` using hierarchical backoff.

    Args:
        rows: Deliveries that form both the population and the rows to score.
        values: Numeric/bool columns whose per-row mean is the expected rate.
        levels: Grouping keys from most to least specific. The last level is always used
            as the fallback regardless of sample size.
        min_n: Minimum rows in a bucket for that level to be trusted.
    """
    values = list(values)
    out = pd.DataFrame(index=rows.index, columns=values, dtype=float)
    assigned = pd.Series(False, index=rows.index)
    if rows.empty:
        return out
    data = rows[values].astype(float)
    for i, keys in enumerate(levels):
        keys = list(keys)
        frame = pd.concat([rows[keys], data], axis=1)
        grp = frame.groupby(keys, dropna=False)
        means = grp[values].mean()
        n = grp.size().rename("_n")
        stats = means.join(n).reset_index()
        merged = rows[keys].reset_index().merge(stats, on=keys, how="left").set_index("index")
        last = i == len(levels) - 1
        ok = (~assigned) & (merged["_n"].fillna(0) >= (0 if last else min_n))
        out.loc[ok, values] = merged.loc[ok, values].to_numpy()
        assigned |= ok
        if assigned.all():
            break
    return out


def baseline_table(rows: pd.DataFrame, keys: Sequence[str], agg: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """Simple grouped aggregate used to publish competition/phase reference values."""
    return rows.groupby(list(keys), dropna=False).agg(**agg).reset_index()
