from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "docs/article/article_profile.json"


def test_manage_article_profile_cli_updates_profile_and_renders_docs() -> None:
    original_text = PROFILE_PATH.read_text(encoding="utf-8")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_article_profile.py",
                "--author-set",
                "1:name_ru=Иван Иванов",
                "--author-set",
                "1:name_en=Ivan Ivanov",
                "--author-set",
                "1:email=ivan.ivanov@example.org",
                "--author-set",
                "1:orcid=0000-0001-2345-6789",
                "--author-set",
                "1:affiliation_ru=Университет, Москва, Россия",
                "--author-set",
                "1:affiliation_en=University, Moscow, Russia",
                "--keywords-ru",
                "глубокое нечеткое обучение;геоаналитика;объяснимый ИИ",
                "--keywords-en",
                "deep fuzzy learning;geoanalytics;explainable ai",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert "Ivan Ivanov" in result.stdout

        payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        assert payload["authors"][0]["name_ru"] == "Иван Иванов"
        assert payload["authors"][0]["email"] == "ivan.ivanov@example.org"
        assert payload["keywords_en"] == ["deep fuzzy learning", "geoanalytics", "explainable ai"]

        profile_card = (ROOT / "docs/article/article_profile_card.md").read_text(encoding="utf-8")
        ready_ru = (ROOT / "docs/article/shablon_dokladov_ready.md").read_text(encoding="utf-8")
        assert "Иван Иванов" in profile_card
        assert "ivan.ivanov@example.org" in ready_ru
        assert "0000-0001-2345-6789" in ready_ru
    finally:
        PROFILE_PATH.write_text(original_text, encoding="utf-8")
        subprocess.run(
            [sys.executable, "scripts/render_article_profile_docs.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def test_manage_article_profile_cli_rejects_out_of_range_author_index() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/manage_article_profile.py",
            "--author-set",
            "99:name_ru=Nobody",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Author index out of range" in (result.stderr or result.stdout)


def test_manage_article_profile_cli_can_add_and_remove_authors() -> None:
    original_text = PROFILE_PATH.read_text(encoding="utf-8")

    try:
        add_result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_article_profile.py",
                "--author-add",
                "name_ru=Петр Петров|name_en=Petr Petrov|email=petr.petrov@example.org|orcid=0000-0002-3456-7890|affiliation_ru=Институт, Санкт-Петербург, Россия|affiliation_en=Institute, Saint Petersburg, Russia",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert add_result.returncode == 0, add_result.stderr or add_result.stdout

        added_payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        assert len(added_payload["authors"]) == 3
        assert added_payload["authors"][2]["name_en"] == "Petr Petrov"

        profile_card = (ROOT / "docs/article/article_profile_card.md").read_text(encoding="utf-8")
        assert "Petr Petrov" in profile_card

        remove_result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_article_profile.py",
                "--author-remove",
                "3",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert remove_result.returncode == 0, remove_result.stderr or remove_result.stdout

        removed_payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        assert len(removed_payload["authors"]) == 2
        assert all(author["name_en"] != "Petr Petrov" for author in removed_payload["authors"])
    finally:
        PROFILE_PATH.write_text(original_text, encoding="utf-8")
        subprocess.run(
            [sys.executable, "scripts/render_article_profile_docs.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
