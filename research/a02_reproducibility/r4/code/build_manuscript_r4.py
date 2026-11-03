"""Integrate independently verified A06 data into the preserved R3 manuscript.

All original figures, tables, results and references remain part of the base
file. This generator patches only identifiable text and adds a new section.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches,Pt
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent.parent


def find(doc, exact):
    x=[p for p in doc.paragraphs if p.text.strip()==exact]
    if len(x)!=1:raise ValueError(f'expected exactly one paragraph {exact}, got {len(x)}')
    return x[0]


def text_like(anchor,text,example,*,kind='body'):
    p=anchor.insert_paragraph_before()
    if example._p.pPr is not None:
        new=deepcopy(example._p.pPr)
        old=p._p.pPr
        if old is not None:p._p.remove(old)
        p._p.insert(0,new)
    r=p.add_run(text)
    source=next((t for t in example.runs if t.text),None)
    if source:
        r.font.name=source.font.name
        r.font.size=source.font.size
        r.font.bold=source.font.bold
        r.font.italic=source.font.italic
    if kind=='header':
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        r.bold=False
        p.paragraph_format.keep_with_next=True
    if kind=='subheader':
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        r.bold=True
        p.paragraph_format.keep_with_next=True
    return p


def picture_before(doc,anchor,filename,width=Inches(3.18)):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(6)
    p.paragraph_format.space_after=Pt(2)
    p.add_run().add_picture(str(filename),width=width)
    anchor._p.addprevious(p._p)
    return p


def make(docx_r3,out):
    doc=Document(docx_r3)
    D=doc.paragraphs
    base_body=D[132];head=D[131];subhead=D[124];caption=D[128]
    # Preserve and correct a pre-existing alphabetical heading slip in Section III.
    a=find(doc,'E. Conditional Score-Concentration Condition')
    b=find(doc,'D. Finite-Sample Certificate for a Fixed Reference')
    for p,s in [(a,'D. Conditional Score-Concentration Condition'),(b,'E. Finite-Sample Certificate for a Fixed Reference')]:
        if len(p.runs)==1:p.runs[0].text=s
        else:p.text=s

    title=D[1]
    title.runs[0].text=('When High Confidence Is Not Reproducible: Conditional Certificates, '
       'Matched-Budget Review and Streaming Thresholds')
    abstract=(
       'Abstract—A confident prediction can change when an otherwise fixed training procedure is repeated. '
       'We separate confidence, prediction reproducibility and selective-review risk while keeping one fitted model as the sole predictor. '
       'The original A01 experiment (300 fits) identified high-confidence disagreement but no universal coverage-matched review gain. '
       'We state deterministic and distributional sufficient conditions for label stability and conditional exact-binomial replication certificates; '
       'A05 nominally certified 4,601/5,400 held-out class decisions under a within-cell multiplicity adjustment, including 184 incorrect predictions. '
       'In an exploratory A03 study (2,480 fits, 80 correlated dataset–model–split cells), a fixed confidence-plus-disagreement ranking improved '
       'accepted-case risk against confidence alone in 28 cells, tied in 47, and worsened it in five at exactly matched batch review counts. '
       'A06 investigates whether this result survives streaming-style deployment: on four additional packaged datasets, '
       '32 cells and 512 fits, the review threshold and boundary randomization were frozen exclusively on validation data. '
       'On held-out cases the combined rule improved, tied and worsened accepted-case risk in 17, eight and seven cells, respectively; '
       'realized coverage differed, precluding a pure risk-effect interpretation. '
       'An equal-budget batch diagnostic yielded 18 improvements, 11 ties and three deteriorations. '
       'The within-cell average risk difference is descriptive; datasets are reused across splits. '
       'Reproducibility supports conditional auditing, but is neither correctness nor a deployment guarantee.'
    )
    find(doc,next(p.text for p in D if p.text.startswith('Abstract—'))).runs[0].text=abstract
    intro=find(doc,next(p.text for p in D if p.text.startswith('The study addresses six related questions.')))
    intro.runs[0].text=(intro.text.replace('six related questions','seven related questions')+
        ' RQ7 asks whether a validation-frozen, per-case online review threshold preserves the comparative ranking behavior on additional, previously unused datasets, and how it compares with ensemble-style audit-only uncertainty scores.')
    contribution=find(doc,next(p.text for p in D if p.text.startswith('The contribution is a careful separation of the operational prediction')))
    contribution.runs[0].text=(contribution.text.replace('A04 examines fit-budget sensitivity, and A05 checks certificates on public-dataset held-out cases.',
           'A04 examines fit-budget sensitivity, A05 checks certificates on public-dataset held-out cases, and A06 independently evaluates validation-frozen streaming thresholds, new benchmark domains and ensemble-style audit-only baselines.'))

    anchor=find(doc,'VII. DISCUSSION')
    text_like(anchor,'VII. VALIDATION-FROZEN EXTERNAL-DOMAIN REVIEW (A06)',head,kind='header')
    text_like(anchor,'A. Independent domains, fixed predictors and streaming rule',subhead,kind='subheader')
    text_like(anchor,
      'A06 uses four additional, historically collected and previously unused tasks available with statsmodels 0.14.6 [22]: '
      'a binary outcome for Fair (6,366 rows), any physician visit in RAND HIE (20,190 rows), alternative choice in the Australian travel-mode dataset (840 rows for 210 travellers), and a binary response from ANES96 (944 rows). '
      'Each target is excluded from the features; ANES96 party identification is excluded, and all alternatives for the same traveller are kept in one split. '
      'Two split seeds (303, 404), four fixed model families, one reference fit per cell and 15 auxiliary fits form 32 cells and 512 total trainings. '
      'There are 45,352 held-out case–model predictions. Reference predictions are never voted upon or recalibrated using auxiliary models. '
      'The score mixing coefficient 0.5 was inherited unchanged from A03, not tuned to A06 labels.',base_body)
    text_like(anchor,
      'The primary comparator is reference confidence only. Further audit-only scores are reference disagreement alone, confidence plus probability dispersion, '
      'audit-vote uncertainty, and entropy of the audit mean probability. For each score, the k-th largest validation value is frozen as a threshold, '
      'where k = ceil(0.10 N_val). If b validation scores exceed that boundary and e scores tie, the frozen tie-rejection probability is (k-b)/e. '
      'A later case is reviewed if its score exceeds the threshold or it ties and a fixed seeded hash falls below that probability. '
      'The resulting rule operates on an individual case without knowing the number or distribution of later cases. '
      'Thus, test coverage is not constrained to exactly 90%, and comparison of accepted risks alone may be confounded by workload.',base_body)
    text_like(anchor,'B. Results and audit-only uncertainty baselines',subhead,kind='subheader')
    text_like(anchor,
      'For the prespecified streaming tie seed, combined confidence and disagreement had lower, equal and higher accepted risk than confidence-only '
      'in 17, eight and seven of 32 dependent cells. Its unweighted mean accepted-risk difference was -0.624 percentage points; '
      'the mean absolute within-cell difference in realized coverage was 0.80 points, reaching 3.57 points in one cell. '
      'This effect cannot be attributed solely to information from disagreement. '
      'An independent exact-review-count batch diagnostic on the same held-out predictions instead gave 18 favorable, 11 equal and three adverse cells, '
      'with mean risk difference -0.672 points at identical coverage. '
      'These two tests answer distinct operational questions: validation-frozen per-case workload versus conditional quality of batch ranking.',base_body)

    # Attach verified descriptive results by family in a compact IEEE column table.
    analysis=pd.read_csv(ROOT/'results'/'analysis'/'A06_CELL_CONTRASTS.csv')
    source=analysis[analysis.policy=='combined_fixed'].groupby(['evaluation','model']).risk_delta_vs_confidence.mean()
    text_like(anchor,'TABLE VII. EXTERNAL A06 MEAN ACCEPTED-RISK DIFFERENCE VERSUS CONFIDENCE-ONLY (PP); EIGHT DEPENDENT CELLS PER MODEL.',caption)
    tbl=doc.add_table(rows=5,cols=3);tbl.alignment=WD_TABLE_ALIGNMENT.CENTER;tbl.autofit=False
    values=[('Model','Batch','Streaming')]
    labels={'decision_tree':'Decision Tree','logistic_regression':'Logistic Reg.','random_forest':'Random Forest','sgd_log_loss':'SGD Logistic'}
    for model in ['logistic_regression','decision_tree','random_forest','sgd_log_loss']:
        values.append((labels[model],f"{source[('batch_exact_secondary',model)]*100:+.2f}",f"{source[('streaming_frozen',model)]*100:+.2f}"))
    for i,row in enumerate(values):
        for j,value in enumerate(row):
            cell=tbl.cell(i,j);cell.text=value;cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.width=Inches([1.45,.85,.85][j])
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(0)
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.name='Times New Roman';run.font.size=Pt(7.2)
                    if i==0:run.bold=True
    tbl.columns[0].width=Inches(1.45);tbl.columns[1].width=Inches(.85);tbl.columns[2].width=Inches(.85)
    anchor._p.addprevious(tbl._tbl)
    text_like(anchor,
      'The improvement remained heterogeneous across model families and domains. In the exact-budget diagnostic, Logistic Regression tied in all eight cells, '
      'while Random Forest improved in seven of eight and SGD Logistic in six. '
      'The audit-vote uncertainty baseline improved only eight cells, tied five and worsened 19; audit ensemble entropy improved 12, tied nine and worsened 11. '
      'Consequently, an ensemble-derived uncertainty statistic is not automatically a better review score, even though it uses additional fits.',base_body)
    picture_before(doc,anchor,ROOT/'figures'/'fig7_external_batch_delta.png')
    text_like(anchor,'Fig. 7. External-domain exact-budget held-out risk difference (combined minus confidence-only); dots represent correlated dataset–split cells and lines indicate within-model means.',caption)
    text_like(anchor,'C. Streaming coverage, uncertainty and negative cases',subhead,kind='subheader')
    text_like(anchor,
      'Frozen streaming cutoffs did not preserve exact test coverage. For confidence-only the empirical test coverage ranged from 80.36% to 93.12% across cells. '
      'The combined score had an absolute realized-coverage difference from confidence-only of up to 3.57 points, despite similar mean coverage. '
      'The fixed threshold is therefore an expected validation operating point rather than a test-set budget guarantee; unconditional risk differences must be interpreted together with the realized review workload.',base_body)
    picture_before(doc,anchor,ROOT/'figures'/'fig8_streaming_coverage_drift.png',width=Inches(2.9))
    text_like(anchor,'Fig. 8. Realized held-out coverage for fixed validation thresholds (32 correlated cells, tie seed 1). The diagonal means equal workload; 90% was the validation target, not a test-time constraint.',caption)
    text_like(anchor,
      'In the exact-budget batch diagnostic, conditional fixed-mask paired bootstrap intervals (2,500 resamples) excluded zero in four of 32 cells, '
      'all favorable to the combined score; group-level resampling was used for mode-choice travellers. '
      'These are uncorrected exploratory intervals, not 32 independent hypothesis tests. '
      'The largest within-cell gain occurred for SGD Logistic on the travel-choice benchmark (split 404, -5.96 points), while Decision Tree '
      'on the same task worsened by +0.66 points, illustrating a model-dependent failure mode. '
      'A traceable adverse example is travel-choice Decision Tree, split 404, case 679: the single reference predicted 0 for a true label of 1 '
      'with confidence 1.0 and auxiliary-run agreement 1.0. Under the exact-budget batch comparator, confidence-only reviewed this error, '
      'whereas the combined score accepted it because review places went to other cases. Thus, reproducible predictions can be wrong and '
      'a disagreement-aware review policy can miss such errors. On Fair, SGD Logistic split 303 also lost review of a wrong '
      'reference prediction at case 162 despite agreement 1.0 and confidence 0.526. '
      'Across eight tie seeds, pure disagreement and vote-based uncertainty were more sensitive to tie resolution than the combined rule.',base_body)
    text_like(anchor,'D. Review-effort sensitivity after outcome inspection',subhead,kind='subheader')
    text_like(anchor,
      'To avoid comparing accepted-case risk alone when streaming workloads differ, we also compute a post-hoc operational burden '
      'L(lambda) = (E_auto + lambda N_review)/N, where E_auto counts wrong predictions retained in the automated stream and '
      'lambda is the hypothetical cost of reviewing one case measured in units of one automatic classification error. '
      'No reviewer quality is assumed or estimated: this is a transparent workload-error accounting proxy, not realized human-in-the-loop utility. '
      'Under the fixed streaming tie seed, the combined method was Pareto better (no more errors and no more reviews) in five '
      'of 32 cells, Pareto worse in one, identical in eight and involved an error/workload tradeoff in 18. '
      'At lambda = 0.1, its burden was lower/equal/higher in 17/8/7 cells; at lambda = 0.5, in 19/8/5. '
      'Across the exploratory lambda grid from 0 to 1 the unweighted mean burden contrast ranged from -0.534 to -0.502 '
      'error-equivalents per 100 cases. No lambda was selected as a deployment-relevant cost, and these post-hoc calculations '
      'do not establish an optimal streaming policy.',base_body)
    # Revision of sections and implications, not rewriting source results.
    find(doc,'VII. DISCUSSION').runs[0].text='VIII. DISCUSSION'
    find(doc,'VIII. LIMITATIONS').runs[0].text='IX. LIMITATIONS'
    find(doc,'IX. CONCLUSION').runs[0].text='X. CONCLUSION'
    last_disc=find(doc,next(p.text for p in doc.paragraphs if p.text.startswith('The high-confidence disagreement/error relationship is strongest')))
    next_lim=find(doc,'IX. LIMITATIONS')
    text_like(next_lim,
      'A06 sharpens the distinction between a transductive ranking experiment and operationally frozen per-case review. '
      'At equal batch coverage the fixed mixture can identify more errors in these external tasks, but its validation-frozen threshold can shift the workload on deployment cases, '
      'and the main inference across domains remains descriptive. Stronger audit-only ensemble uncertainty baselines did not dominate. '
      'No claim is made that 32 correlated experimental cells constitute 32 new independent datasets.',base_body)
    limit_anchor=find(doc,'X. CONCLUSION')
    text_like(limit_anchor,
      'The A06 benchmark tasks are historical observational/survey records: their outcomes and sampling mechanisms differ from modern deployment. '
      'RAND HIE may contain within-person dependence not captured by the provided feature table; Modechoice is evaluated as an alternative-level binary task, '
      'not a full multinomial choice-set decision. Even grouping all traveller alternatives during splitting cannot cure that modeling limitation. '
      'A06 uses only two re-partitions of the same four datasets, is not externally preregistered and supplies no truly novel institutional or temporal cohort. '
      'The conditional row/bootstrap intervals are neither multiplicity-corrected nor proof of universality.',base_body)
    concl=find(doc,next(p.text for p in doc.paragraphs if p.text.startswith('The frozen A01 and expanded exploratory A02 findings remain unchanged.')))
    concl.runs[0].text=(concl.text+
      ' External A06 further distinguishes exact-budget ranking from validation-frozen streaming review: '
      'the combined score improved 18/32 dependent cells at exactly matched batch review counts, but only 17/32 under fixed per-case thresholds, '
      'where coverage was sometimes different. The evidence is positive in several model–domain regimes but is not a universal selective-risk guarantee.')
    reference_anchor=find(doc,next(p.text for p in doc.paragraphs if p.text.startswith('[21] S. Rabanser')))
    # Add after last existing reference, retaining its font through a fresh paragraph.
    ref=doc.add_paragraph()
    rr=ref.add_run('[22] S. Seabold and J. Perktold, "Statsmodels: Econometric and Statistical Modeling with Python," in Proc. SciPy, pp. 92–96, 2010, doi: 10.25080/Majora-92bf1922-011.')
    rr.font.name='Times New Roman';rr.font.size=Pt(8)
    reference_anchor._p.addnext(ref._p)
    out.parent.mkdir(parents=True,exist_ok=True)
    doc.save(out)
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(make(a.base,a.output))

if __name__=='__main__': main()
