# RuFLEX: текущее состояние относительно ТЗ и abstract

Дата среза: 2026-04-12

Этот файл фиксирует не идеальный замысел, а фактическое состояние текущего кода в репозитории.

## 1. Краткий вывод

На текущий момент репозиторий уже соответствует ядру первой версии платформы RuFLEX:

- есть собственный платформенный слой `src/ruflex`;
- deep fuzzy backend берется из vendored snapshot `src/ruanfis`;
- реализованы две основные конфигурации первой версии:
  - `flat_neuro_fuzzy`;
  - `deep_fuzzy_feature_learning`;
- есть Python SDK, toolbox-style API, Streamlit workbench, explainability payloads, сериализация, experiment history и study pipelines.

Главные незавершенные зоны относительно ТЗ и abstract:

- `spatial/deep fuzzy` пока только экспериментальный каркас;
- нет реализованного контрфактуального explainability;
- нет полноценной логической прослеживаемости правил в том смысле, как это можно было бы вынести в заголовок статьи как уже завершенную функцию;
- нет прикладной валидации на целевых геодатасетах и готовых article-grade результатов;
- в текущем окружении не выполнен runtime smoke / pytest из-за отсутствующих `pandas` и `pytest`.

## 2. Матрица покрытия ТЗ

| Блок ТЗ | Статус | Что есть в коде | Комментарий |
|---|---|---|---|
| Ядро платформы | Реализовано | `src/ruflex/core`, `src/ruflex/data`, `src/ruflex/io`, `src/ruflex/sdk/project.py` | Базовые сущности платформы есть |
| Переменные, термы, membership functions | Реализовано | `VariableSpec`, membership specs, ручное редактирование в SDK/UI | Поддерживаются Gaussian, generalized bell, triangular, trapezoidal |
| Правила и rule base | Реализовано | `src/ruflex/core/rules.py`, manual rule editing, catalogs, JSON/table/guided UI | Есть ручной ввод, импорт, ограничение числа правил и блоков |
| Базовая плоская neuro-fuzzy модель | Реализовано | `src/ruflex/models/flat_nf/model.py` | Рабочий baseline |
| Deep Fuzzy Feature Learning | Реализовано | `src/ruflex/models/deep_fuzzy_feature_learning/model.py`, vendored `src/ruanfis` | Это главный рабочий исследовательский режим |
| Гибридная дифференцируемая архитектура | Частично реализовано | end-to-end обучение через backend, общие training configs | Есть как текущий контур, но не выделено как отдельное модельное семейство `hybrid_fuzzy` |
| Hidden/final layers | Реализовано | `src/ruflex/models/specs.py`, `configure_deep_model`, concept-flow explainability | Разделение hidden concept layers и decision layer есть |
| Обучение: end-to-end, bootstrap, stage-wise, refinement | Реализовано | `src/ruflex/training/config.py`, `src/ruflex/models/base.py`, `src/ruanfis/*` | Для manual rule bases refinement ограничен |
| Метрики | Реализовано | regression/classification metrics в `Project._compute_metrics` | Есть MSE, RMSE, MAE, R2, accuracy, precision, recall, F1 |
| Регуляризация и структурный контроль | Частично реализовано | rule sparsity, rule length, orthogonality, membership order/overlap/coverage | Часть штрафов идет через backend, но нет отдельного продвинутого UI для всей регуляризации |
| Explainability Dashboard | Реализовано | `src/ruflex/explain/*`, `dashboard`, `concept_flow`, `path_concept_flow`, `rule_chain_flow`, Streamlit tab | Хороший прототип для статьи |
| SDK | Реализовано | `Project`, `Trainer`, `Evaluator`, toolbox API | Функционально покрывает ядро ТЗ |
| Пользовательский интерфейс | Частично реализовано | `src/ruflex/ui/streamlit_app.py` | Есть workbench, но это еще не финальный polished designer |
| Работа с данными | Реализовано / частично | CSV, DataFrame, normalization, split, missing handling | Геоданные пока только как табличные геопризнаки |
| Сохранение и воспроизводимость | Реализовано | manifest, bundle, presets, histories, study pipelines, exported artifacts | Сильная часть текущего состояния |
| Spatial/deep fuzzy режим | Каркас | `src/ruflex/models/spatial_fuzzy/experimental.py` | Пока только scaffold |
| Логическая прослеживаемость правил | Частично реализовано | `path_concept_flow`, `rule_chain_flow` | Есть path/rule-chain анализ, но не полноценный mature traceability module |
| Контрфактуальный анализ | Не реализовано | нет отдельного модуля | Это перспектива, а не текущее ядро |

## 3. Соответствие abstract

### Уже соответствует abstract

- платформа позиционируется именно как платформа, а не как один ANFIS;
- есть гибридный контур поверх PyTorch-совместимого deep fuzzy backend;
- есть совместное обучение membership / rules / hidden representations;
- есть Python SDK;
- есть UI;
- есть Explainability Dashboard и анализ правил, membership functions и вкладов факторов.

### Частично соответствует abstract

- формулировка про `deep fuzzy convolutions` пока поддерживается только как направление развития, а не как готовый боевой модуль;
- ориентация на геоданные есть концептуально, но прикладная валидация на геодатасетах в репозитории пока не оформлена как готовый экспериментальный пакет.

### Пока не стоит заявлять как полностью готовое

- логическая прослеживаемость правил как завершенная feature-area;
- контрфактуальная объяснимость;
- зрелый spatial/deep fuzzy модуль.

## 4. Риск по текущему названию статьи

Текущее предложенное название:

`RuFLEX: гибридная платформа глубокого нечеткого интеллекта для геоданных с логической прослеживаемостью правил и контрфактуальной объяснимостью`

Риск: оно звучит так, будто логическая прослеживаемость и counterfactual explainability уже реализованы как завершенные пользовательские модули. По фактическому коду это пока не так.

Более безопасная формулировка на текущий код:

`RuFLEX: гибридная платформа глубокого нечеткого обучения для геоданных с интерпретируемым анализом правил и факторов`

Если хочется сохранить сильную перспективную формулировку, лучше прямо маркировать это в статье как направление развития, а не как полностью завершенную часть первой версии.

## 5. Что уже можно честно показывать в статье

- архитектуру платформы `RuFLEX -> SDK/UI -> model specs -> vendored deep fuzzy backend`;
- две рабочие модельные конфигурации: flat baseline и deep fuzzy feature learning;
- ручное задание переменных, membership functions и rule bases;
- training presets, study pipelines и reproducibility flow;
- explainability:
  - membership visualization;
  - rule activation/contribution;
  - hidden concept flow;
  - path-based rule chain analysis;
  - project/model reports;
- сохранение проекта и экспорт study artifacts.

## 6. Что еще нужно добить до article-final

### Обязательное

- поднять рабочее Python-окружение и прогнать реальные runtime tests;
- выбрать 1-2 прикладных датасета, желательно с геоориентированными табличными признаками;
- собрать воспроизводимые экспериментальные таблицы качества;
- снять скриншоты UI и explainability;
- зафиксировать final title/abstract/keywords без overclaim.

### Желательно

- оформить benchmark script для article figures;
- сохранить готовые `experiments/...` артефакты для финальных запусков;
- подготовить отдельную папку `docs/article/assets` под рисунки и таблицы статьи.

### Можно оставить как future work

- counterfactual analysis;
- mature logical traceability module;
- spatial fuzzy convolutions;
- перенос части backend в C++.
