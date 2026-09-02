# S03 Statistical Analysis Plan

Primary estimates are family- and validator-specific detection proportions with 95% Wilson intervals. Clean false-rejection proportions use the same interval. Denominators include only applicable checks; `NOT_APPLICABLE`, `NOT_AVAILABLE`, and `INVALID_INPUT` are reported as coverage categories, not failures or successes.

Primary comparisons are: identity-only versus combined for identity-visible failures; metric-only versus combined for quality-only failures; combined across failure families; clean false rejection; and applicability. Paired comparisons use the same matched clean/corrupt pair and exact McNemar test only where both paired binary outcomes are defined. Holm adjustment applies within each pre-declared comparison family. No global XAI trust score is created.

Localization is correct when the product-native reason identifies the injected component (for example model identity, preprocessing identity, sample/target identity, reference identity, repeatability, or numerical completeness). Generic failure is reported separately, not credited as correct localization. Reopen/replay agreement is reported as a proportion. Runtime is descriptive.

Undefined proportions use null plus a reason code. A missing Quantus counterpart is `NOT_AVAILABLE`; explainer concepts not present are `NOT_APPLICABLE`. Negative results, false rejections, disagreements with Quantus, and unstable/expensive checks remain in primary tables. Future claims are limited to constructed failure families and the declared RuFLEX mechanisms.
