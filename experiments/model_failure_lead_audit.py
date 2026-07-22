"""Audit whether a price-model failure state contains *next* month's information.

The earlier exploratory table compared each model's realised holding-period
return with the market return from that same holding period.  That is a useful
description of common failure, but it is not a forward test.  This script
observes the failure only after month t has closed, then asks about the
eligible-universe return in month t+1.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
N_HOLDINGS = 30
WINDOW = 36
MIN_PERIODS = 24


def select(group: pd.DataFrame, column: str, ascending: bool) -> pd.DataFrame:
    return group.sort_values(column, ascending=ascending).head(N_HOLDINGS)


def main() -> None:
    price = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl").sort_values(["ticker", "date"]).copy()
    mcap = pd.read_pickle(OUT / "monthly_mcap_panel.pkl")
    x = price.merge(mcap, on=["date", "ticker"], how="left")
    x["next_1m"] = x.groupby("ticker").price.shift(-1) / x.price - 1
    x["ret_1m"] = x.groupby("ticker").price.pct_change()
    x["ret_6m"] = x.groupby("ticker").price.pct_change(6)
    x["vol_12m"] = x.groupby("ticker").ret_1m.transform(lambda s: s.rolling(12, min_periods=8).std())

    specifications = {
        "반전(1개월)": ("ret_1m", True),
        "모멘텀(6개월)": ("ret_6m", False),
        "저변동성": ("vol_12m", True),
        "소형주": ("mcap", True),
    }
    rows: list[dict[str, object]] = []
    for date, group in x.groupby("date"):
        group = group.dropna(subset=["next_1m", "ret_1m", "ret_6m", "vol_12m", "mcap", "adv_21d"])
        if len(group) < N_HOLDINGS:
            continue
        row: dict[str, object] = {"formation_date": date, "eligible_universe_return": float(group.next_1m.mean())}
        for label, (column, ascending) in specifications.items():
            row[label] = float(select(group, column, ascending).next_1m.mean())
        rows.append(row)

    monthly = pd.DataFrame(rows).sort_values("formation_date").reset_index(drop=True)
    signal_columns = list(specifications)
    for column in signal_columns:
        history_mean = monthly[column].rolling(WINDOW, min_periods=MIN_PERIODS).mean().shift(1)
        history_std = monthly[column].rolling(WINDOW, min_periods=MIN_PERIODS).std().shift(1)
        monthly[f"{column}_z"] = (monthly[column] - history_mean) / (history_std + 1e-12)
    monthly["failed_signals"] = (monthly[[f"{c}_z" for c in signal_columns]] < -1).sum(axis=1)

    # The failure is known only after the holding month.  Shift the target by one
    # formation date, so it is the following holding month's eligible-universe return.
    monthly["following_month_market_return"] = monthly.eligible_universe_return.shift(-1)
    audit = monthly.dropna(subset=["following_month_market_return"]).copy()
    summary = (
        audit.groupby("failed_signals").following_month_market_return.agg(["size", "mean", "median"]).reset_index()
        .rename(columns={"size": "observations", "mean": "mean_following_month_return", "median": "median_following_month_return"})
    )

    split_rows: list[dict[str, object]] = []
    for label, subset in [("2000~2013", audit[audit.formation_date < "2014-01-01"]), ("2014~2026", audit[audit.formation_date >= "2014-01-01"])]:
        if len(subset) < 24:
            continue
        slope = np.polyfit(subset.failed_signals, subset.following_month_market_return, 1)[0]
        split_rows.append({
            "period": label,
            "observations": int(len(subset)),
            "spearman_failed_signals_vs_following_return": float(subset.failed_signals.rank().corr(subset.following_month_market_return.rank())),
            "linear_slope_per_additional_failure": float(slope),
        })

    audit.to_csv(OUT / "model_failure_lead_monthly.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "model_failure_lead_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(split_rows).to_csv(OUT / "model_failure_lead_time_split.csv", index=False, encoding="utf-8-sig")
    report = {
        "timing": "Each failure is computed from the realised return during month t. The target is the eligible-universe equal-weighted return during month t+1. This is a forward audit, not a same-month association.",
        "market_definition": "The target is not KOSPI/KOSDAQ index return. It is the equal-weighted next-month adjusted-price return of stocks with all four signal inputs and 21-day ADV available at the formation month.",
        "failure_definition": "For each of four 30-stock signal portfolios, realised month-t return is below its own trailing 36-month mean by more than one trailing standard deviation; at least 24 history months are required.",
        "summary": summary.to_dict(orient="records"),
        "time_split": split_rows,
        "warning": "The four portfolios share a price/volume/market-cap panel. Sparse high-failure states and common inputs prevent a trading-rule interpretation.",
    }
    (OUT / "model_failure_lead_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
