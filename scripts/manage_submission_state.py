from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs/article/submission_state.json"
FLAG_DESCRIPTIONS = {
    "profile_confirmed": "Подтверждены реальные authors / affiliations / e-mail / ORCID.",
    "references_checked": "Стартовый список литературы проверен и приведен к стилю площадки.",
    "figures_finalized": "Итоговые figures и captions окончательно утверждены.",
    "antiplagiat_screenshot_added": "В РИНЦ-файл добавлен реальный antiplagiat screenshot.",
    "layout_reviewed": "Итоговая верстка `.docx`/`.pdf` просмотрена вручную.",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or update docs/article/submission_state.json.")
    parser.add_argument(
        "--set",
        dest="updates",
        action="append",
        default=[],
        help="Update a flag using key=true or key=false. Can be passed multiple times.",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Replace the free-form notes field.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all submission flags back to false before applying updates.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the resulting state as JSON.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print the current submission state summary. This is also the default when no updates are passed.",
    )
    args = parser.parse_args()

    state = default_submission_state() if args.reset else load_submission_state()
    if args.notes is not None:
        state["notes"] = args.notes
    for item in args.updates:
        key, value = _parse_update(item)
        state[key] = value
    write_submission_state(state)

    if args.json:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return
    print(render_submission_state(state))


def load_submission_state() -> dict[str, object]:
    payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state = default_submission_state()
    for key in FLAG_DESCRIPTIONS:
        value = payload.get(key, False)
        state[key] = bool(value)
    state["notes"] = str(payload.get("notes", ""))
    return state


def write_submission_state(state: dict[str, object]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def default_submission_state() -> dict[str, object]:
    state: dict[str, object] = {key: False for key in FLAG_DESCRIPTIONS}
    state["notes"] = ""
    return state


def render_submission_state(state: dict[str, object]) -> str:
    pending = [key for key in FLAG_DESCRIPTIONS if not bool(state.get(key, False))]
    lines = [
        "# RuFLEX submission state",
        "",
        f"- path: `{STATE_PATH}`",
        f"- ready: `{'yes' if not pending else 'no'}`",
        "",
        "## Flags",
        "",
    ]
    for key, description in FLAG_DESCRIPTIONS.items():
        status = "done" if bool(state.get(key, False)) else "pending"
        lines.append(f"- `{status}` {key}: {description}")
    lines.extend(["", "## Notes", "", str(state.get("notes", "")) or "(empty)"])
    return "\n".join(lines)


def _parse_update(raw: str) -> tuple[str, bool]:
    if "=" not in raw:
        raise ValueError(f"Expected key=true or key=false, got: {raw}")
    key, value = raw.split("=", 1)
    key = key.strip()
    if key not in FLAG_DESCRIPTIONS:
        raise KeyError(f"Unknown submission flag: {key}")
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise ValueError(f"Submission flag must be true or false, got: {value}")
    return key, normalized == "true"


if __name__ == "__main__":
    main()
