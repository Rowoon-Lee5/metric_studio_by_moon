"""Alpha Topological Persistence: measure continents, not the best backtest peak.

A node is a (signal, liquidity universe, holdings, AUM, cost shock) strategy.
Robust nodes must have positive net CAGR, t-stat > 1.96, MDD > -60%, and at
least 80% average fill. Adjacent robust nodes form a 'continent'.
"""
from __future__ import annotations
import json
from pathlib import Path
from collections import deque
from statistics import NormalDist
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'
PCTS=np.arange(.2,1.01,.1); NS=[10,20,30,50]; AUMS=[1e8,1e9,1e10]; COSTS=[.5,1.,1.5,2.]
PARTICIPATION=.05
def cagr(r):
    r=pd.Series(r).dropna(); return float((1+r).prod()**(12/len(r))-1)
def mdd(r):
    w=(1+pd.Series(r).fillna(0)).cumprod(); return float((w/w.cummax()-1).min())
def node_key(signal,p,n,a,c): return f'{signal}|p{p:.1f}|n{n}|a{int(a)}|c{c:.1f}'

def components(nodes):
    """Connected components where one ordered parameter changes by one step."""
    node_set=set(nodes); seen=set(); out=[]
    for root in node_set:
        if root in seen: continue
        q=deque([root]); seen.add(root); group=[]
        while q:
            k=q.popleft(); group.append(k); signal,p,n,a,c=k
            for values,cur in [(PCTS,p),(NS,n),(AUMS,a),(COSTS,c)]:
                i=list(values).index(cur)
                for j in [i-1,i+1]:
                    if 0<=j<len(values):
                        cand=(signal, values[j] if values is PCTS else p, values[j] if values is NS else n, values[j] if values is AUMS else a, values[j] if values is COSTS else c)
                        if cand in node_set and cand not in seen: seen.add(cand); q.append(cand)
        out.append(group)
    return sorted(out,key=len,reverse=True)

def main():
    x=pd.read_pickle(OUT/'monthly_price_adv_panel.pkl').sort_values(['ticker','date']).copy()
    mc=pd.read_pickle(OUT/'monthly_mcap_panel.pkl'); x=x.merge(mc,on=['date','ticker'],how='left')
    x['next']=x.groupby('ticker').price.shift(-1)/x.price-1; x['r1']=x.groupby('ticker').price.pct_change(); x['r6']=x.groupby('ticker').price.pct_change(6); x['vol12']=x.groupby('ticker').r1.transform(lambda s:s.rolling(12,min_periods=8).std())
    specs={'reversal_1m':('r1',True),'momentum_6m':('r6',False),'low_volatility':('vol12',True),'small_cap':('mcap',True)}
    paths={}; rows=[]
    for date,d in x.groupby('date'):
        d=d.dropna(subset=['next','adv_21d','r1','r6','vol12','mcap']); d=d[(d.adv_21d>0)&(d.price>0)&(d.mcap>0)]
        for signal,(col,ascending) in specs.items():
            for p in PCTS:
                u=d.nlargest(max(max(NS),int(len(d)*p)),'adv_21d')
                for n in NS:
                    selected=u.sort_values(col,ascending=ascending).head(n)
                    if len(selected)<n: continue
                    adv=selected.adv_21d.to_numpy(); ret=selected.next.to_numpy()
                    for aum in AUMS:
                        filled=np.minimum(aum/n,PARTICIPATION*adv); fill=filled.sum()/aum; ratio=np.divide(filled,adv,out=np.zeros(n),where=adv>0)
                        for cost in COSTS:
                            one_way=.001+.005*cost*np.sqrt(ratio)
                            realised=(filled*ret).sum()/aum-2*(filled*one_way).sum()/aum
                            k=(signal,float(p),n,float(aum),float(cost)); paths.setdefault(k,{'dates':[],'returns':[],'fills':[]})['dates'].append(date); paths[k]['returns'].append(realised); paths[k]['fills'].append(fill)
    for k,values in paths.items():
        signal,p,n,a,c=k; r=pd.Series(values['returns']).dropna(); t=float(r.mean()/(r.std(ddof=1)/np.sqrt(len(r)))) if r.std(ddof=1)>0 else 0.0; pv=float(2*(1-NormalDist().cdf(abs(t))) )
        rows.append({'key':node_key(*k),'signal':signal,'universe_pct':p,'holdings':n,'aum_krw':a,'cost_multiplier':c,'months':len(r),'net_cagr':cagr(r),'mdd':mdd(r),'t_stat':t,'p_value':pv,'mean_fill':float(np.mean(values['fills']))})
    summary=pd.DataFrame(rows)
    summary['robust']=(summary.net_cagr>0)&(summary.t_stat>1.96)&(summary.mdd>-.60)&(summary.mean_fill>=.80)
    robust_tuples=[(r.signal,r.universe_pct,r.holdings,r.aum_krw,r.cost_multiplier) for r in summary[summary.robust].itertuples()]
    comps=components(robust_tuples)
    records=[]
    for i,g in enumerate(comps,1):
        sub=summary[summary.key.isin([node_key(*k) for k in g])]
        records.append({'continent_id':i,'nodes':len(g),'signals':','.join(sorted(sub.signal.unique())),'mean_net_cagr':float(sub.net_cagr.mean()),'min_net_cagr':float(sub.net_cagr.min()),'max_cost_multiplier':float(sub.cost_multiplier.max()),'aum_range':f'{sub.aum_krw.min():.0f}-{sub.aum_krw.max():.0f}'})
    continents=pd.DataFrame(records); summary.to_csv(OUT/'alpha_topology_nodes.csv',index=False,encoding='utf-8-sig'); continents.to_csv(OUT/'alpha_topology_continents.csv',index=False,encoding='utf-8-sig')
    monthly=[]
    for k,values in paths.items():
        key=node_key(*k)
        monthly.extend({'date':d,'key':key,'net_return':r} for d,r in zip(values['dates'],values['returns']))
    pd.DataFrame(monthly).to_csv(OUT/'alpha_topology_monthly_returns.csv',index=False,encoding='utf-8-sig')
    report={'definition':'A robust node has positive net CAGR, t-stat>1.96, MDD>-60% and mean order fill>=80%. A continent is a connected component under one-step parameter perturbations.','grid':{'signals':list(specs),'universe_pct':PCTS.tolist(),'holdings':NS,'aum_krw':AUMS,'cost_multipliers':COSTS},'nodes_total':int(len(summary)),'robust_nodes':int(summary.robust.sum()),'continents':records,'warning':'This is a topology diagnostic, not a multiple-testing correction. Formal reality-check/permutation testing remains a separate gate.'}
    (OUT/'alpha_topology_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
