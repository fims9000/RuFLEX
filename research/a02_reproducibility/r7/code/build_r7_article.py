"""Build the standalone R7 exploratory research note, not an IEEE submission."""
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent.parent
DOC=ROOT/'article/R7_Group_Respecting_Sequential_Review_Evidence.docx'
DATA=json.loads((ROOT/'results/analysis/R7_DIAGNOSTICS.json').read_text())
SIM=json.loads((ROOT/'results/simulation/R7_SIMULATION_SUMMARY.json').read_text())
FEAS=json.loads((ROOT/'results/analysis/R7_FEASIBILITY.json').read_text())
SCORES=pd.read_csv(ROOT/'results/analysis/R7_POSTHOC_BASELINES.csv')

D=Document();sec=D.sections[0]
sec.page_height=Inches(11);sec.page_width=Inches(8.5)
sec.left_margin=Inches(.94);sec.right_margin=Inches(.94)
sec.top_margin=Inches(.84);sec.bottom_margin=Inches(.76)
sec.header_distance=Inches(.34);sec.footer_distance=Inches(.4)

style=D.styles['Normal'];style.font.name='Aptos';style.font.size=Pt(9.8)
style.font.color.rgb=RGBColor(32,41,51)
style.paragraph_format.space_after=Pt(6)
style.paragraph_format.line_spacing=1.13
for name,size,before,after in [('Title',17,0,9),('Heading 1',12.5,11,5),('Heading 2',10.6,9,4)]:
 s=D.styles[name];s.font.name='Aptos Display' if name!='Heading 2' else 'Aptos'
 s.font.size=Pt(size);s.font.bold=True;s.font.color.rgb=RGBColor(22,59,82)
 s.paragraph_format.space_before=Pt(before);s.paragraph_format.space_after=Pt(after)
 s.paragraph_format.keep_with_next=True
# Remove the Word default Title-style bottom rule for a clean research layout.
title_ppr=D.styles['Title']._element.pPr
title_bdr=title_ppr.find(qn('w:pBdr'))
if title_bdr is not None:title_ppr.remove(title_bdr)
if 'Caption' not in D.styles:
 s=D.styles.add_style('Caption',WD_STYLE_TYPE.PARAGRAPH)
else:s=D.styles['Caption']
s.font.name='Aptos';s.font.size=Pt(8.7);s.font.italic=True;s.font.color.rgb=RGBColor(75,81,88)
s.paragraph_format.space_after=Pt(9)
s.paragraph_format.keep_together=True

footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
fr=footer.add_run('R7  |  Research note  |  4 November 2026  |  ');fr.font.size=Pt(8);fr.font.color.rgb=RGBColor(100,110,120)
pf=OxmlElement('w:fldSimple');pf.set(qn('w:instr'),'PAGE');footer._p.append(pf)

def txt(content='',boldlead=None,style=None):
 p=D.add_paragraph(style=style)
 if boldlead and content.startswith(boldlead):p.add_run(boldlead).bold=True;p.add_run(content[len(boldlead):])
 else:p.add_run(content)
 return p

def subtitle(content):
 p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 r=p.add_run(content);r.font.size=Pt(9.4);r.font.color.rgb=RGBColor(100,110,120)
 p.paragraph_format.space_after=Pt(12)

def section(text):D.add_heading(text,level=1)
def subsection(text):D.add_heading(text,level=2)
def formula(t):
 p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 r=p.add_run(t);r.font.name='Cambria Math';r.font.size=Pt(10.5)
 p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(9)

def shade(cell,color='E9F0F4'):
 tcpr=cell._tc.get_or_add_tcPr();sh=OxmlElement('w:shd');sh.set(qn('w:fill'),color);tcpr.append(sh)

def marg(cell,top=100,start=95,bottom=85,end=95):
 tc=cell._tc;tcpr=tc.get_or_add_tcPr();m=OxmlElement('w:tcMar')
 for s,v in [('top',top),('start',start),('bottom',bottom),('end',end)]:
  z=OxmlElement('w:'+s);z.set(qn('w:w'),str(v));z.set(qn('w:type'),'dxa');m.append(z)
 tcpr.append(m)

def table(headers,rows,widths=None):
 t=D.add_table(rows=1, cols=len(headers));t.style='Table Grid';t.alignment=WD_TABLE_ALIGNMENT.CENTER
 t.autofit=False
 if widths:
  for i,w in enumerate(widths):t.columns[i].width=Inches(w)
 for i,h in enumerate(headers):
  cell=t.rows[0].cells[i];cell.text=str(h);shade(cell)
  for r in cell.paragraphs[0].runs:r.bold=True;r.font.size=Pt(8.2)
  cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;marg(cell)
  if widths:cell.width=Inches(widths[i])
 tblhdr=OxmlElement('w:tblHeader');tblhdr.set(qn('w:val'),'true');t.rows[0]._tr.get_or_add_trPr().append(tblhdr)
 for row in rows:
  c=t.add_row().cells
  for j,val in enumerate(row):
   c[j].text=str(val);marg(c[j]);c[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   for p in c[j].paragraphs:
    p.paragraph_format.space_after=Pt(0)
    for run in p.runs:run.font.size=Pt(8.2)
   if widths:c[j].width=Inches(widths[j])
 D.add_paragraph().paragraph_format.space_after=Pt(1)
 return t

def fig(path,caption,width=6.5):
 p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(2)
 p.paragraph_format.keep_with_next=True
 p.add_run().add_picture(str(path),width=Inches(width))
 p2=D.add_paragraph(caption,style='Caption');p2.alignment=WD_ALIGN_PARAGRAPH.CENTER

D.add_heading('What Counts as Independent Evidence?',level=0)
subtitle('Group-respecting sequential audits for reproducibility-aware selective review  |  R7 research note  |  4 November 2026')

p=D.add_paragraph();p.add_run('Abstract. ').bold=True
p.add_run('Retraining disagreement may improve the ranking of predictions for human review, but a large statistical signal need not be valid when its observations are correlated. We study the paired utility of two frozen review policies through bounded gains and standard betting e-processes. In a zero-mean simulation with 12 independent years and 200 perfectly correlated records per year, naïvely updating an e-process on every record falsely confirmed an advantage in 769 of 1,000 repetitions. Annual aggregation produced no such alarms, although for that particular effect amplitude and horizon its test had insufficient power. A fresh World Bank fertility panel supplied 7,992 country–year observations and 64 model fits. One model showed a descriptive 5.94 percentage-point cost advantage for a reproducibility-conditioned policy in a later period, yet the six-year annual monitor could never reach its registered evidence threshold, even under maximal gain. We disclose this post-freeze feasibility failure, provide stronger exploratory baselines, and distinguish valid sequential monitoring assumptions from assumptions that are merely convenient. The contribution is an auditable failure-mode analysis, not a new betting theorem or deployment guarantee.')

p=D.add_paragraph();p.add_run('Keywords—').bold=True;p.add_run('selective prediction; retraining reproducibility; decision auditing; e-process; pseudoreplication; temporal shift; evidence unit')

section('1. Introduction')
txt('Confidence and cross-run agreement answer different questions. A single model can confidently predict a class that is not reproduced after retraining; conversely, multiple fits can confidently agree on a wrong class. Our earlier A01–R6 experiments found regimes where disagreement provided useful review information, but also conditions where it hurt, and an unobservable shift counterexample that prevents any universal label-free guarantee.')
txt('R7 asks a different question: how much independent evidence is needed before changing an operational review rule? An apparent sample of thousands of country–year observations may contain only a small number of novel time shocks. Sequential hypothesis tests that treat every correlated row as an additional independent or conditionally nonpositive-mean observation can become severely anti-conservative. The distinction between a statistical test being mathematically valid and being powerful enough to trigger is equally consequential.')

section('2. Hypotheses and fixed review decisions')
txt('Let h_ref(x) be a frozen reference prediction with error indicator e(x)=1{h_ref(x) ≠ y}. Let b(x) and a(x) be binary decisions to request review under a supervised confidence-only error-risk ranker and an augmented ranker using retraining disagreement and probability dispersion. The auxiliary models only audit the reference prediction; they do not vote on its class.')
txt('With a review-cost proxy λ=0.25 (one reviewed case costs one quarter of an unresolved automated error), the paired gain at case x is:')
formula('X(x) = [a(x) − b(x)] [e(x) − λ],    −1 ≤ X(x) ≤ 1.')
txt('Positive expected gain means lower joint cost under the augmented policy. This identity localizes any advantage to cases where the policies disagree. It is exact accounting, not statistical significance.')
txt('H7a: In a population with independent years but perfectly dependent country records within a year, sequential inference at the country-row level can falsely authorize a policy more often than the nominal 5% level; the annual aggregate is the appropriate synthetic observation unit.')
txt('H7b: A frozen annual-unit monitor on new time periods may provide evidence for activating the augmented policy. Feasibility is itself tested, and a protocol incapable of crossing the threshold cannot be credited for a cautious decision.')
txt('H7c: Later held-out costs and stronger confidence/disagreement-only controls must be reported even when they contradict a claim that the augmented ranker dominates.')

section('3. Sequential evidence and the unit of observation')
txt('For ordered group-level gains X_t in [−1,1], choose five fixed stakes η ∈ {0.03, 0.07, 0.15, 0.30, 0.60}. The average betting capital is:')
formula('K_t = (1/5) Ση ∏s=1…t (1 + η X_s).')
txt('Proposition 1 (standard supermartingale argument). If each frozen review decision is predictable before its outcome and the null E[X_t | F_(t−1)] ≤ 0 holds at every step, then each product and their mixture are nonnegative supermartingales with initial value one. Consequently P(sup_t K_t ≥ 1/α) ≤ α for any α in (0,1).')
txt('Proof. Since 0<η<1 and X_t≥−1, every factor is nonnegative. Its conditional expectation is 1 + η E[X_t|F_(t−1)]≤1. Multiplication by the previous nonnegative capital preserves the supermartingale property; finite mixtures preserve it; Ville’s inequality gives the crossing bound. This is a known testing-by-betting result [1–2], not a new theorem.')

txt('Counterexample. Suppose year t has a fair common shock S_t ∈ {−0.5,+0.5}; every one of its 200 country rows has gain X_(t,j)=S_t, and shocks are independent across years. Annual gains have zero conditional mean. However, after the first positive row, subsequent within-year gains are known to be positive, invalidating the rowwise conditional-mean null. When the first year is positive, the component with η=0.60 alone yields mixture wealth at least (1.3)^200/5, above 20. Therefore a nominal rowwise 5% positive-benefit test has false-alarm probability at least 50% in this synthetic null, even before looking at later years.')
txt('The country panel is not claimed to satisfy independent-year sampling. Group aggregation is a better representation of common shocks, but does not establish the conditional-mean null on historical data or guarantee benefit on a future unseen period.')

section('4. Frozen new-data experiment')
txt('We use the fertility-rate panel bundled with statsmodels, sourced from World Bank World Development Indicators [3]. After filtering to ISO3-coded entities and requiring complete historical lags and next-year labels, the data contain 7,992 country–year instances. The binary label is one if the next-year fertility rate decreases by at least 0.05 births per woman. Features include the current level, lags 1, 2, 3 and 5, historical differences, an earlier three-year average and a calendar-year term. Target values are never interpolated or used in the feature vector.')
table(['Stage','Calendar years (input t)','Number of country–years'],[
 ['Reference model fitting','1965–1984','3,771'],['Supervised risk fitting','1986–1993','1,519'],['Threshold calibration, labels unused','1995–1997','576'],['Labelled monitoring','1999–2004','1,150'],['Future counterfactual evaluation','2006–2012','976']],[2.55,1.9,2.15])
txt('The four frozen model families are Logistic Regression, a randomized-split Decision Tree, Random Forest and Extra Trees. Per family, seed 71000 defines the operational reference and 15 different seeds define auditing-only retrainings: 64 model fits in all. Each of two supervised logistic error-risk models fits only on the risk-fitting stage. Thresholds for approximately 20% review are fixed from the separate calibration scores without their labels. Ties are resolved with a fixed hash. The primary monitoring unit is the mean paired gain across all available countries in one year.')
txt('The protocol SHA-256 fb047cc115129cf66b00d9ddd9206463d88cd9580beaea8ba1c7fd47932edbac was recorded in GitHub before these fits. A year-column indexing error was corrected before any training and documented separately. This local freeze is not external preregistration.')

section('5. Results: controlled common-shock null')
fig(ROOT/'figures/figure1_correlated_null.png','Figure 1. Frequency of false positive-benefit alarms under a true zero-mean *yearwise* null. The rowwise procedure violates its conditional-mean assumption. The yearwise procedure is valid in this constructed world but also underpowered for ±0.5 shocks over 12 groups.',width=6.25)
txt('Across 1,000 repetitions, the invalid rowwise analysis triggered in 769 (76.9%; Wilson 95% descriptive range 74.2%–79.4%). Annual aggregation triggered in 0/1,000. The latter is not a power success: with all 12 annual gains equal to +0.5, the chosen mixture reaches at most 6.75, below the alarm threshold 20. These statistics illustrate the interaction between type-I validity and achievable detection, not a realistic distribution of deployments.')

section('6. Results: new country–year panel')
rows=[]
for m in ['logistic_regression','decision_tree','random_forest','extra_trees']:
 r=next(z for z in DATA['rows'] if z['model']==m)
 rows.append([m.replace('_',' ').title(),f"{r['future_baseline_cost']:.4f}",f"{r['future_augmented_cost']:.4f}",f"{100*r['future_gain']:+.2f}",f"{r['group_respecting_max_e']:.3f}"])
table(['Family','Baseline cost','Augmented cost','Δ gain (pp)','Annual max e'],rows,[2.13,1.10,1.18,1.06,1.13])
txt('On held-out 2006–2012 observations, augmented and baseline costs differ; for Decision Tree the observed paired reduction is 0.0594 per case, or +5.94 percentage points. Extra Trees is slightly worse. These are counterfactual policy evaluations on later historical observations, not realized human review outcomes, and no policy was promoted by the original gate.')
fig(ROOT/'figures/figure3_future_costs.png','Figure 2. Frozen policy costs in the held-out country–year period. The review-cost multiplier of 0.25 is a hypothetical accounting proxy; the augmented decisions were evaluated counterfactually.',width=6.1)
subsection('6.1. A fatal power-feasibility finding')
txt('The frozen monitor has exactly six annual observations. With |X_t|≤1, K_t is increasing in each X_t, so the maximum conceivable capital is attained by setting all six gains equal to +1. Under the declared stake grid this maximum is only 5.3224, below 20. Consequently zero promotions is a mathematical certainty: the test could never authorize a policy, irrespective of empirical performance. This was discovered after the protocol freeze and cannot be concealed as a successful conservative deployment decision.')
txt('Even a hypothetical constant annual gain of +0.05 would require 151 annual groups to reach 20 with these stakes. A useful monitoring design must therefore perform an a priori feasibility and plausible-effect power audit at the number of independent groups actually available.')
fig(ROOT/'figures/figure2_evidence_granularity.png','Figure 3. Maximum mixture e-values on the same monitoring records. Rowwise values are numerically dramatic for Decision Tree but cannot be interpreted as valid evidence under unspecified within-year dependence. Year-level values remain close to one.',width=6.0)

section('7. Stronger exploratory baselines and negative evidence')
txt('Following inspection of the primary outcomes, we added three label-blind score controls: raw confidence, disagreement alone and a fixed confidence-plus-disagreement heuristic. The rules still use thresholds determined on the calibration stage only. Since these controls were chosen post hoc, the comparisons below are exploratory and should not be treated as prespecified discovery.')
rows=[]
for m in ['logistic_regression','decision_tree','random_forest','extra_trees']:
 q=SCORES[(SCORES.model==m)&(SCORES.stage=='frozen_future_evaluation')].set_index('policy').joint_cost
 rows.append([m.replace('_',' ').title(),f"{q['raw_confidence']:.4f}",f"{q['disagreement_only']:.4f}",f"{q['supervised_confidence']:.4f}",f"{q['supervised_conditional']:.4f}"])
table(['Family','Raw confidence','Disagreement only','Learned confidence','Learned augmented'],rows,[1.80,1.17,1.18,1.28,1.17])
txt('A simpler disagreement-only score slightly outperforms the learned augmented ranker for Decision Tree, while raw confidence is better for Logistic Regression and Random Forest. Adding retraining features is therefore not universally beneficial. The family-specific effects should motivate an a priori decision rule for whether to audit at all—not a post-hoc search for a winning score.')

section('8. Interpretation and limitations')
txt('The central empirical observation is not that annual aggregation reduced the alarm rate to zero. That result was entangled with extremely low power. The central methodological lesson is that a nominal e-process can become meaningless if its increments are correlated in a way that violates the claimed conditional-mean null, and that the correct unit may leave too little information for useful certification. More model trainings cannot resolve a shortage of independent units of target feedback.')
txt('The panel contains countries and territories with shared global time trends, repeated observations and potentially estimated/interpolated official source values. ISO3 membership is not evidence of independence. The model families and years overlap. A yearwise betting guarantee requires the actual conditional-mean null to hold; historical calendar grouping alone does not establish it. No real reviewer accuracy or cost was measured. No valid statistical claim about new future institutions is made from the small set of annual groups. Results are exploratory, and the local protocol freeze occurred after prior R6 literature and data exploration.')
txt('Known mathematical ingredients include selective risk ranking [4], betting supermartingales and time-uniform tests [1–2], as well as paired policy-loss decomposition. This note does not claim novelty for any such general identity. The research contribution under development is an operational, falsifiable audit of the *evidential unit* and a protocol feasibility gate that can reject scientifically uninformative monitoring designs before a costly experiment.')

section('9. Requirements for a confirmatory successor')
for text in [
 'Identify independently sampled deployment domains or defend explicit conditional-mean assumptions and dependence structure; do not count numerous correlated observations as separate replications.',
 'Freeze both review policies before collecting target labels, predeclare the review-cost or capacity objective, and evaluate straightforward confidence-only and disagreement-only baselines.',
 'Run a pre-execution feasibility/power audit at plausible group-level gain magnitudes. An e-value threshold that cannot be crossed is an invalid way to assess practical usefulness.',
 'Use multiple genuinely independent new domains and blocks; separately report predictive correctness, reproducibility, review workload, paired utility, and monitoring false-alarm performance.',
 'If year/group conditional expectations can change unpredictably, do not claim safety on an unseen future period based only on previous labelled monitoring windows.'
]:
 p=D.add_paragraph(style='List Bullet');p.add_run(text)

section('References')
for t in [
 '[1] I. Waudby-Smith and A. Ramdas, “Estimating means of bounded random variables by betting,” Journal of the Royal Statistical Society: Series B, 2023. DOI: 10.1093/jrsssb/qkad009.',
 '[2] A. Timans, R. Verma, E. Nalisnick, and C. A. Naesseth, “On Continuous Monitoring of Risk Violations under Unknown Shift,” Proceedings of UAI, PMLR 286, 2025, pp. 4204–4226.',
 '[3] World Bank, “Fertility rate, total (births per woman),” World Development Indicators, historical 1960–2013 panel distributed with statsmodels, https://www.statsmodels.org/stable/datasets/generated/fertility.html.',
 '[4] V. Franc, D. Prusa, and V. Voracek, “Optimal Strategies for Reject Option Classifiers,” JMLR 24, 2023, https://www.jmlr.org/papers/v24/21-0048.html.'
]:
 p=D.add_paragraph(t);p.paragraph_format.space_after=Pt(3)
 for run in p.runs:run.font.size=Pt(8.5)

DOC.parent.mkdir(parents=True,exist_ok=True)
D.save(DOC)
print('CREATED',DOC,'paragraphs',len(D.paragraphs),'tables',len(D.tables))
