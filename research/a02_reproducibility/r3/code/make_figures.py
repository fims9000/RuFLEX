"""Reproducible print-friendly A03/A04/A05 figures. Every datapoint is from saved CSV."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).parents[1]
res=ROOT/'results'; out=ROOT/'figures'; out.mkdir(exist_ok=True)
policy=pd.concat([pd.read_csv(res/x/'A03_POLICY_OUTCOMES.csv') for x in ('split101','split202')])
model_order=['decision_tree','sgd_log_loss','random_forest','extra_trees','logistic_regression']
labels=['Decision Tree','SGD Logistic','Random Forest','Extra Trees','Logistic Regression']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.spines.top':False,'axes.spines.right':False})

# Figure A: descriptive cell-level held-out risk contrasts. All 80 independent runs? No;
# splits and datasets are reused, so no inferential standard error is plotted.
p=policy[(policy.budget==.9)&(policy.policy=='combined_fixed')]
fig,ax=plt.subplots(figsize=(5.9,2.6))
rng=np.random.default_rng(30)
for k,(mod,label) in enumerate(zip(model_order,labels)):
    sub=p[p.model_family==mod]
    offsets=rng.uniform(-.16,.16,size=len(sub))
    ax.scatter(100*sub.delta_risk_vs_confidence, np.full(len(sub),k)+offsets,
               facecolors='white',edgecolors='0.22',linewidths=.7,s=19)
    ax.plot(100*sub.delta_risk_vs_confidence.mean(),k,'s',color='black',markersize=5)
ax.axvline(0,color='0.45',linestyle='--',linewidth=.8)
ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis()
ax.set_xlabel('Held-out risk difference, percentage points\n(combined − confidence-only; negative is better)')
ax.grid(axis='x',color='0.88',linewidth=.5)
fig.tight_layout(pad=.8)
fig.savefig(out/'fig3_a03_per_cell_delta.png',dpi=240,bbox_inches='tight');plt.close(fig)

# Figure B: review-budget sensitivity at exact matched coverage
s=policy[policy.policy.isin(['confidence_only','combined_fixed'])].groupby(['budget','policy']).accepted_risk.mean().reset_index()
fig,ax=plt.subplots(figsize=(3.25,2.2))
for name,label,style in [('confidence_only','Confidence-only','--o'),('combined_fixed','Combined','-s')]:
    g=s[s.policy==name].sort_values('budget')
    ax.plot(100*g.budget,100*g.accepted_risk,style,markersize=4,linewidth=1.1,label=label)
ax.set_xlabel('Accepted coverage (%)');ax.set_ylabel('Mean held-out risk (%)')
ax.set_xticks([80,90,95]);ax.grid(alpha=.35)
ax.legend(loc='upper left',fontsize=7,frameon=False);fig.tight_layout(pad=.7)
fig.savefig(out/'fig4_a03_risk_coverage.png',dpi=240,bbox_inches='tight');plt.close(fig)

# Figure C: 5-30 independent audit-model scores; A04 post-hoc on A03 splits
a04=pd.read_csv(res/'a04_budget'/'A04_CHECKPOINTS.csv')
fig,ax=plt.subplots(figsize=(3.25,2.15))
for fam,label,style in [('decision_tree','Decision Tree','-o'),('sgd_log_loss','SGD Logistic','--s')]:
    g=a04[a04.model_family==fam].groupby('n_audit_fits').delta_risk_vs_confidence.mean()
    ax.plot(g.index,100*g.values,style,linewidth=1,markersize=4,label=label)
ax.axhline(0,color='.5',linewidth=.7)
ax.set_xlabel('Number of audit-model fits');ax.set_ylabel('Mean risk difference (pp)')
ax.set_xticks([5,10,20,30]);ax.grid(alpha=.35)
ax.legend(fontsize=7,frameon=False);fig.tight_layout(pad=.7)
fig.savefig(out/'fig5_a04_budget.png',dpi=240,bbox_inches='tight');plt.close(fig)

# Figure D: certification does not ensure correctness
cert=pd.read_csv(res/'a05_certification'/'A05_CELLS.csv').groupby('model_family').agg(n=('n_test','sum'),
 cert=('n_certified','sum'),bad=('certified_wrong','sum')).reindex(model_order)
fig,ax=plt.subplots(figsize=(3.4,2.45))
bar=ax.barh(range(len(cert)),100*cert.cert/cert.n,facecolor='.78',edgecolor='.2',height=.6)
ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis()
ax.set_xlim(0,112);ax.set_xlabel('Certified fixed-reference decisions (%)')
for i,(r,b) in enumerate(zip((100*cert.cert/cert.n).values,cert.bad)):
    ax.text(r+1.1,i,f'{r:.1f}%  ({int(b)} incorrect)',va='center',fontsize=7)
ax.spines['left'].set_visible(False);ax.grid(axis='x',alpha=.3)
fig.tight_layout(pad=.7)
fig.savefig(out/'fig6_a05_certification.png',dpi=240,bbox_inches='tight');plt.close(fig)
print('Figures:',*[str(x) for x in out.glob('*.png')],sep='\n')
