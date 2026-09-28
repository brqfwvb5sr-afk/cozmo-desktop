#!/usr/bin/env bash
# Read-only platform inventory. Avoid SSIDs, IPs, device serials and microphone audio.
set -u
cd "$(dirname "$0")/.."
echo 'Cozmo Desktop platform inventory'
if [[ -r /etc/os-release ]]; then
    . /etc/os-release
    printf 'Distribution: %s\nVersion: %s\nID: %s\nBase: %s\n' \
        "${NAME:-unknown}" "${VERSION_ID:-unknown}" "${ID:-unknown}" "${ID_LIKE:-unknown}"
fi
printf 'Architecture: %s\nKernel: %s\nDesktop: %s\n' \
    "$(uname -m)" "$(uname -r)" "${XDG_CURRENT_DESKTOP:-unknown}"
if command -v python3 >/dev/null; then python3 --version; else echo 'Python 3: missing'; fi
if [[ -x .venv312/bin/python ]]; then
    if .venv312/bin/python -c 'import PySide6, qasync' >/dev/null 2>&1; then
        echo 'Project Qt imports: available'
    else echo 'Project Qt imports: failed'; fi
else echo 'Project Qt imports: environment not installed'; fi
if command -v apt-get >/dev/null; then echo 'Package manager: apt'; else echo 'Package manager: unknown'; fi
if command -v nmcli >/dev/null; then
    echo 'NetworkManager: available'
    nmcli -t -f TYPE,STATE device status | sort -u
else echo 'NetworkManager: missing or not on PATH'; fi
if command -v lsusb >/dev/null; then echo 'USB enumeration: available'; else echo 'USB enumeration: unavailable'; fi
if command -v pactl >/dev/null; then
    printf 'Audio server: '
    pactl info 2>/dev/null | sed -n 's/^Server Name: /\1/p' | head -1
else echo 'Audio server: pactl unavailable'; fi
if command -v arecord >/dev/null; then
    if arecord -l 2>/dev/null | grep -q '^card '; then
        echo 'Microphone/recording devices: detected (capture unverified)'
    else echo 'Microphone/recording devices: none listed'; fi
else echo 'Microphone diagnostic: arecord unavailable'; fi
if command -v ollama >/dev/null; then ollama --version; else echo 'Ollama: not installed'; fi
if command -v curl >/dev/null && curl --noproxy '*' --silent --max-time 2 --fail http://127.0.0.1:11434/api/tags >/dev/null; then
    echo 'Ollama local service: responding'
else echo 'Ollama local service: not responding'; fi
if [[ -r /proc/meminfo ]]; then
    awk '/^(MemTotal|MemAvailable):/ {printf "%s %s kB\n", $1, $2}' /proc/meminfo
fi
printf 'CPU threads: '
getconf _NPROCESSORS_ONLN 2>/dev/null || echo unknown
