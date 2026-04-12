from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]


def test_article_readiness_script_generates_reports() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_article_readiness.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    report_path = Path(result.stdout.strip())
    assert report_path.exists()

    json_path = ROOT / "docs/article/readiness_report.json"
    assert json_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "pass"
    assert any(item["name"] == "submission_bundle_zip" and item["ok"] for item in payload["checks"])
    assert any(item["name"] == "doc:docs/article/shablon_dokladov_ready.docx" and item["ok"] for item in payload["checks"])
    assert any(
        item["name"] == "doc:docs/article/conference_template_ready_en.docx" and item["ok"]
        for item in payload["checks"]
    )
    assert any(
        item["name"] == "doc:docs/article/shablon_dokladov_illustrated.docx" and item["ok"]
        for item in payload["checks"]
    )
    assert any(
        item["name"] == "doc:docs/article/conference_template_illustrated_en.docx" and item["ok"]
        for item in payload["checks"]
    )

    bundle_report = ROOT / "docs/article/submission_bundle/docs/readiness_report.md"
    assert bundle_report.exists()
    assert (ROOT / "docs/article/submission_bundle/docs/shablon_dokladov_ready.docx").exists()
    assert (ROOT / "docs/article/submission_bundle/docs/conference_template_ready_en.docx").exists()
    ru_illustrated = ROOT / "docs/article/submission_bundle/docs/shablon_dokladov_illustrated.docx"
    en_illustrated = ROOT / "docs/article/submission_bundle/docs/conference_template_illustrated_en.docx"
    assert ru_illustrated.exists()
    assert en_illustrated.exists()

    with zipfile.ZipFile(ru_illustrated) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())
    with zipfile.ZipFile(en_illustrated) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())


def test_illustrated_manuscripts_pick_up_article_profile() -> None:
    profile_path = ROOT / "docs/article/article_profile.json"
    original_text = profile_path.read_text(encoding="utf-8")
    payload = json.loads(original_text)
    payload["authors"][0]["name_ru"] = "Тестовый Автор"
    payload["authors"][0]["name_en"] = "Test Author"
    payload["authors"][0]["email"] = "test.author@example.com"
    payload["funding_ru"] = "Тестовое финансирование."
    payload["funding_en"] = "Test funding."

    try:
        profile_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/build_article_illustrated_manuscripts.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout

        ru_doc = Document(ROOT / "docs/article/shablon_dokladov_illustrated.docx")
        en_doc = Document(ROOT / "docs/article/conference_template_illustrated_en.docx")
        ru_text = "\n".join(paragraph.text for paragraph in ru_doc.paragraphs)
        en_text = "\n".join(paragraph.text for paragraph in en_doc.paragraphs)
        profile_card = (ROOT / "docs/article/article_profile_card.md").read_text(encoding="utf-8")
        final_metadata = (ROOT / "docs/article/final_metadata.md").read_text(encoding="utf-8")
        ready_ru = (ROOT / "docs/article/shablon_dokladov_ready.md").read_text(encoding="utf-8")
        ready_en = (ROOT / "docs/article/conference_template_ready_en.md").read_text(encoding="utf-8")
        rinc_md = (ROOT / "docs/article/rinc_draft.md").read_text(encoding="utf-8")
        rinc_txt = (ROOT / "docs/article/rinc_draft.txt").read_text(encoding="utf-8")

        assert "Тестовый Автор" in ru_text
        assert "test.author@example.com" in ru_text
        assert "Тестовое финансирование." in ru_text
        assert "Test Author" in en_text
        assert "test.author@example.com" in en_text
        assert "Test funding." in en_text
        assert "Тестовый Автор" in profile_card
        assert "test.author@example.com" in profile_card
        assert "Тестовый Автор" in ready_ru
        assert "Test Author" in ready_en
        assert "test.author@example.com" in ready_ru
        assert "test.author@example.com" in ready_en
        assert payload["title_ru"] in final_metadata
        assert payload["title_en"] in final_metadata
        assert "Тестовый Автор" in rinc_md
        assert "Test Author" in rinc_txt
    finally:
        profile_path.write_text(original_text, encoding="utf-8")
        subprocess.run(
            [sys.executable, "scripts/render_article_profile_docs.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(
            [sys.executable, "scripts/build_article_illustrated_manuscripts.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
