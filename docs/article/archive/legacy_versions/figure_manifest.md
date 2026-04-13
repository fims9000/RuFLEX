# RuFLEX figure manifest

## Схемы платформы

### Схема 1. Архитектура платформы

Файл:

- `docs/article/generated_figures/scheme1_ruflex_platform_architecture.png`
- `docs/article/submission_bundle/figures/scheme1_ruflex_platform_architecture.png`

Подпись:

- Общая архитектура RuFLEX: вычислительное ядро глубокого нечеткого вывода, платформенный слой, программный интерфейс, пользовательская оболочка, контур интерпретации и исследовательский контур экспериментов.

### Схема 2. Модельный контур

Файл:

- `docs/article/generated_figures/scheme2_model_contour.png`
- `docs/article/submission_bundle/figures/scheme2_model_contour.png`

Подпись:

- Модельный контур RuFLEX: плоская нейро-нечеткая конфигурация и глубокое нечеткое формирование признаков в единой платформе.

### Схема 3. Контур интерпретации

Файл:

- `docs/article/generated_figures/scheme3_explainability_pipeline.png`
- `docs/article/submission_bundle/figures/scheme3_explainability_pipeline.png`

Подпись:

- Контур интерпретации: от фаззификации объекта к активированным правилам, скрытым концептам и итоговым отчетам.

## Основной набор рисунков для статьи

### Рисунок 1. Сводный график регрессии

Файл:

- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/results_overview.png`
- `docs/article/submission_bundle/figures/figure1_regression_benchmark.png`

Подпись:

- Сравнение конфигураций RuFLEX на задаче California Housing Regression.

### Рисунок 2. Панель интерпретации для регрессии

Файл:

- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/article_board_regression.png`
- `docs/article/submission_bundle/figures/figure2_regression_board.png`

Подпись:

- Пример панели интерпретации RuFLEX для лучшей конфигурации на задаче регрессии: сводка результатов, история обучения, вклад активированных правил и скрытые концепты.

### Рисунок 3. Сводный график классификации

Файл:

- `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark/results_overview.png`
- `docs/article/submission_bundle/figures/figure3_classification_benchmark.png`

Подпись:

- Сравнение конфигураций RuFLEX на задаче California Value Binary Geo.

### Рисунок 4. Панель интерпретации для классификации

Файл:

- `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark/article_board_classification.png`
- `docs/article/submission_bundle/figures/figure4_classification_board.png`

Подпись:

- Панель интерпретации для лучшей конфигурации на задаче классификации: история обучения, наиболее активные правила и скрытые концепты.

### Рисунок 5. Функции принадлежности

Варианты:

- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/membership_medinc.png`
- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/membership_houseage.png`
- `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark/membership_medinc.png`
- `docs/article/submission_bundle/figures/figure5_membership_example.png`

Подпись:

- Примеры функций принадлежности, используемых RuFLEX для интерпретируемой фаззификации входных признаков.

## Таблицы

### Таблица 1. Результаты на задаче регрессии

Файл:

- `docs/article/submission_bundle/tables/regression_results_table.csv`

Подпись:

- Сравнение четырех конфигураций RuFLEX на задаче California Housing Regression по метрикам `test_rmse`, `test_mae` и `test_r2`.

### Таблица 2. Результаты на задаче классификации

Файл:

- `docs/article/submission_bundle/tables/classification_results_table.csv`

Подпись:

- Сравнение четырех конфигураций RuFLEX на задаче California Value Binary Geo по метрикам `test_accuracy`, `test_precision`, `test_recall` и `test_f1`.

## Дополнительные материалы

- `best_sample_concept_flow.txt`
- `best_sample_rule_chain.txt`
- `benchmark_report.md`
- `article_summary.md`

Эти файлы полезны как исходный материал для разделов статьи, связанных с интерпретацией и обсуждением результатов.
