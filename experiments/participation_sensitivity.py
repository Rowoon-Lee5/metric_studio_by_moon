"""Stress the 5%-of-ADV execution participation assumption used in part 1.

The original topology grid varies liquidity, holdings, AUM and market-impact
assumptions, but it fixes the maximum tradable share of each name's 21-day ADV
at 5%.  This audit reruns the identical grid at 2.5%, 5%, and 10% so the
participation rule itself is no longer an untested hidden parameter.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from panel_integrity import audit_dict, quarantine_reentries, return_over_months, trailing_return


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
PCTS = np.arange(0.2, 1.01, 0.1)
NS = [10, 20, 30, 50]
AUMS = [1e8, 1e9, 1e10]
COSTS = [0.5, 1.0, 1.5, 2.0]
PARTICIPATIONS = [0.025, 0.05, 0.10]


def cagr(returns: list[float]) -> float:
    series = pd.Series(returns).dropna()
    return float((1 + series).prod() ** (12 / len(series)) - 1)


def mdd(returns: list[float]) -> float:
    wealth = (1 + pd.Series(returns).fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def main() -> None:
    panel = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl").sort_values(["ticker", "date"]).copy()
    before = len(panel)
    panel, breaks = quarantine_reentries(panel)
    integrity = audit_dict(breaks, before, len(panel))
    mcap = pd.read_pickle(OUT / "monthly_mcap_panel.pkl")
    panel = panel.merge(mcap, on=["date", "ticker"], how="left")
    panel["next"] = return_over_months(panel, 1)
    panel["r1"] = trailing_return(panel, 1)
    panel["r6"] = trailing_return(panel, 6)
    panel["vol12"] = panel.groupby("ticker").r1.transform(lambda s: s.rolling(12, min_periods=8).std())
    specs = {
        "reversal_1m": ("r1", True),
        "momentum_6m": ("r6", False),
        "low_volatility": ("vol12", True),
        "small_cap": ("mcap", True),
    }
    paths: dict[tuple, dict[str, list[float]]] = {}
    for _, month in panel.groupby("date"):
        month = month.dropna(subset=["adv_21d", "r1", "r6", "vol12", "mcap"])
        month = month[(month.adv_21d > 0) & (month.price > 0) & (month.mcap > 0)]
        for signal, (column, ascending) in specs.items():
            for pct in PCTS:
                universe = month.nlargest(max(max(NS), int(len(month) * pct)), "adv_21d")
                for holdings in NS:
                    selected = universe.sort_values(column, ascending=ascending).head(holdings)
                    if len(selected) < holdings:
                        continue
                    adv = selected.adv_21d.to_numpy()
                    next_return = selected.next.fillna(0.0).to_numpy()
                    for aum in AUMS:
                        requested = aum / holdings
                        for participation in PARTICIPATIONS:
                            filled = np.minimum(requested, participation * adv)
                            fill = filled.sum() / aum
                            ratio = np.divide(filled, adv, out=np.zeros(holdings), where=adv > 0)
                            for cost in COSTS:
                                one_way = 0.001 + 0.005 * cost * np.sqrt(ratio)
                                realised = (filled * next_return).sum() / aum - 2 * (filled * one_way).sum() / aum
                                key = (signal, float(pct), holdings, float(aum), float(cost), participation)
                                paths.setdefault(key, {"returns": [], "fills": []})["returns"].append(float(realised))
                                paths[key]["fills"].append(float(fill))

    rows = []
    for key, values in paths.items():
        signal, pct, holdings, aum, cost, participation = key
        returns = values["returns"]
        series = pd.Series(returns).dropna()
        t_stat = float(series.mean() / (series.std(ddof=1) / np.sqrt(len(series)))) if series.std(ddof=1) > 0 else 0.0
        rows.append(
            {
                "signal": signal,
                "universe_pct": pct,
                "holdings": holdings,
                "aum_krw": aum,
                "cost_multiplier": cost,
                "participation": participation,
                "months": len(series),
                "net_cagr": cagr(returns),
                "mdd": mdd(returns),
                "t_stat": t_stat,
                "p_value": float(2 * (1 - NormalDist().cdf(abs(t_stat)))),
                "mean_fill": float(np.mean(values["fills"])),
            }
        )
    result = pd.DataFrame(rows)
    result["robust"] = (
        (result.net_cagr > 0)
        & (result.t_stat > 1.96)
        & (result.mdd > -0.60)
        & (result.mean_fill >= 0.80)
    )
    result.to_csv(OUT / "participation_sensitivity_nodes.csv", index=False, encoding="utf-8-sig")

    robust = result[result.robust]
    summary = []
    for participation in PARTICIPATIONS:
        subset = robust[robust.participation == participation]
        summary.append(
            {
                "participation": participation,
                "robust_nodes": int(len(subset)),
                "low_volatility_nodes": int((subset.signal == "low_volatility").sum()),
                "small_cap_nodes": int((subset.signal == "small_cap").sum()),
                "robust_at_100m": int((subset.aum_krw == 1e8).sum()),
                "robust_at_1bn": int((subset.aum_krw == 1e9).sum()),
                "robust_at_10bn": int((subset.aum_krw == 1e10).sum()),
            }
        )
    report = {
        "assumption": "Each name can trade at most participation × 21-day ADV at the monthly rebalance; unfilled capital remains cash.",
        "participations": PARTICIPATIONS,
        "summary": summary,
        "panel_integrity": integrity,
        "warning": "This is an execution-assumption sensitivity, not observed order-book execution or a validation of the impact function.",
    }
    (OUT / "participation_sensitivity_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
