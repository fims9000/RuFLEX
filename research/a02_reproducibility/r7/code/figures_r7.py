"""Create R7 figures from frozen outputs; these are descriptive visuals."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent.parent
out=root/'figures';out.mkdir(parents=True,exist_ok=True)
s=json.loads((root/'results/simulation/R7_SIMULATION_SUMMARY.json').read_text())
names=['Naive per-country\nsequential evidence','One mean per year\n(group-respecting)']
vals=[s['naive_rowwise']['rate']*100,s['year_grouped']['rate']*100]
fig,ax=plt.subplots(figsize=(8.5,4.1));ax.bar(names,vals,width=.5)
ax.set_ylabel('False activation rate (% of 1,000 simulations)')
ax.set_ylim(0,100);ax.set_title('Perfect within-year dependence, zero true mean gain')
for i,v in enumerate(vals):ax.text(i,v+2,f'{v:.1f}%',ha='center',fontsize=11)
ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(out/'figure1_correlated_null.png',dpi=170);plt.close(fig)

x=json.loads((root/'results/analysis/R7_DIAGNOSTICS.json').read_text())['rows']
models=[r['model'].replace('_',' ').title() for r in x]
naive=[max(1e-9,r['naive_rowwise_max_e']) for r in x]
group=[max(1e-9,r['group_respecting_max_e']) for r in x]
ix=np.arange(len(models));fig,ax=plt.subplots(figsize=(9.1,4.3))
ax.bar(ix-.18,naive,width=.36,label='Country-year rowwise (invalid if dependent)')
ax.bar(ix+.18,group,width=.36,label='One observation per year')
ax.axhline(20,linestyle='--',linewidth=1.3,label='Alarm threshold: 20')
ax.set_yscale('log');ax.set_xticks(ix,models,rotation=8)
ax.set_ylim(.7,1e18);ax.set_ylabel('Maximum evidence process (log scale)')
ax.legend(fontsize=8.2,loc='upper right');ax.set_title('Same predictions, different inferential unit')
ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(out/'figure2_evidence_granularity.png',dpi=170);plt.close(fig)

base=[r['future_baseline_cost'] for r in x];aug=[r['future_augmented_cost'] for r in x]
fig,ax=plt.subplots(figsize=(8.6,4.2));ax.bar(ix-.18,base,width=.36,label='Confidence-only policy')
ax.bar(ix+.18,aug,width=.36,label='Reproducibility-conditioned policy')
ax.set_xticks(ix,models,rotation=8);ax.set_ylim(0,max(max(base),max(aug))*.10+max(max(base),max(aug)))
ax.set_ylabel('Mean (unresolved automated error + 0.25 × review)')
ax.set_title('2006–2012 held-out counterfactual utility; no model promoted')
ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(out/'figure3_future_costs.png',dpi=170);plt.close(fig)
print([str(p) for p in out.glob('*.png')])
