# RuFLEX article final status

Дата среза: 2026-04-13

## Что уже готово

- рабочее Python-окружение в `.venv`
- импорт модулей времени выполнения и `pytest` проходят
- подготовлены воспроизводимые наборы данных:
  - `experiments/datasets/california_housing_regression`
  - `experiments/datasets/california_value_binary_geo`
- `covtype_binary_geo` сохранен как дополнительный, но не основной набор данных для статьи
- выполнен актуальный пакетный контур экспериментов:
  - `experiments/article_suite/2026_04_12t21_40_59_671052_00_00_article_suite`
- собраны экспериментальные запуски сравнения конфигураций:
  - `experiments/article_benchmark/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark`
  - `experiments/article_benchmark/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark`
- собраны материалы для статьи:
  - `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark`
  - `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark`
- подготовлены рабочие название, аннотация и ключевые слова:
  - `docs/article/final_metadata.md`
- подготовлены черновые материалы для текста статьи:
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
  - `docs/article/shablon_dokladov_template_based.docx`
  - `docs/article/shablon_dokladov_template_based.pdf`
  - `docs/article/shablon_dokladov_illustrated.docx`
  - `docs/article/shablon_dokladov_illustrated.pdf`
  - `docs/article/conference_template_ready_en.md`
  - `docs/article/conference_template_ready_en.docx`
  - `docs/article/conference_template_illustrated_en.docx`
  - `docs/article/conference_template_illustrated_en.pdf`
  - `docs/article/figure_manifest.md`
- подготовлена заготовка для РИНЦ:
  - `docs/article/rinc_draft.md`
  - `docs/article/rinc_draft.docx`
  - `docs/article/rinc_draft.pdf`
- собран пакет материалов для подачи:
  - `docs/article/submission_bundle`
  - `docs/article/submission_bundle.zip`
- подготовлен автоматический контрольный слой перед подачей:
  - `docs/article/manual_finish.md`
  - `docs/article/readiness_report.md`
  - `profile_status`/`submission_status` в отчете готовности для отделения технической готовности от реальной готовности к отправке

## Основной регрессионный пример

Датасет:

- `california_housing_regression`

Лучший вариант:

- `Расширенный глубокий режим`
- `test_rmse = 0.795757`
- `test_mae = 0.593770`
- `test_r2 = 0.507159`

Практический вывод:

- на геоориентированной задаче регрессии глубокое нечеткое формирование признаков выигрывает у плоской базовой конфигурации;
- это хороший основной эксперимент для статьи, потому что он одновременно показывает и качество, и материалы для интерпретации.

Рекомендуемые figures:

- `results_overview.png`
- `best_training_history.png`
- `best_sample_top_rules.png`
- `best_sample_hidden_concepts.png`
- `best_sample_decision_concepts.png`
- `best_sample_fuzzification.png`
- `article_board_regression.png`

## Основной классификационный пример

Датасет:

- `california_value_binary_geo`

Лучший вариант:

- `Плоская интерпретируемая конфигурация`
- `test_accuracy = 0.746341`
- `test_f1 = 0.739348`

Практический вывод:

- бинарный геоориентированный сценарий классификации у нас уже выглядит существенно лучше, чем ранний `covtype_binary_geo`;
- для статьи это хороший второй эксперимент, потому что он показывает, что платформа поддерживает не только регрессию, но и классификацию;
- при этом результат полезен и концептуально: в задаче классификации не обязательно побеждает самый глубокий режим, что хорошо поддерживает тезис о платформе, а не об одной всегда лучшей архитектуре.

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
- сводные панели интерпретации:
  - regression: `article_board_regression.png`
  - classification: `article_board_classification.png`
- название, аннотация и ключевые слова из `docs/article/final_metadata.md`
- черновые разделы статьи из `docs/article/paper_draft.md`
- версии под реальные шаблоны:
  - `docs/article/shablon_dokladov_ready.docx`
  - `docs/article/shablon_dokladov_template_based.docx`
  - `docs/article/conference_template_ready_en.docx`
- версии с уже встроенными таблицами и рисунками:
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
- готовые итоговые рисунки из `docs/article/submission_bundle/figures/`

## Что осталось вручную перед подачей

- заполнить и утвердить `docs/article/article_profile.json`, если еще не внесены реальные данные авторов, аффилиаций, адресов электронной почты и ORCID
- отметить завершенные ручные шаги в `docs/article/submission_state.json`
- при необходимости подправить и дополнить стартовый список литературы под требования площадки
- утвердить, остаются ли сводные панели интерпретации основными иллюстрациями, или дополнительно вставить 1-2 отдельные рисунка интерпретации
- вручную сделать 1-2 нормальных снимка пользовательского интерфейса Streamlit только если площадка требует именно изображения интерфейса
- вставить реальные подписи к рисункам в шаблон статьи
- вручную сделать проверку в системе антиплагиата и вставить снимок экрана в РИНЦ-файл
- вручную проверить итоговую верстку `.docx` после автоматической подстановки авторов, литературы и рисунков
