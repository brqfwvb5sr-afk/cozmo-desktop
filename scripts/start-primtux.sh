#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv312/bin/python ]]; then
    echo 'First run: bash scripts/setup-primtux.sh' >&2
    exit 1
fi
if ! .venv312/bin/python -c 'import PySide6, qasync, pycozmo, cozmo_desktop'; then
    echo 'Missing dependencies. Run bash scripts/setup-primtux.sh while online.' >&2
    exit 1
fi
if command -v curl >/dev/null && curl --noproxy '*' --silent --max-time 2 --fail http://127.0.0.1:11434/api/tags >/dev/null; then
    echo 'Ollama is responding on localhost.'
else
    echo 'Ollama is unavailable. Robot controls and non-AI features remain usable.'
fi
exec .venv312/bin/python -m cozmo_desktop --backend direct "$@"
