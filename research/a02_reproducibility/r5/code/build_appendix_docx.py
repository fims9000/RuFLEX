"""Create a standalone article-ready R5 appendix from frozen results only."""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_BREAK
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'manuscript'/'R5_Conditional_Decision_Value_Research_Appendix.docx'

d=Document()
sec=d.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.75);sec.bottom_margin=Inches(.7);sec.left_margin=Inches(.8);sec.right_margin=Inches(.8)
styles=d.styles
normal=styles['Normal'];normal.font.name='Cambria';normal.font.size=Pt(10.5)
normal.paragraph_format.space_after=Pt(6)
normal.paragraph_format.line_spacing=1.13
for name,size,after,before in [('Title',19,10,0),('Heading 1',12.5,6,11),('Heading 2',11,5,8)]:
    s=styles[name];s.font.name='Cambria';s.font.size=Pt(size);s.font.color.rgb=RGBColor(27,40,52)
    s.font.bold=True;s.paragraph_format.space_before=Pt(before);s.paragraph_format.space_after=Pt(after)
    s.paragraph_format.keep_with_next=True
if 'Equation R5' not in styles:
    eq=styles.add_style('Equation R5',WD_STYLE_TYPE.PARAGRAPH)
    eq.font.name='Cambria Math';eq.font.size=Pt(11)
    eq.paragraph_format.space_before=Pt(4);eq.paragraph_format.space_after=Pt(7)

def para(txt='',style=None):
    return d.add_paragraph(txt,style=style)

def heading(txt,l=1):return d.add_heading(txt,l)

def eq(txt):
    p=d.add_paragraph(style='Equation R5');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run(txt)
    return p

def table(headers,rows,widths=None):
    t=d.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.style='Table Grid'
    for j,h in enumerate(headers):
        cell=t.rows[0].cells[j];cell.text=str(h)
        tcPr=cell._tc.get_or_add_tcPr();sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E9EEF2');tcPr.append(sh)
        for run in cell.paragraphs[0].runs:run.font.bold=True;run.font.size=Pt(8.8)
    for row in rows:
        cells=t.add_row().cells
        for j,val in enumerate(row):
            cells[j].text=str(val)
            cells[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cells[j].paragraphs:
                paragraph.paragraph_format.space_after=Pt(2)
                for run in paragraph.runs:run.font.size=Pt(8.7)
    if widths:
        for row in t.rows:
            for j,w in enumerate(widths):row.cells[j].width=Inches(w)
    d.add_paragraph('').paragraph_format.space_after=Pt(1)
    return t

p=d.add_paragraph();p.paragraph_format.space_after=Pt(9);r=p.add_run('When Is Retraining Disagreement Worth Using?');r.font.name='Cambria';r.font.size=Pt(19);r.font.color.rgb=RGBColor(27,40,52);r.bold=True
p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=p.add_run('Conditional decision value of prediction reproducibility — R5 research appendix');r.italic=True
p=d.add_paragraph('Research extension of “When High Confidence Is Not Reproducible”  |  4 November 2026')
p.alignment=WD_ALIGN_PARAGRAPH.CENTER

heading('Abstract')
para('A confident classifier may give a decision that changes after retraining, but the existence of disagreement does not guarantee that it can improve error-aware review. We formulate a falsifiable conditional decision-value hypothesis: retraining-based audit signals are operationally useful when they alter the conditional probability of reference-model error within confidence and predicted-class strata enough to change review decisions near a specified operating budget. The value-of-information inequality is a known decision-theoretic consequence, not a new theorem. We test a validation-fitted conditional error-risk model against an equally supervised confidence-only comparator on a previously unused chronological CO₂ task. Across two overlapping temporal folds and four reference model families (248 fits), the late-period streaming cost improved in three cells and tied in one; the earlier fold contained an adverse case. A post-hoc reanalysis of 32 previously inspected A06 cells was heterogeneous. Our contribution is the falsifiable framing and an auditable stress test, not a universal risk-reduction claim.')

heading('1. Central research hypothesis')
para('H-R5: Additional information about prediction reproducibility is useful only insofar as it changes conditional error-risk ordering, or crosses a cost-sensitive review boundary, beyond what reference-model confidence and predicted class already reveal. In particular, agreement among retrained models does not imply correctness.')
para('The operational prediction comes from a single fixed reference model. Auxiliary retrainings never vote or alter that prediction. Let E be its binary error indicator, C its confidence, ŷ its predicted class, D the fraction of auxiliary fits disagreeing with ŷ, and S the standard deviation of their class-1 probabilities.')
eq('r₀(C, ŷ) = P(E = 1 | C, ŷ)')
eq('r₁(C, ŷ, D, S) = P(E = 1 | C, ŷ, D, S)')
para('The new empirical question is whether the second risk can be estimated more usefully than the first, and whether that increment transfers to future cases without using their labels to select the reviewing rule.')

heading('2. Decision-theoretic conditions')
para('Let g(x) be the probability of sending a case for review and λ be a hypothetical review cost measured in units of an unresolved automated error. Assuming no automated error is output for a reviewed case, the cost proxy is:')
eq('Lλ(g) = 𝔼[E · (1 − g) + λg]')
para('The unconstrained Bayes reviewer checks cases whose conditional error risk exceeds λ. Enlarging the available information from (C, ŷ) to (C, ŷ, D, S) cannot reduce the optimal information value:')
eq('Vλ = 𝔼[(r₁ − λ)₊] − 𝔼[(r₀ − λ)₊] ≥ 0')
para('The inequality is conditional Jensen, since r₀ = 𝔼[r₁ | C, ŷ]. For a capacity restriction 𝔼[g] ≤ q, the marginal boundary becomes λ + ν, where ν is the nonnegative budget shadow price:')
eq('W(F; q, λ) = min over ν ≥ 0 {νq + 𝔼[(rF − λ − ν)₊]}')
para('Crucially, these statements concern true conditional risks and optimal actions. They do not guarantee that a finite-sample error-risk classifier fitted on validation labels will improve. Positive dependence between disagreement and error is insufficient if it does not change the cases that should be reviewed at the operating cost or budget.')

heading('3. Frozen temporal experiment')
para('The fresh task uses weekly Mauna Loa atmospheric CO₂ observations distributed with statsmodels. The target asks whether the next observed week rises above the current value. Features comprise the current and lagged CO₂ levels, historical changes and averages, and known seasonal coordinates; future target values never enter the features. Targets with missing weekly observations are excluded. The temporal split includes embargo gaps of at least eight weeks.')
para('The primary later fold uses training data up to 1986, validation in 1987–1994 and test cases from April 1995 through 2001. A preceding train/validation/test window provides a dependent secondary assessment. Every model family has one frozen reference fit plus 30 predeclared auxiliary fits; across two folds, this produces 248 training calls. Risk regressors are trained on validation error labels only. Policy thresholds and tie handling are fixed on validation. The primary target is 20% review on validation and λ = 0.25; actual test workload may differ.')

heading('4. Main results: streaming utility')
para('Lower joint review cost is better; negative differences favour the conditional model. Each later-period model is evaluated on the same 352 chronological test weeks, so the four comparisons are dependent.')
rows=[('Logistic Regression','0.2372','0.2372','0.00','70 → 70'),('Decision Tree','0.3239','0.3118','−1.21','68 → 71'),('Random Forest','0.3970','0.3629','−3.41','63 → 71'),('SGD Logistic','0.4972','0.4886','−0.85','4 → 8')]
table(['Family','Conf. cost','Conditional cost','Δ, pp','Reviewed'],rows,[1.35,1.13,1.48,.8,1.15])
para('The late block contains three improvements and one exact tie. On a strictly equal batch budget of 71 reviewed cases, the conditional method leaves 0, 2, 6, and 2 fewer errors than the fitted confidence-only method for the respective families. This batch-ranking comparison is supplementary: top-k over the entire test batch is not a streaming policy.')
para('In the earlier secondary block the conditional rule improves three models but is worse for Logistic Regression (+0.354 pp). Moreover, raw confidence outperforms the learned conditional rule for the late Decision Tree (0.3111 vs 0.3118 streaming cost). The method does not dominate all reasonable baselines.')

im=d.add_picture(str(ROOT/'figures/R5_TEMPORAL_COST_DELTA.png'),width=Inches(5.90))
d.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
p=d.add_paragraph('Figure 1. Descriptive cost contrasts by temporal fold and model; costs are an accounting proxy, not observed human performance.');p.style='Normal';p.paragraph_format.keep_together=True;p.paragraph_format.space_after=Pt(3);p.runs[0].font.size=Pt(9);p.runs[0].italic=True

heading('5. A falsification-oriented analysis')
para('The post-hoc A06 reanalysis (32 dataset–model–split cells from the earlier R4 study) gave 13 gains, 4 ties and 15 losses under validation-frozen streaming thresholds, despite a favourable but small unweighted mean difference of −0.00551 cost units. Because the underlying labels had been inspected before R5, this analysis is not independent confirmation.')
para('The factor ablation is also post-hoc. On the later Random Forest window, the review costs were 0.3970 (confidence only), 0.3608 (confidence plus disagreement), 0.3984 (confidence plus probability dispersion), and 0.3629 (both). On Decision Tree the corresponding values were 0.3239, 0.3175, 0.3118 and 0.3118. Different training families benefit from different audit statistics; extra features are not automatically helpful.')
para('A further counterexample is that the late Decision Tree produced 88 wrong predictions with confidence ≥0.90 and zero observed disagreement among the 30 auxiliary runs. Reproducibility may coexist with systematic error.')

heading('6. Interpretation and next validation gate')
para('This is not a claim of generalizable superiority. The fresh CO₂ task is one historical time series, the temporal folds overlap, four model families are not independent datasets, and the pseudo-random seeds are not a proof of an independent retraining distribution. The cost parameter λ is hypothetical, and validation-frozen thresholds can drift substantially in realized test coverage (notably for SGD Logistic).')
para('The central next confirmatory test should use at least several genuinely independent temporal or institutional cohorts, chosen and frozen before outcome inspection. Error-risk training and review-threshold calibration should be separated; the primary model family, operating budget and review-cost definition must be predefined. Inference must use independent cohorts or valid clustering rather than treating correlated seeds or overlapping data partitions as independent replications.')

heading('Selected related work')
for item in [
'Franc, Prusa and Voracek (2023). Optimal Strategies for Reject Option Classifiers. Journal of Machine Learning Research 24(11).',
'Black, Leino and Fredrikson (2022). Selective Ensembles for Consistent Predictions. ICLR.',
'Hidey, Liu and Goel (2022). Reducing Model Churn: Stable Re-training of Conversational Agents. SIGDIAL.',
'Paplhám, Waegeman, Hüllermeier and Franc (2026). Evaluating Epistemic Uncertainty: Beyond OOD Detection and Active Learning. arXiv:2607.14817.',
'statsmodels dataset documentation. CO₂: Mauna Loa weekly observations, 1958–2001.'
]:para(item)

OUT.parent.mkdir(parents=True,exist_ok=True);d.save(OUT)
print(OUT)
