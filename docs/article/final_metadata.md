# RuFLEX: final article metadata draft

Дата обновления: 2026-04-13

Этот файл фиксирует безопасную финальную формулировку для статьи на основе текущего кода репозитория.

## Рекомендуемое название

### Русский

`RuFLEX: гибридная платформа глубокого нечеткого обучения для геоданных с интерпретируемым анализом правил, факторов и скрытых концептов`

### English

`RuFLEX: A Hybrid Deep Fuzzy Learning Platform for Geodata with Interpretable Analysis of Rules, Factors, and Hidden Concepts`
## Финальная аннотация

### Русский

В работе представлена платформа RuFLEX для гибридного глубокого нечеткого обучения, ориентированная на задачи геоаналитики, пространственно обусловленной классификации, прогнозирования и интеллектуальной поддержки принятия решений. В отличие от black-box-подходов, RuFLEX объединяет интерпретируемые rule-based механизмы, дифференцируемые нечеткие слои и архитектуры deep fuzzy feature learning в едином контуре, реализованном на Python и PyTorch. Платформа поддерживает задание переменных, лингвистических термов, функций принадлежности и правил, обучение параметров функций принадлежности, локальных rule bases и скрытых представлений, а также сравнение плоских neuro-fuzzy baseline-моделей и глубоких нечетких конфигураций. Программное ядро реализовано в виде Python SDK и toolbox-style API, а пользовательский контур включает веб-интерфейс визуального проектирования, средства воспроизводимых экспериментов и Explainability Dashboard для анализа фаззификации, активированных правил, скрытых концептов и вклада факторов в итоговое решение. Архитектура платформы допускает дальнейшее расширение в сторону пространственных fuzzy-модулей, углубленной логической прослеживаемости и контрфактуального анализа.

### English

This paper presents RuFLEX, a platform for hybrid deep fuzzy learning oriented toward geoanalytics, spatially informed classification, forecasting, and intelligent decision support. In contrast to black-box approaches, RuFLEX combines interpretable rule-based mechanisms, differentiable fuzzy layers, and deep fuzzy feature-learning architectures within a unified workflow implemented in Python and PyTorch. The platform supports the definition of variables, linguistic terms, membership functions, and rules; the training of membership-function parameters, local rule bases, and hidden representations; and the comparison of flat neuro-fuzzy baseline models against deeper fuzzy configurations. The software core is delivered as a Python SDK and toolbox-style API, while the user-facing contour includes a web-based visual modeling interface, reproducible experiment tooling, and an Explainability Dashboard for analyzing fuzzification, activated rules, hidden concepts, and factor contributions to the final decision. The platform is designed to be extensible toward spatial fuzzy modules, stronger logical traceability, and counterfactual analysis in future work.

## Ключевые слова

### Русский

- глубокое нечеткое обучение
- hybrid neuro-fuzzy models
- deep fuzzy feature learning
- explainability
- геоаналитика
- интерпретируемое машинное обучение

### English

- deep fuzzy learning
- hybrid neuro-fuzzy models
- deep fuzzy feature learning
- explainability
- geoanalytics
- interpretable machine learning
## Важная граница claims

Что заявляется как реализованное:

- flat neuro-fuzzy baseline
- deep fuzzy feature learning
- совместимое дифференцируемое обучение
- explainability по membership functions, rules, hidden concepts и factor contributions
- reproducible experiment pipeline

Что остается как future work:

- зрелый spatial/deep fuzzy модуль
- полноценная logical traceability engine
- counterfactual explainability

## Привязка к article suite

Актуальный article suite:

- `experiments/article_suite/2026_04_12t21_40_59_671052_00_00_article_suite`

Актуальные benchmark directories:

- regression: `experiments/article_benchmark/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark`
- classification: `experiments/article_benchmark/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark`

Лучшие результаты текущего article suite:

- `California Housing Regression`: `Deep Research`, `test_rmse = 0.795757`, `test_r2 = 0.507159`
- `California Value Binary Geo`: `Flat Interpretable`, `test_accuracy = 0.746341`, `test_f1 = 0.739348`

Основные figure assets:

- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/article_board_regression.png`
- `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark/article_board_classification.png`
- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/results_overview.png`
- `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark/results_overview.png`
- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/membership_medinc.png`
