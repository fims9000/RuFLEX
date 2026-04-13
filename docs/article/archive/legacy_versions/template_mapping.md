# RuFLEX template mapping

Этот файл связывает реальные шаблоны из репозитория с уже собранными article-материалами.

## Какие шаблоны есть

### `shablon-dokladov.doc`

Основной русскоязычный шаблон доклада. Из извлеченного текста следуют такие обязательные блоки:

- заголовок статьи;
- авторы, организации, e-mail;
- аннотация на русском;
- ключевые слова на русском;
- введение;
- обзор литературы;
- основная часть;
- результаты;
- заключение;
- благодарность / финансирование;
- список литературы.

Для него подготовлен почти готовый текст:

- `docs/article/shablon_dokladov_ready.md`
- `docs/article/shablon_dokladov_ready.docx`
- `docs/article/shablon_dokladov_template_based.docx`
- `docs/article/shablon_dokladov_illustrated.docx`

### `1.-conference-paper-template.doc`

Англоязычный IEEE-style шаблон. Из извлеченного текста следуют такие блоки:

- paper title;
- authors and affiliations;
- abstract;
- keywords;
- Introduction;
- structured body sections;
- Acknowledgment;
- References.

Для него подготовлен рабочий вариант:

- `docs/article/conference_template_ready_en.md`
- `docs/article/conference_template_ready_en.docx`
- `docs/article/conference_template_illustrated_en.docx`

### `fajl-dlya-rinc.doc`

Служебный РИНЦ-файл. Для него уже подготовлены:

- `docs/article/rinc_draft.md`
- `docs/article/rinc_draft.txt`
- `docs/article/rinc_draft.docx`

## Какой набор брать в работу

### Минимальный пакет для русскоязычной подачи

1. `docs/article/shablon_dokladov_ready.docx`
2. `docs/article/shablon_dokladov_template_based.docx`
3. `docs/article/shablon_dokladov_illustrated.docx`
4. `docs/article/shablon_dokladov_illustrated.pdf`
5. `docs/article/rinc_draft.docx`
6. `docs/article/rinc_draft.pdf`
7. `docs/article/submission_bundle/figures/*`
8. `docs/article/submission_bundle/tables/*`

### Если нужен англоязычный paper-style вариант

1. `docs/article/conference_template_ready_en.docx`
2. `docs/article/conference_template_illustrated_en.docx`
3. `docs/article/conference_template_illustrated_en.pdf`
4. `docs/article/final_metadata.md`
5. `docs/article/submission_bundle/figures/*`
6. `docs/article/submission_bundle/tables/*`

## Откуда брать содержимое

- авторы, аффилиации, e-mail, ORCID, funding и acknowledgments: `docs/article/article_profile.json`
- краткая проверка profile перед сборкой: `docs/article/article_profile_card.md`
- единый список литературы: `docs/article/article_references.json`
- ручные submission-флаги: `docs/article/submission_state.json`
- сгенерированные reference-листы: `docs/article/references_ru_gost.md`, `docs/article/references_en_ieee.md`
- safe title / abstract / keywords: `docs/article/final_metadata.md`
- narrative text: `docs/article/paper_draft.md`
- figures and captions: `docs/article/figure_manifest.md`
- final readiness snapshot: `docs/article/readiness_report.md`
- manual-only tail: `docs/article/manual_finish.md`

## Что еще останется руками

- при изменении авторских данных сначала запустить `scripts/render_article_profile_docs.py`;
- при необходимости только проверить, что authors / affiliations / e-mail / ORCID корректно подтянулись из `docs/article/article_profile.json`;
- проверить стиль списка литературы под площадку;
- вставить рисунки в `.docx`;
- сделать antiplagiat screenshot для РИНЦ.
