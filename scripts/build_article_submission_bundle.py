from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE_ROOT = ROOT / "experiments/article_suite"
OUTPUT_DIR = ROOT / "docs/article/submission_bundle"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a submission-ready article bundle from one article suite.")
    parser.add_argument(
        "--suite-dir",
        default=None,
        help="Optional article suite directory. If omitted, the latest suite under experiments/article_suite is used.",
    )
    args = parser.parse_args()

    output_dir = build_submission_bundle(suite_dir=None if args.suite_dir is None else Path(args.suite_dir))
    print(output_dir)


def build_submission_bundle(*, suite_dir: Path | None = None) -> Path:
    resolved_suite_dir = _resolve_suite_dir(suite_dir)
    suite_summary = _load_suite_summary(resolved_suite_dir)
    asset_dirs = _asset_dirs_by_task(suite_summary)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    docs_dir = OUTPUT_DIR / "docs"
    figures_dir = OUTPUT_DIR / "figures"
    tables_dir = OUTPUT_DIR / "tables"
    docs_dir.mkdir()
    figures_dir.mkdir()
    tables_dir.mkdir()

    _copy(ROOT / "docs/article/final_metadata.md", docs_dir / "final_metadata.md")
    _copy(ROOT / "docs/article/final_status.md", docs_dir / "final_status.md")
    _copy(ROOT / "docs/article/paper_draft.md", docs_dir / "paper_draft.md")
    _copy_if_exists(ROOT / "docs/article/paper_draft.docx", docs_dir / "paper_draft.docx")
    _copy(ROOT / "docs/article/article_profile.template.json", docs_dir / "article_profile.template.json")
    _copy(ROOT / "docs/article/article_profile.json", docs_dir / "article_profile.json")
    _copy_if_exists(ROOT / "docs/article/article_profile_card.md", docs_dir / "article_profile_card.md")
    _copy(ROOT / "docs/article/template_mapping.md", docs_dir / "template_mapping.md")
    _copy(ROOT / "docs/article/shablon_dokladov_ready.md", docs_dir / "shablon_dokladov_ready.md")
    _copy_if_exists(ROOT / "docs/article/shablon_dokladov_ready.docx", docs_dir / "shablon_dokladov_ready.docx")
    _copy_if_exists(ROOT / "docs/article/shablon_dokladov_illustrated.docx", docs_dir / "shablon_dokladov_illustrated.docx")
    _copy(ROOT / "docs/article/conference_template_ready_en.md", docs_dir / "conference_template_ready_en.md")
    _copy_if_exists(
        ROOT / "docs/article/conference_template_ready_en.docx",
        docs_dir / "conference_template_ready_en.docx",
    )
    _copy_if_exists(
        ROOT / "docs/article/conference_template_illustrated_en.docx",
        docs_dir / "conference_template_illustrated_en.docx",
    )
    _copy(ROOT / "docs/article/figure_manifest.md", docs_dir / "figure_manifest.md")
    _copy(ROOT / "docs/article/manual_finish.md", docs_dir / "manual_finish.md")
    _copy(ROOT / "docs/article/rinc_draft.md", docs_dir / "rinc_draft.md")
    _copy(ROOT / "docs/article/rinc_draft.txt", docs_dir / "rinc_draft.txt")
    _copy(ROOT / "docs/article/rinc_draft.docx", docs_dir / "rinc_draft.docx")
    _copy_if_exists(ROOT / "docs/article/readiness_report.md", docs_dir / "readiness_report.md")
    _copy_if_exists(ROOT / "docs/article/readiness_report.json", docs_dir / "readiness_report.json")

    regression_asset_dir = asset_dirs.get("regression")
    classification_asset_dir = asset_dirs.get("binary_classification")
    if regression_asset_dir is not None:
        _copy(regression_asset_dir / "results_table.csv", tables_dir / "regression_results_table.csv")
    if classification_asset_dir is not None:
        _copy(classification_asset_dir / "results_table.csv", tables_dir / "classification_results_table.csv")
    _copy(resolved_suite_dir / "article_suite_results.csv", tables_dir / "article_suite_results.csv")

    figure_map = {}
    if regression_asset_dir is not None:
        figure_map.update(
            {
                "figure1_regression_benchmark.png": regression_asset_dir / "results_overview.png",
                "figure2_regression_board.png": regression_asset_dir / "article_board_regression.png",
                "figure5_membership_example.png": regression_asset_dir / "membership_medinc.png",
            }
        )
    if classification_asset_dir is not None:
        figure_map.update(
            {
                "figure3_classification_benchmark.png": classification_asset_dir / "results_overview.png",
                "figure4_classification_board.png": classification_asset_dir / "article_board_classification.png",
            }
        )
    for target_name, source_path in figure_map.items():
        _copy_if_exists(source_path, figures_dir / target_name)

    manifest = {
        "suite_dir": str(resolved_suite_dir),
        "docs": sorted(path.name for path in docs_dir.iterdir() if path.is_file()),
        "tables": sorted(path.name for path in tables_dir.iterdir() if path.is_file()),
        "figures": sorted(path.name for path in figures_dir.iterdir() if path.is_file()),
    }
    (OUTPUT_DIR / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "README.md").write_text(_bundle_readme(manifest), encoding="utf-8")
    archive_base = OUTPUT_DIR.parent / OUTPUT_DIR.name
    shutil.make_archive(str(archive_base), "zip", OUTPUT_DIR.parent, OUTPUT_DIR.name)
    return OUTPUT_DIR


def _resolve_suite_dir(suite_dir: Path | None) -> Path:
    if suite_dir is not None:
        resolved = suite_dir.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Article suite directory was not found: {resolved}")
        return resolved

    if not DEFAULT_SUITE_ROOT.exists():
        raise FileNotFoundError(f"Article suite root was not found: {DEFAULT_SUITE_ROOT}")
    candidates = sorted((path for path in DEFAULT_SUITE_ROOT.iterdir() if path.is_dir()), key=lambda path: path.name)
    if not candidates:
        raise FileNotFoundError(f"No article suite directories were found under: {DEFAULT_SUITE_ROOT}")
    return candidates[-1]


def _load_suite_summary(suite_dir: Path) -> dict[str, Any]:
    summary_path = suite_dir / "article_suite_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Article suite summary was not found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _asset_dirs_by_task(suite_summary: dict[str, Any]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for item in suite_summary.get("dataset_runs", ()):
        dataset = item.get("dataset") or {}
        task_type = str(dataset.get("task_type"))
        materials_dir = item.get("materials_dir")
        if materials_dir is None or task_type in mapping:
            continue
        mapping[task_type] = Path(str(materials_dir))
    return mapping


def _copy(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Required source file is missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_if_exists(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _bundle_readme(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# RuFLEX submission bundle",
            "",
            "Эта папка собирает основные материалы для финальной подготовки статьи.",
            "",
            f"- suite_dir: `{manifest['suite_dir']}`",
            "",
            "## Содержимое",
            "",
            "- `docs/final_metadata.md`: title, abstract, keywords",
            "- `docs/final_status.md`: краткий статус готовности",
            "- `docs/paper_draft.md`: черновик основного текста статьи",
            "- `docs/paper_draft.docx`: редактируемый черновик основного текста статьи",
            "- `docs/article_profile*.json`: единый профиль авторов, аффилиаций и funding",
            "- `docs/article_profile_card.md`: быстрая сводка по заполненному article profile",
            "- `docs/template_mapping.md`: привязка материалов к реальным шаблонам",
            "- `docs/shablon_dokladov_ready.*`: русскоязычный template-ready вариант",
            "- `docs/shablon_dokladov_illustrated.docx`: русскоязычная версия с вшитыми figures и tables",
            "- `docs/conference_template_ready_en.*`: англоязычный template-ready вариант",
            "- `docs/conference_template_illustrated_en.docx`: англоязычная версия с вшитыми figures и tables",
            "- `docs/figure_manifest.md`: рекомендуемые рисунки и подписи",
            "- `docs/manual_finish.md`: что осталось только на ручную фазу",
            "- `docs/rinc_draft.md`: текстовая заготовка РИНЦ",
            "- `docs/rinc_draft.txt`: plain-text версия РИНЦ-заготовки",
            "- `docs/rinc_draft.docx`: редактируемый РИНЦ-черновик",
            "- `docs/readiness_report.*`: автоматическая проверка критичных article assets",
            "- `tables/*.csv`: основные таблицы результатов",
            "- `figures/*.png`: базовый набор figure assets для статьи",
            "- `bundle_manifest.json`: фактический состав собранного пакета",
            "",
            "## Что остается вручную",
            "",
            "- вписать authors / affiliations / e-mail / ORCID",
            "- при необходимости дополнить стартовый список литературы",
            "- вставить figures в шаблон статьи",
            "- добавить antiplagiat screenshot в РИНЦ-файл",
            "- при необходимости снять отдельные UI screenshots из Streamlit вручную",
        ]
    )


if __name__ == "__main__":
    main()
