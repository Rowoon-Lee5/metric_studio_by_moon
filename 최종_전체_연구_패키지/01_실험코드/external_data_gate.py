"""Fail-closed gate for the three external datasets required to close chapter 2.

Place non-versioned extracts in ``external_data/``.  The gate never invents a
settlement value or a quote.  It reports coverage against the actual selected
small-cap holdings and remains failed until the required observations exist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
INPUT = ROOT / "external_data"

CONTRACTS = {
    "corporate_actions": {
        "file": "corporate_actions.csv",
        "required": {"ticker", "event_date", "event_type", "cash_settlement"},
        "meaning": "상장폐지·합병·감자·청산의 실제 현금 결제값. successor_ticker와 stock_settlement_ratio가 있으면 함께 제공.",
    },
    "historical_quotes": {
        "file": "historical_quotes.parquet",
        "required": {"timestamp", "ticker", "best_bid", "best_ask", "bid_size", "ask_size"},
        "meaning": "리밸런싱 시점 이전 최우선 호가와 잔량. 분봉 또는 스냅샷 모두 가능하나 timestamp는 필수.",
    },
    "security_master": {
        "file": "security_master.csv",
        "required": {"ticker", "effective_from", "security_type"},
        "meaning": "일자별 보통주·우선주·ETF·리츠·스팩 구분 및 코드변경 매핑. effective_to, predecessor_ticker, successor_ticker 권장.",
    },
}


def normalize(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("A", "", regex=False).str.split(".").str[0].str.zfill(6)


def read_contract(spec: dict) -> tuple[pd.DataFrame | None, dict]:
    path = INPUT / spec["file"]
    if not path.exists():
        return None, {"status": "missing_file", "expected_path": str(path), "required_columns": sorted(spec["required"]), "meaning": spec["meaning"]}
    data = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    missing = sorted(spec["required"] - set(data.columns))
    if missing:
        return None, {"status": "schema_error", "path": str(path), "missing_columns": missing, "required_columns": sorted(spec["required"])}
    return data, {"status": "loaded", "path": str(path), "rows": int(len(data)), "tickers": int(normalize(data.ticker).nunique())}


def main() -> None:
    INPUT.mkdir(exist_ok=True)
    holdings = pd.read_csv(OUT / "smallcap_selected_holdings.csv", parse_dates=["date"])
    holdings["ticker"] = normalize(holdings.ticker)
    outputs: dict[str, dict] = {"holdings": {"rows": int(len(holdings)), "tickers": int(holdings.ticker.nunique()), "start": str(holdings.date.min().date()), "end": str(holdings.date.max().date())}}
    loaded: dict[str, pd.DataFrame] = {}
    for name, spec in CONTRACTS.items():
        data, status = read_contract(spec)
        outputs[name] = status
        if data is not None:
            data = data.copy()
            data["ticker"] = normalize(data.ticker)
            loaded[name] = data
    if "corporate_actions" in loaded:
        actions = loaded["corporate_actions"].copy()
        actions["event_date"] = pd.to_datetime(actions.event_date)
        unresolved = holdings.merge(actions[["ticker", "event_date"]], on="ticker", how="left")
        unresolved = unresolved[(unresolved.event_date.isna()) | (unresolved.event_date < unresolved.date)]
        outputs["corporate_actions"]["holding_rows_without_later_action"] = int(len(unresolved))
    if "security_master" in loaded:
        master = loaded["security_master"]
        outputs["security_master"]["held_tickers_covered"] = int(holdings.ticker.isin(master.ticker).sum())
    if "historical_quotes" in loaded:
        quotes = loaded["historical_quotes"].copy()
        quotes["timestamp"] = pd.to_datetime(quotes.timestamp)
        bad = quotes[(quotes.best_bid <= 0) | (quotes.best_ask < quotes.best_bid)]
        outputs["historical_quotes"]["invalid_quote_rows"] = int(len(bad))
    outputs["gate_status"] = "pass" if all(outputs[name]["status"] == "loaded" for name in CONTRACTS) else "blocked_missing_external_data"
    (OUT / "external_data_gate_report.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
