# RuFLEX article writing blueprint

Этот файл нужен не для обзора литературы, а для сборки финальной статьи о платформе `RuFLEX`.

## 1. Что именно мы пишем

Мы пишем статью не о литературном обзоре и не о частной модели, а о программной платформе `RuFLEX`.

Главный предмет статьи:

- `RuFLEX` как расширяемая платформа для гибридного глубокого нечеткого обучения;
- поддержка двух ключевых режимов первой версии:
  - `flat neuro-fuzzy baseline`;
  - `deep fuzzy feature learning`;
- встроенный контур интерпретации;
- воспроизводимый экспериментальный контур;
- прикладная демонстрация на geo-oriented табличных задачах.

## 2. Главная логика статьи

Статья должна отвечать на такую связку вопросов:

1. Почему нужен платформенный подход, а не один отдельный fuzzy-прототип.
2. Как устроен `RuFLEX` на уровне архитектуры, SDK, UI и explainability.
3. Какие модельные режимы уже реально реализованы.
4. Как организованы обучение, воспроизводимость и анализ работы модели.
5. Что показывают два прикладных эксперимента.
6. Где проходит честная граница между реализованным ядром и future work.

## 3. Финальная структура статьи

Текущий рекомендуемый порядок разделов:

1. Введение
2. Архитектура платформы `RuFLEX`
3. Поддерживаемые модельные режимы
4. Контур обучения и интерпретации
5. Экспериментальная постановка
6. Результаты экспериментов
7. Обсуждение результатов
8. Ограничения и перспективы
9. Заключение
10. References

## 4. Что уже готово по разделам

### Уже есть хороший каркас

- [paper_draft.md](./paper_draft.md)
- [final_metadata.md](./final_metadata.md)
- [final_status.md](./final_status.md)

### Уже почти готовы к вставке без дополнительной переработки

- название статьи;
- русская и английская аннотация;
- ключевые слова;
- блок про regression showcase;
- блок про classification showcase;
- список реализованных и перспективных направлений;
- стартовый список литературы.

### Требуют литературной доводки, а не содержательной переделки

- введение;
- архитектура платформы;
- explainability-контур;
- обсуждение результатов;
- заключение.

## 5. Какие материалы уже можно брать в текст

### Основной текст

- [paper_draft.md](./paper_draft.md)

### Название, abstract, keywords и безопасная граница claims

- [final_metadata.md](./final_metadata.md)

### Текущий статус статьи и экспериментальный срез

- [final_status.md](./final_status.md)

### Шаблонные версии статьи

- [shablon_dokladov_ready.docx](./shablon_dokladov_ready.docx)
- [conference_template_ready_en.docx](./conference_template_ready_en.docx)
- [shablon_dokladov_illustrated.docx](./shablon_dokladov_illustrated.docx)
- [conference_template_illustrated_en.docx](./conference_template_illustrated_en.docx)

## 6. Какие две таблицы берем в финальную статью

### Таблица 1. Regression results

Источник:

- `docs/article/submission_bundle/tables/regression_results_table.csv`

Смысл таблицы:

- сравнение `Flat Baseline`, `Flat Interpretable`, `Deep Article Demo`, `Deep Research`;
- метрики `test_rmse`, `test_mae`, `test_r2`;
- ключевой вывод: на `California Housing Regression` лучший результат показывает `Deep Research`.

### Таблица 2. Classification results

Источник:

- `docs/article/submission_bundle/tables/classification_results_table.csv`

Смысл таблицы:

- сравнение тех же конфигураций на `California Value Binary Geo`;
- метрики `test_accuracy`, `test_precision`, `test_recall`, `test_f1`;
- ключевой вывод: на classification лучшей оказывается `Flat Interpretable`.

## 7. Какие рисунки берем в финальную статью

### Обязательный минимальный набор

1. Regression benchmark figure  
   Источник:
   `docs/article/submission_bundle/figures/figure1_regression_benchmark.png`

2. Regression explainability board  
   Источник:
   `docs/article/submission_bundle/figures/figure2_regression_board.png`

3. Classification benchmark figure  
   Источник:
   `docs/article/submission_bundle/figures/figure3_classification_benchmark.png`

4. Classification explainability board  
   Источник:
   `docs/article/submission_bundle/figures/figure4_classification_board.png`

5. Membership-function example  
   Источник:
   `docs/article/submission_bundle/figures/figure5_membership_example.png`

### Дополнительный набор, если площадка допускает больше иллюстраций

- `best_training_history.png`
- `best_sample_top_rules.png`
- `best_sample_hidden_concepts.png`
- `best_sample_decision_concepts.png`
- `best_sample_fuzzification.png`
- `workbench_article_snapshot.png`

Источники:

- `docs/article/assets/2026_04_12t21_40_59_674987_00_00_california_housing_regression_article_benchmark/...`
- `docs/article/assets/2026_04_12t21_42_50_661750_00_00_california_value_binary_geo_article_benchmark/...`

## 8. Какие три схемы еще стоит сделать отдельно

Эти схемы упростят статью сильнее всего.

### Схема 1. Общая архитектура `RuFLEX`

Что должно быть на схеме:

- `src/ruanfis` как deep fuzzy backend;
- `src/ruflex` как platform layer;
- SDK;
- UI;
- training;
- explainability;
- serialization;
- experiment pipeline.

### Схема 2. Модельный контур

Что показать:

- `flat neuro-fuzzy baseline`;
- `deep fuzzy feature learning`;
- hidden concept layers;
- final decision layer;
- блоки правил;
- переход от входных признаков к concept space и к итоговому решению.

### Схема 3. Explainability pipeline

Что показать:

- fuzzification;
- membership functions;
- rule activation;
- normalized rule weights;
- hidden concepts;
- final decision;
- factor contribution / concept flow / rule chain flow.

## 9. Что именно еще надо дописать в самой статье

### Раздел 1. Введение

Нужно:

- убрать ощущение перечисления;
- сделать логичную связку:
  - проблема интерпретируемости;
  - ограниченность black-box подходов;
  - ценность fuzzy и neuro-fuzzy методов;
  - переход к идее платформы;
  - краткое перечисление вклада статьи.

### Раздел 2. Архитектура платформы

Нужно:

- сделать плавный текст о слоях платформы;
- убрать сухую раскладку по bullet-логике;
- показать, что backend и platform layer разделены осознанно.

### Раздел 4. Контур обучения и интерпретации

Нужно:

- связно описать:
  - training flow;
  - bootstrap / stage-wise / refinement;
  - explainability flow;
  - reproduciability flow.

### Раздел 6. Результаты

Нужно:

- встроить таблицы и figures в повествование;
- не просто перечислить метрики, а показать, что они подтверждают платформенный тезис.

### Раздел 7. Обсуждение

Нужно:

- объяснить, почему на одной задаче выигрывает deep режим, а на другой flat;
- аккуратно подвести к мысли, что `RuFLEX` ценен именно как платформа выбора и сравнения архитектур.

### Раздел 8. Ограничения и перспективы

Нужно:

- сохранить честную границу claims;
- явно отделить текущее ядро от будущих направлений:
  - spatial;
  - mature logical traceability;
  - counterfactual explainability;
  - C++ acceleration.

## 10. Что писать нельзя

- нельзя превращать статью в обзор литературы;
- нельзя писать так, будто уже есть зрелый spatial module, если его нет;
- нельзя утверждать, что логическая прослеживаемость и контрфактуальный анализ уже реализованы как finished feature;
- нельзя сводить всю статью к одному `ANFIS`;
- нельзя подавать `deep fuzzy` как единственный центральный результат вне платформенного контекста.

## 11. Что делать следующим шагом

Рекомендуемый порядок работы:

1. Довести введение.
2. Довести архитектуру платформы.
3. Довести экспериментальную постановку и результаты.
4. Подготовить 3 схемы.
5. Вставить 2 таблицы и 5 основных рисунков.
6. Финально вычистить обсуждение и заключение.

## 12. Практический минимум для уже хорошей статьи

Если делать короткий, но сильный вариант статьи, то достаточно:

- текста из [paper_draft.md](./paper_draft.md) после литературной доводки;
- 2 таблиц результатов;
- 5 рисунков;
- 1 общей архитектурной схемы;
- честной формулировки claims из [final_metadata.md](./final_metadata.md);
- current article suite metrics из [final_status.md](./final_status.md).
