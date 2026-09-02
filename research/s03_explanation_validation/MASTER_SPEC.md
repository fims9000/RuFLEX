# S03 Master Specification

Frozen models/explainers are the compatible native combinations in `config/matrix.json`: logistic regression (occlusion/permutation SHAP); decision tree, random forest and gradient boosting (occlusion/TreeSHAP); Flat Neuro-Fuzzy (occlusion/integrated gradients/GradientSHAP). No unsupported combination is manufactured to enlarge N.

The exact execution plan is generated deterministically from all dataset/model/explainer/sample/failure/validator-mode/repeat combinations. CLEAN rows are controls. Quantitative failures have three locked severity levels. Identity failures have `severity=NONE`. Each execution row contains an expected detection mechanism and never embeds a product result.
