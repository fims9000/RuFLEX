# RuFLEX: draft article text

## Название

RuFLEX: гибридная платформа глубокого нечеткого обучения для геоданных с интерпретируемым анализом правил, факторов и скрытых концептов

## Аннотация

В работе представлена платформа RuFLEX для гибридного глубокого нечеткого обучения, ориентированная на задачи геоаналитики, пространственно обусловленной классификации, прогнозирования и интеллектуальной поддержки принятия решений. В отличие от black-box-подходов, RuFLEX объединяет интерпретируемые rule-based механизмы, дифференцируемые нечеткие слои и архитектуры deep fuzzy feature learning в едином контуре, реализованном на Python и PyTorch. Платформа поддерживает задание переменных, лингвистических термов, функций принадлежности и правил, обучение параметров функций принадлежности, локальных rule bases и скрытых представлений, а также сравнение плоских neuro-fuzzy baseline-моделей и глубоких нечетких конфигураций. Программное ядро реализовано в виде Python SDK и toolbox-style API, а пользовательский контур включает веб-интерфейс визуального проектирования, средства воспроизводимых экспериментов и Explainability Dashboard для анализа фаззификации, активированных правил, скрытых концептов и вклада факторов в итоговое решение. Архитектура платформы допускает дальнейшее расширение в сторону пространственных fuzzy-модулей, углубленной логической прослеживаемости и контрфактуального анализа.

## 1. Введение

В задачах геоаналитики, пространственно обусловленной классификации, прогнозирования и интеллектуальной поддержки принятия решений требуется сочетание двух свойств: высокой прогностической точности и интерпретируемости модели. На практике это приводит к устойчивому противоречию между точностью black-box архитектур и прозрачностью rule-based подходов. Гибридные neuro-fuzzy методы являются одним из немногих направлений, позволяющих совместить эти требования в едином вычислительном контуре.

В данной работе представлена платформа RuFLEX, ориентированная не на одну конкретную модель, а на расширяемый класс гибридных deep fuzzy архитектур. Платформа поддерживает как плоские интерпретируемые neuro-fuzzy baseline-конфигурации, так и режим deep fuzzy feature learning, в котором скрытые слои формируют новые интерпретируемые нечеткие концепты. Отдельное внимание уделяется explainability-контуру: фаззификации признаков, структуре правил, hidden concepts и вкладу факторов в итоговый вывод.

Основной вклад работы заключается в следующем:

- предложена программная платформа RuFLEX как исследовательская и прикладная среда для гибридного глубокого нечеткого обучения;
- реализован Python SDK и toolbox-style API для задания переменных, membership functions, rule bases, режимов обучения и воспроизводимых экспериментов;
- реализован веб-интерфейс visual workbench и Explainability Dashboard;
- подготовлен воспроизводимый article benchmark контур для сравнения flat и deep fuzzy конфигураций;
- показана прикладная валидация на двух geo-oriented табличных задачах: regression и binary classification.

## 2. Архитектура платформы

RuFLEX реализована как платформенный слой поверх vendored deep fuzzy backend `ruanfis`, заимствованного из репозитория `deep-neuro-fuzzy`. Такое разделение позволяет развивать собственный SDK, UI, serialization, explainability и experiment tooling без жесткой привязки всей системы к одному частному прототипу модели.

Текущая архитектура включает следующие уровни:

- ядро платформы: переменные, термы, membership functions, rules, rule bases, model specs;
- модельный слой: flat neuro-fuzzy baseline и deep fuzzy feature learning;
- training layer: bootstrap initialization, stage-wise pretraining, fine-tuning, refinement loop settings;
- explainability layer: rule records, dashboard payloads, concept flow, rule chain flow;
- инструментальный слой: Python SDK, toolbox-style API, Streamlit workbench, reproducible study pipelines и exported experiment artifacts.

Важно подчеркнуть, что RuFLEX позиционируется именно как платформа. На разных задачах лучшие результаты могут давать разные конфигурации. Это особенно важно для прикладных сценариев, где интерпретируемость и структурная компактность модели иногда оказываются не менее значимыми, чем абсолютный максимум одной метрики качества.

## 3. Поддерживаемые модельные режимы

В первой версии платформы поддерживаются два базовых режима.

### 3.1. Flat neuro-fuzzy baseline

Данный режим используется как интерпретируемый baseline и опирается на компактную структуру rule-based вывода. Он удобен для отладки фаззификации, анализа membership functions и интерпретации локальных правил.

### 3.2. Deep fuzzy feature learning

В этом режиме скрытые слои интерпретируются как механизм построения новых нечетких концептов. Локальные блоки ограничивают рост числа правил, а финальный слой принимает решение уже в пространстве hidden concepts. Такая схема позволяет сохранять explainability и одновременно повышать выразительность модели по сравнению с плоским baseline.

## 4. Explainability контур

Explainability в RuFLEX не ограничивается только итоговой важностью признаков. Платформа предоставляет несколько уровней анализа:

- визуализацию membership functions;
- просмотр rule activation и normalized rule weights;
- анализ вклада правил в hidden concepts;
- анализ hidden concepts в decision layer;
- concept flow и rule chain flow для отдельных объектов;
- project/model reports и exported rule records.

Для подготовки статьи были автоматически сгенерированы explainability assets и article boards, которые позволяют использовать один и тот же воспроизводимый эксперимент и как источник метрик, и как источник иллюстративных материалов.

## 5. Экспериментальная постановка

Для валидации платформы использованы две geo-oriented табличные задачи.

### 5.1. California Housing Regression

Использовалась подвыборка из 4096 наблюдений набора `sklearn.fetch_california_housing` с сохранением пространственных признаков `Latitude` и `Longitude`. Целевая переменная: `MedHouseVal`.

Сравнивались четыре конфигурации:

- Flat Baseline
- Flat Interpretable
- Deep Article Demo
- Deep Research

Лучшей оказалась конфигурация `Deep Research`:

- `test_rmse = 0.795757`
- `test_mae = 0.593770`
- `test_r2 = 0.507159`

Для сравнения, `Flat Baseline` показал:

- `test_rmse = 0.890950`
- `test_mae = 0.678868`
- `test_r2 = 0.382192`

Таким образом, глубокая нечеткая конфигурация в данном сценарии дает более высокое качество по сравнению с flat baseline при сохранении explainability-контура.

### 5.2. California Value Binary Geo

Вторая задача построена на том же наборе California Housing, но в формате binary classification. Была сформирована сбалансированная подвыборка из 4096 объектов, где целевая переменная `HighValue` задается порогом по медиане исходной `MedHouseVal`. Это дает удобную geo-oriented classification постановку без разрыва с предметной логикой данных.

Лучшей оказалась конфигурация `Flat Interpretable`:

- `test_accuracy = 0.746341`
- `test_f1 = 0.739348`

Этот результат важен концептуально: платформа не навязывает единственную “всегда лучшую” архитектуру. На regression-задаче выигрывает более глубокий fuzzy режим, а на binary classification лучшей оказывается более компактная и интерпретируемая конфигурация. Это подтверждает корректность позиционирования RuFLEX именно как платформы для сравнения и настройки модельных режимов.

## 6. Обсуждение результатов

Полученные результаты позволяют сделать несколько выводов.

Во-первых, deep fuzzy feature learning в рамках RuFLEX действительно дает измеримый выигрыш на пространственно информированной regression-задаче. Это поддерживает основную исследовательскую линию работы.

Во-вторых, compact flat configurations остаются конкурентоспособными и в ряде задач могут быть предпочтительнее благодаря лучшей структурной интерпретируемости. В бинарной постановке California Value Binary Geo именно `Flat Interpretable` показал лучший результат.

В-третьих, explainability в RuFLEX является не внешней надстройкой, а встроенной частью model pipeline. Для лучших конфигураций автоматически доступны:

- training history;
- results overview;
- membership visualizations;
- top decision rules;
- hidden concept contribution views;
- concept flow и rule chain exports.

Это делает платформу удобной не только для прикладного применения, но и для исследовательской демонстрации.

## 7. Ограничения и перспективы

Текущая версия RuFLEX уже покрывает ядро первой версии платформы, однако ряд направлений остается в статусе future work:

- зрелый spatial/deep fuzzy модуль;
- полноценная logical traceability engine;
- counterfactual explainability;
- перенос вычислительно тяжелых частей в C++.

Поэтому в статье важно не переобещать эти направления как уже полностью реализованные функции, а фиксировать их как архитектурно предусмотренные перспективы развития.

## 8. Заключение

Разработана платформа RuFLEX для гибридного глубокого нечеткого обучения, объединяющая interpretable rule-based mechanisms, differentiable fuzzy layers, deep fuzzy feature learning, Python SDK, visual workbench и explainability tooling в едином reproducible контуре. Экспериментальная валидация на двух geo-oriented задачах показывает, что платформа пригодна как для regression, так и для classification сценариев, при этом разные архитектурные режимы могут становиться предпочтительными в зависимости от структуры задачи. Это подтверждает целесообразность платформенного подхода и создает основу для дальнейшего развития spatial fuzzy модулей и более сильного explainability-контура.

## 9. References

Ниже приведен стартовый список литературы, который уже можно вставлять в шаблон и затем привести к формату конкретной конференции.

1. Jang J.-S. R. ANFIS: Adaptive-Network-Based Fuzzy Inference System // IEEE Transactions on Systems, Man, and Cybernetics. 1993. Vol. 23, No. 3. P. 665-685.
2. Paszke A., Gross S., Massa F. et al. PyTorch: An Imperative Style, High-Performance Deep Learning Library // Advances in Neural Information Processing Systems. 2019. Vol. 32.
3. Pedregosa F., Varoquaux G., Gramfort A. et al. Scikit-learn: Machine Learning in Python // Journal of Machine Learning Research. 2011. Vol. 12. P. 2825-2830.
4. Pace R. K., Barry R. Sparse Spatial Autoregressions // Statistics & Probability Letters. 1997. Vol. 33, No. 3. P. 291-297. DOI: 10.1016/S0167-7152(96)00140-X.
5. Rudin C. Stop Explaining Black Box Machine Learning Models for High Stakes Decisions and Use Interpretable Models Instead // Nature Machine Intelligence. 2019. Vol. 1. P. 206-215. DOI: 10.1038/s42256-019-0048-x.
6. Ma X., Chen L., Deng Z. et al. Deep Image Feature Learning With Fuzzy Rules // IEEE Transactions on Emerging Topics in Computational Intelligence. 2024. Vol. 8. P. 724-737. DOI: 10.1109/TETCI.2023.3259447.
7. Lebedeffson. deep-neuro-fuzzy [Электронный ресурс]. URL: https://github.com/lebedeffson/deep-neuro-fuzzy (дата обращения: 13.04.2026).
