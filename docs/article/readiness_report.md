# RuFLEX article readiness report

- generated_at: `2026-04-12T22:28:16.567680+00:00`
- suite_dir: `/home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_suite/2026_04_12t21_40_59_671052_00_00_article_suite`
- overall_status: `pass`

## Critical automated checks

- `PASS` doc:docs/article/final_metadata.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/final_metadata.md
- `PASS` doc:docs/article/final_status.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/final_status.md
- `PASS` doc:docs/article/paper_draft.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/paper_draft.md
- `PASS` doc:docs/article/paper_draft.docx: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/paper_draft.docx
- `PASS` doc:docs/article/article_profile.template.json: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/article_profile.template.json
- `PASS` doc:docs/article/article_profile.json: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/article_profile.json
- `PASS` doc:docs/article/article_profile_card.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/article_profile_card.md
- `PASS` doc:docs/article/template_mapping.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/template_mapping.md
- `PASS` doc:docs/article/shablon_dokladov_ready.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/shablon_dokladov_ready.md
- `PASS` doc:docs/article/shablon_dokladov_ready.docx: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/shablon_dokladov_ready.docx
- `PASS` doc:docs/article/shablon_dokladov_illustrated.docx: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/shablon_dokladov_illustrated.docx
- `PASS` doc:docs/article/conference_template_ready_en.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/conference_template_ready_en.md
- `PASS` doc:docs/article/conference_template_ready_en.docx: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/conference_template_ready_en.docx
- `PASS` doc:docs/article/conference_template_illustrated_en.docx: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/conference_template_illustrated_en.docx
- `PASS` doc:docs/article/figure_manifest.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/figure_manifest.md
- `PASS` doc:docs/article/manual_finish.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/manual_finish.md
- `PASS` doc:docs/article/rinc_draft.md: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/rinc_draft.md
- `PASS` doc:docs/article/rinc_draft.docx: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/rinc_draft.docx
- `PASS` submission_bundle_dir: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle
- `PASS` submission_bundle_zip: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle.zip
- `PASS` regression:benchmark_dir: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark
- `PASS` regression:materials_dir: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark
- `PASS` regression:best_variant: {"variant_label": "Deep Research", "metrics": {"test_mse": 0.6332284870728699, "test_mae": 0.593769591318177, "test_rmse": 0.7957565501287878, "test_r2": 0.5071592215120452}}
- `PASS` binary_classification:benchmark_dir: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_benchmark/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark
- `PASS` binary_classification:materials_dir: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark
- `PASS` binary_classification:best_variant: {"variant_label": "Flat Interpretable", "metrics": {"test_accuracy": 0.7463414634146341, "test_precision": 0.7430730478589401, "test_recall": 0.7356608478802974, "test_f1": 0.7393483709268163}}
- `PASS` figure:figure1_regression_benchmark.png: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/figures/figure1_regression_benchmark.png
- `PASS` figure:figure2_regression_board.png: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/figures/figure2_regression_board.png
- `PASS` figure:figure3_classification_benchmark.png: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/figures/figure3_classification_benchmark.png
- `PASS` figure:figure4_classification_board.png: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/figures/figure4_classification_board.png
- `PASS` figure:figure5_membership_example.png: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/figures/figure5_membership_example.png
- `PASS` table:article_suite_results.csv: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/tables/article_suite_results.csv
- `PASS` table:regression_results_table.csv: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/tables/regression_results_table.csv
- `PASS` table:classification_results_table.csv: /home/lebedeffson/Code/neurofuzzy_analysis/docs/article/submission_bundle/tables/classification_results_table.csv
- `PASS` pytest_article_suite: ..........                                                               [100%]

## Best benchmark results

- `regression`: california_housing_regression -> Deep Research (test_mse=0.6332284870728699, test_mae=0.593769591318177, test_rmse=0.7957565501287878, test_r2=0.5071592215120452)
- `binary_classification`: california_value_binary_geo -> Flat Interpretable (test_accuracy=0.7463414634146341, test_precision=0.7430730478589401, test_recall=0.7356608478802974, test_f1=0.7393483709268163)

## Test run

- returncode: `0`
- detail: `..........                                                               [100%]`

## Manual items

- `pending` Вписать authors / affiliations / e-mail / ORCID в docx-шаблоны.
- `pending` Проверить и при необходимости дополнить стартовый список литературы под формат площадки.
- `pending` Выполнить antiplagiat check и приложить реальный скриншот в РИНЦ-файл.
- `pending` Проверить итоговую верстку после вставки рисунков, подписей и авторских данных.