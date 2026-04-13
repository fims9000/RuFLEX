from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES_PATH = ROOT / "docs/article/article_references.json"


def test_manage_article_references_cli_can_add_update_and_remove_entries() -> None:
    original_text = REFERENCES_PATH.read_text(encoding="utf-8")

    try:
        add_result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_article_references.py",
                "--add",
                "key=test_reference|ru=Тестовая русская ссылка.|en=Test English reference.",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert add_result.returncode == 0, add_result.stderr or add_result.stdout

        update_result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_article_references.py",
                "--set",
                "test_reference:en=Updated English reference.",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert update_result.returncode == 0, update_result.stderr or update_result.stdout

        payload = json.loads(REFERENCES_PATH.read_text(encoding="utf-8"))
        test_item = next(item for item in payload if item["key"] == "test_reference")
        assert test_item["en"] == "Updated English reference."

        references_ru = (ROOT / "docs/article/references_ru_gost.md").read_text(encoding="utf-8")
        references_en = (ROOT / "docs/article/references_en_ieee.md").read_text(encoding="utf-8")
        assert "Тестовая русская ссылка." in references_ru
        assert "Updated English reference." in references_en

        remove_result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_article_references.py",
                "--remove",
                "test_reference",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert remove_result.returncode == 0, remove_result.stderr or remove_result.stdout
        payload = json.loads(REFERENCES_PATH.read_text(encoding="utf-8"))
        assert all(item["key"] != "test_reference" for item in payload)
    finally:
        REFERENCES_PATH.write_text(original_text, encoding="utf-8")
        subprocess.run(
            [sys.executable, "scripts/manage_article_references.py", "--sync"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def test_manage_article_references_cli_rejects_unknown_key() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/manage_article_references.py",
            "--set",
            "missing_reference:en=Nope",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Unknown reference key" in (result.stderr or result.stdout)
