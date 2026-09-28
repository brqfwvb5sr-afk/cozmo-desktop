# Third-party code, dependencies and ideas

The application is GPL-3.0-or-later. Its UI, icon, procedural faces and synthetic
camera frames are original. No proprietary app assets are included. This is an
unofficial community project, unaffiliated with Anki or Digital Dream Labs.

## Cozmo Code Lab editor

Code Lab bundles a modified production build of the [Scratch Foundation
`scratch-editor` monorepo](https://github.com/scratchfoundation/scratch-editor)
at commit `ec153a14c78cf95df60f333975bbde8d4f031531` (15.1.2).
Its GUI, VM and related workspace packages declare `AGPL-3.0-only`.
The resolved [Scratch Blocks](https://github.com/scratchfoundation/scratch-blocks)
dependency is 2.1.19 and declares Apache-2.0. Source/build instructions and all
local changes are in `frontend/scratch/` and `scripts/build-scratch.sh`.
`src/cozmo_desktop/code_lab/static/` includes the upstream AGPL license, trademark
notice and generated JavaScript license notices. A binary redistributor must also
provide complete corresponding editor source and build information, and review
the lockfile's remaining transitive dependencies and their notices.

This project and Cozmo Code Lab are unofficial and not endorsed by the Scratch
Foundation. The project logo is original. Scratch name, logo and character
graphics are subject to the [upstream trademark notice](https://github.com/scratchfoundation/scratch-editor/blob/develop/TRADEMARK).
The editor is described as based on open-source Scratch technology solely for
attribution and compatibility. Do not use Scratch marks as product branding.

## Researched projects and selected transport

| Project | License inspected | Use |
| --- | --- | --- |
| [c64-dev/Cozmo.AI](https://github.com/c64-dev/Cozmo.AI) | GPL-3.0-or-later (`main.py` notice plus GPLv3 LICENSE) | Concepts: conversation/voice commands, idle behavior, photo and animation activities. No application code/assets copied. Standard GPL text reused as LICENSE. Credit: c64-dev. |
| [Anki Cozmo Python SDK](https://github.com/anki/cozmo-python-sdk) | Apache-2.0; Copyright 2016–2017 Anki Inc. in root notice | API/transport research only; no copied implementation or asset. |
| [c64-dev/cozmo-python-sdk](https://github.com/c64-dev/cozmo-python-sdk) | Apache-2.0, retaining Anki notices | Modernization/compatibility research only. |
| [zayfod/PyCozmo](https://github.com/zayfod/pycozmo) | MIT root; NOTICE additionally credits Apache-2.0 SDK and cozmoclad code, Copyright 2016–2019 Anki Inc. | Optional direct transport dependency, pinned 0.8.0. No external app resources. Root LICENSE/NOTICE and Apache text retained in docs/licenses. |
| [nexo-robot/nexo-pycozmo](https://github.com/nexo-robot/nexo-pycozmo) | Metadata declares MIT; a full per-file audit is pending if adopted | Python compatibility metadata inspected; not integrated. |

Exact inspected revisions and file-level findings: CONNECTION_RESEARCH.md.
Any future adaptation must preserve applicable notices and document file origins.
GPLv3 compatibility with Apache-2.0 is described by the
[Apache Software Foundation](https://apache.org/licenses/GPL-compatibility.html).

## Runtime dependencies

| Dependency/source | License | Use |
| --- | --- | --- |
| [PySide6 / Qt for Python](https://code.qt.io/cgit/pyside/pyside-setup.git/) | Community LGPL-3.0/GPL-3.0; module-specific notices apply | Native Qt GUI; QtCore, QtGui, QtWidgets only used. PySide wheels also install Essentials/Addons and Shiboken6. |
| [Qt](https://code.qt.io/cgit/qt/) | LGPL-3.0/GPL-3.0 and third-party notices by module | Dynamic GUI libraries supplied by PySide wheels. See [Qt licensing](https://doc.qt.io/qt-6/licensing.html). |
| [qasync](https://github.com/CabbageDevelopment/qasync) | BSD-2-Clause | Qt/asyncio event loop integration. |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU (HPND in older releases); bundled codecs carry their own notices | Original expression rasterization and synthetic camera/snapshot generation. |
| [Python](https://www.python.org/downloads/source/) | PSF-2.0 and included third-party notices | Interpreter; system dependency on Ubuntu. |

Dependencies are imported, not vendored into application source. Binary packages
retain upstream wheel metadata/licenses and dynamically load libraries.
The optional `[direct]` extra (also included in the development .deb) adds:

| Dependency/source | License | Use |
| --- | --- | --- |
| [PyCozmo 0.8.0](https://github.com/zayfod/pycozmo/tree/0.8.0) | MIT plus Apache-2.0 notices | Direct UDP protocol, image/audio encoding; imported, not copied |
| [NumPy](https://github.com/numpy/numpy) | BSD-3-Clause and bundled notices | PyCozmo math and camera decoding |
| [FlatBuffers](https://github.com/google/flatbuffers) | Apache-2.0 | PyCozmo import dependency; app animation resources unused |
| [dpkt 1.9.8](https://github.com/kbandla/dpkt) | BSD-3-Clause | PyCozmo import dependency |
| [eSpeak NG](https://github.com/espeak-ng/espeak-ng) | GPL-3.0-or-later plus bundled data notices | Optional Ubuntu system executable for local TTS, not vendored |
| [uv](https://github.com/astral-sh/uv) | Apache-2.0 OR MIT | Source setup helper; not an application runtime dependency |

No Selenium, speech recognition or external AI package is installed. No Anki SDK
package or proprietary animation/sound pack is downloaded. The optional Python
interpreter installed by uv retains its distribution notices.

## Build and test dependencies

| Dependency/source | License | Use |
| --- | --- | --- |
| [setuptools](https://github.com/pypa/setuptools), [wheel](https://github.com/pypa/wheel), [build](https://github.com/pypa/build) | MIT | Package builds |
| [pytest](https://github.com/pytest-dev/pytest), [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio), [pytest-qt](https://github.com/pytest-dev/pytest-qt) | MIT | Unit/async/Qt tests |
| [ruff](https://github.com/astral-sh/ruff) | MIT | Formatting and lint |
| [mypy](https://github.com/python/mypy), [mypy-extensions](https://github.com/python/mypy_extensions), [librt](https://github.com/mypyc/librt) | MIT | Static typing |
| [typing_extensions](https://github.com/python/typing_extensions) | PSF-2.0 | Typing support |
| [packaging](https://github.com/pypa/packaging) | Apache-2.0 OR BSD-2-Clause | Build/version metadata |
| [pyproject-hooks](https://github.com/pypa/pyproject-hooks), [pluggy](https://github.com/pytest-dev/pluggy), [iniconfig](https://github.com/pytest-dev/iniconfig) | MIT | Build and test infrastructure |
| [Pygments](https://github.com/pygments/pygments), [colorama](https://github.com/tartley/colorama) | BSD-2-Clause; BSD-3-Clause respectively | Test output formatting |
| [pathspec](https://github.com/cpburnz/python-pathspec) | MPL-2.0 | Mypy path matching |

Optional local conversation calls the user-installed
[Ollama HTTP API](https://github.com/ollama/ollama/blob/main/docs/api.md) over
`127.0.0.1` using Python's standard library. Ollama and its models are not bundled,
installed by this project or required to start the application. No code/assets are
copied from Ollama.

The [Anki SDK Quick Tap example](https://github.com/anki/cozmo-python-sdk/blob/master/examples/apps/quick_tap.py)
was consulted for the matching-color, red-trap and third-cube countdown rules.
No example source code, animation triggers or assets were copied; game behavior
here is independently implemented against the direct cube event interface.

Optional offline microphone input uses [Vosk](https://alphacephei.com/vosk/)
and [python-sounddevice](https://python-sounddevice.readthedocs.io/).
Their packages and separate speech models are not bundled into the current `.deb`.
Users select their own downloaded German/English Vosk model folders. The project's
code does not copy model files or microphone recordings into the repository.

[Ollama](https://ollama.com/) is a separately installed local server; models are
not bundled or downloaded by this project. Check the individual model license
before redistributing any model or a future all-in-one package.

GitHub Actions uses checkout, setup-python and upload-artifact from
[actions](https://github.com/actions), under MIT. Ubuntu system packages retain
their distribution copyright notices. For each binary build consult its generated
runtime-dependencies.json and installed `.dist-info/licenses` (or LICENSE metadata)
for the exact shipped versions/notices, including transitive binary libraries.
