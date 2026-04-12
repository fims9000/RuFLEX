# Article Benchmark Report

- generated_at_utc: 2026-04-12T21:39:19.818049+00:00
- source_project: california_value_binary_probe
- task_type: binary_classification
- target_name: HighValue
- benchmark_dir: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_probe/2026_04_12t21_38_43_089515_00_00_california_value_binary_probe_article_benchmark

## Variants
- Flat Baseline (`flat_baseline_benchmark`): Reference flat neuro-fuzzy baseline for the article tables.
- Flat Interpretable (`interpretable_flat_study`): Compact interpretable flat model for rule-oriented comparison.
- Deep Article Demo (`deep_article_demo`): Primary deep fuzzy feature learning configuration for the paper.
- Deep Research (`deep_research_study`): Broader deep fuzzy configuration for extended article comparisons.

## Results

| variant_name | variant_label | article_role | study_pipeline | training_preset | model_kind | test_accuracy | test_precision | test_recall | test_f1 | epochs_ran | export_dir | training_preset_override | training_source | train_accuracy | train_precision | train_recall | train_f1 | validation_accuracy | validation_precision | validation_recall | validation_f1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_baseline | Flat Baseline | baseline | flat_baseline_benchmark | fast_debug | flat_neuro_fuzzy | 0.741463 | 0.741339 | 0.762470 | 0.751756 | 8 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_probe/2026_04_12t21_38_43_089515_00_00_california_value_binary_probe_article_benchmark/runs/2026_04_12t21_38_48_540882_00_00_flat_baseline_benchmark | fast_debug | bootstrap_plus_finetuning | 0.742776 | 0.729968 | 0.755390 | 0.742461 | 0.735043 | 0.740000 | 0.723716 | 0.731768 |
| flat_interpretable | Flat Interpretable | interpretable_baseline | interpretable_flat_study | fast_debug | flat_neuro_fuzzy | 0.662195 | 0.904494 | 0.382423 | 0.537563 | 8 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_probe/2026_04_12t21_38_43_089515_00_00_california_value_binary_probe_article_benchmark/runs/2026_04_12t21_38_52_161028_00_00_interpretable_flat_study | fast_debug | bootstrap_plus_finetuning | 0.695157 | 0.923933 | 0.412935 | 0.570774 | 0.666667 | 0.925000 | 0.361858 | 0.520211 |
| deep_article_demo | Deep Article Demo | primary_deep_model | deep_article_demo | fast_debug | deep_fuzzy_feature_learning | 0.753659 | 0.780051 | 0.724466 | 0.751232 | 8 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_probe/2026_04_12t21_38_43_089515_00_00_california_value_binary_probe_article_benchmark/runs/2026_04_12t21_39_03_298616_00_00_deep_article_demo | fast_debug | bootstrap_plus_finetuning | 0.748067 | 0.760889 | 0.709784 | 0.734449 | 0.736264 | 0.765840 | 0.679707 | 0.720207 |
| deep_research | Deep Research | extended_deep_model | deep_research_study | fast_debug | deep_fuzzy_feature_learning | 0.757317 | 0.832335 | 0.660333 | 0.736424 | 8 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_probe/2026_04_12t21_38_43_089515_00_00_california_value_binary_probe_article_benchmark/runs/2026_04_12t21_39_19_787989_00_00_deep_research_study | fast_debug | bootstrap_plus_finetuning | 0.746846 | 0.810638 | 0.631841 | 0.710158 | 0.730159 | 0.821918 | 0.586797 | 0.684736 |

## Suggested Winners

- test_accuracy: `Deep Research` (0.757317)
- test_f1: `Flat Baseline` (0.751756)
- test_recall: `Flat Baseline` (0.762470)