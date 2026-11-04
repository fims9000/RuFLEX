"""Figures for R6, generated only from persisted CSVs."""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent
RES=ROOT/'results'
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)

sim=pd.read_csv(RES/'simulation'/'R6_SIMULATION_SUMMARY.csv')
fig,ax=plt.subplots(figsize=(7.7,4.25))
for label,name in [('Stable conditional risk','actionable'),('Invisible conditional-risk reversal','invisible_reversal')]:
    d=sim[sim.scenario==name].sort_values('cert_n')
    ax.plot(d.cert_n,d.mean_realized_target_gain*100,marker='o',label=label)
ax.set_xscale('log');ax.set_xticks([100,400,1600,6400]);ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.axhline(0,color='0.5',linewidth=.8)
ax.set_xlabel('Independent labeled certification cases')
ax.set_ylabel('Expected target gain of certification-gated rule (pp)')
ax.set_title('More source evidence can increase target harm after invisible shift')
ax.legend(fontsize=9);ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(OUT/'figure1_hidden_shift_more_data.png',dpi=170);plt.close(fig)

cells=pd.read_csv(RES/'R6_POLICY_SWITCH_CELLS.csv')
d=cells[(cells.gain_per_case>0)&(cells.epsilon_to_erase_positive_gain.notna())].copy()
fig,ax=plt.subplots(figsize=(7.7,4.5))
for mode,g in d.groupby('mode'):
    ax.scatter(g.switch_fraction*100,g.epsilon_to_erase_positive_gain*100,alpha=.75,label=f'{mode} (n={len(g)})')
ax.axhline(5,linestyle='--',linewidth=.8,color='0.4')
ax.set_xlabel('Cases where routing decisions differ (%)')
ax.set_ylabel('Worst-case conditional-risk drift needed to erase gain (pp)')
ax.set_yscale('log')
ax.set_title('Empirical wins have heterogeneous conditional-shift fragility')
ax.grid(alpha=.2);ax.legend(fontsize=9);fig.tight_layout()
fig.savefig(OUT/'figure2_switch_fragility.png',dpi=170);plt.close(fig)

real=pd.read_csv(RES/'new_temporal'/'R6_TEMPORAL_RESULTS.csv')
fig,ax=plt.subplots(figsize=(8,4.5))
real['label']=real['dataset'].map({'sunspots_next_year_rise':'Sunspots','us_macro_next_quarter_unemployment_rise':'US macro'})+' / '+real['model'].map({'logistic_regression':'LogReg','decision_tree':'Tree','random_forest':'Forest','sgd_log_loss':'SGD'})
ax.barh(np.arange(len(real)),real.aug_gain*100)
ax.set_yticks(np.arange(len(real)),real['label'])
ax.axvline(0,color='0.5',linewidth=.8)
ax.set_xlabel('Ungated augmented minus baseline savings at lambda=0.25 (pp)')
ax.set_title('New time-blocked studies: gains and losses; guard enabled in 0/8')
ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
fig.tight_layout();fig.savefig(OUT/'figure3_new_real_time_series.png',dpi=170);plt.close(fig)
print('Saved',*[p.name for p in sorted(OUT.glob('figure*.png'))])
