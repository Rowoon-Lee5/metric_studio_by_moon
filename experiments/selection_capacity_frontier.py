"""Does alpha survive selection and execution constraints?

Unlike the first capacity experiment, each selected stock is constrained
individually.  At rebalance, no more than 5% of its 21-day ADV can be traded;
unfilled capital remains cash.  The effective number of executed names is
exp(Shannon entropy of realised position weights), not merely the requested N.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'
PCTS=np.arange(.2,1.01,.1); AUMS=[100_000_000,1_000_000_000,10_000_000_000,100_000_000_000]
N, PARTICIPATION=30,.05

def cagr(x):
    x=pd.Series(x).dropna(); return float((1+x).prod()**(12/len(x))-1)

def main():
    x=pd.read_pickle(OUT/'monthly_price_adv_panel.pkl').sort_values(['ticker','date']).copy()
    x['next_return']=x.groupby('ticker').price.shift(-1)/x.price-1
    x['ret_1m']=x.groupby('ticker').price.pct_change()
    x['ret_6m']=x.groupby('ticker').price.pct_change(6)
    configs={'reversal_1m':('ret_1m',True),'momentum_6m':('ret_6m',False)}
    rows=[]
    for date,d in x.groupby('date'):
        d=d.dropna(subset=['next_return','ret_1m','ret_6m','adv_21d']); d=d[(d.adv_21d>0)&(d.price>0)]
        for signal,(col,ascending) in configs.items():
            for pct in PCTS:
                universe=d.nlargest(max(N,int(len(d)*pct)),'adv_21d')
                selected=universe.sort_values(col,ascending=ascending).head(N)
                if len(selected) < N: continue
                ideal=selected.next_return.mean()
                for aum in AUMS:
                    requested=aum/N
                    filled=np.minimum(requested,PARTICIPATION*selected.adv_21d.to_numpy())
                    executed=filled.sum()/aum
                    # Per-position impact: same transparent square-root functional form as the first experiment.
                    one_way=.001+.005*np.sqrt(np.divide(filled,selected.adv_21d.to_numpy(),out=np.zeros(N),where=selected.adv_21d.to_numpy()>0))
                    realised=(filled*selected.next_return.to_numpy()).sum()/aum - 2*(filled*one_way).sum()/aum
                    weights=filled/filled.sum() if filled.sum()>0 else np.zeros(N)
                    effective_n=float(np.exp(-(weights[weights>0]*np.log(weights[weights>0])).sum())) if filled.sum()>0 else 0
                    rows.append(dict(date=date,signal=signal,universe_pct=pct,aum_krw=aum,ideal_return=ideal,realised_return=realised,executed_fraction=executed,effective_n=effective_n,avg_one_way_cost=float(np.average(one_way,weights=filled))))
    monthly=pd.DataFrame(rows); monthly.to_csv(OUT/'selection_capacity_monthly.csv',index=False,encoding='utf-8-sig')
    summary=(monthly.groupby(['signal','universe_pct','aum_krw']).agg(months=('date','size'),ideal_cagr=('ideal_return',cagr),realised_cagr=('realised_return',cagr),mean_executed_fraction=('executed_fraction','mean'),mean_effective_n=('effective_n','mean'),mean_one_way_cost=('avg_one_way_cost','mean')).reset_index())
    summary.to_csv(OUT/'selection_capacity_summary.csv',index=False,encoding='utf-8-sig')
    best=summary.loc[summary.groupby(['signal','aum_krw']).realised_cagr.idxmax()].sort_values(['signal','aum_krw'])
    report={'assumptions':{'signals':'bottom 30 by 1-month return; top 30 by 6-month return','liquidity_universe':'top 20% through 100% by 21-day ADV','max_participation_per_name':'5% of 21-day ADV at rebalance','unfilled_capital':'cash','impact_cost':'one-way 10bp + 50bp*sqrt(order/ADV)'},'optimal_implementable_frontier':best.to_dict(orient='records'),'interpretation':'effective_n measures execution concentration. If it falls below requested N, apparent diversification is not realised diversification.'}
    (OUT/'selection_capacity_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
