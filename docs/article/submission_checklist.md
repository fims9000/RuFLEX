# RuFLEX: что нужно для статьи и подачи

Этот чеклист собран по текущему ТЗ, abstract и найденным в репозитории шаблонам:

- `1.-conference-paper-template.doc`
- `shablon-dokladov.doc`
- `fajl-dlya-rinc.doc`

## 1. Пакет статьи

Нужно подготовить:

- название статьи на русском;
- название статьи на английском;
- список авторов;
- организации и аффилиации;
- e-mail и ORCID;
- аннотацию на русском;
- abstract на английском;
- ключевые слова на русском;
- keywords на английском;
- раздел о финансировании, если он есть;
- список литературы в требуемом формате;
- финальный PDF статьи;
- отдельный файл для РИНЦ;
- скриншот антиплагиата с уникальностью не менее 75%, если это обязательное требование оргкомитета.

## 2. Что требуют шаблоны по структуре текста

Из `shablon-dokladov.doc` и `1.-conference-paper-template.doc` следуют минимальные обязательные части:

- введение / обзор литературы;
- основная часть:
  - постановка задачи;
  - архитектура платформы;
  - методология обучения;
  - explainability;
  - результаты экспериментов;
- заключение;
- дальнейшие перспективы;
- благодарности / funding при необходимости;
- список литературы.

## 3. Что нужно собрать из репозитория для статьи

### Архитектурные материалы

- схема слоев платформы:
  - `RuFLEX SDK/UI`
  - model specs
  - training/explainability
  - vendored `ruanfis` backend
- схема deep fuzzy feature learning контура;
- схема потока explainability:
  - fuzzification
  - rule activation
  - hidden concepts
  - final decision

### Иллюстрации

- графики membership functions;
- training history;
- example dashboard screenshot;
- concept flow / rule chain flow example;
- screenshot workbench:
  - Data
  - Variables
  - Rules
  - Training
  - Explainability
  - Experiment Browser

### Таблицы

- сравнение flat baseline vs deep fuzzy feature learning;
- метрики на train/validation/test;
- краткая таблица интерпретируемости:
  - число правил;
  - число активных блоков;
  - число hidden concepts;
  - manual rule targets;
- таблица ablation / preset comparison, если успеваем.

## 4. Что еще не собрано и нужно сделать

### Код и эксперименты

- `done`: поднято рабочее окружение с `.venv`, `pandas`, `pytest`, `torch`, `streamlit`;
- `done`: прогнаны smoke и runtime tests;
- `done`: выбраны и подготовлены датасеты `california_housing_regression` и `california_value_binary_geo`;
- `done`: выполнен воспроизводимый `article suite` и сохранены артефакты в `experiments/...`;
- `done`: собраны article-grade таблицы и figure assets в `docs/article/assets/...`;
- `done`: classification showcase переведен на более сильную постановку `california_value_binary_geo`;
- `done`: собран `docs/article/submission_bundle.zip`;
- `done`: подготовлен `docs/article/manual_finish.md` и будущий `docs/article/readiness_report.md`;
- `done`: собираются PDF-версии ключевых article документов;
- `done`: добавлен `docs/article/submission_state.json` для фиксации ручной готовности к отправке;

### Текст статьи

- `done`: синхронизирован безопасный title/abstract/keywords в `docs/article/final_metadata.md`;
- `done`: собран черновик статьи в `docs/article/paper_draft.md`;
- `done`: подготовлены template-ready версии под `shablon-dokladov.doc` и `1.-conference-paper-template.doc`;
- `done`: добавлен стартовый список литературы;
- `done`: прописаны architecture / modes / explainability / setup / discussion / limitations;

### Подача и сопровождение

- `draft ready`: подготовлена текстовая заготовка `docs/article/rinc_draft.md` под `fajl-dlya-rinc.doc`;
- при необходимости дополнить стартовый список литературы;
- заполнить `docs/article/article_profile.json` и пересобрать template-ready / illustrated документы;
- вручную подготовить antiplagiat screenshot после финального текста статьи;
- привести все рисунки к единому стилю и качеству.

## 5. Практический приоритет на ближайшие шаги

### Блок A. Обязательно для финала статьи

- `done`: поднять окружение;
- `done`: прогнать 2-3 воспроизводимых эксперимента;
- `done`: собрать таблицу результатов;
- `done`: отобрать базовые 5 итоговых figures и положить их в `submission_bundle/figures`;
- `done`: зафиксировать title/abstract/keywords.

### Блок B. Очень желательно

- `done`: добавить benchmark/script flow для статьи;
- `done`: оформить папку `docs/article/assets`;
- `done`: сохранить лучшие study runs и сводную таблицу сравнения;
- `done`: подготовить article-ready summary files через benchmark materials packager.

### Блок C. Можно вынести в future work

- counterfactual module;
- full logical traceability engine;
- spatial/deep fuzzy conv module;
- C++ acceleration.
