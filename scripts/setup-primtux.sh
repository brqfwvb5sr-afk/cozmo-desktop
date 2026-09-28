#!/usr/bin/env bash
# Explicit project-local installation. Never changes system Python or installs Ollama.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then echo 'Linux is required.' >&2; exit 1; fi
bash scripts/primtux-info.sh
case "$(uname -m)" in
    x86_64|aarch64) ;;
    *) echo 'This architecture has not been verified with PySide6/PyCozmo wheels.' >&2; exit 1 ;;
esac
echo 'Installing project Python dependencies into .venv312 (network required once).'
bash scripts/setup-ubuntu.sh "$@"
echo 'For optional microphone dependencies use --with-voice; download Vosk models separately.'
echo 'Ollama is not installed or started by this script. See docs/OLLAMA.md.'
