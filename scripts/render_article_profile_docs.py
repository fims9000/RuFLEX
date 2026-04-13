from __future__ import annotations

from pathlib import Path

from article_profile import (
    format_affiliations,
    format_author_names,
    format_emails,
    format_keywords,
    format_orcids,
    load_article_profile,
)
from article_references import format_reference_lines


ROOT = Path(__file__).resolve().parents[1]
FINAL_METADATA_PATH = ROOT / "docs/article/final_metadata.md"
RINC_MD_PATH = ROOT / "docs/article/rinc_draft.md"
RINC_TXT_PATH = ROOT / "docs/article/rinc_draft.txt"
PROFILE_CARD_PATH = ROOT / "docs/article/article_profile_card.md"
READY_RU_PATH = ROOT / "docs/article/shablon_dokladov_ready.md"
READY_EN_PATH = ROOT / "docs/article/conference_template_ready_en.md"
REFERENCES_RU_PATH = ROOT / "docs/article/references_ru_gost.md"
REFERENCES_EN_PATH = ROOT / "docs/article/references_en_ieee.md"


def main() -> None:
    render_article_profile_docs()
    print(FINAL_METADATA_PATH)
    print(RINC_MD_PATH)
    print(RINC_TXT_PATH)
    print(PROFILE_CARD_PATH)
    print(READY_RU_PATH)
    print(READY_EN_PATH)
    print(REFERENCES_RU_PATH)
    print(REFERENCES_EN_PATH)


def render_article_profile_docs() -> None:
    profile = load_article_profile()
    final_metadata_text = FINAL_METADATA_PATH.read_text(encoding="utf-8")
    final_metadata_text = _render_final_metadata(profile, final_metadata_text)
    FINAL_METADATA_PATH.write_text(final_metadata_text, encoding="utf-8")
    abstracts = _extract_abstracts(final_metadata_text)
    references_ru = format_reference_lines("ru")
    references_en = format_reference_lines("en")

    RINC_MD_PATH.write_text(_render_rinc_md(profile, abstracts, references_ru), encoding="utf-8")
    RINC_TXT_PATH.write_text(_render_rinc_txt(profile, abstracts, references_ru), encoding="utf-8")
    PROFILE_CARD_PATH.write_text(_render_profile_card(profile), encoding="utf-8")
    READY_RU_PATH.write_text(_render_ready_ru(profile, abstracts), encoding="utf-8")
    READY_EN_PATH.write_text(_render_ready_en(profile, abstracts), encoding="utf-8")
    render_reference_docs(reference_lines_ru=references_ru, reference_lines_en=references_en)


def render_reference_docs(
    *,
    reference_lines_ru: list[str] | None = None,
    reference_lines_en: list[str] | None = None,
) -> None:
    references_ru = reference_lines_ru if reference_lines_ru is not None else format_reference_lines("ru")
    references_en = reference_lines_en if reference_lines_en is not None else format_reference_lines("en")
    REFERENCES_RU_PATH.write_text(
        _render_reference_list("Список литературы для русскоязычной версии", references_ru),
        encoding="utf-8",
    )
    REFERENCES_EN_PATH.write_text(
        _render_reference_list("References for the English version", references_en),
        encoding="utf-8",
    )


def _render_final_metadata(profile: dict[str, object], text: str) -> str:
    title_block = "\n".join(
        [
            "## Рекомендуемое название",
            "",
            "### Русский",
            "",
            f"`{profile['title_ru']}`",
            "",
            "### English",
            "",
            f"`{profile['title_en']}`",
            "",
        ]
    )
    keywords_block = "\n".join(
        [
            "## Ключевые слова",
            "",
            "### Русский",
            "",
            *[f"- {item}" for item in profile["keywords_ru"]],
            "",
            "### English",
            "",
            *[f"- {item}" for item in profile["keywords_en"]],
            "",
        ]
    )
    text = _replace_section(text, "## Рекомендуемое название", "## Финальная аннотация", title_block)
    text = _replace_section(text, "## Ключевые слова", "## Важная граница claims", keywords_block)
    return text


def _render_ready_ru(profile: dict[str, object], abstracts: dict[str, str]) -> str:
    body = _extract_markdown_body(READY_RU_PATH, "## I. Введение")
    lines = [
        f"# {profile['title_ru']}",
        "",
        format_author_names(profile, language="ru"),
        "",
    ]
    for index, value in enumerate(format_affiliations(profile, language="ru"), start=1):
        lines.append(f"{index} {value}  ")
    lines.extend(
        [
            f"E-mail: {format_emails(profile)}",
            f"ORCID: {format_orcids(profile)}",
            "",
            f"Аннотация. {abstracts['ru']}",
            "",
            f"Ключевые слова: {format_keywords(profile['keywords_ru'])}",
            "",
            body,
        ]
    )
    return "\n".join(lines)


def _render_ready_en(profile: dict[str, object], abstracts: dict[str, str]) -> str:
    body = _extract_markdown_body(READY_EN_PATH, "## I. Introduction")
    lines = [
        f"# {profile['title_en']}",
        "",
        format_author_names(profile, language="en"),
        "",
    ]
    for value in format_affiliations(profile, language="en"):
        lines.append(f"{value}  ")
    lines.extend(
        [
            format_emails(profile),
            f"ORCID: {format_orcids(profile)}",
            "",
            "## Abstract",
            "",
            abstracts["en"],
            "",
            "## Keywords",
            "",
            format_keywords(profile["keywords_en"]),
            "",
            body,
        ]
    )
    return "\n".join(lines)


def _render_rinc_md(profile: dict[str, object], abstracts: dict[str, str], references: list[str]) -> str:
    author_lines = []
    for author in profile["authors"]:
        author_lines.extend(
            [
                f"- {author['name_ru']} / {author['name_en']}",
                f"- {author['email']}",
                f"- ORCID: {author['orcid']}",
                f"- {author['affiliation_ru']}",
                f"- {author['affiliation_en']}",
            ]
        )
    return "\n".join(
        [
            "# RuFLEX: draft for `fajl-dlya-rinc.doc`",
            "",
            "Этот файл повторяет структуру РИНЦ-шаблона в виде plain text, чтобы можно было быстро перенести содержимое в `.doc`.",
            "",
            "## 1. Название",
            "",
            "### Русский",
            "",
            str(profile["title_ru"]),
            "",
            "### English",
            "",
            str(profile["title_en"]),
            "",
            "## 2. Авторы",
            "",
            *author_lines,
            "",
            "## 3. Abstract",
            "",
            "### English",
            "",
            abstracts["en"],
            "",
            "### Русский",
            "",
            abstracts["ru"],
            "",
            "## 4. Keywords",
            "",
            "### English",
            "",
            format_keywords(profile["keywords_en"]),
            "",
            "### Русский",
            "",
            format_keywords(profile["keywords_ru"]),
            "",
            "## 5. References",
            "",
            *[f"{index}. {item}" for index, item in enumerate(references, start=1)],
            "",
            "## 6. Funding",
            "",
            str(profile["funding_ru"]),
            "",
            "## 7. Antiplagiat",
            "",
            "На последней странице РИНЦ-файла нужно вставить реальный скриншот проверки из antiplagiat.ru с уникальностью не менее 75%.",
            "",
            "Статус на текущий момент:",
            "",
            "- текстовая заготовка подготовлена",
            "- реальный скриншот пока не сформирован автоматически и должен быть добавлен после финальной проверки текста статьи",
        ]
    )


def _render_rinc_txt(profile: dict[str, object], abstracts: dict[str, str], references: list[str]) -> str:
    author_block = []
    for author in profile["authors"]:
        author_block.append(
            f"{author['name_ru']}\t\t\t{author['name_en']}\t\t\t{author['email']}\t\t\tORCID {author['orcid']}"
        )
    aff_ru = "; ".join(format_affiliations(profile, language="ru"))
    aff_en = "; ".join(format_affiliations(profile, language="en"))
    return "\n".join(
        [
            str(profile["title_ru"]),
            str(profile["title_en"]),
            "",
            *author_block,
            aff_ru,
            aff_en,
            "",
            f"Abstract — {abstracts['en']}",
            "",
            f"Аннотация. {abstracts['ru']}",
            "",
            f"Keywords — {format_keywords(profile['keywords_en'])}",
            f"Ключевые слова — {format_keywords(profile['keywords_ru'])}",
            "",
            "Список литературы",
            *[f"{index}. {item}" for index, item in enumerate(references, start=1)],
            "",
            str(profile["funding_ru"]),
            "",
            "На последней странице файла вставить реальный скриншот из antiplagiat.ru после окончательной проверки текста статьи.",
        ]
    )


def _render_profile_card(profile: dict[str, object]) -> str:
    lines = [
        "# RuFLEX article profile card",
        "",
        "Этот файл помогает быстро проверить, что лежит в `article_profile.json` перед пересборкой article-пакета.",
        "",
        f"- title_ru: `{profile['title_ru']}`",
        f"- title_en: `{profile['title_en']}`",
        f"- authors_ru: `{format_author_names(profile, language='ru')}`",
        f"- authors_en: `{format_author_names(profile, language='en')}`",
        f"- emails: `{format_emails(profile)}`",
        f"- orcids: `{format_orcids(profile)}`",
        f"- keywords_ru: `{format_keywords(profile['keywords_ru'])}`",
        f"- keywords_en: `{format_keywords(profile['keywords_en'])}`",
        "",
        "## Affiliations RU",
        "",
    ]
    lines.extend(f"- `{value}`" for value in format_affiliations(profile, language="ru"))
    lines.extend(["", "## Affiliations EN", ""])
    lines.extend(f"- `{value}`" for value in format_affiliations(profile, language="en"))
    lines.extend(
        [
            "",
            "## Funding RU",
            "",
            str(profile["funding_ru"]),
            "",
            "## Funding EN",
            "",
            str(profile["funding_en"]),
        ]
    )
    return "\n".join(lines)


def _render_reference_list(title: str, references: list[str]) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            *[f"{index}. {item}" for index, item in enumerate(references, start=1)],
        ]
    )


def _extract_abstracts(text: str) -> dict[str, str]:
    marker = "## Финальная аннотация"
    start = text.index(marker)
    block = text[start:]
    ru_marker = "### Русский"
    en_marker = "### English"
    kw_marker = "## Ключевые слова"
    ru_start = block.index(ru_marker) + len(ru_marker)
    en_start = block.index(en_marker)
    kw_start = block.index(kw_marker)
    ru_text = block[ru_start:en_start].strip()
    en_text = block[en_start + len(en_marker):kw_start].strip()
    return {"ru": ru_text, "en": en_text}


def _extract_markdown_body(path: Path, marker: str) -> str:
    text = path.read_text(encoding="utf-8")
    index = text.index(marker)
    return text[index:].strip()


def _replace_section(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker)
    return text[:start] + replacement + text[end:]

if __name__ == "__main__":
    main()
