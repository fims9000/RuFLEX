# RuFLEX manual finish guide

Этот файл фиксирует только те шаги, которые уже нельзя честно закрыть автоматически.

## Что уже не нужно доделывать вручную

- окружение поднято;
- тесты проходят;
- article suite и benchmark runs сохранены;
- итоговые figures и tables уже собраны;
- `submission_bundle` и `submission_bundle.zip` уже готовы;
- safe title, abstract и draft текста уже подготовлены.
- PDF-версии основных article документов уже собираются автоматически.

## Что остается вручную

1. Заполнить авторов, аффилиации, e-mail и ORCID в `docs/article/article_profile.json`.
2. Отметить в `docs/article/submission_state.json`, что профиль подтвержден.
3. Сначала обновить `docs/article/article_profile.json`, затем свериться с `docs/article/article_profile_card.md` и пересобрать пакет.
4. Выбрать, что удобнее редактировать дальше: `*_ready.docx` или уже `*_illustrated.docx`.
5. Привести стартовый список литературы к стилю конкретной площадки и отметить это в `docs/article/submission_state.json`.
6. Проверить, нужны ли площадке именно screenshots интерфейса. Если нет, можно использовать уже собранные article boards.
7. Выполнить antiplagiat check, приложить скриншот в РИНЦ-файл и отметить это в `docs/article/submission_state.json`.
8. Финально проверить верстку `.docx` после автоматической подстановки авторов, литературы и рисунков и отметить это в `docs/article/submission_state.json`.

## Рекомендуемый минимальный набор figures

1. `figure1_regression_benchmark.png`
2. `figure2_regression_board.png`
3. `figure3_classification_benchmark.png`
4. `figure4_classification_board.png`
5. `figure5_membership_example.png`

Файлы уже лежат в `docs/article/submission_bundle/figures/`.

## Рекомендуемая команда перед финальной отправкой

```bash
.venv/bin/python scripts/manage_article_profile.py --show
.venv/bin/python scripts/manage_article_references.py --show
.venv/bin/python scripts/manage_submission_state.py --show
.venv/bin/python scripts/build_article_final_package.py --skip-suite
.venv/bin/python scripts/check_article_readiness.py --run-tests
.venv/bin/python scripts/check_article_readiness.py --run-tests --strict-submission
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

## Автоматическая защита от шаблонных данных

`scripts/check_article_readiness.py` теперь отдельно показывает:

- `overall_status`: собран ли пакет технически;
- `submission_status`: можно ли считать пакет реально готовым к отправке;
- `profile_status`: остались ли в `article_profile.json` шаблонные authors / affiliations / e-mail / ORCID.

То есть зеленый `overall_status` еще не означает, что профиль статьи уже заполнен реальными данными.
Для фактической финальной проверки перед отправкой теперь есть строгий режим:
`scripts/check_article_readiness.py --strict-submission`. Он завершится с ошибкой,
пока `profile_status != ready` или `submission_status != ready`.

Для обновления author block из терминала можно использовать не только `--author-set`, но и:

```bash
.venv/bin/python scripts/manage_article_profile.py \
  --author-add "name_ru=Петр Петров|name_en=Petr Petrov|email=petr.petrov@example.org|orcid=0000-0002-3456-7890|affiliation_ru=Институт, Санкт-Петербург, Россия|affiliation_en=Institute, Saint Petersburg, Russia"

.venv/bin/python scripts/manage_article_profile.py --author-remove 3
```

Для списка литературы теперь есть отдельный CLI:

```bash
.venv/bin/python scripts/manage_article_references.py --show
.venv/bin/python scripts/manage_article_references.py \
  --add "key=new_reference|ru=Новая русская ссылка.|en=New English reference."
.venv/bin/python scripts/manage_article_references.py \
  --set "new_reference:en=Updated English reference."
.venv/bin/python scripts/manage_article_references.py --remove new_reference
```
