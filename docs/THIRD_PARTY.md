# Third-party code, dependencies and ideas

The application is GPL-3.0-or-later. Its UI, icon, procedural faces and synthetic
camera frames are original. No proprietary app assets are included. This is an
unofficial community project, unaffiliated with Anki or Digital Dream Labs.

## Researched projects (not installed or bundled)

| Project | License inspected | Use |
| --- | --- | --- |
| [c64-dev/Cozmo.AI](https://github.com/c64-dev/Cozmo.AI) | GPL-3.0-or-later (`main.py` notice plus GPLv3 LICENSE) | Concepts: conversation/voice commands, idle behavior, photo and animation activities. No application code/assets copied. Standard GPL text reused as LICENSE. Credit: c64-dev. |
| [Anki Cozmo Python SDK](https://github.com/anki/cozmo-python-sdk) | Apache-2.0; Copyright 2016–2017 Anki Inc. in root notice | API/transport research only; no copied implementation or asset. |
| [c64-dev/cozmo-python-sdk](https://github.com/c64-dev/cozmo-python-sdk) | Apache-2.0, retaining Anki notices | Modernization/compatibility research only. |
| [zayfod/PyCozmo](https://github.com/zayfod/pycozmo) | MIT root; NOTICE additionally credits Apache-2.0 SDK and cozmoclad code, Copyright 2016–2019 Anki Inc. | Direct protocol research only. Do not assume MIT covers external app resources. |
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
retain upstream wheel metadata/licenses and dynamically load libraries. No SDK,
PyCozmo, Selenium, audio-recognition or external AI package is installed.

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

GitHub Actions uses checkout, setup-python and upload-artifact from
[actions](https://github.com/actions), under MIT. Ubuntu system packages retain
their distribution copyright notices. For each binary build consult its generated
runtime-dependencies.json and installed `.dist-info/licenses` (or LICENSE metadata)
for the exact shipped versions/notices, including transitive binary libraries.
