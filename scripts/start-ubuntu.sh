#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv312/bin/python ]]; then
    echo 'First run: bash scripts/setup-ubuntu.sh' >&2
    exit 1
fi
exec .venv312/bin/python -m cozmo_desktop --backend direct "$@"
