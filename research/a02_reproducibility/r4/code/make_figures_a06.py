"""Deterministic figures generated only from frozen A06 derived result tables."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent.parent
src=ROOT/'results'/'analysis'
out=ROOT/'figures';out.mkdir(exist_ok=True)
d=pd.read_csv(src/'A06_CELL_CONTRASTS.csv')
d=d[d.policy=='combined_fixed'].copy()
models=['logistic_regression','decision_tree','random_forest','sgd_log_loss']
names=['Logistic','Decision tree','Random forest','SGD logistic']
fig, ax = plt.subplots(figsize=(6.2,3.2),dpi=210)
for j,m in enumerate(models):
    x=d[(d.model==m)&(d.evaluation=='batch_exact_secondary')].sort_values('cell')
    y=x.risk_delta_vs_confidence.to_numpy()*100
    off=np.linspace(-.13,.13,len(y))
    ax.scatter(np.full(len(y),j)+off,y,alpha=.68,s=24)
    ax.plot([j-.26,j+.26],[y.mean(),y.mean()],linewidth=2.2)
ax.axhline(0,linestyle='--',linewidth=1.0)
ax.set_xticks(range(4),names)
ax.set_ylabel('Difference in accepted risk (pp)')
ax.set_xlabel('Reference-model family')
ax.set_title('A06: held-out, exact 90% accepted coverage')
ax.grid(axis='y',alpha=.2)
fig.tight_layout()
fig.savefig(out/'fig7_external_batch_delta.png',bbox_inches='tight')
plt.close(fig)

fig,ax=plt.subplots(figsize=(5.2,4.0),dpi=220)
r=d[d.evaluation=='streaming_frozen']
ax.scatter(r.coverage_confidence*100,r.coverage*100,s=35,alpha=.75)
ax.plot([78,98],[78,98],linestyle='--',linewidth=1.2)
ax.axvline(90,linestyle=':',linewidth=.8);ax.axhline(90,linestyle=':',linewidth=.8)
ax.set_xlabel('Confidence-only test coverage (%)')
ax.set_ylabel('Combined rule test coverage (%)')
ax.set_title('A06: validation-frozen streaming thresholds')
ax.grid(alpha=.2)
ax.set_xlim(78,98);ax.set_ylim(78,98)
fig.tight_layout()
fig.savefig(out/'fig8_streaming_coverage_drift.png',bbox_inches='tight')
plt.close(fig)
print('generated',*[p.name for p in out.glob('*.png')])
