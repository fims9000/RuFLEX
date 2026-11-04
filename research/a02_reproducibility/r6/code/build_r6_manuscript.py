"""Build a self-contained R6 full research manuscript from verified R6 results."""
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
RES=ROOT/'results'
DOC=Document()
sec=DOC.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.82);sec.bottom_margin=Inches(.78)
sec.left_margin=Inches(.92);sec.right_margin=Inches(.92)
sec.header_distance=Inches(.35);sec.footer_distance=Inches(.45)

styles=DOC.styles
title_style=styles.add_style('R6 Paper Title', WD_STYLE_TYPE.PARAGRAPH)
title_style.font.name='Tinos';title_style.font.size=Pt(17);title_style.font.bold=True
title_style.font.color.rgb=RGBColor(15,32,51)
title_style.paragraph_format.space_after=Pt(10)
title_style.paragraph_format.keep_with_next=True
base=styles['Normal'];base.font.name='Tinos';base.font.size=Pt(10.7);base.font.color.rgb=RGBColor(27,34,43)
base.paragraph_format.space_after=Pt(5)
base.paragraph_format.line_spacing=1.12
for name,size,bold,before,after in [('Title',17,True,0,10),('Heading 1',12.6,True,12,5),('Heading 2',11.1,True,9,3)]:
 st=styles[name];st.font.name='Tinos';st.font.size=Pt(size);st.font.bold=bold
 st.font.color.rgb=RGBColor(15,32,51)
 st.paragraph_format.space_before=Pt(before);st.paragraph_format.space_after=Pt(after)
 st.paragraph_format.keep_with_next=True

footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
run=footer.add_run('Research manuscript  •  R6  |  ');run.font.name='Tinos';run.font.size=Pt(8);run.font.color.rgb=RGBColor(95,101,110)
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)


def para(text='',boldlead=None,style=None):
 text=text.replace('*','') # strip literal Markdown emphasis in prose
 p=DOC.add_paragraph(style=style)
 if boldlead and text.startswith(boldlead):p.add_run(boldlead).bold=True;p.add_run(text[len(boldlead):])
 else:p.add_run(text)
 return p


def head(text,level=1):
 p=DOC.add_heading(text,level)
 if text.startswith('11. New chronological'):
  p.paragraph_format.page_break_before=True
 return p

def mathline(text):
 p=DOC.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 p.paragraph_format.space_before=Pt(7);p.paragraph_format.space_after=Pt(7)
 r=p.add_run(text);r.font.name='Cambria Math';r.font.size=Pt(11)
 return p


def tbl(headers,rows,widths=None):
 t=DOC.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER
 t.style='Table Grid'
 for i,h in enumerate(headers):
  c=t.rows[0].cells[i];c.text=str(h)
  shading=OxmlElement('w:shd');shading.set(qn('w:fill'),'E7EDF3');c._tc.get_or_add_tcPr().append(shading)
 for row in rows:
  cells=t.add_row().cells
  for i,v in enumerate(row):cells[i].text=str(v)
 for row in t.rows:
  row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
  for c in row.cells:
   c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   for p in c.paragraphs:
    p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(2)
    for r in p.runs:r.font.size=Pt(8.5);r.font.name='Tinos'
 for c in t.rows[0].cells:
  for p in c.paragraphs:
   for r in p.runs:r.bold=True
 t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 if widths:
  for row in t.rows:
   for c,w in zip(row.cells,widths):c.width=Inches(w)
 DOC.add_paragraph().paragraph_format.space_after=Pt(1)
 return t


def fig(path,caption,width=6.4):
 p=DOC.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 p.paragraph_format.space_before=Pt(5);p.paragraph_format.space_after=Pt(4)
 p.add_run().add_picture(str(path),width=Inches(width))
 c=DOC.add_paragraph();c.alignment=WD_ALIGN_PARAGRAPH.CENTER
 c.paragraph_format.space_after=Pt(9)
 r=c.add_run(caption);r.font.size=Pt(9);r.italic=True


p=DOC.add_paragraph(style='R6 Paper Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.add_run('The Hidden-Shift Limit of Reproducibility-Aware Review: A Policy-Switch Analysis')
p=DOC.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.add_run('Scientific research revision R6  |  4 November 2026').italic=True

head('Abstract',1)
para('Repeated model training can reveal prediction churn, but a stable prediction need not be correct, and instability need not justify paying for review. We study the incremental decision value of retraining disagreement with a fixed reference predictor and a confidence-only review baseline. We derive an exact switch-set decomposition of cost difference and a sharp sensitivity bound under conditional error-risk shift. A constructive two-world example has identical observable confidence and disagreement distributions, yet reverses a policy advantage from +5.0 to −12.5 percentage points after an unobservable label-mechanism change. Independent source certification becomes more likely to activate the harmful policy as the labeled calibration sample grows. A retrospective audit of 40 previously evaluated model/dataset cells finds that policies disagree on only 4.44% of streaming cases on average. On two new chronological tasks we perform 136 actual model fits with five disjoint train-to-test stages; observed improvements coexist with failures and the conservative certification rule activates in zero of eight cells. These results delimit what reproducibility auditing can and cannot establish. Theoretical bounds assume explicitly limited conditional-risk drift; they are not deployment guarantees when the bound is unknown.')
para('Keywords: prediction reproducibility; selective classification; abstention; conditional shift; policy evaluation; finite-sample certification; uncertainty.')

head('1. Introduction')
para('A classifier may be highly confident but sensitive to retraining, while another may reproduce the same incorrect decision across every observed run. This distinction motivated the earlier A01–R5 studies in RuFLEX. Those experiments showed that confidence and agreement capture different properties, but their measured value for review was heterogeneous: some model families improved, others tied, and some deteriorated. Expanding a benchmark table is insufficient to resolve this tension.')
para('The deeper question is whether the incremental *information* supplied by repeated training remains useful once the system must choose an action at a stated cost. If a baseline reviews a case and an augmented method releases it, the consequences depend on whether that case is wrong; if both policies take the same action, their cost is identical regardless of confidence or disagreement. This observation directs attention away from a global correlation coefficient and toward the small subset where the policies genuinely differ.')
para('We therefore analyze three distinct objects: a frozen operational prediction, an auxiliary retraining signal, and the routing decision. We do not treat the average of retrainings as the deployed predictor. We ask (i) where observed policy gains arise, (ii) what additional conditions are required to transfer their sign to a new population, and (iii) how much independent labeled evidence is required before a new routing rule should replace a baseline.')
para('The practical objective is intentionally asymmetric: a system is allowed to decline an unsupported improvement. This is not proof that the baseline is safe; it is a disciplined rule for making incremental changes when evidence about benefit is insufficient.')

head('2. Relation to established work')
para('Optimal reject-option classification and cost-aware Bayes selection are classical: Franc, Prusa, and Voracek [1] formalize cost, coverage, and optimal uncertainty scores. Black, Leino, and Fredrikson [2] address consistent decisions using selective ensembles, whereas our auxiliary fits do not vote on the operational class. Liang, Peng, and Sun [3] study selective classification under distribution shift. Distributionally robust policy learning under concept drift has also been investigated [4]. A more recent cost-aware conformal deferral study [5] illustrates how calibration and reviewer costs enter high-stakes selective prediction.')
para('We do not claim a new reject-option theorem, a new concentration inequality, or the first treatment of shift. The contribution investigated here is narrower: exact accounting for where an existing policy changes, a tight conditional-risk transport sensitivity for these changes, a transparent independent evidence rule, and reproducible positive and negative evaluations with a fixed reference model. A priority claim would require a broader literature review.')

head('3. Experimental decision and notation')
para('Fix a reference prediction h_ref(x), a ground-truth label y, and the error indicator e=1{h_ref(x)≠y}. Let z include all features visible to a routing policy: the reference confidence and predicted class, optional disagreement and score dispersion across auxiliary retrainings, and the deterministic tie-breaking variable where relevant. The baseline and augmented review indicators b(z),a(z) equal one for REVIEW and zero for ACCEPT. The assumption that a reviewed case has accounting cost λ is a surrogate; no human-review accuracy or real monetary loss was measured.')
mathline('ℓ(g) = e(1 − g) + λg,   λ ∈ [0, 1]')
para('A positive gain G means the augmented rule lowers expected total cost. All following policy bounds concern a fixed reference predictor; improving the predictor itself is a separate research problem.')

head('4. Policy-switch locality')
para('Proposition 1 (exact accounting). The paired gain of switching from b to a is')
mathline('G = L(b) − L(a) = E[(a − b)(e − λ)].')
para('Define S+={a=1,b=0} (newly reviewed), S−={a=0,b=1} (released from review), their probabilities q+,q−, and their conditional error rates r+,r−. The same quantity is')
mathline('G = q+ (r+ − λ) − q− (r− − λ).')
para('Proof. Expand ℓ(b)−ℓ(a) and partition the sample space into S+, S−, and a=b. The last part is zero pointwise. With exactly matched review counts, q+=q− and the review-cost term cancels. This is a basic identity, but it dictates what a scientifically informative comparison must report.')
para('Implication. Global disagreement–error correlation is neither necessary nor sufficient for review benefit. The useful signal is whether the two policies move *high-error* objects into review without releasing a comparable number of high-error objects, after accounting for λ.')

head('5. Invisible label shift: an identifiability limit')
para('Proposition 2. Without restrictions on the conditional error law P(e=1|z), the observable distribution P(z) does not identify the sign of policy gain. Proof: hold P(z), the fixed reference class, and both routing rules constant while changing only the conditional distribution of y given z. Both worlds produce identical distributions of confidence and retraining disagreement, but their gains can differ arbitrarily within the allowable loss range.')
para('Explicit example. Consider four equally likely observable groups (high or low confidence, no or high disagreement). The baseline reviews both low-confidence groups. The augmented rule reviews only low-confidence cases with high disagreement, releasing the other low-confidence group. In the source, conditional error risks by confidence and disagreement are [[0.05,0.05],[0.05,0.75]]. In the target, they are [[0.05,0.05],[0.75,0.05]]. At λ=0.25, the source gain is +0.05 while the target gain is −0.125, although the unlabelled feature law is identical.')
para('The case is not an assertion that actual model-disagreement mechanisms flip in this particular way. It is a rigorous counterexample to any unconditional safety guarantee based *only* on the observable model outputs. Monitoring confidence and disagreement marginals cannot reveal a shift that exists solely in their relationship to label errors.')

head('6. A tight sensitivity condition')
para('Proposition 3 (conditional-risk transport). Let P be a labeled source population and Q an intended target population, with common routing support. Assume |r_Q(z)−r_P(z)|≤ε uniformly, where r(z)=P(e=1|z), and both review rules are frozen. Define the gain transported using the source conditional risk and the target observable feature law:')
mathline('G(P→Q) = E[ (a(z)−b(z)) (rP(z)−λ) | z∼Q ].')
mathline('|GQ − G(P→Q)| ≤ ε ρQ,  where ρQ = Q(a≠b).')
para('Proof. Subtract the expectations and bound their absolute difference by E_Q[|a−b| |r_Q−r_P|]. Because |a−b| is the switch-set indicator, the right-hand side equals at most ερ_Q. If the source risk estimate has an independently justified uniform pointwise error η, the radius becomes (ε+η)ρ_Q. A positive transported estimate establishes target benefit only when it exceeds this radius.')
para('The bound is sharp in the constructed example: ε=0.70, ρ_Q=0.25, and ερ_Q=0.175. The source gain +0.050 declines by exactly 0.175 to −0.125. Crucially, ε is an assumption requiring labeled or external knowledge; it cannot be derived from unchanged unlabelled features.')

head('7. Conservative activation from separate labeled data')
para('For policies fixed independently of certification data, define q±=P(S±) and r±=P(e=1|S±). On a new IID labeled certification set, estimate these four probabilities and construct four exact two-sided Clopper–Pearson intervals at confidence 1−α/4. By the union bound, all four intervals jointly cover with probability at least 1−α. The lower corner of the expression q+(r+−λ)−q−(r−−λ) is therefore a conservative lower confidence bound on incremental value. If a switch set contains no observations, its error rate is treated as unknown in [0,1].')
para('The operational activation rule is intentionally simple: enable the augmented review rule only if the independent lower bound is strictly above zero; otherwise retain the baseline. The certificate concerns a *relative* cost improvement under IID distributional stability. On chronological data, exchangeability may fail and the same calculated number is only a diagnostic; we never describe it as an unconditional time-series safety certificate.')

head('8. Study design and reproducibility')
para('We use three deliberately separated evidence channels. Historical A06 and R5 case-level predictions are reanalyzed without refitting models, and are explicitly post-hoc because their labels were previously inspected. A controlled simulation evaluates five known conditional-error worlds at four labeled certification sample sizes, 200 repetitions each (4,000 episodes), with fixed seed 20261104. Finally, we freeze a protocol before studying two previously unused historical time-series tasks. The source, risk, threshold, certification and final-test partitions are chronologically disjoint, separated by gaps.')
para('The two new tasks are (i) whether next-year sunspot activity exceeds the current year, using only current and past activity and known year; and (ii) whether next-quarter U.S. unemployment rises, using only current and past macroeconomic variables [6]. Logistic regression, decision tree, random forest and SGD log-loss share fixed parameters per family, one reference fit and 16 auxiliary fits each. This yields eight correlated cells and 136 actual model fits. An L2 logistic error-risk model trained on a separate label subset provides an equally supervised confidence-only baseline and an augmented model with disagreement and probability dispersion. Review thresholds are fitted only on a later, *unlabelled* subset; a further labeled certification subset is reserved for the activation test. The final chronological block is untouched by policy selection.')
para('The original A01 findings are not overwritten. There is no retuning to reverse unfavorable signs and no pooling of repeated model families as if they were independent institutions. All raw per-case evidence, protocol SHA-256 and replay checks are included in the companion research package.')

head('9. Results: case-level mechanism and practical trade-offs')
para('Across the historical 40 model/dataset/fold cells, the augmented and confidence policies disagree on an average of 4.44% of cases in stream mode and 4.63% in exact-budget batch mode. The apparent gains are concentrated on a small switched subset; five positive streaming cells and nine positive batch cells could lose their measured improvement after a single adverse switched-case error change. These observations motivate stress-testing the small decision-changing population rather than collecting more indiscriminate retrainings.')

hist=pd.read_csv(RES/'R6_COST_FRONTIER_SUMMARY.csv')
tbl(['Study / mode','Cells','Aug dominates','Base dominates','Identical','Trade-off'],
 [[f"{r.study} / {r['mode']}",r['cells'],r['AUGMENTED_PARETO_DOMINATES'],r['BASELINE_PARETO_DOMINATES'],r['IDENTICAL_COST'],r['COST_DEPENDENT_TRADEOFF']] for _,r in hist.iterrows()],
 [1.5,.6,1,1,1,1])
para('Table 1. Cost frontier among fixed policies. In streaming A06, only 5/32 cells reduce both errors and review workload, while 18/32 have an explicit trade-off. Cost-dependent cells cannot be called universally better without a defensible λ. The exact batch results are a ranking diagnostic, not a deployable single-case quota guarantee.')
fig(ROOT/'figures'/'figure2_switch_fragility.png','Figure 1. Break-even worst-case conditional-error shift among historical positive gains; this is a sensitivity threshold, not measured target drift.',6.35)

head('10. Results: certification can become confidently wrong')
para('The controlled environments isolate the difference between *sampling uncertainty* and *distributional validity*. The source actionable world has true gain +5.0 percentage points, while the invisible-reversal target has −12.5 points. Their observable model outputs have identical distributions. As source certification grows from 100 to 400 labeled cases, the augmented policy is activated in 8.0% to 100% of 200 repeated invisible-reversal simulations. Thus more source evidence can increase target harm, rather than prevent it, when the unobserved label mechanism changes.')

sim=pd.read_csv(RES/'simulation'/'R6_SIMULATION_SUMMARY.csv')
subset=sim[sim.scenario.isin(['actionable','invisible_reversal','neutral','wrong_signal']) & sim.cert_n.isin([100,400,1600])]
tbl(['World','N cert','True source gain','True target gain','Activation rate'],
 [[r.scenario,int(r.cert_n),f'{100*r.source_oracle_gain:+.2f} pp',f'{100*r.target_oracle_gain:+.2f} pp',f'{100*r.certification_rate:.1f}%'] for _,r in subset.iterrows()],
 [1.45,.66,1.35,1.35,1.1])
para('Table 2. A total of 200 replications per cell; values are empirical frequencies for explicit synthetic Bernoulli populations, not results of training an actual retraining ensemble.')
fig(ROOT/'figures'/'figure1_hidden_shift_more_data.png','Figure 2. Expected target gain of a rule activated on independent source labels. Stronger source evidence is harmful if target conditional-error risks reverse invisibly.',6.35)

head('11. New chronological challenge: honest negative outcomes')
real=pd.read_csv(RES/'new_temporal'/'R6_TEMPORAL_RESULTS.csv')
rows=[]
for _,r in real.iterrows():
 group='Sunspots' if r.dataset.startswith('sunspots') else 'U.S. macro'
 rows.append([group,r.model.replace('_',' '),int(r.test_n),f'{r.base_cost:.3f}',f'{r.aug_cost:.3f}',f'{100*r.aug_gain:+.2f} pp','No'])
tbl(['Dataset','Reference family','N final','Base cost','Aug cost','Gain','Certify?'],rows,[.94,1.32,.65,.81,.81,.94,.7])
para('Table 3. Predeclared historical time-blocked test, λ=0.25. Reference and audit models are trained separately; 136 new fits in total. The augmented score improved in three of eight cells, deteriorated in two and tied in three. Independent switch-set certification activated in zero of eight. There are just 47 heldout annual cases per family in the solar task and 31 heldout quarterly cases per family in the macro task. The result does not imply that augmented review never works; it shows that a small, drift-prone calibration sample is insufficient to substantiate its upgrade.')
fig(ROOT/'figures'/'figure3_new_real_time_series.png','Figure 3. Heldout cost improvement of the unguarded augmented score on the two new time-series tasks. The conservative activation rule retained baseline throughout.',6.35)
para('Independent verification reconstructed all fixed thresholds and hash-resolved ties, 192 labeled certification decisions and 312 heldout per-case decisions; the five core result CSVs were byte-identical across two complete 136-fit executions. Simulation sources and outputs are recorded by protocol and SHA-256 hashes. There is no direct human-review evaluation.')

head('12. Interpretation, limitations and decisions')
para('Three conclusions withstand these checks. First, disagreement is an *audit observation*, not a guarantee of risk or truth: perfectly stable predictions can still be wrong, as also observed in R5. Second, policy value is switch-local: averaging disagreement statistics across all predictions dilutes the small subset where an intervention changes. Third, a finite-sample source certificate cannot address a conditional-label shift that is invisible to model outputs; a credible deployment claim requires externally justified restrictions on such shift or new labeled target observations.')
para('Our derived transport radius is deliberately conditional. Without a numerical, defensible epsilon it is not an operational pass/fail guarantee. The independent certification lower bound assumes IID cases and fixed policies, while time-series dependence and drifting error laws violate those assumptions. All 32 A06 cells derive from four reused survey datasets and two resplits; the eight R5 cells share a single CO₂ station. The two new real temporal tasks use historical, finite datasets rather than prospective multi-institution deployments, and small test samples permit large random variation. Review cost λ is hypothetical, and we assume that review removes the automated error without measuring residual human error. None of the experimental counts justifies dataset-population statistical significance.')
para('For practice, a defensible review policy should (i) keep the reference predictor fixed, (ii) separately audit the cases changed by the candidate rule, (iii) preserve both false negatives and review workload in the objective, (iv) demand independent labeled evidence for incremental gain, and (v) monitor conditional error drift through appropriately delayed labels rather than relying on unchanged confidence or disagreement. Until those conditions are met, the transparent outcome is a failed upgrade, not a stronger claim.')

head('13. What would constitute a strong independent confirmation?')
para('An externally registered study should freeze the model family, primary review-cost ratio, sample-size calculation, stopping criteria and a single primary effect *before* recruiting new institutions. A suitable multi-site panel should provide disjoint source sites and unseen target sites, plus longitudinal labels available after the prediction horizon. Error-risk fitting, threshold calibration, candidate certification and final evaluation need separate organizational or time units. Inference should use institutions or blocks as units, not model seeds or overlapping splits. Site-level hidden label shifts should be reported even when every unlabelled monitoring statistic is stable.')
para('An important failure criterion is that the measured lower confidence bound on the gain is nonpositive, or that any defensible upper bound on conditional-risk drift exceeds the gain-to-switch ratio. This is not an engineering failure: it states exactly what evidence would be needed before replacing the baseline. The key research extension is to estimate those drift bounds from time-lagged labels without retroactively tuning the review policy.')

head('References')
refs=[
 '[1] V. Franc, D. Prusa, V. Voracek. Optimal Strategies for Reject Option Classifiers. Journal of Machine Learning Research 24, 1–49, 2023. https://www.jmlr.org/papers/v24/21-0048.html',
 '[2] E. Black, K. Leino, M. Fredrikson. Selective Ensembles for Consistent Predictions. 2022. https://arxiv.org/abs/2111.08230',
 '[3] H. Liang, L. Peng, J. Sun. Selective Classification Under Distribution Shifts. Transactions on Machine Learning Research, 2024. https://arxiv.org/abs/2405.05160',
 '[4] J. Wang, Z. Ren, R. Zhan, Z. Zhou. Distributionally Robust Policy Learning under Concept Drifts. ICML, PMLR 267, 2025. https://proceedings.mlr.press/v267/wang25cm.html',
 '[5] H. Kwon, D.-J. Kim. Conformal Selective Prediction with Cost Aware Deferral for Safe Clinical Triage under Distribution Shift. Scientific Reports 16, 10016, 2026. https://doi.org/10.1038/s41598-026-40637-w',
 '[6] Statsmodels developers. Datasets: yearly Sunspots (1700–2008), U.S. Macroeconomic Data (1959Q1–2009Q3), statsmodels 0.14.6. https://www.statsmodels.org/stable/datasets/index.html',
 '[7] A01–R5 historical reproducibility experiments, RuFLEX research repository. https://github.com/fims9000/RuFLEX/tree/research/r5-conditional-decision-value/research/a02_reproducibility',
]
for r in refs:
 p=DOC.add_paragraph();p.paragraph_format.space_after=Pt(3)
 rr=p.add_run(r);rr.font.size=Pt(9)

out=ROOT/'The_Hidden_Shift_Limit_of_Reproducibility_Aware_Review_R6.docx'
DOC.save(out)
print('Saved',out,out.stat().st_size,'bytes','paragraphs',len(DOC.paragraphs),'tables',len(DOC.tables))
