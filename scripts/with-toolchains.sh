#!/usr/bin/env bash
# Run a command with paperunit's local toolchains on PATH.
#
# This is a convenience for the workspace where optional toolchains are
# installed under .toolchains/ and .venv/ (both gitignored). On a normal
# machine, install Python/z3 and Lean yourself and skip this script.
#
# Usage:
#   scripts/with-toolchains.sh python3 -m paperunit run --audit examples/lean_demo/audit.json --out out/lean
#   scripts/with-toolchains.sh python3 -m unittest discover -s tests -v
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "$ROOT/.venv/bin" ]; then
  export PATH="$ROOT/.venv/bin:$PATH"
fi

if [ -d "$ROOT/.toolchains/elan/bin" ]; then
  export ELAN_HOME="${ELAN_HOME:-$ROOT/.toolchains/elan}"
  export PATH="$ROOT/.toolchains/elan/bin:$PATH"
fi

LEAN_BIN="$(find "$ROOT/.toolchains" -maxdepth 5 -type f -path '*/bin/lean' 2>/dev/null | head -n 1 || true)"
if [ -n "$LEAN_BIN" ]; then
  export PATH="$(dirname "$LEAN_BIN"):$PATH"
fi

exec "$@"
