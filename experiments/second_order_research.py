"""Second-order tests: research delay, information censorship, attention proxy,
and failure-aware long-only construction.  All signals are fixed ex ante."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'; N=30
PCTS=np.arange(.2,1.01,.1)
def cagr(r):
    r=pd.Series(r).dropna(); return float((1+r).prod()**(12/len(r))-1)
def mdd(r):
    w=(1+pd.Series(r).fillna(0)).cumprod(); return float((w/w.cummax()-1).min())
def stats(r): return {'cagr':cagr(r),'annual_vol':float(pd.Series(r).std()*np.sqrt(12)),'mdd':mdd(r),'months':int(pd.Series(r).notna().sum())}

def candidate_returns(x):
    rows=[]
    for date,d in x.groupby('date'):
        d=d.dropna(subset=['ret_1m','ret_6m','next_1m','adv_21d']); d=d[d.adv_21d>0]
        for pct in PCTS:
            u=d.nlargest(max(N,int(len(d)*pct)),'adv_21d')
            if len(u)<N: continue
            rows += [{'date':date,'candidate':f'reversal_top_{int(pct*100)}','return':u.nsmallest(N,'ret_1m').next_1m.mean()},
                     {'date':date,'candidate':f'momentum_top_{int(pct*100)}','return':u.nlargest(N,'ret_6m').next_1m.mean()}]
    return pd.DataFrame(rows).pivot(index='date',columns='candidate',values='return').sort_index()

def alpha_half_life(r):
    """Walk-forward choose from fixed candidates with a realistic implementation delay."""
    out=[]
    for delay in [0,1,3,6,12]:
        realised=[]; choices=[]
        for t in range(61+delay,len(r)):
            decision=t-delay; history=r.iloc[decision-60:decision]
            choice=history.mean().idxmax()  # selection sees no future return
            realised.append(r.iloc[t][choice]); choices.append(choice)
        out.append({'implementation_delay_months':delay,**stats(realised),'unique_selected_models':len(set(choices)),'most_selected_model':pd.Series(choices).mode().iloc[0]})
    return out

def liquidity_censorship(x):
    rows=[]
    for date,d in x.groupby('date'):
        d=d.dropna(subset=['ret_1m','ret_6m','next_1m','adv_21d']); d=d[d.adv_21d>0]
        for signal,ascending in [('reversal',True),('momentum',False)]:
            col='ret_1m' if signal=='reversal' else 'ret_6m'
            full=set(d.sort_values(col,ascending=ascending).head(N).ticker)
            for pct in PCTS:
                u=d.nlargest(max(N,int(len(d)*pct)),'adv_21d'); chosen=u.sort_values(col,ascending=ascending).head(N)
                rows.append({'date':date,'signal':signal,'universe_pct':pct,'selection_recall_vs_full':len(full&set(chosen.ticker))/N,'signal_dispersion':u[col].std(),'next_1m_return':chosen.next_1m.mean(),'universe_n':len(u)})
    detail=pd.DataFrame(rows)
    summary=detail.groupby(['signal','universe_pct']).agg(months=('date','size'),mean_recall=('selection_recall_vs_full','mean'),mean_signal_dispersion=('signal_dispersion','mean'),mean_next_1m_return=('next_1m_return','mean')).reset_index()
    return detail,summary

def attention_proxy(x):
    rows=[]
    for date,d in x.groupby('date'):
        d=d.dropna(subset=['turnover_proxy','ret_1m','ret_6m','next_12m'])
        try:d=d.assign(bucket=pd.qcut(d.turnover_proxy,5,labels=False,duplicates='drop'))
        except ValueError:continue
        for b,g in d.groupby('bucket'):
            for sig in ['ret_1m','ret_6m']:
                ic=g[sig].rank().corr(g.next_12m.rank())
                rows.append({'date':date,'turnover_bucket':int(b)+1,'signal':sig,'rank_ic_12m':ic,'n':len(g)})
    detail=pd.DataFrame(rows); return detail,detail.groupby(['turnover_bucket','signal']).rank_ic_12m.mean().reset_index()

def failure_aware(x):
    """Top-60 momentum candidates; choose 30 by prior downside resilience + low volatility."""
    pivot=x.pivot(index='date',columns='ticker',values='ret_1m').sort_index(); dates=pivot.index
    market=pivot.mean(axis=1); base=[]; aware=[]
    for t in range(36,len(dates)-1):
        hist=pivot.iloc[t-36:t]; bad=market.iloc[t-36:t]<=market.iloc[t-36:t].quantile(.2)
        downside=hist.loc[bad].mean(); vol=hist.std(); current=x[x.date==dates[t]].set_index('ticker')
        cand=current.dropna(subset=['ret_6m','next_1m']).nlargest(60,'ret_6m')
        base.append({'date':dates[t],'return':cand.nlargest(N,'ret_6m').next_1m.mean()})
        score=(downside.rank(pct=True)-vol.rank(pct=True)).reindex(cand.index)
        aware.append({'date':dates[t],'return':cand.assign(failure_score=score).nlargest(N,'failure_score').next_1m.mean()})
    b=pd.DataFrame(base).set_index('date')['return']; a=pd.DataFrame(aware).set_index('date')['return']
    return {'momentum_only':stats(b),'failure_aware_long_only':stats(a),'definition':'Each month, choose the top 60 by 6-month momentum; retain the 30 with historically smaller losses in the worst 20% market months and lower trailing volatility.'},pd.DataFrame({'momentum_only':b,'failure_aware':a})

def main():
    x=pd.read_pickle(OUT/'monthly_price_adv_panel.pkl').sort_values(['ticker','date']).copy()
    x['next_1m']=x.groupby('ticker').price.shift(-1)/x.price-1; x['next_12m']=x.groupby('ticker').price.shift(-12)/x.price-1
    x['ret_1m']=x.groupby('ticker').price.pct_change(); x['ret_6m']=x.groupby('ticker').price.pct_change(6); x['turnover_proxy']=x.adv_21d/x.groupby('ticker').price.transform(lambda p:p) # overwritten after mcap merge if available
    mcap=pd.read_pickle(OUT/'monthly_mcap_panel.pkl'); x=x.merge(mcap,on=['date','ticker'],how='left'); x['turnover_proxy']=x.adv_21d/x.mcap
    alpha=alpha_half_life(candidate_returns(x)); censor_detail,censor=liquidity_censorship(x); attention_detail,attention=attention_proxy(x); failure,failure_ts=failure_aware(x)
    censor_detail.to_csv(OUT/'liquidity_information_censorship_detail.csv',index=False,encoding='utf-8-sig'); censor.to_csv(OUT/'liquidity_information_censorship_summary.csv',index=False,encoding='utf-8-sig')
    attention_detail.to_csv(OUT/'attention_proxy_predictability_detail.csv',index=False,encoding='utf-8-sig'); attention.to_csv(OUT/'attention_proxy_predictability_summary.csv',index=False,encoding='utf-8-sig'); failure_ts.to_csv(OUT/'failure_aware_portfolio_returns.csv',encoding='utf-8-sig')
    report={'alpha_half_life':alpha,'liquidity_as_information_censorship':censor.to_dict(orient='records'),'attention_proxy_predictability':attention.to_dict(orient='records'),'failure_aware_long_only':failure,'warnings':['Turnover is not popularity or attention; no causal interpretation is permitted.','This portfolio uses monthly close data, equal weights and no trading costs.','The 5% ADV rule is a sensitivity assumption, not observed execution.']}
    (OUT/'second_order_research_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
