# Финальная benchmark-сводка RuFLEX

## Базовая серия

Финальной для статьи считается серия `article_benchmark_q2_final_plus` со следующими каталогами:

1. `experiments/article_benchmark_q2_final_plus/2026_04_13t10_28_03_935704_00_00_california_housing_regression_article_benchmark`
2. `experiments/article_benchmark_q2_final_plus/2026_04_13t10_36_54_637555_00_00_california_value_binary_geo_article_benchmark`
3. `experiments/article_benchmark_q2_final_plus/2026_04_13t10_45_35_740062_00_00_covtype_binary_geo_article_benchmark`

Во всех трех задачах использованы повторные запуски по seed `11, 23, 47`. Внешняя таблица включает `Linear/Logistic Regression`, `Gradient Boosting`, `Random Forest` и `MLP`.

## Ключевые результаты

### California Housing Regression

- Лучший вариант внутри RuFLEX: `Deep Depth 1`
- `test_rmse = 0.780 ± 0.033`
- `test_mae = 0.586 ± 0.008`
- `test_r2 = 0.504 ± 0.046`
- Лучший внешний baseline: `Gradient Boosting`
- `test_rmse = 0.505 ± 0.015`
- `test_mae = 0.349 ± 0.010`
- `test_r2 = 0.793 ± 0.013`

Вывод: умеренная глубина улучшает RuFLEX относительно плоского базового режима, но на компактной табличной георегрессии сильный бустинговый baseline остается заметно сильнее по чистой метрике.

### California Value Binary Geo

- Лучший по `accuracy` вариант внутри RuFLEX: `Deep Depth 1`
- `test_accuracy = 0.751 ± 0.008`
- `test_f1 = 0.745 ± 0.009`
- По среднему `F1` немного выше `Deep No Regularization`: `0.748 ± 0.014`
- Лучший внешний baseline: `Gradient Boosting`
- `test_accuracy = 0.892 ± 0.006`
- `test_f1 = 0.895 ± 0.007`

Вывод: внутри семейства RuFLEX умеренная глубина дает лучший результат по `accuracy` и один из лучших результатов по `F1`, но внешние табличные baseline-модели на этой задаче существенно сильнее.

### Covertype Binary Geo

- Лучший вариант внутри RuFLEX: `Deep Research`
- `test_accuracy = 0.499 ± 0.007`
- `test_f1 = 0.321 ± 0.272`
- Лучший внешний baseline: `Random Forest`
- `test_accuracy = 0.804 ± 0.001`
- `test_f1 = 0.808 ± 0.001`

Вывод: независимая задача Covertype честно показывает границу текущего табличного контура RuFLEX и подтверждает необходимость дальнейшего развития пространственного направления.

## Общая интерпретация

Эта серия не поддерживает позиционирование статьи как работы о численном превосходстве RuFLEX над лучшими табличными методами. Зато она хорошо поддерживает более точную и сильную рамку: RuFLEX является платформой для сравнения архитектурных режимов, воспроизводимого benchmark-анализа и внутренне интерпретируемого гибридного нечеткого обучения.

## Дополнительная enlarged-серия

Дополнительно была проведена отдельная проверка устойчивости выводов на увеличенных выборках. Эта серия не заменяет базовый benchmark статьи, но показывает, сохраняется ли внутренний тренд RuFLEX при росте объема данных.

### California Housing Regression, full n=20640

- `Flat Baseline`: `test_rmse = 0.940 ± 0.159`, `test_mae = 0.720 ± 0.140`, `test_r2 = 0.329 ± 0.233`
- `Deep Depth 1`: `test_rmse = 0.786 ± 0.005`, `test_mae = 0.591 ± 0.003`, `test_r2 = 0.544 ± 0.008`
- `Deep Article Demo`: `test_rmse = 0.786 ± 0.005`, `test_mae = 0.590 ± 0.003`, `test_r2 = 0.543 ± 0.008`
- Лучший внешний baseline: `Gradient Boosting`, `test_rmse = 0.486 ± 0.001`, `test_mae = 0.334 ± 0.001`, `test_r2 = 0.826 ± 0.001`

Вывод: на полном регрессионном датасете выигрыш умеренной глубины над плоским baseline внутри RuFLEX сохраняется и становится более устойчивым по разбросу между seed.

### California Value Binary Geo, enlarged n=16000

- `Flat Baseline`: `test_accuracy = 0.745 ± 0.001`, `test_f1 = 0.732 ± 0.006`
- `Deep Depth 1`: `test_accuracy = 0.762 ± 0.006`, `test_f1 = 0.748 ± 0.006`
- `Deep Article Demo`: `test_accuracy = 0.762 ± 0.006`, `test_f1 = 0.749 ± 0.006`
- `Deep No Regularization`: `test_accuracy = 0.763 ± 0.011`, `test_f1 = 0.762 ± 0.016`
- Лучший внешний baseline: `Gradient Boosting`, `test_accuracy = 0.901 ± 0.001`, `test_f1 = 0.901 ± 0.001`

Вывод: enlarged-классификация подтверждает тот же тренд. Глубокие конфигурации снова лучше плоского baseline внутри RuFLEX, хотя сильные внешние табличные модели остаются заметно впереди по абсолютной метрике.
