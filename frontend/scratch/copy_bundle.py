"""Copy only runtime Scratch assets from an upstream build into the Python package."""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "src/cozmo_desktop/code_lab/static"


def main(source: Path) -> None:
    if not (source / "gui.js").is_file() or not (source / "index.html").is_file():
        raise RuntimeError("Scratch GUI build is incomplete")
    if DESTINATION.resolve() != (ROOT / "src/cozmo_desktop/code_lab/static").resolve():
        raise RuntimeError("Refusing to replace an unexpected bundle directory")
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name in (
        "gui.js",
        "gui.js.LICENSE.txt",
        "extension-worker.js",
        "extension-worker.js.LICENSE.txt",
    ):
        file = source / name
        if file.is_file():
            shutil.copyfile(file, DESTINATION / name)
    for directory in ("static", "chunks"):
        target = DESTINATION / directory
        shutil.copytree(
            source / directory,
            target,
            dirs_exist_ok=True,
            ignore=lambda _path, names: [
                name
                for name in names
                if name.endswith(".map") or name in {"README.md", "favicon.ico"}
            ],
        )
    html = (source / "index.html").read_text(encoding="utf-8")
    html = html.replace("Scratch 3.0 GUI", "Cozmo Code Lab")
    html = html.replace('href="static/favicon.ico"', 'href="code-lab-logo.svg"')
    (DESTINATION / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(ROOT / "frontend/scratch/code-lab-logo.svg", DESTINATION / "code-lab-logo.svg")
    shutil.copyfile(source.parents[2] / "LICENSE", DESTINATION / "SCRATCH-LICENSE.txt")
    shutil.copyfile(source.parents[2] / "TRADEMARK", DESTINATION / "SCRATCH-TRADEMARK.txt")
    shutil.copyfile(
        source.parents[2] / "node_modules/scratch-blocks/LICENSE",
        DESTINATION / "SCRATCH-BLOCKS-LICENSE.txt",
    )
    print(f"Copied Scratch runtime bundle to {DESTINATION}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python copy_bundle.py /path/to/scratch-gui/build")
    main(Path(sys.argv[1]).resolve())
