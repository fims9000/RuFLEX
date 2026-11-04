# R6 development in response to prior reviews

This is a research-development response, not an appeal letter or claim that ACDSA 2027 paper #1326 has been reconsidered.

## Reviewer 3: a priori reproducibility and conditions ensuring it

The original manuscript studied observed cross-run agreement, but lacked a principled statement about when stable decisions can be relied upon for action. R5 added conditional decision value and basic probabilistic certificates. R6 addresses a more fundamental **limitation**: even if repeated models agree and source-label evidence strongly favors a review gate, the value can reverse under changes in the unobserved conditional error law. This is not contradicted by high confidence or observed agreement.

R6 states what can and cannot be guaranteed: an exact policy-switch gain decomposition; a same-observables opposite-utility counterexample; an epsilon-rho conditional-shift bound that is tight in the constructed example; and a labelled independent switch-set check with explicitly limited IID validity. Crucially, no shift radius can be identified from unlabelled confidence and disagreement alone. We **do not** claim unconditional prediction or review reproducibility.

## Reviewer 4: generalizability beyond three datasets

Beyond A01's three original datasets, R2–R5 added multiple exploratory tabular and chronological tasks. R6 adds two previously unused temporal datasets with a five-part chronological split, keeping risk fitting separate from threshold calibration and labelled certification. Unlike repeated seed retraining counts, the two new temporal sources are genuine independent *data sources*, though historical, modestly sized, and not samples of broad populations or multiple institutions. All eight model cells are reported, with **three wins, two losses and three ties**, and the independent rule did not authorize augmentation in any cell (0/8). A06/R5 evidence is correctly marked retrospective; no indiscriminate pooling across correlated cells.

## Meaningful negative findings

A positive source estimate is not sufficient evidence of a robust target benefit. In a known-risk conditional-label reversal, increasing labelled source calibration data raises source-side certification from about 8% at n=100 to 100% at n>=1600, while the target action is harmful. Under the real chronological challenge, certification lacked power and declined to activate. This is an informative refusal, not a 'failed experiment' to hide.

## Unresolved research questions

Theoretical novelty must be assessed against prior robust decision-making/selective-classification results; the current counterexample and bounds are mathematically elementary in isolation. A next study should use multiple genuinely independent institutional/time deployments, externally frozen objectives, justified target conditional-shift bounds from refreshed labelled samples, measured review costs and human reviewer accuracy, and inference at data-source level rather than treating retrainings as independent observations.
