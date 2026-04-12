# RuFLEX manual finish guide

Этот файл фиксирует только те шаги, которые уже нельзя честно закрыть автоматически.

## Что уже не нужно доделывать вручную

- окружение поднято;
- тесты проходят;
- article suite и benchmark runs сохранены;
- итоговые figures и tables уже собраны;
- `submission_bundle` и `submission_bundle.zip` уже готовы;
- safe title, abstract и draft текста уже подготовлены.

## Что остается вручную

1. Вписать авторов, аффилиации, e-mail и ORCID в `paper_draft.docx` и `rinc_draft.docx`.
2. Сначала обновить `docs/article/article_profile.json`, затем свериться с `docs/article/article_profile_card.md` и пересобрать пакет.
3. Выбрать, что удобнее редактировать дальше: `*_ready.docx` или уже `*_illustrated.docx`.
4. Привести стартовый список литературы к стилю конкретной площадки.
5. Проверить, нужны ли площадке именно screenshots интерфейса. Если нет, можно использовать уже собранные article boards.
6. Выполнить antiplagiat check и приложить скриншот в РИНЦ-файл.
7. Финально проверить верстку `.docx` после вставки авторов, литературы и рисунков.

## Рекомендуемый минимальный набор figures

1. `figure1_regression_benchmark.png`
2. `figure2_regression_board.png`
3. `figure3_classification_benchmark.png`
4. `figure4_classification_board.png`
5. `figure5_membership_example.png`

Файлы уже лежат в `docs/article/submission_bundle/figures/`.

## Рекомендуемая команда перед финальной отправкой

```bash
.venv/bin/python scripts/build_article_final_package.py --skip-suite
.venv/bin/python scripts/check_article_readiness.py --run-tests
```

## Важная граница claims

В финальной версии текста безопасно заявлять как реализованное:

- flat neuro-fuzzy baseline;
- deep fuzzy feature learning;
- differentiable fuzzy training contour;
- explainability по rules, factors и hidden concepts;
- reproducible article benchmark pipeline.

В future work лучше оставлять:

- mature spatial/deep fuzzy module;
- full logical traceability engine;
- counterfactual explainability.
