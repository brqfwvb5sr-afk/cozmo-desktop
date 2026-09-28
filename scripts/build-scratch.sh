#!/usr/bin/env bash
# Build the pinned open-source Scratch editor. Run only on a development/build machine.
set -euo pipefail
cd "$(dirname "$0")/.."
scratch_ref="ec153a14c78cf95df60f333975bbde8d4f031531"
checkout="$PWD/build/scratch-editor"
mkdir -p build
if [[ ! -d "$checkout/.git" ]]; then
    git clone --filter=blob:none --depth=1 https://github.com/scratchfoundation/scratch-editor.git "$checkout"
fi
git -C "$checkout" fetch --depth=1 origin "$scratch_ref"
git -C "$checkout" checkout --detach "$scratch_ref"
# Restore only the upstream files patched by our overlay so a second build is
# reproducible. The build checkout is project-owned; never reset other files.
git -C "$checkout" restore -- \
    packages/scratch-vm/src/extension-support/extension-manager.js \
    packages/scratch-gui/src/containers/gui.jsx \
    packages/scratch-gui/src/playground/render-gui.jsx \
    packages/scratch-gui/src/components/menu-bar/menu-bar.jsx \
    packages/scratch-gui/src/reducers/locales.js
python3 frontend/scratch/apply_overlay.py "$checkout"
npm --prefix "$checkout" ci --no-audit --no-fund --ignore-scripts
npm --prefix "$checkout" run build
python3 frontend/scratch/copy_bundle.py "$checkout/packages/scratch-gui/build"
