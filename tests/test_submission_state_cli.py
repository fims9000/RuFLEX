from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs/article/submission_state.json"


def test_manage_submission_state_cli_updates_flags_and_notes() -> None:
    original_text = STATE_PATH.read_text(encoding="utf-8")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/manage_submission_state.py",
                "--reset",
                "--set",
                "profile_confirmed=true",
                "--set",
                "figures_finalized=true",
                "--notes",
                "Manual review in progress.",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout

        payload = json.loads(result.stdout)
        assert payload["profile_confirmed"] is True
        assert payload["figures_finalized"] is True
        assert payload["references_checked"] is False
        assert payload["notes"] == "Manual review in progress."

        persisted = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        assert persisted == payload
    finally:
        STATE_PATH.write_text(original_text, encoding="utf-8")
