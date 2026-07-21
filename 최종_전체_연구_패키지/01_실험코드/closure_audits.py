"""Close the remaining chapter-2 objections with reproducible falsification tests.

This file deliberately separates what the supplied panel can test from what it
cannot.  It does not replace historical bid/ask observations with a current
quote snapshot.  Instead it reports the break-even execution cost required to
erase the result, fixes the next protocol before reruns, tests timing and time
blocks, audits whether news and turnover measure the same construct, and
measures the size coefficient after liquidity controls.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from panel_integrity import audit_dict, quarantine_reentries, return_over_months, trailing_return


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
SEED = 20260722
PCTS = np.arange(0.2, 1.01, 0.1)
NS = [10, 20, 30, 50]
AUMS = [1e8, 1e9, 1e10]
COSTS = [0.5, 1.0, 1.5, 2.0]
PARTICIPATION = 0.05


def cagr(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    terminal_wealth = float((1 + values).prod())
    return -1.0 if terminal_wealth <= 0 else float(terminal_wealth ** (12 / len(values)) - 1)


def t_stat(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values))))


def mdd(values: pd.Series | np.ndarray) -> float:
    wealth = (1 + pd.Series(values).dropna()).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def prepare() -> pd.DataFrame:
    price = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl").sort_values(["ticker", "date"]).copy()
    before = len(price)
    price, breaks = quarantine_reentries(price)
    mcap = pd.read_pickle(OUT / "monthly_mcap_panel.pkl")
    x = price.merge(mcap, on=["date", "ticker"], how="left")
    x["next"] = return_over_months(x, 1)
    x["r1"] = trailing_return(x, 1)
    x["r6"] = trailing_return(x, 6)
    x["vol12"] = x.groupby("ticker").r1.transform(lambda s: s.rolling(12, min_periods=8).std())
    x.attrs["panel_integrity"] = audit_dict(breaks, before, len(price))
    return x


def choose(day: pd.DataFrame, pct: float = 0.9, n: int = 50) -> pd.DataFrame:
    usable = day.dropna(subset=["adv_21d", "mcap", "price"])
    usable = usable[(usable.adv_21d > 0) & (usable.mcap > 0) & (usable.price > 0)]
    universe = usable.nlargest(max(n, int(len(usable) * pct)), "adv_21d")
    return universe.nsmallest(n, "mcap")


def realised_return(selected: pd.DataFrame, *, aum: float = 1e8, cost_multiplier: float = 0.5, extra_one_way: float = 0.0, terminal_return: float = 0.0) -> tuple[float, float, int]:
    """Existing cost convention plus an explicit unobserved one-way spread term."""
    selected = selected.dropna(subset=["adv_21d"])
    if len(selected) < 50:
        return np.nan, np.nan, 0
    adv = selected.adv_21d.to_numpy(float)
    filled = np.minimum(aum / 50, PARTICIPATION * adv)
    fill = float(filled.sum() / aum)
    ratio = np.divide(filled, adv, out=np.zeros(50), where=adv > 0)
    existing_one_way = 0.001 + 0.005 * cost_multiplier * np.sqrt(ratio)
    missing = selected.next.isna()
    returns = selected.next.fillna(terminal_return).to_numpy(float)
    net = float((filled * returns).sum() / aum - 2 * (filled * (existing_one_way + extra_one_way)).sum() / aum)
    return net, fill, int(missing.sum())


def selected_monthly(x: pd.DataFrame, delay_months: int = 0, extra_one_way: float = 0.0, terminal_return: float = 0.0) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(x.date.unique()))
    rows = []
    for i in range(delay_months, len(dates)):
        decision_date = dates[i - delay_months]
        execution_date = dates[i]
        selection = choose(x.loc[x.date == decision_date])[["ticker", "adv_21d"]].rename(columns={"adv_21d": "formation_adv_21d"})
        execution = x.loc[x.date == execution_date, ["ticker", "next", "adv_21d"]]
        selected = selection.merge(execution, on="ticker", how="left")
        selected["adv_21d"] = selected["adv_21d"].fillna(selected["formation_adv_21d"])
        net, fill, missing = realised_return(selected, extra_one_way=extra_one_way, terminal_return=terminal_return)
        if np.isfinite(net):
            rows.append({"date": execution_date, "decision_date": decision_date, "delay_months": delay_months, "net_return": net, "fill": fill, "terminal_unpriced_holdings": missing})
    return pd.DataFrame(rows)


def execution_break_even(x: pd.DataFrame) -> dict:
    base = selected_monthly(x)
    stresses = []
    for bp in [0, 25, 50, 100, 150, 200, 300, 500]:
        sample = base.copy()
        sample["net_return"] = sample.net_return - 2 * (bp / 10_000) * sample.fill
        stresses.append({"additional_one_way_bp": bp, "months": len(sample), "net_cagr": cagr(sample.net_return), "t_stat": t_stat(sample.net_return), "mdd": mdd(sample.net_return)})
    lo, hi = 0.0, 0.20
    for _ in range(50):
        mid = (lo + hi) / 2
        trial = base.copy()
        trial["net_return"] = trial.net_return - 2 * mid * trial.fill
        if cagr(trial.net_return) > 0:
            lo = mid
        else:
            hi = mid
    endpoint = []
    for convention, value in {"neutral_cash_at_last_price": 0.0, "total_loss_at_unpriced_endpoint": -1.0}.items():
        sample = selected_monthly(x, terminal_return=value)
        endpoint.append({"endpoint_convention": convention, "months": len(sample), "terminal_unpriced_holdings": int(sample.terminal_unpriced_holdings.sum()), "net_cagr": cagr(sample.net_return), "t_stat": t_stat(sample.net_return), "mdd": mdd(sample.net_return)})
    pd.DataFrame(stresses).to_csv(OUT / "execution_break_even_stress.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(endpoint).to_csv(OUT / "smallcap_endpoint_sensitivity.csv", index=False, encoding="utf-8-sig")
    base.to_csv(OUT / "smallcap_execution_baseline_returns.csv", index=False, encoding="utf-8-sig")
    return {
        "existing_model": "0.10% + 0.50 × 0.50% × sqrt(order_value / ADV), charged on both sides; full monthly rebalance convention",
        "baseline": {"months": len(base), "net_cagr": cagr(base.net_return), "t_stat": t_stat(base.net_return), "mean_fill": float(base.fill.mean())},
        "break_even_additional_one_way_bp": float(lo * 10_000),
        "endpoint_sensitivity": endpoint,
        "interpretation": "This is an implied historical-cost threshold, not an observed bid/ask spread. Historical quote data must be compared against it rather than replaced by a current snapshot.",
        "historical_quote_input_contract": {"required_columns": ["timestamp", "ticker", "best_bid", "best_ask", "bid_size", "ask_size"], "join_key": "ticker plus a quote timestamp no later than the documented rebalance cutoff"},
    }


def timing_and_blocks(x: pd.DataFrame) -> dict:
    timing = []
    for delay in [0, 1, 2, 3]:
        sample = selected_monthly(x, delay_months=delay)
        timing.append({"delay_months": delay, "months": len(sample), "net_cagr": cagr(sample.net_return), "t_stat": t_stat(sample.net_return), "mdd": mdd(sample.net_return)})
    pd.DataFrame(timing).to_csv(OUT / "smallcap_timing_lag_audit.csv", index=False, encoding="utf-8-sig")

    strategies = pd.read_csv(OUT / "alpha_topology_monthly_returns.csv", parse_dates=["date"]).pivot(index="date", columns="key", values="net_return").sort_index()
    blocks = [("2000_2004", "2000-01-01", "2005-01-01"), ("2005_2009", "2005-01-01", "2010-01-01"), ("2010_2014", "2010-01-01", "2015-01-01"), ("2015_2019", "2015-01-01", "2020-01-01"), ("2020_2026", "2020-01-01", "2027-01-01")]
    rows = []
    for label, start, end in blocks:
        holdout = strategies.loc[(strategies.index >= start) & (strategies.index < end)]
        train = strategies.drop(holdout.index)
        selected_key = str(train.apply(t_stat).idxmax())
        realised = holdout[selected_key].dropna()
        rows.append({"held_out_block": label, "selected_on_other_blocks": selected_key, "months": len(realised), "net_cagr": cagr(realised), "t_stat": t_stat(realised), "mdd": mdd(realised)})
    pd.DataFrame(rows).to_csv(OUT / "topology_leave_block_out_audit.csv", index=False, encoding="utf-8-sig")
    protocol = {
        "version": "chapter2-protocol-v1",
        "frozen_after_results": True,
        "future_validation_rule": "No signal, parameter, cost convention, or acceptance threshold may be changed before a new untouched evaluation window is scored.",
        "candidate_grid": {"signals": ["reversal_1m", "momentum_6m", "low_volatility", "small_cap"], "liquidity_percentiles": [round(float(v), 1) for v in PCTS], "holdings": NS, "aum_krw": AUMS, "cost_multipliers": COSTS},
        "selected_candidate": "small_cap|p0.9|n50|a100000000|c0.5",
        "acceptance": "positive net CAGR, t-stat > 1.96, MDD > -60%, mean fill >= 80%, and no failure under one-month decision lag",
    }
    (OUT / "chapter2_frozen_protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"decision_lag": timing, "leave_block_out": rows, "protocol": protocol}


def attention_measurement(x: pd.DataFrame) -> dict:
    news = pd.read_csv(OUT / "news_attention_raw_source_snapshot.csv", parse_dates=["date"])
    news["ticker"] = news.ticker.astype(str).str.replace("A", "", regex=False).str.split(".").str[0].str.zfill(6)
    y = x.copy()
    y["ticker"] = y.ticker.astype(str).str.zfill(6)
    y["next_12m"] = y.groupby("ticker").price.shift(-12) / y.price - 1
    y = y.merge(news[["date", "ticker", "n_titles"]], on=["date", "ticker"], how="inner").dropna(subset=["adv_21d", "mcap", "r6", "next_12m"])
    y["turnover"] = y.adv_21d / y.mcap
    rows, cells = [], []
    for date, day in y.groupby("date"):
        if day.ticker.nunique() < 30:
            continue
        rho = day.n_titles.rank().corr(day.turnover.rank())
        n = len(day)
        top_news = set(day.nlargest(max(1, n // 10), "n_titles").ticker)
        top_turn = set(day.nlargest(max(1, n // 10), "turnover").ticker)
        rows.append({"date": date, "n": n, "spearman_news_turnover": rho, "top_decile_overlap": len(top_news & top_turn) / max(1, len(top_news))})
        day = day.assign(news_high=day.n_titles.rank(method="first", pct=True) > .5, turnover_high=day.turnover.rank(method="first", pct=True) > .5)
        for (n_high, t_high), group in day.groupby(["news_high", "turnover_high"]):
            if len(group) >= 10:
                cells.append({"date": date, "news_high": bool(n_high), "turnover_high": bool(t_high), "n": len(group), "rank_ic_12m": group.r6.rank().corr(group.next_12m.rank())})
    detail, cell = pd.DataFrame(rows), pd.DataFrame(cells)
    summary = cell.groupby(["news_high", "turnover_high"]).agg(months=("date", "nunique"), mean_n=("n", "mean"), mean_rank_ic_12m=("rank_ic_12m", "mean")).reset_index()
    detail.to_csv(OUT / "attention_measurement_agreement.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "attention_measurement_cells.csv", index=False, encoding="utf-8-sig")
    return {"months": int(detail.date.nunique()), "mean_spearman_news_turnover": float(detail.spearman_news_turnover.mean()), "mean_top_decile_overlap": float(detail.top_decile_overlap.mean()), "cross_measurement_momentum": summary.to_dict(orient="records"), "conclusion": "News count and turnover are empirically distinct measurements in the overlapping universe; neither is promoted to an investor-attention latent variable."}


def size_mechanism(x: pd.DataFrame) -> dict:
    rows, correlations = [], []
    for date, day in x.groupby("date"):
        day = day.dropna(subset=["next", "mcap", "adv_21d", "r6", "vol12"]).copy()
        day = day[(day.mcap > 0) & (day.adv_21d > 0)]
        if len(day) < 50:
            continue
        z = pd.DataFrame({"size": -np.log(day.mcap), "liquidity": np.log(day.adv_21d), "momentum": day.r6, "volatility": day.vol12}, index=day.index)
        z = (z - z.mean()) / z.std(ddof=0).replace(0, np.nan)
        use = z.notna().all(axis=1)
        design = np.column_stack([np.ones(use.sum()), z.loc[use].to_numpy(float)])
        beta = np.linalg.lstsq(design, day.loc[use, "next"].to_numpy(float), rcond=None)[0]
        rows.append({"date": date, "intercept": beta[0], "size": beta[1], "liquidity": beta[2], "momentum": beta[3], "volatility": beta[4], "n": int(use.sum())})
        correlations.append({"date": date, "size_liquidity_rank_corr": day.mcap.rank().corr(day.adv_21d.rank())})
    coefficients = pd.DataFrame(rows)
    rng = np.random.default_rng(SEED)
    values = coefficients["size"].to_numpy(float)
    bootstrap = []
    for _ in range(5000):
        draw = []
        while len(draw) < len(values):
            start = int(rng.integers(len(values)))
            draw.extend(values[(start + np.arange(12)) % len(values)])
        bootstrap.append(float(np.mean(draw[: len(values)])))
    coefficients.to_csv(OUT / "smallcap_liquidity_control_coefficients.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(correlations).to_csv(OUT / "smallcap_liquidity_correlation.csv", index=False, encoding="utf-8-sig")
    means = coefficients[["size", "liquidity", "momentum", "volatility"]].mean()
    return {"months": int(len(coefficients)), "mean_standardized_coefficients": {key: float(value) for key, value in means.items()}, "size_coefficient_block_bootstrap_ci_95": [float(np.quantile(bootstrap, .025)), float(np.quantile(bootstrap, .975))], "mean_size_liquidity_rank_correlation": float(pd.DataFrame(correlations).size_liquidity_rank_corr.mean()), "interpretation": "A controlled size coefficient is an association after observed liquidity, momentum, and volatility controls. It is not a causal risk-premium decomposition."}


def main() -> None:
    x = prepare()
    report = {
        "panel_integrity": x.attrs["panel_integrity"],
        "execution_cost": execution_break_even(x),
        "timing_and_research_freedom": timing_and_blocks(x),
        "attention_measurement": attention_measurement(x),
        "size_mechanism": size_mechanism(x),
    }
    (OUT / "closure_audits_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
