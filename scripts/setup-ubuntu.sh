#!/usr/bin/env bash
# Run while connected to the Internet. Uses a project-local Python 3.12 environment.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then
    echo 'This script is for Linux.' >&2
    exit 1
fi
if [[ $# -gt 1 || ( $# -eq 1 && ${1:-} != --with-voice ) ]]; then
    echo 'Usage: setup-ubuntu.sh [--with-voice]' >&2
    exit 2
fi
extras='.[direct]'
if [[ ${1:-} == --with-voice ]]; then extras='.[direct,voice]'; fi
if command -v uv >/dev/null 2>&1; then
    uv_cmd=(uv)
elif [[ -x .venv/bin/uv ]]; then
    uv_cmd=(.venv/bin/uv)
else
    python3 -m venv .venv-tools
    .venv-tools/bin/python -m pip install 'uv>=0.8,<1'
    uv_cmd=(.venv-tools/bin/uv)
fi
if [[ -x .venv312/bin/python ]]; then
    if ! .venv312/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12)'; then
        echo 'Existing .venv312 is not Python 3.12. Move it aside before retrying.' >&2
        exit 1
    fi
else
    "${uv_cmd[@]}" venv --python 3.12 .venv312
fi
"${uv_cmd[@]}" pip install --python .venv312/bin/python -e "$extras"
echo 'Installed. Connect the USB Wi-Fi adapter to Cozmo, then:'
echo 'bash scripts/start-ubuntu.sh'
