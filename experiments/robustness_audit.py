"""Independent follow-up checks for the Metric Studio chapter-2 experiments.

This script does not create new strategy ideas. It checks whether the claims
already reported survive a time split, dependence-aware resampling, benchmarks,
and an explicit coverage audit.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
SPLIT = pd.Timestamp("2014-01-01")
SEED = 20260722


def cagr(series: pd.Series) -> float:
    series = series.dropna()
    return float((1 + series).prod() ** (12 / len(series)) - 1)


def t_stat(series: pd.Series) -> float:
    series = series.dropna()
    return float(series.mean() / (series.std(ddof=1) / np.sqrt(len(series))))


def moving_block_means(series: pd.Series, block: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    values = series.dropna().to_numpy(float)
    n = len(values)
    starts = np.arange(n)
    output = np.empty(reps)
    for rep in range(reps):
        sample: list[float] = []
        while len(sample) < n:
            start = int(rng.choice(starts))
            sample.extend(values[(start + np.arange(block)) % n])
        output[rep] = np.mean(sample[:n])
    return output


def topology_time_split() -> dict:
    long = pd.read_csv(OUT / "alpha_topology_monthly_returns.csv", parse_dates=["date"])
    wide = long.pivot(index="date", columns="key", values="net_return").sort_index()
    train = wide.loc[wide.index < SPLIT]
    test = wide.loc[wide.index >= SPLIT]
    train_t = train.apply(t_stat)
    chosen_key = str(train_t.idxmax())
    chosen_test = test[chosen_key].dropna()
    top10 = train_t.nlargest(10).rename("train_t").reset_index().rename(columns={"key": "strategy_key"})
    top10["test_t"] = top10.strategy_key.map(lambda k: t_stat(test[k]))
    top10["test_cagr"] = top10.strategy_key.map(lambda k: cagr(test[k]))
    top10.to_csv(OUT / "topology_time_split_top10.csv", index=False, encoding="utf-8-sig")
    return {
        "split": {"train_end": "2013-12-31", "test_start": "2014-01-01"},
        "chosen_on_train": chosen_key,
        "train_t": float(train_t[chosen_key]),
        "test_months": int(chosen_test.size),
        "test_t": t_stat(chosen_test),
        "test_cagr": cagr(chosen_test),
    }


def topology_rolling_walk_forward() -> dict:
    long = pd.read_csv(OUT / "alpha_topology_monthly_returns.csv", parse_dates=["date"])
    wide = long.pivot(index="date", columns="key", values="net_return").sort_index()
    selections = []
    realised = []
    for year in range(2008, int(wide.index.max().year) + 1):
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year + 1}-01-01")
        train = wide.loc[wide.index < start]
        test = wide.loc[(wide.index >= start) & (wide.index < end)]
        if len(train) < 60 or test.empty:
            continue
        key = str(train.apply(t_stat).idxmax())
        returns = test[key].dropna()
        selections.append({"test_year": year, "selected_key": key, "train_months": len(train), "train_t": float(t_stat(train[key])), "test_months": len(returns), "test_cagr": cagr(returns)})
        realised.extend({"date": date, "selected_key": key, "net_return": value} for date, value in returns.items())
    selected = pd.DataFrame(selections)
    realised_frame = pd.DataFrame(realised)
    selected.to_csv(OUT / "topology_rolling_walk_forward_selections.csv", index=False, encoding="utf-8-sig")
    realised_frame.to_csv(OUT / "topology_rolling_walk_forward_returns.csv", index=False, encoding="utf-8-sig")
    series = realised_frame.net_return
    return {"test_years": int(len(selected)), "months": int(len(series)), "cagr": cagr(series), "t_stat": t_stat(series), "unique_selected_strategies": int(selected.selected_key.nunique())}


def news_dependence_audit(rng: np.random.Generator) -> dict:
    """Use the raw-headline panel rather than the old 70-ticker sentiment slice."""
    detail = pd.read_csv(OUT / "news_attention_raw_ic_detail.csv", parse_dates=["date"])
    pivot = detail.pivot(index="date", columns="bucket", values="rank_ic_12m").dropna().sort_index()
    diff = pivot[3] - pivot[1]
    boot = moving_block_means(diff, block=12, reps=5000, rng=rng)
    observed = float(diff.mean())
    p_two_sided = float(2 * min((boot <= 0).mean(), (boot >= 0).mean()))
    return {
        "months": int(diff.size),
        "high_minus_low_mean_rank_ic": observed,
        "moving_block_bootstrap": {
            "block_months": 12,
            "replications": 5000,
            "ci_95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "two_sided_sign_p": p_two_sided,
        },
    }


def consensus_benchmark() -> dict:
    price = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl").sort_values(["ticker", "date"]).copy()
    mcap = pd.read_pickle(OUT / "monthly_mcap_panel.pkl")
    x = price.merge(mcap, on=["date", "ticker"], how="left")
    x["next"] = x.groupby("ticker").price.shift(-1) / x.price - 1
    x["r1"] = x.groupby("ticker").price.pct_change()
    x["r6"] = x.groupby("ticker").price.pct_change(6)
    x["vol"] = x.groupby("ticker").r1.transform(lambda s: s.rolling(12, min_periods=8).std())
    specs = [("r1", True), ("r6", False), ("vol", True), ("mcap", True)]
    pcts, holdings = [.5, .7, .9, 1.0], [20, 30, 50]
    rows = []
    for date, day in x.groupby("date"):
        day = day.dropna(subset=["next", "r1", "r6", "vol", "mcap", "adv_21d"])
        if day.empty:
            continue
        for signal, asc in specs:
            for pct in pcts:
                allowed = day.nlargest(max(30, int(len(day) * pct)), "adv_21d")
                for n in holdings:
                    chosen = allowed.sort_values(signal, ascending=asc).head(n)
                    rows.append({"date": date, "signal": signal, "pct": pct, "holdings": n, "return": chosen.next.mean()})
    indiv = pd.DataFrame(rows)
    monthly_mean = indiv.groupby("date")["return"].mean().rename("mean_component_return")
    consensus = pd.read_csv(OUT / "epistemic_stability_returns.csv", parse_dates=["date"]).set_index("date").stability_return
    aligned = pd.concat([consensus, monthly_mean], axis=1).dropna()
    aligned.reset_index().to_csv(OUT / "consensus_benchmark_monthly.csv", index=False, encoding="utf-8-sig")
    summary = pd.DataFrame(
        [
            {"portfolio": "model_consensus_top30", "months": len(aligned), "cagr": cagr(aligned.stability_return), "mean_monthly_return": float(aligned.stability_return.mean())},
            {"portfolio": "mean_of_48_components", "months": len(aligned), "cagr": cagr(aligned.mean_component_return), "mean_monthly_return": float(aligned.mean_component_return.mean())},
        ]
    )
    summary.to_csv(OUT / "consensus_benchmark_summary.csv", index=False, encoding="utf-8-sig")
    return {
        "benchmark_summary": summary.to_dict(orient="records"),
        "monthly_return_correlation": float(aligned.corr().iloc[0, 1]),
    }


def failure_time_split(rng: np.random.Generator) -> dict:
    x = pd.read_csv(OUT / "model_failure_states.csv", parse_dates=["date"]).dropna(subset=["market_next"]).copy()
    results = {}
    tables = []
    for name, sample in {"train": x.loc[x.date < SPLIT], "test": x.loc[x.date >= SPLIT]}.items():
        sample = sample.copy()
        grouped = sample.groupby("failure_coherence").market_next.agg(["size", "mean"]).reset_index()
        grouped["split"] = name
        tables.append(grouped)
        ordered = sample.sort_values("date").reset_index(drop=True)
        effects = []
        for _ in range(5000):
            parts = []
            while sum(len(part) for part in parts) < len(ordered):
                start = int(rng.integers(len(ordered)))
                indices = (start + np.arange(6)) % len(ordered)
                parts.append(ordered.iloc[indices])
            resample = pd.concat(parts, ignore_index=True).iloc[: len(ordered)]
            means = resample.groupby("failure_coherence").market_next.mean().sort_index()
            effects.append(float(means.diff().dropna().mean()))
        boot = np.asarray(effects)
        results[name] = {
            "months": int(len(sample)),
            "state_return_correlation": float(sample.failure_coherence.rank().corr(sample.market_next.rank())),
            "mean_successive_state_difference": float(sample.groupby("failure_coherence").market_next.mean().diff().dropna().mean()),
            "bootstrap_ci_of_successive_difference": [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))],
        }
    pd.concat(tables).to_csv(OUT / "failure_coherence_time_split.csv", index=False, encoding="utf-8-sig")
    return results


def coverage_audit() -> dict:
    x = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl")
    coverage = x.dropna(subset=["price"]).groupby("ticker").date.agg(["min", "max", "size"]).reset_index()
    global_end = coverage["max"].max()
    early_end = coverage.loc[coverage["max"] < global_end]
    coverage.to_csv(OUT / "price_panel_coverage_audit.csv", index=False, encoding="utf-8-sig")
    delisting = json.loads((OUT / "delisting_universe_audit_report.json").read_text(encoding="utf-8"))
    return {
        "tickers": int(len(coverage)),
        "global_last_observation": str(global_end.date()),
        "tickers_ending_before_global_end": int(len(early_end)),
        "supplied_delisted_tickers": delisting["supplied_delisted_tickers"],
        "delisted_tickers_present_in_raw_adjusted_price": delisting["delisted_tickers_present_in_raw_adjusted_price"],
        "delisted_tickers_present_in_monthly_panel": delisting["delisted_tickers_present_in_monthly_panel"],
        "note": "Early terminal observations are a coverage flag, not a delisting label. The supplied delisted-stock universe is directly present in the raw adjusted-price universe.",
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    report = {
        "topology_time_split": topology_time_split(),
        "topology_rolling_walk_forward": topology_rolling_walk_forward(),
        "news_dependence_audit": news_dependence_audit(rng),
        "consensus_benchmark": consensus_benchmark(),
        "failure_time_split": failure_time_split(rng),
        "coverage_audit": coverage_audit(),
    }
    (OUT / "robustness_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
