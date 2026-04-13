# RuFLEX submission bundle

Эта папка собирает основные материалы для финальной подготовки статьи.

- suite_dir: `/home/lebedeffson/Code/neurofuzzy_analysis/experiments/article_suite/2026_04_12t21_40_59_671052_00_00_article_suite`

## Содержимое

- `docs/final_metadata.md`: title, abstract, keywords
- `docs/final_status.md`: краткий статус готовности
- `docs/paper_draft.md`: черновик основного текста статьи
- `docs/paper_draft.docx`: редактируемый черновик основного текста статьи
- `docs/paper_draft.pdf`: PDF-версия черновика статьи
- `docs/article_profile*.json`: единый профиль авторов, аффилиаций и funding
- `docs/article_profile_card.md`: быстрая сводка по заполненному article profile
- `docs/article_references.json`: единый source of truth для библиографии
- `docs/submission_state*.json`: ручные флаги фактической готовности к отправке
- `docs/references_*.md`: сгенерированные reference-листы для RU/EN версий
- `docs/template_mapping.md`: привязка материалов к реальным шаблонам
- `docs/shablon_dokladov_ready.*`: русскоязычный template-ready вариант
- `docs/shablon_dokladov_template_based.*`: русскоязычная версия, собранная на стилях исходного шаблона `shablon-dokladov.doc`
- `docs/shablon_dokladov_illustrated.*`: русскоязычная версия с вшитыми figures и tables
- `docs/conference_template_ready_en.*`: англоязычный template-ready вариант
- `docs/conference_template_illustrated_en.*`: англоязычная версия с вшитыми figures и tables
- `docs/figure_manifest.md`: рекомендуемые рисунки и подписи
- `docs/manual_finish.md`: что осталось только на ручную фазу
- `docs/rinc_draft.*`: текстовая, docx- и PDF-версии РИНЦ-заготовки
- `docs/readiness_report.*`: автоматическая проверка критичных article assets
- `tables/*.csv`: основные таблицы результатов
- `figures/*.png`: схемы платформы, benchmark-рисунки и explainability figures для статьи
- `bundle_manifest.json`: фактический состав собранного пакета

## Что остается вручную

- при необходимости уточнить authors / affiliations / e-mail / ORCID в docs/article/article_profile.json и пересобрать пакет
- при необходимости дополнить стартовый список литературы
- вставить figures в шаблон статьи
- добавить antiplagiat screenshot в РИНЦ-файл
- при необходимости снять отдельные UI screenshots из Streamlit вручную