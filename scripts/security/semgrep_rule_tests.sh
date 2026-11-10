#!/usr/bin/env bash
# Run the annotated fixtures in .semgrep/tests against .semgrep/vams-security.yml.
# `semgrep --test` pairs rule and test files by mirrored name, so both are
# copied into a temporary rules/ and tests/ layout. Offline: no metrics, no
# version check.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SEMGREP="${SEMGREP:-semgrep}"
export SEMGREP_ENABLE_VERSION_CHECK=0
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/rules" "$WORK/tests"
cp "$ROOT/.semgrep/vams-security.yml" "$WORK/rules/vams-security.yml"
cp "$ROOT/.semgrep/tests/vams-security.py" "$WORK/tests/vams-security.py"
cp "$ROOT/.semgrep/tests/vams-security.js" "$WORK/tests/vams-security.js"
cp "$ROOT/.semgrep/tests/vams-launch.sh" "$WORK/tests/vams-security.sh"
cd "$WORK"
"$SEMGREP" --test --metrics off --config rules tests
