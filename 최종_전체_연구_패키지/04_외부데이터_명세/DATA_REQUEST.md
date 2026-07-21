# Chapter 2 외부 데이터 요청서

아래 세 파일을 `external_data/`에 넣고 `experiments/external_data_gate.py`를 실행한다. 원시 추출 파일은 개인 라이선스 데이터이므로 Git에 올리지 않는다.

| 파일 | 필수 열 | 목적 |
| --- | --- | --- |
| `corporate_actions.csv` | `ticker,event_date,event_type,cash_settlement` | 종료 보유 종목의 실제 청산·합병·감자 현금흐름 연결 |
| `historical_quotes.parquet` | `timestamp,ticker,best_bid,best_ask,bid_size,ask_size` | 리밸런싱 시점 호가 스프레드·잔량·체결 가능성 검증 |
| `security_master.csv` | `ticker,effective_from,security_type` | 보통주·우선주·ETF·리츠·스팩 분리 및 코드변경 매핑 |

권장 열: `effective_to`, `predecessor_ticker`, `successor_ticker`, `stock_settlement_ratio`, `source`, `available_at`.

DataGuide 추출 시에는 종목코드가 6자리 보통주 코드인지 확인하고, 사건일과 정보 이용 가능일을 별도 열로 보존한다.
