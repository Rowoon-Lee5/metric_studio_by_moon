"""Separate small-cap market exposure from residual alpha and model actual turnover.

The original topology run charges a full buy and sell every month.  This audit
keeps the same formation rule but computes drift-adjusted portfolio turnover,
then compares the portfolio with its same-liquidity equal-weight universe.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from panel_integrity import audit_dict, quarantine_reentries, return_over_months


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
PARTICIPATION = 0.05
AUM = 1e8
N = 50
PCT = 0.9


def cagr(values: pd.Series) -> float:
    values = values.dropna()
    return float((1 + values).prod() ** (12 / len(values)) - 1)


def t_stat(values: pd.Series) -> float:
    values = values.dropna()
    return float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values))))


def prepare() -> tuple[pd.DataFrame, dict]:
    price = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl").sort_values(["ticker", "date"])
    before = len(price)
    price, breaks = quarantine_reentries(price)
    mcap = pd.read_pickle(OUT / "monthly_mcap_panel.pkl")
    x = price.merge(mcap, on=["date", "ticker"], how="left")
    x["next"] = return_over_months(x, 1)
    return x, audit_dict(breaks, before, len(price))


def cost_rate(day: pd.DataFrame) -> tuple[np.ndarray, float]:
    adv = day.adv_21d.to_numpy(float)
    filled = np.minimum(AUM / N, PARTICIPATION * adv)
    ratio = np.divide(filled, adv, out=np.zeros(N), where=adv > 0)
    # Same 0.5x cost convention used by the leading topology node.
    one_way = 0.001 + 0.005 * 0.5 * np.sqrt(ratio)
    return one_way, float(filled.sum() / AUM)


def drift_turnover(previous: pd.DataFrame | None, current: pd.DataFrame, all_rows: pd.DataFrame) -> float:
    target = pd.Series(1 / N, index=current.ticker)
    if previous is None:
        return 1.0
    prior_tickers = previous.ticker.tolist()
    realised = all_rows.set_index("ticker").reindex(prior_tickers).next.fillna(0.0)
    pre = pd.Series(1 / N, index=prior_tickers) * (1 + realised)
    pre = pre / pre.sum() if pre.sum() > 0 else pd.Series(0.0, index=prior_tickers)
    union = target.index.union(pre.index)
    return float(0.5 * (target.reindex(union, fill_value=0) - pre.reindex(union, fill_value=0)).abs().sum())


def main() -> None:
    x, integrity = prepare()
    rows, holdings = [], []
    previous: pd.DataFrame | None = None
    for date, day in x.groupby("date"):
        # Formation never uses the next-month observation. Missing endpoint
        # returns receive the same neutral cash convention as closure_audits.
        eligible = day.dropna(subset=["adv_21d", "mcap", "price"])
        eligible = eligible[(eligible.adv_21d > 0) & (eligible.mcap > 0)]
        if len(eligible) < N:
            continue
        liquid = eligible.nlargest(max(N, int(len(eligible) * PCT)), "adv_21d")
        chosen = liquid.nsmallest(N, "mcap").copy()
        one_way, fill = cost_rate(chosen)
        gross = float((np.minimum(AUM / N, PARTICIPATION * chosen.adv_21d.to_numpy()) * chosen.next.fillna(0.0).to_numpy()).sum() / AUM)
        full_turnover_net = gross - 2 * float(np.mean(one_way)) * fill
        turnover = drift_turnover(previous, chosen, day)
        turnover_net = gross - 2 * float(np.mean(one_way)) * fill * turnover
        benchmark = float(liquid.next.fillna(0.0).mean())
        rows.append({"date": date, "gross_return": gross, "full_turnover_net_return": full_turnover_net, "drift_turnover_net_return": turnover_net, "liquidity_matched_equal_weight_return": benchmark, "drift_turnover": turnover, "fill": fill, "holdings": len(chosen)})
        holdings.extend({"date": date, "ticker": ticker} for ticker in chosen.ticker)
        previous = chosen[["ticker"]].copy()
    returns = pd.DataFrame(rows).sort_values("date")
    holdings_frame = pd.DataFrame(holdings)
    excess = returns.drift_turnover_net_return - returns.liquidity_matched_equal_weight_return
    design = np.column_stack([np.ones(len(returns)), returns.liquidity_matched_equal_weight_return.to_numpy(float)])
    alpha, beta = np.linalg.lstsq(design, returns.drift_turnover_net_return.to_numpy(float), rcond=None)[0]
    residual = returns.drift_turnover_net_return - (alpha + beta * returns.liquidity_matched_equal_weight_return)
    relative = (1 + returns.drift_turnover_net_return) / (1 + returns.liquidity_matched_equal_weight_return) - 1
    report = {
        "formation": "smallest 50 market-cap stocks inside the top-90% ADV universe, 100m KRW, 0.5x existing cost convention",
        "panel_integrity": integrity,
        "months": int(len(returns)),
        "turnover": {"mean_drift_adjusted_one_way_turnover": float(returns.drift_turnover.mean()), "median_drift_adjusted_one_way_turnover": float(returns.drift_turnover.median())},
        "performance": {
            "full_monthly_turnover_net_cagr": cagr(returns.full_turnover_net_return),
            "drift_adjusted_turnover_net_cagr": cagr(returns.drift_turnover_net_return),
            "liquidity_matched_equal_weight_cagr": cagr(returns.liquidity_matched_equal_weight_return),
            "drift_adjusted_excess_mean_monthly": float(excess.mean()),
            "drift_adjusted_excess_t_stat": t_stat(excess),
            "drift_adjusted_relative_cagr": cagr(relative),
        },
        "single_factor_decomposition": {"monthly_intercept": float(alpha), "intercept_t_stat": t_stat(residual + alpha), "liquidity_matched_beta": float(beta)},
        "interpretation": "The benchmark is a liquidity-matched equal-weight universe, not a factor model. A positive residual is evidence against a pure broad-liquidity-market explanation, not proof of a priced alpha.",
    }
    returns.to_csv(OUT / "smallcap_benchmark_turnover_returns.csv", index=False, encoding="utf-8-sig")
    holdings_frame.to_csv(OUT / "smallcap_selected_holdings.csv", index=False, encoding="utf-8-sig")
    (OUT / "benchmark_turnover_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
