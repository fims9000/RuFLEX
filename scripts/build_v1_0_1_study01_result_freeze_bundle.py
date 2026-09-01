"""Build a portable source-and-evidence bundle for RuFLEX V1.0.1 / Study 01."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release" / "RuFLEX_V1_0_1_STUDY01_RESULT_FREEZE.zip"
TOP = "RuFLEX_V1_0_1_STUDY01_RESULT_FREEZE"
ROOT_FILES = ("README.md", "LICENSE", "AGENTS.md", "pyproject.toml")
DIRS = ("src", "tests", "docs", "scripts", "examples", "frontend/src", "frontend/tests", "frontend/e2e", "frontend/.storybook", "research/study01_conformance_trace")
FRONTEND_FILES = ("frontend/index.html", "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/playwright.config.ts")
ARCHIVES = ("release/RuFLEX_PRODUCT_V1_RC2_SOURCE.zip", "release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip")
SKIP_PARTS = {"__pycache__", ".pytest_cache", "node_modules", "dist", "storybook-static", ".playwright-browsers", ".git", ".product-state", ".agent-state", ".venv", "release"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def permitted(path: Path) -> bool:
    return not any(part in SKIP_PARTS for part in path.parts) and path.suffix not in SKIP_SUFFIXES


def selected_files() -> list[Path]:
    files = [ROOT / name for name in ROOT_FILES] + [ROOT / name for name in FRONTEND_FILES] + [ROOT / name for name in ARCHIVES]
    for name in DIRS:
        directory = ROOT / name
        files.extend(path for path in directory.rglob("*") if path.is_file() and permitted(path.relative_to(ROOT)))
    archives = {Path(name) for name in ARCHIVES}
    return sorted({path for path in files if path.is_file() and (path.relative_to(ROOT) in archives or permitted(path.relative_to(ROOT)))})


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    files = selected_files()
    checksums = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    manifest = {
        "schema_version": 1,
        "bundle": "RuFLEX V1.0.1 + Study 01 RESULT FREEZE",
        "product_baseline_sha256": "772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224",
        "protocol_sha256": "fca2df2dc95318486c4c596905242d96d5fd5540311bfe4a7853e25d290e6838",
        "locked_manifest_hash": "ec75f178661cd32e8c418461ac782ece3708fb5641fed51baf9b850cf4b18580",
        "exclusions": sorted(SKIP_PARTS),
        "files": checksums,
    }
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f"{TOP}/{path.relative_to(ROOT).as_posix()}")
        archive.writestr(f"{TOP}/BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        archive.writestr(f"{TOP}/SHA256SUMS.txt", "".join(f"{digest}  {name}\n" for name, digest in checksums.items()))
    print(f"{OUT}\nsha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}\nfiles={len(files)}")


if __name__ == "__main__":
    main()
