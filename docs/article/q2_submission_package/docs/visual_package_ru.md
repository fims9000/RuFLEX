# Визуальный пакет статьи RuFLEX

## Назначение

Этот файл фиксирует рекомендуемый финальный набор схем, графиков и скриншотов для статьи и расширенных материалов. Он нужен для того, чтобы в финальную версию попадали не случайные картинки из разных каталогов, а согласованный и воспроизводимый комплект.

## Готовые схемы для основной статьи

1. Общая архитектура платформы:
   `docs/article/generated_figures/scheme1_ruflex_platform_architecture.png`

2. Модельный контур с плоским и глубоким режимами:
   `docs/article/generated_figures/scheme2_model_contour.png`

3. Контур интерпретации и explainability:
   `docs/article/generated_figures/scheme3_explainability_pipeline.png`

## Готовые экспериментальные boards для основной статьи

1. Регрессионная сводная панель:
   `docs/article/assets_q2_final_plus/2026_04_13t10_28_03_935704_00_00_california_housing_regression_article_benchmark/article_board_regression_q2.png`

2. Классификационная сводная панель по California Value Binary Geo:
   `docs/article/assets_q2_final_plus/2026_04_13t10_36_54_637555_00_00_california_value_binary_geo_article_benchmark/article_board_classification_q2.png`

3. Стресс-тест по Covertype Binary Geo:
   `docs/article/assets_q2_final_plus/2026_04_13t10_45_35_740062_00_00_covtype_binary_geo_article_benchmark/article_board_covtype_q2.png`

## Готовые отдельные графики, если нужен более компактный вариант

1. Регрессия, сводные метрики:
   `docs/article/assets_q2_final_plus/2026_04_13t10_28_03_935704_00_00_california_housing_regression_article_benchmark/results_overview.png`

2. California Value Binary Geo, сводные метрики:
   `docs/article/assets_q2_final_plus/2026_04_13t10_36_54_637555_00_00_california_value_binary_geo_article_benchmark/results_overview.png`

3. Covertype Binary Geo, сводные метрики:
   `docs/article/assets_q2_final_plus/2026_04_13t10_45_35_740062_00_00_covtype_binary_geo_article_benchmark/results_overview.png`

4. Примеры функций принадлежности, истории обучения, правил и скрытых концептов:
   брать из соответствующих каталогов `docs/article/assets_q2_final_plus/<benchmark_dir>/`

## Какая benchmark-серия считается финальной

Для основной статьи и расширенных материалов в качестве базовой следует использовать именно серию `article_benchmark_q2_final_plus`. В ней:

1. сохранены многосидовые прогоны по seed `11, 23, 47`;
2. добавлен внешний baseline `Gradient Boosting`;
3. исправлены имена экспортируемых run-каталогов для абляций;
4. графики, boards и численные формулировки в тексте должны ссылаться именно на эту серию.

## Что лучше оставить в основной статье

1. `scheme1_ruflex_platform_architecture.png`
2. `scheme2_model_contour.png`
3. `scheme3_explainability_pipeline.png`
4. `article_board_regression_q2.png`
5. `article_board_classification_q2.png`

Если по объему проходит еще одна иллюстрация, то имеет смысл добавить `article_board_covtype_q2.png` как честный стресс-тест или вынести его в расширенные материалы.

## Что лучше вынести в расширенные материалы

1. Отдельные `results_overview.png` по всем трем задачам.
2. Примеры функций принадлежности.
3. `best_sample_top_rules.png`
4. `best_sample_hidden_concepts.png`
5. `best_sample_decision_concepts.png`
6. `best_sample_fuzzification.png`
7. Текстовые артефакты `best_sample_concept_flow.txt` и `best_sample_rule_chain.txt`

## Какие живые скриншоты интерфейса еще стоит снять

1. Экран конфигурирования проекта:
   переменные, термы, выбор режима `flat/deep`.

2. Экран обучения и benchmark-контура:
   запуск article benchmark, список вариантов, seeds, сохранение артефактов.

3. Экран Explainability Dashboard:
   активные правила, скрытые концепты, вклад факторов.

4. Если нужен один “витринный” скриншот:
   лучше всего брать именно экран Explainability Dashboard, а не стартовую страницу.

## Практический принцип

Для основной статьи лучше смешивать два типа визуализации:

1. Схемы, которые объясняют архитектуру и модельный контур.
2. Живые экспериментальные панели, которые показывают, что платформа реально считает метрики, правила, концепты и интерпретацию.

Скриншоты интерфейса полезны, но не должны подменять собой схемы и экспериментальные boards. Их лучше использовать как 1 дополнительную витринную иллюстрацию в статье или как 2-3 опорных изображения в расширенных материалах.
