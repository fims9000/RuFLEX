from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from article_profile import analyze_article_profile, load_article_profile
from article_references import analyze_article_references, load_article_references


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE_ROOT = ROOT / "experiments/article_suite"
DEFAULT_REPORT_MD = ROOT / "docs/article/readiness_report.md"
DEFAULT_REPORT_JSON = ROOT / "docs/article/readiness_report.json"
SUBMISSION_BUNDLE_DIR = ROOT / "docs/article/submission_bundle"
SUBMISSION_BUNDLE_ZIP = ROOT / "docs/article/submission_bundle.zip"

REQUIRED_DOCS = (
    ROOT / "docs/article/final_metadata.md",
    ROOT / "docs/article/final_status.md",
    ROOT / "docs/article/paper_draft.md",
    ROOT / "docs/article/paper_draft.docx",
    ROOT / "docs/article/paper_draft.pdf",
    ROOT / "docs/article/article_profile.template.json",
    ROOT / "docs/article/article_profile.json",
    ROOT / "docs/article/article_profile_card.md",
    ROOT / "docs/article/article_references.json",
    ROOT / "docs/article/submission_state.template.json",
    ROOT / "docs/article/submission_state.json",
    ROOT / "docs/article/references_ru_gost.md",
    ROOT / "docs/article/references_en_ieee.md",
    ROOT / "docs/article/template_mapping.md",
    ROOT / "docs/article/shablon_dokladov_ready.md",
    ROOT / "docs/article/shablon_dokladov_ready.docx",
    ROOT / "docs/article/shablon_dokladov_illustrated.docx",
    ROOT / "docs/article/shablon_dokladov_illustrated.pdf",
    ROOT / "docs/article/conference_template_ready_en.md",
    ROOT / "docs/article/conference_template_ready_en.docx",
    ROOT / "docs/article/conference_template_illustrated_en.docx",
    ROOT / "docs/article/conference_template_illustrated_en.pdf",
    ROOT / "docs/article/figure_manifest.md",
    ROOT / "docs/article/manual_finish.md",
    ROOT / "docs/article/rinc_draft.md",
    ROOT / "docs/article/rinc_draft.docx",
    ROOT / "docs/article/rinc_draft.pdf",
)

REQUIRED_BUNDLE_FIGURES = (
    "figure1_regression_benchmark.png",
    "figure2_regression_board.png",
    "figure3_classification_benchmark.png",
    "figure4_classification_board.png",
    "figure5_membership_example.png",
)

REQUIRED_BUNDLE_TABLES = (
    "article_suite_results.csv",
    "regression_results_table.csv",
    "classification_results_table.csv",
)

MANUAL_ITEMS = (
    "При необходимости заполнить или уточнить authors / affiliations / e-mail / ORCID в docs/article/article_profile.json и пересобрать пакет.",
    "Проверить и при необходимости дополнить стартовый список литературы под формат площадки.",
    "Выполнить antiplagiat check и приложить реальный скриншот в РИНЦ-файл.",
    "Проверить итоговую верстку после вставки рисунков, подписей и авторских данных.",
)

SUBMISSION_FLAGS = (
    ("profile_confirmed", "Подтверждены реальные authors / affiliations / e-mail / ORCID."),
    ("references_checked", "Стартовый список литературы проверен и приведен к стилю площадки."),
    ("figures_finalized", "Итоговые figures и captions окончательно утверждены."),
    ("antiplagiat_screenshot_added", "В РИНЦ-файл добавлен реальный antiplagiat screenshot."),
    ("layout_reviewed", "Итоговая верстка `.docx`/`.pdf` просмотрена вручную."),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check RuFLEX article package readiness.")
    parser.add_argument(
        "--suite-dir",
        default=None,
        help="Optional article suite directory. If omitted, the latest suite under experiments/article_suite is used.",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run the article-related pytest suite as part of the readiness report.",
    )
    parser.add_argument(
        "--strict-profile",
        action="store_true",
        help="Exit with non-zero status unless profile_status is `ready`.",
    )
    parser.add_argument(
        "--strict-submission",
        action="store_true",
        help="Exit with non-zero status unless submission_status is `ready`.",
    )
    args = parser.parse_args()

    report_path = build_readiness_report(
        suite_dir=None if args.suite_dir is None else Path(args.suite_dir),
        run_tests=args.run_tests,
    )
    print(report_path)
    report_payload = json.loads(DEFAULT_REPORT_JSON.read_text(encoding="utf-8"))
    if args.strict_profile and report_payload["profile_status"] != "ready":
        print(
            f"strict-profile gate failed: profile_status={report_payload['profile_status']}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if args.strict_submission and report_payload["submission_status"] != "ready":
        print(
            f"strict-submission gate failed: submission_status={report_payload['submission_status']}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def build_readiness_report(*, suite_dir: Path | None = None, run_tests: bool = False) -> Path:
    resolved_suite_dir = _resolve_suite_dir(suite_dir)
    suite_summary = _load_suite_summary(resolved_suite_dir)
    profile_report = _profile_report()
    references_report = _references_report()
    submission_state, submission_state_error = _load_submission_state()
    checks: list[dict[str, Any]] = []

    for path in REQUIRED_DOCS:
        checks.append(
            _check(
                name=f"doc:{path.relative_to(ROOT)}",
                ok=path.exists(),
                detail=str(path),
            )
        )
    checks.append(
        _check(
            name="article_profile_valid",
            ok=not profile_report["errors"],
            detail=_profile_detail(profile_report),
        )
    )
    checks.append(
        _check(
            name="article_references_valid",
            ok=not references_report["errors"],
            detail=_references_detail(references_report),
        )
    )
    checks.append(
        _check(
            name="submission_state_valid",
            ok=submission_state_error is None,
            detail=submission_state_error or "submission_state.json schema is valid",
        )
    )

    checks.append(
        _check(
            name="submission_bundle_dir",
            ok=SUBMISSION_BUNDLE_DIR.exists(),
            detail=str(SUBMISSION_BUNDLE_DIR),
        )
    )
    checks.append(
        _check(
            name="submission_bundle_zip",
            ok=SUBMISSION_BUNDLE_ZIP.exists(),
            detail=str(SUBMISSION_BUNDLE_ZIP),
        )
    )

    dataset_runs = list(suite_summary.get("dataset_runs", ()))
    regression_item = next(
        (item for item in dataset_runs if str((item.get("dataset") or {}).get("task_type")) == "regression"),
        None,
    )
    classification_item = next(
        (
            item
            for item in dataset_runs
            if str((item.get("dataset") or {}).get("task_type")) == "binary_classification"
        ),
        None,
    )

    checks.extend(_dataset_checks("regression", regression_item))
    checks.extend(_dataset_checks("binary_classification", classification_item))

    for figure_name in REQUIRED_BUNDLE_FIGURES:
        path = SUBMISSION_BUNDLE_DIR / "figures" / figure_name
        checks.append(_check(name=f"figure:{figure_name}", ok=path.exists(), detail=str(path)))
    for table_name in REQUIRED_BUNDLE_TABLES:
        path = SUBMISSION_BUNDLE_DIR / "tables" / table_name
        checks.append(_check(name=f"table:{table_name}", ok=path.exists(), detail=str(path)))

    test_status: dict[str, Any] | None = None
    if run_tests:
        test_status = _run_article_tests()
        checks.append(
            _check(
                name="pytest_article_suite",
                ok=bool(test_status["ok"]),
                detail=test_status["detail"],
            )
        )

    best_results = {
        "regression": _best_result_payload(regression_item),
        "binary_classification": _best_result_payload(classification_item),
    }

    overall_ok = all(bool(item["ok"]) for item in checks)
    submission_items = _submission_items(submission_state)
    submission_ready = all(item["done"] for item in submission_items)
    report_payload = {
        "generated_at": _utc_now(),
        "suite_dir": str(resolved_suite_dir),
        "overall_status": "pass" if overall_ok else "fail",
        "submission_status": "ready"
        if overall_ok
        and submission_ready
        and profile_report["status"] == "ready"
        and references_report["status"] == "ready"
        else "pending",
        "profile_status": profile_report["status"],
        "references_status": references_report["status"],
        "profile_errors": profile_report["errors"],
        "profile_warnings": profile_report["warnings"],
        "profile_placeholder_warnings": profile_report["placeholder_warnings"],
        "references_errors": references_report["errors"],
        "references_warnings": references_report["warnings"],
        "references_placeholder_warnings": references_report["placeholder_warnings"],
        "checks": checks,
        "best_results": best_results,
        "manual_items": [{"status": "pending", "item": item} for item in MANUAL_ITEMS],
        "submission_state": submission_state,
        "submission_items": submission_items,
    }
    if test_status is not None:
        report_payload["test_status"] = test_status

    DEFAULT_REPORT_MD.write_text(_render_markdown(report_payload), encoding="utf-8")
    DEFAULT_REPORT_JSON.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _sync_report_into_bundle(DEFAULT_REPORT_MD, DEFAULT_REPORT_JSON)
    return DEFAULT_REPORT_MD


def _dataset_checks(task_name: str, item: dict[str, Any] | None) -> list[dict[str, Any]]:
    if item is None:
        return [_check(name=f"dataset:{task_name}", ok=False, detail="dataset run missing from article suite")]

    benchmark_dir = Path(str(item.get("benchmark_dir", "")))
    materials_dir = Path(str(item.get("materials_dir", "")))
    checks = [
        _check(name=f"{task_name}:benchmark_dir", ok=benchmark_dir.exists(), detail=str(benchmark_dir)),
        _check(name=f"{task_name}:materials_dir", ok=materials_dir.exists(), detail=str(materials_dir)),
    ]
    best_variant = item.get("best_variant") or {}
    checks.append(
        _check(
            name=f"{task_name}:best_variant",
            ok=bool(best_variant),
            detail=json.dumps(
                {
                    "variant_label": best_variant.get("variant_label"),
                    "metrics": {
                        key: value
                        for key, value in best_variant.items()
                        if str(key).startswith("test_")
                    },
                },
                ensure_ascii=False,
            ),
        )
    )
    return checks


def _best_result_payload(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    best_variant = item.get("best_variant") or {}
    if not best_variant:
        return None
    return {
        "dataset": (item.get("dataset") or {}).get("name"),
        "variant_label": best_variant.get("variant_label"),
        "metrics": {key: value for key, value in best_variant.items() if str(key).startswith("test_")},
    }


def _run_article_tests() -> dict[str, Any]:
    python_executable = ROOT / ".venv/bin/python"
    if not python_executable.exists():
        python_executable = Path(sys.executable)
    command = [
        str(python_executable),
        "-m",
        "pytest",
        "tests/test_toolbox_api.py",
        "tests/test_sdk_smoke.py",
        "tests/test_article_dataset_recipes.py",
        "tests/test_article_profile_cli.py",
        "tests/test_article_profile_validation.py",
        "tests/test_article_references_cli.py",
        "tests/test_article_references_validation.py",
        "tests/test_article_package_scripts.py",
        "tests/test_submission_state_cli.py",
        "-q",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    detail = (completed.stdout or completed.stderr).strip()
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command,
        "detail": detail,
    }


def _profile_report() -> dict[str, Any]:
    try:
        profile = load_article_profile()
    except Exception as error:  # pragma: no cover - defensive path for broken local configs
        return {
            "status": "invalid",
            "errors": [str(error)],
            "warnings": [],
            "placeholder_warnings": [],
        }
    return analyze_article_profile(profile)


def _references_report() -> dict[str, Any]:
    try:
        references = load_article_references()
    except Exception as error:  # pragma: no cover - defensive path for broken local configs
        return {
            "status": "invalid",
            "errors": [str(error)],
            "warnings": [],
            "placeholder_warnings": [],
        }
    return analyze_article_references(references)


def _profile_detail(profile_report: dict[str, Any]) -> str:
    if profile_report["errors"]:
        return "; ".join(profile_report["errors"])
    detail_parts = [f"profile_status={profile_report['status']}"]
    if profile_report["placeholder_warnings"]:
        detail_parts.append(
            "placeholders=" + "; ".join(profile_report["placeholder_warnings"])
        )
    elif profile_report["warnings"]:
        detail_parts.append("warnings=" + "; ".join(profile_report["warnings"]))
    return " | ".join(detail_parts)


def _references_detail(references_report: dict[str, Any]) -> str:
    if references_report["errors"]:
        return "; ".join(references_report["errors"])
    detail_parts = [f"references_status={references_report['status']}"]
    if references_report["placeholder_warnings"]:
        detail_parts.append(
            "placeholders=" + "; ".join(references_report["placeholder_warnings"])
        )
    elif references_report["warnings"]:
        detail_parts.append("warnings=" + "; ".join(references_report["warnings"]))
    return " | ".join(detail_parts)


def _load_submission_state() -> tuple[dict[str, Any], str | None]:
    path = ROOT / "docs/article/submission_state.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # pragma: no cover - defensive path for broken local configs
        return _default_submission_state(), f"submission_state.json could not be parsed: {error}"
    for key, _description in SUBMISSION_FLAGS:
        value = payload.get(key, False)
        if not isinstance(value, bool):
            default_state = _default_submission_state()
            return default_state, f"submission_state key `{key}` must be boolean"
        payload[key] = value
    notes = payload.get("notes", "")
    if not isinstance(notes, str):
        default_state = _default_submission_state()
        return default_state, "submission_state key `notes` must be a string"
    payload["notes"] = notes
    return payload, None


def _submission_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, description in SUBMISSION_FLAGS:
        items.append(
            {
                "key": key,
                "done": bool(state.get(key, False)),
                "description": description,
            }
        )
    return items


def _check(*, name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def _sync_report_into_bundle(markdown_path: Path, json_path: Path) -> None:
    docs_dir = SUBMISSION_BUNDLE_DIR / "docs"
    if not docs_dir.exists():
        return
    shutil.copy2(markdown_path, docs_dir / markdown_path.name)
    shutil.copy2(json_path, docs_dir / json_path.name)


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# RuFLEX article readiness report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- suite_dir: `{report['suite_dir']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- submission_status: `{report['submission_status']}`",
        f"- profile_status: `{report['profile_status']}`",
        f"- references_status: `{report['references_status']}`",
        "",
        "## Critical automated checks",
        "",
    ]
    for item in report["checks"]:
        status = "PASS" if item["ok"] else "FAIL"
        lines.append(f"- `{status}` {item['name']}: {item['detail']}")
    lines.extend(["", "## Best benchmark results", ""])
    for task_name, payload in report["best_results"].items():
        if payload is None:
            lines.append(f"- `{task_name}`: unavailable")
            continue
        metric_text = ", ".join(f"{key}={value}" for key, value in payload["metrics"].items())
        lines.append(
            f"- `{task_name}`: {payload['dataset']} -> {payload['variant_label']} ({metric_text})"
        )
    if "test_status" in report:
        lines.extend(
            [
                "",
                "## Test run",
                "",
                f"- returncode: `{report['test_status']['returncode']}`",
                f"- detail: `{report['test_status']['detail']}`",
            ]
        )
    if report["profile_placeholder_warnings"] or report["profile_warnings"] or report["profile_errors"]:
        lines.extend(["", "## Profile review", ""])
        for item in report["profile_errors"]:
            lines.append(f"- `error` {item}")
        for item in report["profile_warnings"]:
            lines.append(f"- `warning` {item}")
        for item in report["profile_placeholder_warnings"]:
            lines.append(f"- `placeholder` {item}")
    if report["references_placeholder_warnings"] or report["references_warnings"] or report["references_errors"]:
        lines.extend(["", "## References review", ""])
        for item in report["references_errors"]:
            lines.append(f"- `error` {item}")
        for item in report["references_warnings"]:
            lines.append(f"- `warning` {item}")
        for item in report["references_placeholder_warnings"]:
            lines.append(f"- `placeholder` {item}")
    lines.extend(["", "## Submission state", ""])
    for item in report["submission_items"]:
        status = "done" if item["done"] else "pending"
        lines.append(f"- `{status}` {item['description']}")
    lines.extend(["", "## Manual items", ""])
    for item in report["manual_items"]:
        lines.append(f"- `{item['status']}` {item['item']}")
    return "\n".join(lines)


def _load_suite_summary(suite_dir: Path) -> dict[str, Any]:
    summary_path = suite_dir / "article_suite_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Article suite summary was not found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


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


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _default_submission_state() -> dict[str, Any]:
    payload: dict[str, Any] = {key: False for key, _description in SUBMISSION_FLAGS}
    payload["notes"] = ""
    return payload


if __name__ == "__main__":
    main()
