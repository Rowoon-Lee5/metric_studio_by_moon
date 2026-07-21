"""Re-test observed-news attention using the full 264-ticker raw news panel."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
SOURCE = OUT / "news_attention_raw_source_snapshot.csv"
SEED = 20260722


def normalize(v: object) -> str:
    value = str(v).replace("A", "").split(".")[0]
    return value.zfill(6) if value.isdigit() else value


def block_bootstrap(series: pd.Series, rng: np.random.Generator, block: int = 12, reps: int = 5000) -> np.ndarray:
    values = series.dropna().to_numpy(float)
    n = len(values)
    out = np.empty(reps)
    for rep in range(reps):
        sample: list[float] = []
        while len(sample) < n:
            start = int(rng.integers(n))
            sample.extend(values[(start + np.arange(block)) % n])
        out[rep] = np.mean(sample[:n])
    return out


def main() -> None:
    price = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl").sort_values(["ticker", "date"]).copy()
    price["ticker"] = price.ticker.map(normalize)
    price["next_12m"] = price.groupby("ticker").price.shift(-12) / price.price - 1
    price["ret_6m"] = price.groupby("ticker").price.pct_change(6)
    news = pd.read_csv(SOURCE, parse_dates=["date"])
    news["ticker"] = news.ticker.map(normalize)
    news["news_log_count"] = np.log1p(news.n_titles.clip(lower=0))
    x = price.merge(news[["date", "ticker", "n_titles", "news_log_count"]], on=["date", "ticker"], how="inner").dropna(subset=["ret_6m", "next_12m"])
    rows = []
    for date, day in x.groupby("date"):
        if day.ticker.nunique() < 30:
            continue
        day = day.assign(bucket=pd.qcut(day.news_log_count.rank(method="first"), 3, labels=False))
        for bucket, group in day.groupby("bucket"):
            rows.append({"date": date, "bucket": int(bucket) + 1, "rank_ic_12m": group.ret_6m.rank().corr(group.next_12m.rank()), "n": int(len(group))})
    detail = pd.DataFrame(rows)
    summary = detail.groupby("bucket").agg(months=("date", "nunique"), mean_rank_ic_12m=("rank_ic_12m", "mean"), mean_n=("n", "mean")).reset_index()
    pivot = detail.pivot(index="date", columns="bucket", values="rank_ic_12m").dropna()
    diff = pivot[3] - pivot[1]
    boot = block_bootstrap(diff, np.random.default_rng(SEED))
    report = {
        "source": {"rows": int(len(x)), "tickers": int(x.ticker.nunique()), "start": str(x.date.min().date()), "end": str(x.date.max().date())},
        "summary": summary.to_dict(orient="records"),
        "high_minus_low": {
            "mean_rank_ic": float(diff.mean()),
            "months": int(len(diff)),
            "block_months": 12,
            "ci_95": [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))],
            "two_sided_sign_p": float(2 * min((boot <= 0).mean(), (boot >= 0).mean())),
        },
    }
    detail.to_csv(OUT / "news_attention_raw_ic_detail.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "news_attention_raw_ic_summary.csv", index=False, encoding="utf-8-sig")
    (OUT / "news_attention_raw_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
