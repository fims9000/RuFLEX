# RuFLEX article final status

Дата среза: 2026-04-13

## Что уже готово

- рабочее Python-окружение в `.venv`
- runtime imports и `pytest` проходят
- подготовлены reproducible datasets:
  - `experiments/datasets/california_housing_regression`
  - `experiments/datasets/california_value_binary_geo`
- `covtype_binary_geo` сохранен как дополнительный, но не дефолтный article dataset
- выполнен актуальный article suite:
  - `experiments/article_suite/2026_04_12t21_40_59_671052_00_00_article_suite`
- собраны benchmark runs:
  - `experiments/article_benchmark/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark`
  - `experiments/article_benchmark/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark`
- собраны article assets:
  - `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark`
  - `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark`
- подготовлены safe title/abstract/keywords:
  - `docs/article/final_metadata.md`
- подготовлены draft-материалы для текста статьи:
  - `docs/article/paper_draft.md`
  - `docs/article/paper_draft.docx`
  - `docs/article/paper_draft.pdf`
  - `docs/article/article_profile.json`
  - `docs/article/article_profile_card.md`
  - `docs/article/article_references.json`
  - `docs/article/submission_state.json`
  - `docs/article/references_ru_gost.md`
  - `docs/article/references_en_ieee.md`
  - `docs/article/shablon_dokladov_ready.md`
  - `docs/article/shablon_dokladov_ready.docx`
  - `docs/article/shablon_dokladov_illustrated.docx`
  - `docs/article/shablon_dokladov_illustrated.pdf`
  - `docs/article/conference_template_ready_en.md`
  - `docs/article/conference_template_ready_en.docx`
  - `docs/article/conference_template_illustrated_en.docx`
  - `docs/article/conference_template_illustrated_en.pdf`
  - `docs/article/figure_manifest.md`
- подготовлена заготовка под РИНЦ:
  - `docs/article/rinc_draft.md`
  - `docs/article/rinc_draft.docx`
  - `docs/article/rinc_draft.pdf`
- собран submission bundle:
  - `docs/article/submission_bundle`
  - `docs/article/submission_bundle.zip`
- подготовлен pre-submission контрольный слой:
  - `docs/article/manual_finish.md`
  - `docs/article/readiness_report.md`
  - `profile_status`/`submission_status` в readiness-report для отделения технической готовности от реальной submission-ready фазы

## Main regression showcase

Датасет:

- `california_housing_regression`

Лучший вариант:

- `Deep Research`
- `test_rmse = 0.795757`
- `test_mae = 0.593770`
- `test_r2 = 0.507159`

Практический вывод:

- на geo-oriented regression задаче deep fuzzy feature learning выигрывает у flat baseline;
- это хороший основной эксперимент для статьи, потому что он одновременно показывает и качество, и explainability assets.

Рекомендуемые figures:

- `results_overview.png`
- `best_training_history.png`
- `best_sample_top_rules.png`
- `best_sample_hidden_concepts.png`
- `best_sample_decision_concepts.png`
- `best_sample_fuzzification.png`
- `article_board_regression.png`

## Main classification showcase

Датасет:

- `california_value_binary_geo`

Лучший вариант:

- `Flat Interpretable`
- `test_accuracy = 0.746341`
- `test_f1 = 0.739348`

Практический вывод:

- бинарный geo-classification сценарий у нас уже выглядит существенно лучше, чем ранний `covtype_binary_geo`;
- для статьи это хороший второй эксперимент, потому что он показывает, что платформа поддерживает не только regression, но и classification;
- при этом результат еще и полезен концептуально: на classification не обязательно побеждает самый глубокий режим, что хорошо поддерживает тезис о платформе, а не об одной “всегда лучшей” архитектуре.

Рекомендуемые figures:

- `results_overview.png`
- `best_training_history.png`
- `best_sample_top_rules.png`
- `best_sample_hidden_concepts.png`
- `best_sample_decision_concepts.png`
- `best_sample_fuzzification.png`
- `article_board_classification.png`

## Что уже можно прямо вставлять в статью

- основные таблицы результатов из `results_table.csv` / `results_table.md`
- сводные article boards:
  - regression: `article_board_regression.png`
  - classification: `article_board_classification.png`
- title / abstract / keywords из `docs/article/final_metadata.md`
- narrative draft sections из `docs/article/paper_draft.md`
- template-ready версии под реальные шаблоны:
  - `docs/article/shablon_dokladov_ready.docx`
  - `docs/article/conference_template_ready_en.docx`
- illustrated версии с уже встроенными таблицами и figures:
  - `docs/article/shablon_dokladov_illustrated.docx`
  - `docs/article/shablon_dokladov_illustrated.pdf`
  - `docs/article/conference_template_illustrated_en.docx`
  - `docs/article/conference_template_illustrated_en.pdf`
- единый профиль статьи для авторов и аффилиаций:
  - `docs/article/article_profile.json`
- PDF-версии для быстрой отправки и просмотра:
  - `docs/article/paper_draft.pdf`
  - `docs/article/rinc_draft.pdf`
- стартовый список литературы из раздела `References` в `docs/article/paper_draft.md`
- готовые имена итоговых рисунков из `docs/article/submission_bundle/figures/`

## Что осталось вручную перед подачей

- заполнить и утвердить `docs/article/article_profile.json`, если еще не внесены реальные authors / affiliations / e-mail / ORCID
- отметить завершенные ручные шаги в `docs/article/submission_state.json`
- при необходимости подправить и дополнить стартовый список литературы под требования площадки
- утвердить, остаются ли article boards основными иллюстрациями, или дополнительно вставить 1-2 отдельные explainability figures
- вручную сделать 1-2 нормальных UI screenshots из Streamlit только если площадка требует именно screenshots интерфейса
- вставить реальные figure captions в шаблон статьи
- вручную сделать antiplagiat check и вставить скриншот в РИНЦ-файл
- вручную проверить итоговую верстку `.docx` после автоматической подстановки авторов, литературы и рисунков
