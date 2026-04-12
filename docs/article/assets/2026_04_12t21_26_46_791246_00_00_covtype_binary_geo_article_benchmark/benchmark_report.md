# Article Benchmark Report

- generated_at_utc: 2026-04-12T21:29:05.281069+00:00
- source_project: covtype_binary_geo
- task_type: binary_classification
- target_name: CoverTypeBinary
- benchmark_dir: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_26_46_791246_00_00_covtype_binary_geo_article_benchmark

## Variants
- Flat Baseline (`flat_baseline_benchmark`): Reference flat neuro-fuzzy baseline for the article tables.
- Flat Interpretable (`interpretable_flat_study`): Compact interpretable flat model for rule-oriented comparison.
- Deep Article Demo (`deep_article_demo`): Primary deep fuzzy feature learning configuration for the paper.
- Deep Research (`deep_research_study`): Broader deep fuzzy configuration for extended article comparisons.

## Results

| variant_name | variant_label | article_role | study_pipeline | training_preset | model_kind | test_accuracy | test_precision | test_recall | test_f1 | epochs_ran | export_dir | training_preset_override | training_source | train_accuracy | train_precision | train_recall | train_f1 | validation_accuracy | validation_precision | validation_recall | validation_f1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_baseline | Flat Baseline | baseline | flat_baseline_benchmark | balanced | flat_neuro_fuzzy | 0.488333 | 0.488333 | 1.000000 | 0.656215 | 14 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_26_46_791246_00_00_covtype_binary_geo_article_benchmark/runs/2026_04_12t21_26_52_215631_00_00_flat_baseline_benchmark |  | bootstrap_plus_finetuning | 0.505278 | 0.505278 | 1.000000 | 0.671342 | 0.495833 | 0.495833 | 1.000000 | 0.662953 |
| flat_interpretable | Flat Interpretable | interpretable_baseline | interpretable_flat_study | interpretable | flat_neuro_fuzzy | 0.488333 | 0.488333 | 1.000000 | 0.656215 | 28 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_26_46_791246_00_00_covtype_binary_geo_article_benchmark/runs/2026_04_12t21_27_22_318960_00_00_interpretable_flat_study |  | bootstrap_plus_finetuning | 0.505278 | 0.505278 | 1.000000 | 0.671342 | 0.495833 | 0.495833 | 1.000000 | 0.662953 |
| deep_article_demo | Deep Article Demo | primary_deep_model | deep_article_demo | article_demo | deep_fuzzy_feature_learning | 0.488333 | 0.488333 | 1.000000 | 0.656215 | 14 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_26_46_791246_00_00_covtype_binary_geo_article_benchmark/runs/2026_04_12t21_27_51_427931_00_00_deep_article_demo |  | stagewise_pretraining_plus_finetuning | 0.505278 | 0.505278 | 1.000000 | 0.671342 | 0.495833 | 0.495833 | 1.000000 | 0.662953 |
| deep_research | Deep Research | extended_deep_model | deep_research_study | article_demo | deep_fuzzy_feature_learning | 0.515833 | 0.503671 | 0.585324 | 0.541436 | 28 | /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_26_46_791246_00_00_covtype_binary_geo_article_benchmark/runs/2026_04_12t21_29_05_245408_00_00_deep_research_study |  | stagewise_pretraining_plus_finetuning | 0.520000 | 0.522739 | 0.575041 | 0.547644 | 0.517500 | 0.511696 | 0.588235 | 0.547303 |

## Suggested Winners

- test_accuracy: `Deep Research` (0.515833)
- test_f1: `Flat Baseline` (0.656215)
- test_recall: `Flat Baseline` (1.000000)