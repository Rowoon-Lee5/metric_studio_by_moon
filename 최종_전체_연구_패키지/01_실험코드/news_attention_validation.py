"""Validate the 'attention removes predictability' hypothesis with observed news.

The source panel covers only 72 Korean stocks.  It is therefore an external
validation sample for the turnover proxy, not a claim about the whole market.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'
NEWS=Path(r'C:\Users\benef\OneDrive\바탕 화면\KRX_AutoTrader_Global\results\news_sentiment.parquet')
NEWS_SNAPSHOT=OUT/'news_attention_source_snapshot.csv'
def norm_ticker(v):
    s=str(v).replace('A','').split('.')[0]
    return s.zfill(6) if s.isdigit() else s
def main():
    price=pd.read_pickle(OUT/'monthly_price_adv_panel.pkl').sort_values(['ticker','date']).copy()
    price['ticker']=price.ticker.map(norm_ticker); price['next_1m']=price.groupby('ticker').price.shift(-1)/price.price-1; price['next_12m']=price.groupby('ticker').price.shift(-12)/price.price-1; price['ret_6m']=price.groupby('ticker').price.pct_change(6)
    news=(pd.read_csv(NEWS_SNAPSHOT) if NEWS_SNAPSHOT.exists() else pd.read_parquet(NEWS)).copy(); news['date']=pd.to_datetime(news.date); news['ticker']=news.ticker.map(norm_ticker); news['news_log_count']=np.log1p(news.news_count.fillna(0))
    x=price.merge(news[['date','ticker','news_count','news_sent','news_log_count']],on=['date','ticker'],how='inner').dropna(subset=['ret_6m','next_12m'])
    rows=[]
    for date,d in x.groupby('date'):
        # Ties at zero news make quintiles ill-defined; three bins retain the no-news group.
        try:d=d.assign(attention_bucket=pd.qcut(d.news_log_count.rank(method='first'),3,labels=False))
        except ValueError:continue
        for b,g in d.groupby('attention_bucket'):
            rows.append({'test':'attention_vs_momentum_ic','date':date,'bucket':int(b)+1,'rank_ic_12m':g.ret_6m.rank().corr(g.next_12m.rank()),'mean_next_12m':g.next_12m.mean(),'n':len(g)})
    # Per-stock trailing z-score: attention surprise is measured without future news.
    x['attention_z']=x.groupby('ticker').news_log_count.transform(lambda s:(s-s.rolling(12,min_periods=6).mean().shift(1))/(s.rolling(12,min_periods=6).std().shift(1)+1e-9))
    x['attention_event']=np.select([x.attention_z>=2,x.attention_z<=-1],['surge','quiet'],default='normal')
    events=(x.groupby('attention_event').agg(observations=('ticker','size'),mean_next_1m=('next_1m','mean'),median_next_1m=('next_1m','median'),mean_news_sent=('news_sent','mean')).reset_index())
    detail=pd.DataFrame(rows); summary=detail.groupby('bucket').agg(months=('date','nunique'),mean_rank_ic_12m=('rank_ic_12m','mean'),mean_next_12m=('mean_next_12m','mean'),mean_n=('n','mean')).reset_index()
    detail.to_csv(OUT/'news_attention_ic_detail.csv',index=False,encoding='utf-8-sig'); summary.to_csv(OUT/'news_attention_ic_summary.csv',index=False,encoding='utf-8-sig'); events.to_csv(OUT/'news_attention_event_summary.csv',index=False,encoding='utf-8-sig')
    report={'source':{'path':str(NEWS_SNAPSHOT if NEWS_SNAPSHOT.exists() else NEWS),'joined_observations':int(len(x)),'tickers':int(x.ticker.nunique()),'start':str(x.date.min().date()),'end':str(x.date.max().date())},'attention_bucket_momentum_predictability':summary.to_dict(orient='records'),'attention_surprise_events':events.to_dict(orient='records'),'interpretation':'Observed news count replaces the turnover proxy. The panel is only 72 tickers and news coverage/collection methodology may be endogenous; results are external validation, not causal proof.'}
    (OUT/'news_attention_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
