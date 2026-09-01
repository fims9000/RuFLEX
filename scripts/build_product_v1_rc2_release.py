"""Build a source-only, reproducible-inspection RuFLEX Product V1 RC2 archive."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release" / "RuFLEX_PRODUCT_V1_RC2_SOURCE.zip"
TOP = "RuFLEX_PRODUCT_V1_RC2"
ROOT_FILES = ("README.md", "LICENSE", "AGENTS.md", "pyproject.toml")
DIRS = ("src", "tests", "docs", "scripts", "examples", "frontend/src", "frontend/tests", "frontend/e2e", "frontend/.storybook")
FRONTEND_FILES = ("frontend/index.html", "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/playwright.config.ts")
SKIP_PARTS = {"__pycache__", ".pytest_cache", "node_modules", "dist", "storybook-static", ".playwright-browsers", ".git", "release", ".product-state"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def permitted(path: Path) -> bool:
    return not any(part in SKIP_PARTS for part in path.parts) and path.suffix not in SKIP_SUFFIXES


def files() -> list[Path]:
    selected = [ROOT / name for name in ROOT_FILES] + [ROOT / name for name in FRONTEND_FILES]
    for name in DIRS:
        selected.extend(path for path in (ROOT / name).rglob("*") if path.is_file() and permitted(path.relative_to(ROOT)))
    return sorted({path for path in selected if path.is_file() and permitted(path.relative_to(ROOT))})


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files(): archive.write(path, f"{TOP}/{path.relative_to(ROOT).as_posix()}")
    print(f"{OUT}\nsha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__": main()
