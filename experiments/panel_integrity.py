"""Calendar-contiguous return construction and ticker-reentry quarantine."""
from __future__ import annotations

import pandas as pd


MAX_MONTHLY_GAP_DAYS = 40


def quarantine_reentries(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exclude only post-gap segments whose ticker identity cannot be assured.

    A reused code or a multi-month data disappearance must not be treated as a
    continuous security.  The original pre-gap history is retained; every row
    after a gap greater than 40 days is quarantined until a security master
    links the two segments.
    """
    x = frame.sort_values(["ticker", "date"]).copy()
    x["_next_date"] = x.groupby("ticker").date.shift(-1)
    x["_gap_to_next_days"] = (x._next_date - x.date).dt.days
    x["_break_before"] = x.groupby("ticker")._gap_to_next_days.shift(1).gt(MAX_MONTHLY_GAP_DAYS).fillna(False)
    x["_post_gap_segment"] = x.groupby("ticker")._break_before.cumsum().gt(0)
    breaks = x.loc[x._gap_to_next_days.gt(MAX_MONTHLY_GAP_DAYS), ["ticker", "date", "_next_date", "_gap_to_next_days"]].rename(columns={"_next_date": "next_date", "_gap_to_next_days": "gap_days"})
    return x.loc[~x._post_gap_segment].drop(columns=["_break_before", "_post_gap_segment"]), breaks


def return_over_months(frame: pd.DataFrame, periods: int, price_column: str = "price") -> pd.Series:
    """Return only when the shifted observation is exactly ``periods`` months later."""
    x = frame.sort_values(["ticker", "date"]).copy()
    future_price = x.groupby("ticker")[price_column].shift(-periods)
    future_date = x.groupby("ticker").date.shift(-periods)
    month_distance = future_date.dt.to_period("M").astype("int64") - x.date.dt.to_period("M").astype("int64")
    return (future_price / x[price_column] - 1).where(month_distance.eq(periods))


def trailing_return(frame: pd.DataFrame, periods: int, price_column: str = "price") -> pd.Series:
    """Trailing return only when the prior observation is exactly ``periods`` months old."""
    x = frame.sort_values(["ticker", "date"]).copy()
    past_price = x.groupby("ticker")[price_column].shift(periods)
    past_date = x.groupby("ticker").date.shift(periods)
    month_distance = x.date.dt.to_period("M").astype("int64") - past_date.dt.to_period("M").astype("int64")
    return (x[price_column] / past_price - 1).where(month_distance.eq(periods))


def audit_dict(breaks: pd.DataFrame, before: int, after: int) -> dict:
    return {
        "max_allowed_monthly_gap_days": MAX_MONTHLY_GAP_DAYS,
        "non_contiguous_links": int(len(breaks)),
        "tickers_with_non_contiguous_links": int(breaks.ticker.nunique()),
        "rows_before_reentry_quarantine": int(before),
        "rows_after_reentry_quarantine": int(after),
    }
