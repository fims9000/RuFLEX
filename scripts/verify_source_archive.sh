#!/usr/bin/env bash
# Verify what is actually tracked at HEAD, never the caller's dirty worktree.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
archive_root="$(mktemp -d "${TMPDIR:-/tmp}/ruflex-source-archive.XXXXXX")"
cleanup() { rm -rf "$archive_root"; }
trap cleanup EXIT

git -C "$root" archive --format=tar HEAD | tar -xf - -C "$archive_root"
python_bin="${RUFLEX_PYTHON:-python3}"

if [[ "${RUFLEX_ARCHIVE_SKIP_INSTALL:-0}" != "1" ]]; then
  "$python_bin" -m pip install -e "$archive_root[dev,studio]"
fi

(
  cd "$archive_root"
  PYTHONPATH=src "$python_bin" -m compileall -q src/ruflex
  PYTHONPATH=src "$python_bin" -m pytest -q \
    tests/test_model_catalog.py tests/test_plugins.py tests/test_training_product_route.py \
    tests/test_runtime_registry.py tests/test_runtime_entrypoint_plugin.py tests/test_runtime_model_adapter_matrix.py
)
(
  cd "$archive_root/frontend"
  npm ci
  npm test
  npm run build
  npm run build-storybook
)

echo "RuFLEX tracked-source archive smoke: PASS"
