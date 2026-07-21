"""Family-wise block-bootstrap reality check for the full topology grid.

All 1,728 strategy returns are resampled with identical time blocks.  This
preserves their cross-strategy dependence while imposing a zero-mean null on
each strategy. The statistic is the maximum studentised mean across the grid.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'; B=1000; BLOCK=6; SEED=20260721
def tstats(m):
    return m.mean(axis=0)/(m.std(axis=0,ddof=1)/np.sqrt(m.shape[0]))
def main():
    long=pd.read_csv(OUT/'alpha_topology_monthly_returns.csv',parse_dates=['date'])
    wide=long.pivot(index='date',columns='key',values='net_return').dropna(axis=0,how='any')
    m=wide.to_numpy(); observed=tstats(m); observed_max=float(observed.max())
    centered=m-m.mean(axis=0,keepdims=True); rng=np.random.default_rng(SEED); null_max=[]; t=m.shape[0]
    starts=np.arange(t-BLOCK+1)
    for _ in range(B):
        chosen=rng.choice(starts,size=int(np.ceil(t/BLOCK)),replace=True)
        idx=np.concatenate([np.arange(s,s+BLOCK) for s in chosen])[:t]
        null_max.append(float(tstats(centered[idx]).max()))
    null_max=np.asarray(null_max); family_p=float((1+(null_max>=observed_max).sum())/(B+1))
    nodes=pd.read_csv(OUT/'alpha_topology_nodes.csv'); nodes['reality_check_p']=nodes.t_stat.map(lambda z:float((1+(null_max>=z).sum())/(B+1)))
    robust=nodes[nodes.robust].sort_values('t_stat',ascending=False); robust.to_csv(OUT/'reality_check_robust_nodes.csv',index=False,encoding='utf-8-sig')
    best_key=wide.columns[int(np.argmax(observed))]
    best_node=nodes.set_index('key').loc[best_key][['signal','universe_pct','holdings','aum_krw','cost_multiplier','net_cagr','mdd','t_stat','mean_fill']].to_dict()
    best_node['key']=best_key
    report={'method':{'bootstrap':'moving block bootstrap','replications':B,'block_months':BLOCK,'seed':SEED,'null':'each strategy is mean-centred; time blocks are resampled jointly across all strategies'},'common_sample':{'months':int(t),'strategies':int(m.shape[1]),'start':str(wide.index.min().date()),'end':str(wide.index.max().date())},'observed_max_t':observed_max,'family_wise_p_value':family_p,'best_node':best_node,'robust_nodes_with_reality_p':robust[['key','signal','net_cagr','t_stat','reality_check_p']].to_dict(orient='records'),'interpretation':'The p-value answers whether the best t-statistic among the full tested grid exceeds what zero-mean, temporally-blocked returns could produce. It is a family-wise guard, not proof of economic causality.'}
    (OUT/'reality_check_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
