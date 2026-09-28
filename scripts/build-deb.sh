#!/usr/bin/env bash
# Build on Ubuntu 24.04 amd64. No privileged build operations or maintainer scripts.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f src/cozmo_desktop/code_lab/static/index.html || ! -f src/cozmo_desktop/code_lab/static/gui.js ]]; then
    echo "Cozmo Code Lab bundle is missing; build it with scripts/build-scratch.sh first." >&2
    exit 1
fi
if [[ "$(dpkg --print-architecture)" != amd64 ]]; then
    echo "This initial package recipe targets amd64 only." >&2
    exit 1
fi
if [[ "$(/usr/bin/python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != 3.12 ]]; then
    echo "Build with Ubuntu 24.04 system Python 3.12." >&2
    exit 1
fi
mkdir -p build dist
stage="$(mktemp -d "$PWD/build/deb.XXXXXX")"
/usr/bin/python3 -m build
/usr/bin/python3 -m venv "$stage/opt/cozmo-desktop/venv"
"$stage/opt/cozmo-desktop/venv/bin/python" -m pip install 'dist/cozmo_desktop-0.3.0-py3-none-any.whl[direct]'
"$stage/opt/cozmo-desktop/venv/bin/python" -m pip list --format=json > dist/runtime-dependencies.json
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/share/applications"
mkdir -p "$stage/usr/share/icons/hicolor/scalable/apps" "$stage/usr/share/doc/cozmo-desktop"
mkdir -p "$stage/usr/share/cozmo-desktop/examples"
cp examples/scratch/*.sb3 "$stage/usr/share/cozmo-desktop/examples/"
cat > "$stage/DEBIAN/control" <<'EOF'
Package: cozmo-desktop
Version: 0.3.0
Section: education
Priority: optional
Architecture: amd64
Maintainer: Cozmo Desktop contributors <aleunternaehrer@gmail.com>
Depends: python3 (>= 3.12), python3 (<< 3.13), libegl1, libopengl0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-randr0, libxcb-shape0, libxcb-xfixes0, libxcb-sync1, libxcb-render0, libxcb-shm0, libdbus-1-3, libfontconfig1
Homepage: https://github.com/brqfwvb5sr-afk/cozmo-desktop
Recommends: espeak-ng, xdg-utils
Description: Unofficial simulator-first Cozmo desktop companion
 Native Qt workspace with simulated controls, expressions and camera.
 Includes an opt-in experimental direct Wi-Fi adapter using PyCozmo.
EOF
cat > "$stage/usr/bin/cozmo-desktop" <<'EOF'
#!/bin/sh
exec /opt/cozmo-desktop/venv/bin/python -m cozmo_desktop "$@"
EOF
chmod 755 "$stage/usr/bin/cozmo-desktop"
cp scripts/cozmo-desktop.desktop "$stage/usr/share/applications/"
cp scripts/cozmo-desktop.svg "$stage/usr/share/icons/hicolor/scalable/apps/"
cp LICENSE "$stage/usr/share/doc/cozmo-desktop/copyright"
cp docs/THIRD_PARTY.md docs/PACKAGING.md "$stage/usr/share/doc/cozmo-desktop/"
cp docs/SCRATCH_INTEGRATION_PLAN.md docs/SCRATCH_ARCHITECTURE.md \
   docs/SCRATCH_EXTENSION.md "$stage/usr/share/doc/cozmo-desktop/"
cp -r docs/licenses "$stage/usr/share/doc/cozmo-desktop/"
cp dist/runtime-dependencies.json "$stage/usr/share/doc/cozmo-desktop/"
dpkg-deb --root-owner-group -Zgzip --build "$stage" dist/cozmo-desktop_0.3.0_amd64.deb
echo 'Package built. Install with: sudo apt install ./dist/cozmo-desktop_0.3.0_amd64.deb'
