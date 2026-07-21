"""Rank DART terminal-event filings for document-level settlement extraction."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
EXTERNAL = ROOT / "external_data"


def priority(title: str) -> int:
    title = str(title)
    rules = [
        ("상장폐지", 0), ("합병완료", 1), ("합병종료", 1), ("소멸합병", 1),
        ("회사합병결정", 2), ("주식교환", 2), ("주식이전", 2),
        ("감자완료", 3), ("감자결정", 4), ("해산사유", 4), ("청산", 4),
    ]
    return next((value for needle, value in rules if needle in title), 9)


def main() -> None:
    candidates = pd.read_csv(EXTERNAL / "dart_terminal_event_candidates.csv", parse_dates=["terminal_date", "rcept_dt"])
    candidates["priority"] = candidates.report_nm.map(priority)
    candidates["days_from_terminal"] = (candidates.rcept_dt - candidates.terminal_date).abs().dt.days
    candidates = candidates.sort_values(["ticker", "terminal_date", "priority", "days_from_terminal", "rcept_dt"])
    queue = candidates.groupby(["ticker", "terminal_date"], as_index=False).head(3).copy()
    queue["document_status"] = "pending_official_document_parse"
    queue.to_csv(EXTERNAL / "dart_terminal_event_document_queue.csv", index=False, encoding="utf-8-sig")
    report = {
        "filing_candidates": int(len(candidates)),
        "terminal_ticker_months_with_candidate": int(candidates[["ticker", "terminal_date"]].drop_duplicates().shape[0]),
        "document_queue_rows": int(len(queue)),
        "priority_0_or_1_rows": int((queue.priority <= 1).sum()),
        "rule": "At most three official filing documents per terminal ticker-month, ranked by settlement relevance then date proximity. This queue is not a settlement dataset.",
    }
    (OUT / "dart_terminal_event_priority_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
