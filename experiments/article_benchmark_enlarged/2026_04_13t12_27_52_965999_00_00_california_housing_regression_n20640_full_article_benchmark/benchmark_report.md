# Article Benchmark Report

- generated_at_utc: 2026-04-13T12:38:02.501848+00:00
- source_project: california_housing_regression_n20640_full
- task_type: regression
- target_name: MedHouseVal
- benchmark_dir: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_enlarged/2026_04_13t12_27_52_965999_00_00_california_housing_regression_n20640_full_article_benchmark
- seed_count: 3
- seeds: [11, 23, 47]

## RuFLEX Variants
- Flat Baseline (`flat_baseline` / `balanced`): Reference flat neuro-fuzzy baseline for the main comparison table.
- Deep Depth 1 (`deep_article_demo` / `article_demo`): Depth ablation with a single hidden concept stage.
- Deep Article Demo (`deep_article_demo` / `article_demo`): Reference deep fuzzy feature learning configuration for the paper.

## External Baselines

- Linear Regression
- Gradient Boosting
- Random Forest
- MLP

## Aggregated Results

| model_name | model_label | family | article_role | variant_name | workspace_template | training_preset | runs | best_seed | test_rmse_mean | test_rmse_std | test_mae_mean | test_mae_std | test_r2_mean | test_r2_std | export_dir | variant_label | study_pipeline | training_preset_override | seed_values | train_mse_mean | train_mse_std | train_mae_mean | train_mae_std | train_rmse_mean | train_rmse_std | train_r2_mean | train_r2_std | test_mse_mean | test_mse_std | structure_total_rules_mean | structure_total_rules_std | structure_active_rules_mean | structure_active_rules_std | structure_stages_mean | structure_stages_std | structure_hidden_blocks_mean | structure_hidden_blocks_std | structure_hidden_concepts_mean | structure_hidden_concepts_std | explainability_decision_top1_mass_mean | explainability_decision_top1_mass_std | explainability_decision_top3_mass_mean | explainability_decision_top3_mass_std | explainability_decision_entropy_mean | explainability_decision_entropy_std | explainability_hidden_top1_mass_mean | explainability_hidden_top1_mass_std | explainability_hidden_top3_mass_mean | explainability_hidden_top3_mass_std | explainability_hidden_entropy_mean | explainability_hidden_entropy_std | stability_generated_rule_jaccard | stability_active_rule_jaccard | stability_hidden_generated_rule_jaccard | stability_hidden_active_rule_jaccard | stability_decision_generated_rule_jaccard | stability_decision_active_rule_jaccard | stability_layer_active_rule_jaccard | stability_layer_generated_rule_jaccard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| linear_regression | Linear Regression | sklearn | external_baseline |  |  |  | 3 | 47 | 0.800938 | 0.106100 | 0.538741 | 0.003969 | 0.518054 | 0.131276 |  |  |  |  | 11,23,47 | 0.527667 | 0.005567 | 0.530819 | 0.003773 | 0.726397 | 0.003829 | 0.601476 | 0.005498 | 0.652759 | 0.177908 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| hist_gradient_boosting_regressor | Gradient Boosting | sklearn | external_baseline |  |  |  | 3 | 11 | 0.485782 | 0.001402 | 0.334018 | 0.001134 | 0.825761 | 0.001233 |  |  |  |  | 11,23,47 | 0.193734 | 0.000328 | 0.302777 | 0.001177 | 0.440152 | 0.000373 | 0.853684 | 0.000881 | 0.235986 | 0.001363 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| random_forest_regressor | Random Forest | sklearn | external_baseline |  |  |  | 3 | 47 | 0.513520 | 0.003764 | 0.340443 | 0.003095 | 0.805277 | 0.003466 |  |  |  |  | 11,23,47 | 0.038259 | 0.000429 | 0.126464 | 0.000166 | 0.195597 | 0.001098 | 0.971105 | 0.000349 | 0.263717 | 0.003864 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| mlp_regressor | MLP | sklearn | external_baseline |  |  |  | 3 | 11 | 0.553489 | 0.019886 | 0.370583 | 0.009353 | 0.773542 | 0.016093 |  |  |  |  | 11,23,47 | 0.263695 | 0.015358 | 0.352168 | 0.010551 | 0.513294 | 0.014977 | 0.800777 | 0.012777 | 0.306745 | 0.022200 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| flat_baseline | Flat Baseline | ruflex | baseline | flat_baseline | flat_baseline | balanced | 3 | 47 | 0.939871 | 0.158677 | 0.720020 | 0.140469 | 0.329199 | 0.233191 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_enlarged/2026_04_13t12_27_52_965999_00_00_california_housing_regression_n20640_full_article_benchmark/runs/2026_04_13t12_35_15_411311_00_00_flat_baseline_benchmark | Flat Baseline | flat_baseline_benchmark |  | 11,23,47 | 0.900577 | 0.307501 | 0.713057 | 0.137101 | 0.936219 | 0.155151 | 0.321316 | 0.226883 | 0.908535 | 0.315978 | 16.000000 | 0.000000 | 8.000000 | 1.414214 | 1.000000 | 0.000000 | 1.000000 | 0.000000 | 3.000000 | 0.000000 | 0.496904 | 0.102950 | 0.896876 | 0.055081 | 1.286557 | 0.236918 | 0.177545 | 0.025375 | 0.519080 | 0.061698 | 1.998823 | 0.025057 | 0.733333 | 0.666667 | 0.733333 | 0.666667 | 0.733333 | 0.666667 | 0.666667 | 0.733333 |
| deep_stage1_ablation | Deep Depth 1 | ruflex | depth_ablation | deep_stage1_ablation | deep_article_demo | article_demo | 3 | 23 | 0.785962 | 0.005450 | 0.590630 | 0.003374 | 0.543854 | 0.007997 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_enlarged/2026_04_13t12_27_52_965999_00_00_california_housing_regression_n20640_full_article_benchmark/runs/2026_04_13t12_33_22_083751_00_00_deep_stage1_ablation | Deep Depth 1 |  |  | 11,23,47 | 0.623559 | 0.005704 | 0.585168 | 0.003121 | 0.789649 | 0.003611 | 0.529057 | 0.005678 | 0.617767 | 0.008571 | 20.000000 | 0.000000 | 4.666667 | 1.247219 | 1.000000 | 0.000000 | 4.000000 | 0.000000 | 8.000000 | 0.000000 | 0.474179 | 0.039039 | 0.954561 | 0.031666 | 1.038137 | 0.240938 | 0.493645 | 0.025341 | 0.732141 | 0.002160 | 0.657867 | 0.035700 | 0.746032 | 0.491667 | 1.000000 | 0.733333 | 0.200000 | 0.333333 | 0.888889 | 1.000000 |
| deep_article_demo | Deep Article Demo | ruflex | primary_deep_model | deep_article_demo | deep_article_demo | article_demo | 3 | 23 | 0.786480 | 0.005422 | 0.590183 | 0.003017 | 0.543251 | 0.008127 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark_enlarged/2026_04_13t12_27_52_965999_00_00_california_housing_regression_n20640_full_article_benchmark/runs/2026_04_13t12_34_34_273908_00_00_deep_article_demo | Deep Article Demo | deep_article_demo |  | 11,23,47 | 0.623997 | 0.005242 | 0.584693 | 0.003882 | 0.789928 | 0.003320 | 0.528731 | 0.004899 | 0.618580 | 0.008538 | 36.000000 | 0.000000 | 5.333333 | 0.471405 | 2.000000 | 0.000000 | 8.000000 | 0.000000 | 16.000000 | 0.000000 | 0.521906 | 0.134071 | 0.999276 | 0.001024 | 0.917472 | 0.140047 | 0.669765 | 0.022579 | 0.862863 | 0.001929 | 0.487718 | 0.045171 | 0.831579 | 0.458333 | 1.000000 | 0.833333 | 0.111111 | 0.083333 | 0.958333 | 1.000000 |

## Suggested Winners

- test_rmse: `Gradient Boosting` (0.485782)
- test_mae: `Gradient Boosting` (0.334018)
- test_r2: `Gradient Boosting` (0.825761)