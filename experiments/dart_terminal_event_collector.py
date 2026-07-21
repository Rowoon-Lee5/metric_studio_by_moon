"""Collect official DART filing candidates for terminal small-cap holdings.

This is a discovery step, not a settlement-value imputer.  It stores only
filing metadata and receipt numbers; cash consideration must be parsed from
the underlying official document before it may enter corporate_actions.csv.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from panel_integrity import quarantine_reentries, return_over_months


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
EXTERNAL = ROOT / "external_data"
SOURCE = Path(r"C:\Users\benef\OneDrive\바탕 화면\KRX_AutoTrader_Global")
LIST_URL = "https://opendart.fss.or.kr/api/list.json"
KEYWORDS = ("상장폐지", "합병", "감자", "해산", "청산", "주식교환", "주식이전", "영업양도")


def load_env_key() -> str:
    for line in (SOURCE / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("DART_API_KEY="):
            return line.partition("=")[2].strip()
    return os.getenv("DART_API_KEY", "")


def terminal_events() -> pd.DataFrame:
    price = pd.read_pickle(OUT / "monthly_price_adv_panel.pkl")
    price, _ = quarantine_reentries(price)
    mcap = pd.read_pickle(OUT / "monthly_mcap_panel.pkl")
    x = price.merge(mcap, on=["date", "ticker"], how="left")
    x["next"] = return_over_months(x, 1)
    rows = []
    for date, day in x.groupby("date"):
        eligible = day.dropna(subset=["adv_21d", "mcap", "price"])
        eligible = eligible[(eligible.adv_21d > 0) & (eligible.mcap > 0)]
        selected = eligible.nlargest(max(50, int(len(eligible) * .9)), "adv_21d").nsmallest(50, "mcap")
        rows.extend({"ticker": str(ticker).zfill(6), "terminal_date": pd.Timestamp(date)} for ticker in selected.loc[selected.next.isna(), "ticker"])
    return pd.DataFrame(rows).drop_duplicates()


def main() -> None:
    EXTERNAL.mkdir(exist_ok=True)
    api_key = load_env_key()
    if not api_key:
        raise RuntimeError("DART_API_KEY is not configured")
    corp_map = {str(k).zfill(6): str(v) for k, v in json.loads((SOURCE / "data" / "corp_code_map.json").read_text(encoding="utf-8")).items()}
    events = terminal_events()
    events["corp_code"] = events.ticker.map(corp_map).fillna("")
    events.to_csv(EXTERNAL / "dart_terminal_event_targets.csv", index=False, encoding="utf-8-sig")
    records = []
    for index, row in events.loc[events.corp_code.ne("")].reset_index(drop=True).iterrows():
        end = row.terminal_date + pd.Timedelta(days=370)
        start = row.terminal_date - pd.Timedelta(days=370)
        params = {"crtfc_key": api_key, "corp_code": row.corp_code, "bgn_de": start.strftime("%Y%m%d"), "end_de": end.strftime("%Y%m%d"), "page_count": 100}
        with urlopen(f"{LIST_URL}?{urlencode(params)}", timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for filing in payload.get("list", []):
            title = str(filing.get("report_nm", ""))
            if any(word in title for word in KEYWORDS):
                records.append({"ticker": row.ticker, "terminal_date": row.terminal_date, "corp_code": row.corp_code, "rcept_no": filing.get("rcept_no", ""), "rcept_dt": filing.get("rcept_dt", ""), "report_nm": title, "flr_nm": filing.get("flr_nm", "")})
        if index % 25 == 0:
            pd.DataFrame(records).to_csv(EXTERNAL / "dart_terminal_event_candidates.csv", index=False, encoding="utf-8-sig")
        time.sleep(.12)
    candidates = pd.DataFrame(records)
    candidates.to_csv(EXTERNAL / "dart_terminal_event_candidates.csv", index=False, encoding="utf-8-sig")
    report = {"terminal_candidate_rows": int(len(events)), "mapped_to_dart_corp_code": int(events.corp_code.ne("").sum()), "official_filing_candidates": int(len(candidates)), "note": "No cash settlement is inferred from a filing title. Inspect document.xml for each candidate before creating corporate_actions.csv."}
    (OUT / "dart_terminal_event_discovery_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
