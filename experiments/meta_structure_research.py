"""Path dependence, epistemic stability, model failure states, and information age."""
from __future__ import annotations
import bisect,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'
DISC=Path(r'C:\Users\benef\OneDrive\바탕 화면\직박구리2\직박구리\숭실대학교\26-1 금인빅 프로젝트\krx_llm_factor_v3_share\v12\data\disclosure_dates')
PCTS=[.5,.7,.9,1.0]; NS=[20,30,50]; N=30
def cagr(x): x=pd.Series(x).dropna(); return float((1+x).prod()**(12/len(x))-1)
def base():
 x=pd.read_pickle(OUT/'monthly_price_adv_panel.pkl').sort_values(['ticker','date']).copy(); m=pd.read_pickle(OUT/'monthly_mcap_panel.pkl'); x=x.merge(m,on=['date','ticker'],how='left'); x['next']=x.groupby('ticker').price.shift(-1)/x.price-1; x['r1']=x.groupby('ticker').price.pct_change(); x['r6']=x.groupby('ticker').price.pct_change(6); x['vol']=x.groupby('ticker').r1.transform(lambda s:s.rolling(12,min_periods=8).std()); return x
def select(d,col,asc,p,n):
 u=d.nlargest(max(n,int(len(d)*p)),'adv_21d'); return u.sort_values(col,ascending=asc).head(n)
def hysteresis(x):
 dates=sorted(x.date.unique()); out=[]
 for i in range(6,len(dates)-1):
  end=x[x.date==dates[i]].dropna(subset=['vol','next','adv_21d']); paths={'contract':np.linspace(1,.7,6),'expand':np.linspace(.2,.7,6)}
  for name,seq in paths.items():
   banned=set()
   for j,p in enumerate(seq[:-1]):
    old=x[x.date==dates[i-5+j]].dropna(subset=['adv_21d']); allowed=set(old.nlargest(int(len(old)*p),'adv_21d').ticker); banned=(set(old.ticker)-allowed)
   chosen=select(end,'vol',True,.7,N); chosen=chosen[~chosen.ticker.isin(banned)].head(N)
   if len(chosen)>=10: out.append({'date':dates[i],'path':name,'return':chosen.next.mean(),'holdings':len(chosen),'banned_share':len(banned)/max(1,len(end))})
 d=pd.DataFrame(out); return d,d.groupby('path').agg(months=('date','size'),mean_return=('return','mean'),cagr=('return',cagr),mean_holdings=('holdings','mean'),mean_banned_share=('banned_share','mean')).reset_index()
def stability(x):
 rows=[]; specs=[('r1',True),('r6',False),('vol',True),('mcap',True)]
 for date,d in x.groupby('date'):
  d=d.dropna(subset=['next','r1','r6','vol','mcap','adv_21d']); votes=pd.Series(0,index=d.ticker)
  for col,asc in specs:
   for p in PCTS:
    for n in NS: votes.loc[select(d,col,asc,p,n).ticker]+=1
  chosen=d.set_index('ticker').loc[votes.nlargest(N).index]; rows.append({'date':date,'stability_return':chosen.next.mean(),'mean_vote':votes.nlargest(N).mean(),'selected_models':int((votes>0).sum())})
 r=pd.DataFrame(rows); return r,{'months':len(r),'cagr':cagr(r.stability_return),'mean_monthly_return':float(r.stability_return.mean()),'mean_vote_top30':float(r.mean_vote.mean())}
def failure_state(x):
 specs={'reversal':('r1',True),'momentum':('r6',False),'lowvol':('vol',True),'smallcap':('mcap',True)}; dates=[]
 for date,d in x.groupby('date'):
  d=d.dropna(subset=['next','r1','r6','vol','mcap','adv_21d']); row={'date':date,'market_next':d.next.mean()}
  for name,(c,a) in specs.items(): row[name]=select(d,c,a,1.,N).next.mean()
  dates.append(row)
 z=pd.DataFrame(dates).sort_values('date'); signals=list(specs)
 for s in signals: z[s+'_z']=(z[s]-z[s].rolling(36,min_periods=24).mean().shift(1))/(z[s].rolling(36,min_periods=24).std().shift(1)+1e-9)
 z['failure_coherence']=(z[[s+'_z' for s in signals]]<-1).sum(axis=1); q=z.groupby('failure_coherence').market_next.agg(['size','mean','median']).reset_index(); return z,q
def info_age(x):
 mp={}
 for p in DISC.glob('*.json'):
  try: mp[p.stem]=sorted(pd.Timestamp(v) for v in json.loads(p.read_text(encoding='utf-8')))
  except: pass
 def age(r):
  a=mp.get(str(r.ticker),[]); i=bisect.bisect_right(a,r.date)-1
  return (r.date-a[i]).days if i>=0 else np.nan
 y=x.dropna(subset=['next']).copy(); y['disclosure_age_days']=y.apply(age,axis=1); rows=[]
 for date,d in y.groupby('date'):
  d=d.dropna(subset=['disclosure_age_days']);
  if len(d)<30: continue
  d=d.assign(bucket=pd.qcut(d.disclosure_age_days.rank(method='first'),3,labels=False)); rows.append(d.groupby('bucket').next.mean().rename(date))
 wide=pd.DataFrame(rows); return {'matched_observations':int(y.disclosure_age_days.notna().sum()),'tickers_with_dates':len(mp),'fresh_mid_stale_next_1m':{str(int(c)+1):float(wide[c].mean()) for c in wide.columns}}
def main():
 x=base(); h,hs=hysteresis(x); st,ss=stability(x); fs,fq=failure_state(x); ia=info_age(x)
 h.to_csv(OUT/'alpha_hysteresis_monthly.csv',index=False,encoding='utf-8-sig'); st.to_csv(OUT/'epistemic_stability_returns.csv',index=False,encoding='utf-8-sig'); fs.to_csv(OUT/'model_failure_states.csv',index=False,encoding='utf-8-sig'); fq.to_csv(OUT/'model_failure_state_summary.csv',index=False,encoding='utf-8-sig')
 report={'alpha_hysteresis':hs.to_dict(orient='records'),'epistemic_stability':ss,'model_failure_states':fq.to_dict(orient='records'),'information_age':ia,'warnings':['Hysteresis uses six-month contraction/expansion paths and a one-month exclusion cooldown; it is a policy counterfactual, not claimed as an intrinsic market law.','Epistemic stability measures model-configuration consensus, not investor consensus.','Disclosure cache provenance and survivorship require a separate audit.']}; (OUT/'meta_structure_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
