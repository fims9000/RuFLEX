# R7 audit findings after the local protocol freeze

**Does not alter original protocol or erase original outputs.**

1. **Power feasibility** (`code/power_audit.py`): the six-year annual e-value mixture cannot reach the predeclared threshold 20, even with all possible gains set to +1. Maximum 5.32237. Therefore the frozen gate cannot promote any policy. This discovery was made *after* running the new panel and is honestly classified as a post-hoc critical design finding.
2. **Baseline strengthening** (`code/benchmark_baselines.py`): raw-confidence, disagreement-only and a fixed simple combined score were evaluated using frozen validation-only threshold calibration. All such comparisons are post-hoc and must be reported as controls, not used to retroactively select a winning primary endpoint.
3. **Descriptive resampling** (`code/analyze_panel.py`): separate naive case-level and year-level bootstrap ranges are given for sensitivity only; neither is a defensible population confidence interval without its dependence assumptions.

For the next clean confirmatory study, run the e-value feasibility test **before** making any model fit, register effect size and dependence assumptions, and assess future utility on multiple independent institutional domains.
