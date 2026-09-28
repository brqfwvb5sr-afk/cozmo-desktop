"""Apply narrow Code Lab changes to an exact upstream scratch-editor checkout."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "upstream.json").read_text(encoding="utf-8"))["ref"]


def replace(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError(f"Upstream changed: expected one occurrence in {path}: {old[:55]}")
    path.write_text(source.replace(old, new), encoding="utf-8")


def main(root: Path) -> None:
    actual = subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()
    if actual != EXPECTED:
        raise RuntimeError(f"Scratch source mismatch: expected {EXPECTED}, got {actual}")
    vm = root / "packages/scratch-vm/src"
    gui = root / "packages/scratch-gui/src"
    extension = vm / "extensions/cozmo"
    extension.mkdir(exist_ok=True)
    shutil.copyfile(HERE / "cozmo-extension/index.js", extension / "index.js")
    replace(
        vm / "extension-support/extension-manager.js",
        "    coreExample: () => require('../blocks/scratch3_core_example'),",
        "    coreExample: () => require('../blocks/scratch3_core_example'),\n"
        "    cozmo: () => require('../extensions/cozmo'),",
    )
    replace(
        gui / "containers/gui.jsx",
        "        this.props.onVmInit(this.props.vm);",
        "        this.props.onVmInit(this.props.vm);\n"
        "        this.props.vm.extensionManager.loadExtensionURL('cozmo');",
    )
    # The playground normally links its logo to the Scratch website. Code Lab is offline.
    replace(
        gui / "playground/render-gui.jsx",
        "    window.location = 'https://scratch.mit.edu';",
        "    // Code Lab does not navigate to an external site.",
    )
    replace(
        gui / "playground/render-gui.jsx",
        "                backpackVisible\n",
        "                backpackVisible={false}\n",
    )
    shutil.copyfile(HERE / "code-lab-logo.svg", gui / "components/menu-bar/code-lab-logo.svg")
    replace(
        gui / "components/menu-bar/menu-bar.jsx",
        "import scratchLogo from './scratch-logo.svg';",
        "import scratchLogo from './code-lab-logo.svg';",
    )
    shutil.copyfile(HERE / "translations.json", gui / "lib/cozmo-translations.json")
    replace(
        gui / "reducers/locales.js",
        "import editorMessages from 'scratch-l10n/locales/editor-msgs';",
        "import editorMessages from 'scratch-l10n/locales/editor-msgs';\n"
        "import cozmoMessages from '../lib/cozmo-translations.json';\n"
        "const mergedMessages = Object.fromEntries(\n"
        "    Object.entries(editorMessages).map(([locale, messages]) => [\n"
        "        locale, {...messages, ...(cozmoMessages[locale] || {})}\n"
        "    ])\n"
        ");",
    )
    replace(
        gui / "reducers/locales.js",
        "messagesByLocale: editorMessages,",
        "messagesByLocale: mergedMessages,",
    )
    replace(
        gui / "reducers/locales.js",
        "messages: editorMessages.en",
        "messages: mergedMessages.en",
    )
    # micro:bit's upstream prepare step downloads a firmware image. The Cozmo
    # distribution does not ship that unrelated hardware asset.
    generated = gui / "generated/microbit-hex-url.cjs"
    generated.parent.mkdir(exist_ok=True)
    generated.write_text("module.exports = '';\n", encoding="utf-8")
    print(f"Applied Cozmo Code Lab overlay to Scratch {EXPECTED}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python apply_overlay.py /path/to/scratch-editor")
    main(Path(sys.argv[1]).resolve())
