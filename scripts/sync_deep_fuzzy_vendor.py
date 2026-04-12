from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (REPO_ROOT.parent / "deep-neuro-fuzzy").resolve()


def _run(command: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _remove_pycache(root: Path) -> None:
    for directory in root.rglob("__pycache__"):
        shutil.rmtree(directory)


def _write_snapshot_markdown(upstream_url: str, commit: str) -> None:
    content = (
        "# Vendored `ruanfis` Snapshot\n\n"
        f"- upstream repository: `{upstream_url}`\n"
        f"- vendored commit: `{commit}`\n"
        "- purpose: keep a local, controllable deep fuzzy backend snapshot inside `RuFLEX`\n\n"
        "The copy under `src/ruanfis` should stay as close to upstream as possible.\n"
        "RuFLEX-specific behavior belongs under `src/ruflex`, not inside the vendored backend,\n"
        "unless a compatibility fix is truly unavoidable.\n"
    )
    (REPO_ROOT / "docs" / "upstream" / "ruanfis_snapshot.md").write_text(content, encoding="utf-8")


def _write_vendor_manifest(upstream_url: str, commit: str) -> None:
    payload = {
        "upstream_repository": upstream_url,
        "vendored_commit": commit,
        "vendored_paths": [
            "src/ruanfis",
            "tests/upstream",
            "examples/upstream",
            "docs/upstream/deep_fuzzy_feature_learning.md",
        ],
        "copied_license_to_repo_root": True,
    }
    (REPO_ROOT / "docs" / "upstream" / "vendor_manifest.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def sync_vendor(source_repo: Path) -> None:
    if not source_repo.exists():
        raise FileNotFoundError(f"Source repository does not exist: {source_repo}")
    if not (source_repo / ".git").exists():
        raise FileNotFoundError(f"Source path is not a git repository: {source_repo}")

    upstream_url = _run(["git", "remote", "get-url", "origin"], cwd=source_repo)
    commit = _run(["git", "rev-parse", "HEAD"], cwd=source_repo)

    destination_src = REPO_ROOT / "src" / "ruanfis"
    destination_examples = REPO_ROOT / "examples" / "upstream"
    destination_tests = REPO_ROOT / "tests" / "upstream"
    destination_docs = REPO_ROOT / "docs" / "upstream"

    destination_src.parent.mkdir(parents=True, exist_ok=True)
    destination_examples.mkdir(parents=True, exist_ok=True)
    destination_tests.parent.mkdir(parents=True, exist_ok=True)
    destination_docs.mkdir(parents=True, exist_ok=True)

    _copy_tree(source_repo / "src" / "ruanfis", destination_src)
    _copy_tree(source_repo / "examples", destination_examples)
    _copy_tree(source_repo / "tests", destination_tests)
    shutil.copy2(
        source_repo / "docs" / "deep_fuzzy_feature_learning.md",
        destination_docs / "deep_fuzzy_feature_learning.md",
    )
    shutil.copy2(source_repo / "LICENSE", REPO_ROOT / "LICENSE")

    _remove_pycache(destination_src)
    _remove_pycache(destination_examples)
    _remove_pycache(destination_tests)

    _write_snapshot_markdown(upstream_url, commit)
    _write_vendor_manifest(upstream_url, commit)

    print("Vendored deep fuzzy snapshot updated.")
    print(f"source: {source_repo}")
    print(f"upstream: {upstream_url}")
    print(f"commit: {commit}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync vendored deep fuzzy backend from deep-neuro-fuzzy.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Path to the source deep-neuro-fuzzy repository. Default: {DEFAULT_SOURCE}",
    )
    args = parser.parse_args()
    sync_vendor(args.source.resolve())


if __name__ == "__main__":
    main()

