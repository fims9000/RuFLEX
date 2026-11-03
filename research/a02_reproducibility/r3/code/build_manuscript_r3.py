"""Create integrated double-blind R3 paper by surgical edits to the original A01/A02 R2.

Retains all original A01 tables and embedded figures and adds A03/A04/A05
methods, independent checks, losses and failure cases, without fabricating data.
"""
from __future__ import annotations
from pathlib import Path
from docx import Document
from docx.shared import Pt,Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'r2_prior_release'/'When_High_Confidence_Is_Not_Reproducible_REVISED_R2.docx'
if not SRC.is_file():
    raise FileNotFoundError(f'R2 input missing: {SRC}; extract the complete R3 release first')
OUT=ROOT/'manuscript'/'When_High_Confidence_Is_Not_Reproducible_REVISED_R3.docx'
d=Document(SRC);old=list(d.paragraphs)

def replace(i,text):
    p=old[i]
    if p.runs:
        p.runs[0].text=text
        for r in p.runs[1:]:r.text=''
    else:p.add_run(text)
    return p

def addparagraph(anchor_idx,text,kind='body'):
    p=old[anchor_idx].insert_paragraph_before()
    if kind in ('section','subsection','caption'):
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent=Pt(0)
        p.paragraph_format.keep_with_next=(kind!='caption')
        p.paragraph_format.space_before=Pt(7 if kind=='section' else (5 if kind=='subsection' else 3))
    else:
        p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent=Inches(.14)
        p.paragraph_format.space_before=Pt(0)
    p.paragraph_format.space_after=Pt(1 if kind=='caption' else 0)
    r=p.add_run(text)
    r.font.name='Times New Roman'
    r.font.size=Pt(8 if kind=='caption' else (9 if kind in ('section','subsection') else 10))
    r.bold=(kind=='subsection')
    if kind=='caption': r.italic=True
    return p

def native_table(anchor_idx,headers,values,widths):
    t=d.add_table(rows=1,cols=len(headers))
    t.alignment=WD_TABLE_ALIGNMENT.LEFT;t.autofit=False
    for c,h in zip(t.rows[0].cells,headers):c.text=h
    for item in values:
        for c,text in zip(t.add_row().cells,item):c.text=str(text)
    for rid,row in enumerate(t.rows):
        for j,c in enumerate(row.cells):
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0)
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.name='Times New Roman';run.font.size=Pt(7.1)
                    if rid==0:run.bold=True
    for j,width in enumerate(widths):
        t.columns[j].width=Inches(width)
        for row in t.rows:row.cells[j].width=Inches(width)
    for gc,width in zip(t._tbl.tblGrid.gridCol_lst,widths):gc.w=Inches(width)
    tw=t._tbl.tblPr.find(qn('w:tblW'))
    if tw is not None:tw.set(qn('w:type'),'dxa');tw.set(qn('w:w'),str(round(sum(widths)*1440)))
    old[anchor_idx]._p.addprevious(t._tbl)
    return t

def figure(anchor_idx,name,caption,width=3.05):
    image=ROOT/'figures'/name
    p=d.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after=Pt(1)
    p.paragraph_format.space_before=Pt(2)
    p.add_run().add_picture(str(image),width=Inches(width))
    old[anchor_idx]._p.addprevious(p._p)
    addparagraph(anchor_idx,caption,'caption')

# Front matter: specific, concise, honest about uncertainty and non-independence.
replace(1,'When High Confidence Is Not Reproducible: Conditional Certificates and Held-Out Selective Review')
replace(6,('Abstract—Prediction confidence and decision reproducibility answer different questions. '
 'We study the probability that an independently retrained model reproduces the class of a fixed operational predictor, '
 'and whether retraining disagreement helps prioritize cases for review. The original frozen A01 evaluation used '
 '300 fits in 15 dataset–model cells and found high-confidence instability in four validation cells; '
 'its selective-review results were not uniformly beneficial. We give deterministic score-margin conditions, '
 'a conditional score-concentration bound, and exact one-sided binomial certification for a fixed reference '
 '(with within-cell multiplicity correction). In exploratory A02, 3,535 fits across seven data regimes and five '
 'model families yielded 4,739 certified validation case–model decisions out of 6,125, conditional on the '
 'retraining sampling model. A new A03 held-out batch-review study used 2,480 fits, four public datasets and four '
 'synthetic regimes, five model families, and two splits. At exactly matched review counts for a nominal 90% coverage target, a '
 'prespecified confidence-plus-disagreement score reduced accepted-case risk relative to confidence-only ranking '
 'in 28/80 cells, tied in 47, and worsened it in five; the descriptive mean difference was −0.55 percentage points. '
 'A budget ablation tested 5–30 audit fits. An additional 4,040-fit A05 audit on public datasets nominally certified '
 '4,601/5,400 held-out case–model decisions, but 184 certified decisions were wrong. Reproducibility is therefore '
 'not correctness, and the held-out review benefit is heterogeneous. All certificates require a specified '
 'randomness distribution and a justified independent-draw assumption; none proves deployment safety.'))
replace(7,'Keywords—decision reproducibility, prediction churn, selective classification, training randomness, exact binomial bounds, risk–coverage evaluation')
replace(12,('The study addresses six related questions. RQ1–RQ3, tested in frozen A01, concern the occurrence of '
 'high-confidence instability, its information beyond confidence, and the risks of stability-aware review. '
 'RQ4 defines a reproducibility target before the audit and establishes conditional sufficient conditions. '
 'RQ5 probes the generality of reproducibility patterns over more model families, data regimes and splits. '
 'RQ6 asks whether disagreement scores add held-out review value at an exactly matched budget, and how '
 'that value depends on the number of auxiliary fits.'))
replace(13,('The contribution is a careful separation of the operational prediction, repeatability of its class '
 'under a specified retraining distribution, and error reduction after selective review. A01 retains its '
 'fixed protocol and negative findings. A02 formalizes conditional certification and broadens the validation '
 'study. A03 adds an exact-budget held-out comparison against confidence-only, disagreement-only and '
 'dispersion-based ranking; A04 examines fit-budget sensitivity, and A05 checks certificates on public-dataset '
 'held-out cases. We do not claim a new concentration inequality, binomial confidence interval, or universal '
 'improvement. The distinctive empirical question is what reproducibility contributes when one predictor '
 'remains fixed and never votes with the audit fits.'))
replace(18,('Deep ensembles use multiple fits directly for prediction or uncertainty estimation [10], while '
 'Selective Ensembles abstain when a consistent ensemble outcome cannot be established [11]. DAUNT and '
 'consistency-auditing methods route uncertain cases using ensemble disagreement [12], [19]. '
 'Training-dynamics selective prediction instead uses changes across checkpoints of one fit [21]. '
 'In contrast, our operational class and raw score come from one model fixed before independent retraining '
 'audits; extra fits never vote. The claim is not that retraining disagreement is new, but that the audit '
 'can be separated from the prediction and evaluated against confidence at identical review budgets.'))

# Formal proposition: a priori sufficient condition with explicit assumptions.
addparagraph(39,'E. Conditional Score-Concentration Condition','subsection')
addparagraph(39,('Proposition 1. Fix the operational class y₀ = argmaxc z₀,c(x) and a competing class c. '
 'Define the reference score gap M_c = z₀,y₀(x) − z₀,c(x) > 0. For a fresh fit, '
 'let D_c = [zₛ,c(x)−z₀,c(x)] − [zₛ,y₀(x)−z₀,y₀(x)]. Suppose D_c has mean μ_c and '
 'is σ_c-sub-Gaussian about its mean. If for every c ≠ y₀, '
 'M_c > μ_c + σ_c√[2 log((C−1)/δ)], then the probability that retraining changes '
 'the reference class is at most δ.'))
addparagraph(39,('Proof. A class reversal implies D_c ≥ M_c for at least one competitor. '
 'If σ_c>0, the sub-Gaussian upper-tail inequality bounds each event by '
 'exp{−(M_c−μ_c)²/(2σ_c²)} whenever M_c>μ_c. If σ_c=0, '
 'D_c=μ_c almost surely and the strict gap excludes a reversal. Under the stated '
 'margins, each event has probability at most δ/(C−1). A union bound gives '
 'the result. The deterministic '
 '2ε margin criterion is the corresponding worst-case bound with no random-tail assumptions.'))
addparagraph(39,('This proposition identifies conditions that ensure reproducibility conditional on known '
 'score-drift distributions; it is not an empirical guarantee in the present benchmarks. '
 'The drift means and sub-Gaussian scales are not estimated with validated upper bounds here, '
 'and the inequality can be vacuous for hard-label trees. The separate Clopper–Pearson '
 'certificate uses actual repeated class labels, not these unverified distribution parameters.'))

# The appended R2 section already introduced A02, including numbers from A01 and A02.
# Insert the new independent selective-review comparison BEFORE R2 discussion.
anchor=98
addparagraph(anchor,'VI. HELD-OUT SELECTIVE REVIEW AND CERTIFICATION','section')
addparagraph(anchor,'A. Strictly Matched-Coverage Protocol (A03)','subsection')
addparagraph(anchor,('A03 was specified locally before executing its new held-out comparisons. Four public '
 'scikit-learn binary tasks (Iris, Wine, Digits and Wisconsin Breast Cancer) and four fixed synthetic '
 'separation/noise regimes were evaluated with Logistic Regression, Decision Tree, Random Forest '
 '(25 trees), Extra Trees (25 trees), and SGD Logistic. For each of two stratified seeds (101, 202), '
 'a fixed reference model (seed 30000) and 30 disjoint audit fits (seeds 31000–31029) were trained '
 'on the 60% training partition. Validation and final 20% test identities were disjoint; '
 'normalization used train data only. The reference model alone generated each decision. '
 'In total, A03 comprised 80 dataset–model–split cells and 2,480 fits.'))
addparagraph(anchor,('For a case x, let c denote the fixed-reference confidence, a the fraction of fresh fits '
 'repeating its class, and v the standard deviation of auxiliary class-1 probabilities. '
 'Without fitting weights to outcomes, we compared four review scores: '
 's_conf = 1−c; s_dis = 1−a; s_comb = (1−c)+0.5(1−a); and '
 's_disp = (1−c)+0.5v. In each test cell, the top '
 'ceil[(1−q)N] scores are sent for review at target coverage q ∈ {0.80,0.90,0.95}. '
 'Score ties are broken by a deterministic case-ID hash, never a label. All policies therefore '
 'review exactly the same number of cases, independently of their scores. '
 'Test labels are used only after these rankings are fixed. This is a batch-budgeted '
 'comparison, not a per-case online threshold learned on validation.'))
addparagraph(anchor,('The principal descriptive endpoint is ΔR = R_comb−R_conf among automatically '
 'accepted predictions at target coverage 0.90. A paired case bootstrap with 2,000 '
 'replicates was run per cell; the resulting 95% percentile intervals are exploratory, '
 'not a multiplicity-adjusted test across correlated datasets or models. We also recomputed '
 'risk contrasts over 16 label-independent tie-breaking seeds.'))
addparagraph(anchor,'B. Held-Out Results','subsection')
addparagraph(anchor,('In 80 held-out cells, the fixed combination reduced accepted-case risk relative '
 'to confidence-only in 28, produced identical risk in 47, and increased it in five. '
 'The unweighted descriptive cell mean ΔR was −0.00546 (−0.55 percentage points); '
 'the median was exactly zero. Decision Tree showed the clearest pattern: 12/16 '
 'lower-risk cells, one higher-risk cell and three ties, with mean ΔR = −0.01880 '
 '(−1.88 percentage points). Logistic Regression was an effectively deterministic '
 'control: the combination was identical to confidence-only in all 16 cells. '
 'Table V and Fig. 3 show the complete, heterogeneous outcomes.'))
addparagraph(anchor,'TABLE V. HELD-OUT RISK AT TARGET 90% COVERAGE; MEANS OVER 16 NON-INDEPENDENT CELLS PER MODEL.','caption')
native_table(anchor,['Model','Conf. risk','Combined risk','Better/Worse/Tie'],[
 ('Decision Tree','11.66%','9.78%','12 / 1 / 3'),
 ('SGD Logistic','9.58%','9.00%','7 / 1 / 8'),
 ('Random Forest','5.37%','5.12%','6 / 1 / 9'),
 ('Extra Trees','5.24%','5.22%','3 / 2 / 11'),
 ('Logistic Regression','8.17%','8.17%','0 / 0 / 16')],[.88,.63,.74,.76])
figure(anchor,'fig3_a03_per_cell_delta.png',
  'Fig. 3. Held-out accepted-risk differences at the same review count. Circles are dataset–split cells; black squares indicate within-family means. Cells reuse datasets and cannot be treated as independent trials.',width=3.06)
addparagraph(anchor,('The aggregate effect is stronger in the synthetic regimes than in the '
 'public tasks: for the 40 public task–model–split cells, the fixed combination '
 'improved ten, worsened two and tied 28 (mean ΔR = −0.00343, or −0.34 '
 'percentage points); for the 40 synthetic cells, the corresponding counts were '
 '18, three and 19 (mean ΔR = −0.00750, or −0.75 points). '
 'The four synthetic regimes share one generator, so this gap further limits '
 'claims of external generalization.'))
addparagraph(anchor,('Disagreement alone was not a uniformly strong baseline. On all 80 cells its mean '
 'ΔR against confidence-only was +0.00028; it helped in 31, harmed in 25 and tied '
 'in 24 cells. The fixed dispersion combination improved 18, harmed eight and tied '
 '54 cells (mean ΔR −0.00424). Results at 80%, 90% and 95% accepted budgets are '
 'provided in the reproducibility package. The primary conclusion is a '
 'regime-dependent gain from combining confidence and agreement, not dominance.'))
figure(anchor,'fig4_a03_risk_coverage.png',
  'Fig. 4. Mean held-out accepted risk across the 80 correlated cells under exact matched budgets; descriptive, not an unbiased population generalization estimate.',width=3.00)
addparagraph(anchor,'C. Tie Sensitivity and Representative Failures','subsection')
addparagraph(anchor,('Numerically saturated confidence creates large tie groups, particularly for '
 'Decision Trees. Over 16 deterministic tie-break seeds, the combined score had a '
 'negative risk difference in every tie resolution for 23 of the 80 cells, '
 'while the direction was not invariant in the remaining cells. '
 'Thus, a single fixed tie seed should not be interpreted as evidence of '
 'robust superiority. The supplementary table reports the full minimum and '
 'maximum ΔR for each cell.'))
addparagraph(anchor,('Failure 1: on Wisconsin Breast Cancer / Decision Tree / split 202, confidence-only '
 'reviewed an incorrect case (ID 205; reference confidence 1.0 and retraining agreement 1.0), '
 'while the combined policy accepted it, increasing accepted risk by 0.98 percentage points. '
 'No retraining-based score can identify an error that is reproducible across all audit fits.'))
addparagraph(anchor,('Failure 2: on synthetic separation 0.5 / noise 0.01 / Extra Trees / split 202, '
 'the combined rule reviewed two additional erroneous unstable predictions but released '
 'several erroneous low-confidence cases previously reviewed by the baseline, '
 'raising accepted risk by 1.11 percentage points. Disagreement signal and '
 'error risk are not perfectly aligned. Failure 3: on separation 0.5 / noise 0.15 / '
 'SGD Logistic / split 202, the combined rule reviewed one fewer erroneous case '
 'than confidence-only (seven versus eight), raising risk by 0.56 percentage points. '
 'These are observed policy switches, not causal explanations of their failure.'))
addparagraph(anchor,'D. Fit Budget and Ranking Stability (A04)','subsection')
addparagraph(anchor,('A post-hoc ablation retrained 30 auxiliary fits per cell in the 32 Decision Tree '
 'and SGD Logistic cells and recomputed the fixed combined score using only the '
 'first 5, 10, 20 or 30 independent audit fits. At exact 90% coverage, the '
 'mean ΔR for Decision Tree was −1.91, −2.04, −1.97 and −1.88 '
 'percentage points, respectively; for SGD Logistic it was '
 '−0.20, −0.54, −0.62 and −0.59 points. The 10-fit reviewed '
 'set had a mean Jaccard overlap of 0.904 for Decision Tree and 0.880 '
 'for SGD Logistic with the 30-fit reference. The ablation reuses '
 'A03 test labels and is exploratory. It suggests that fewer fits can be '
 'competitive for ranking, not that they provide the same statistical certificate.'))
figure(anchor,'fig5_a04_budget.png',
  'Fig. 5. Post-hoc audit-fit budget sensitivity, exact 90% coverage. Negative values favor the fixed combination; the held-out cases were already examined in A03.',width=3.0)
addparagraph(anchor,'E. Held-Out Replication Certificates (A05)','subsection')
addparagraph(anchor,('To probe the conditional finite-sample definition directly on held-out cases, '
 'A05 repeated the four public benchmarks over both splits and all five families, '
 'using one fixed reference and 100 pseudo-uniformly sampled audit seeds per '
 'cell (40 cells, 4,040 fits). The one-sided exact binomial lower limit '
 'was Bonferroni-adjusted over m held-out cases in each fixed '
 'dataset–model–split cell. With target replication probability 0.90 and nominal '
 'simultaneous within-cell confidence 95%, 4,601/5,400 case–model '
 'predictions met the certificate criterion.'))
addparagraph(anchor,'TABLE VI. A05 HELD-OUT CLASS-REPLICATION CERTIFICATES; THESE DO NOT CERTIFY CORRECTNESS.','caption')
native_table(anchor,['Model','Certified / 1,080','Wrong certified'],[
 ('Logistic Regression','1,080 / 1,080','97'),
 ('Decision Tree','988 / 1,080','75'),
 ('Random Forest','932 / 1,080','2'),
 ('Extra Trees','957 / 1,080','3'),
 ('SGD Logistic','644 / 1,080','7'),
 ('Total','4,601 / 5,400','184')],[1.17,1.05,.79])
figure(anchor,'fig6_a05_certification.png',
  'Fig. 6. Within-cell simultaneous class-repetition certificate rates on public datasets, with counts of wrong certified predictions. A wrong yet reproducible class is not a contradiction.',width=3.0)
addparagraph(anchor,('Among the 4,601 certified cases, 184 were misclassified by the '
 'fixed reference model. Logistic Regression certified 1,080/1,080 cases '
 'but was wrong on 97 of them; deterministic fitting can be perfectly '
 'repeatable without being correct. The certified fraction is therefore '
 'not an accuracy, calibration or safety metric. Certifying all 100-agreeing '
 'fits requires at least ceil[log(0.05/m)/log(0.90)] fresh fits '
 'when correcting over m cases; an audit of 30 fits cannot reach this '
 'nominal 90% target in our cell sizes even if all repetitions agree.'))
addparagraph(anchor,('The probability interpretation of these intervals requires truly independent '
 'draws of training randomness from a declared distribution. A05 sampled '
 'seeds with replacement using a reproducible pseudo-random generator, '
 'which approximates such a design but does not mathematically prove '
 'independence of the induced model outcomes. As in A02, nominal coverage '
 'is simultaneous only within each declared cell; A05 did not provide '
 'a joint 95% bound across all 40 cells.'))

replace(98,'VII. DISCUSSION')
replace(99,('The evidence supports a narrower, operationally useful interpretation than '
 'universal instability-based review. Reproducibility captures a property of '
 'the training procedure conditional on a fixed dataset and configuration; '
 'confidence is one predictor’s score; correctness is a property of the '
 'predictor against ground truth. In A01, stability-aware routing provided '
 'both favorable and unfavorable descriptive contrasts with some imperfect '
 'coverage matching. A03 removes that matching ambiguity by fixing the '
 'same unlabeled batch budget for all strategies, but still shows a '
 'heterogeneous benefit. Neither the A05 certificates nor a fixed high '
 'confidence score can substitute for independent predictive validation.'))
replace(101,('Operational design involves two separate budgets: the number of model '
 'fits needed to estimate a useful review ranking, and the larger number '
 'required to issue a high-confidence replication certificate. A04 suggests '
 'a 10-fit audit may be competitive for some Decision Tree/SGD ranking '
 'settings, while A05 uses 100 fits for conservative within-cell bounds. '
 'These results do not establish a deployment-ready adaptive stopping rule; '
 'ordinary fixed-n Clopper–Pearson bounds would need explicit sequential '
 'error control if stopping decisions depended on intermediate evidence.'))
replace(102,('Our results complement both selective ensembles [11], which allow '
 'multiple models to determine or abstain from the prediction, and '
 'training-dynamics selective prediction [21], which audits one model’s '
 'trajectory. Here the operational class never changes. A formal '
 'concentration condition identifies what would suffice for stable '
 'predictions, while the empirical class-agreement certificate tests '
 'reproducibility without requiring a validated drift distribution. '
 'Neither condition alone controls classification risk.'))
replace(103,('The high-confidence disagreement/error relationship is strongest '
 'for particular stochastic or tie-prone families, especially Decision '
 'Trees. Some improvements in A03 are robust across the tested tie '
 'resolutions; others are not. Because A02, A03, A04 and A05 reuse '
 'several datasets and the latter two share held-out partitions, the '
 'extended study is exploratory and does not justify a new claim of '
 'statistical significance from a pooled cross-cell count.'))
replace(104,'VIII. LIMITATIONS')
replace(105,('The original A01 experiment used one frozen split and its own '
 'validation-selected operational model. A02–A05 use different fixed '
 'reference models and cannot be retroactively treated as repetitions '
 'of A01. A03 evaluates unlabeled batch-top-k review at preset budgets; '
 'its exact coverage guarantee is a combinatorial property of that '
 'batch, not an online selective-risk guarantee. Small Iris and Wine '
 'test partitions have low statistical power.'))
replace(106,('The four synthetic A03 regimes share one generator, and the '
 'four public benchmarks do not cover temporal drift, real industrial '
 'deployment, other architectures or true distribution shift. '
 'Two resplits of the same data are dependent, not independent studies. '
 'A03 bootstrap intervals are per-cell and unadjusted for many '
 'correlated comparisons; count differences and mean effect sizes '
 'must remain descriptive. The A04 subset and budget grid were '
 'examined after observing A03.'))
replace(107,('The mathematical score-drift condition presumes known deterministic '
 'or sub-Gaussian bounds that are not empirically certified here. '
 'Clopper–Pearson coverage is conditional on an independent training-seed '
 'sampling model, whereas actual computational pseudo-random sequences '
 'are deterministic. Bonferroni adjustment is within, not across, '
 'dataset-model cells. High agreement can coincide with systematic '
 'errors, as shown directly in A05. Original A01 coverage and numerical '
 'tie caveats remain intact.'))
replace(108,('A03 does not measure human-review outcomes or the costs of retraining '
 'and storing a pool of auxiliary models. The 30-fit and 100-fit audits '
 'may be prohibitive in production. Adaptive early stopping could '
 'reduce prediction-evaluation costs but would require valid '
 'anytime inference. Replication on independently collected data, '
 'more training-randomness distributions and additional model families '
 'is necessary before operational deployment or broad generalization.'))
replace(109,'IX. CONCLUSION')
replace(110,('A priori decision reproducibility is the probability that a fresh fit '
 'repeats a label from an operational model fixed before the audit. '
 'Conditional score-margin and score-concentration criteria make '
 'sufficient conditions explicit; exact binomial bounds offer a '
 'sampling-based alternative when their independence assumptions hold. '
 'The public-data A05 audit nominally certified 4,601/5,400 '
 'fixed-reference predictions, including 184 incorrect ones. '
 'Reproducibility is therefore a distinct target, not a proxy for '
 'correctness or calibrated confidence.'))
replace(111,('The frozen A01 and expanded exploratory A02 findings remain unchanged. '
 'In the new exactly matched held-out A03 benchmark, adding fixed '
 'retraining disagreement to confidence lowered accepted-case risk '
 'in 28/80 cells, tied in 47 and raised it in five. Benefits were '
 'largest for Decision Trees and absent for effectively deterministic '
 'Logistic Regression. Fit-budget ablations and numerical tie '
 'sensitivity delimit the cost and robustness of these results. '
 'Reproducibility-aware selective review is consequently a useful '
 'conditional audit signal, not a universal accuracy-improvement '
 'or deployment-safety guarantee.'))

# Include verified related work; no newly invented citation details.
reference='[21] S. Rabanser et al., "Selective Prediction via Training Dynamics," Transactions on Machine Learning Research, 2025, https://openreview.net/forum?id=2wgnepQjJf.'
r=d.add_paragraph(reference)
for run in r.runs:run.font.name='Times New Roman';run.font.size=Pt(8)
r.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY

# Re-render required after any subsequent changes.
OUT.parent.mkdir(parents=True,exist_ok=True)
d.save(OUT)
print(OUT)
