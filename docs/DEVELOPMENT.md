# Development

Python 3.11 and 3.12 are the CI targets. Use a venv; no hardware, account or API key
is necessary. See README for Ubuntu system packages and installation.

```bash
python -m pip install -e '.[dev,direct]'
pytest -q
ruff check .
ruff format --check .
mypy src
python -m build
python -m cozmo_desktop
```

For Linux CI/headless work:

```bash
QT_QPA_PLATFORM=offscreen pytest
QT_QPA_PLATFORM=offscreen python -m cozmo_desktop --config-dir /tmp/cozmo-test --smoke-test build/screenshots
```

On Windows, native Qt rendering is preferable for screenshots: the offscreen
plugin can lack usable fonts. Tests do not depend on screenshots or typography.
No WSL installation is needed or performed by the project.

Tests cover backend invariants, immutable state, lease expiry without UI refresh,
backend failures, controller cancellation/latching, settings, procedural expressions,
sequence validation/cancellation, untrusted AI fields, redacted diagnostics, and Qt
controls/focus/navigation. Qt unit tests drive refresh explicitly; the separate
smoke command exercises the actual qasync loop and process exit.

Use `--config-dir PATH` to isolate test settings. Runtime data never belongs in Git.
New backends must implement the ABC and independently enforce motor stop semantics.
Do not broaden simulator behavior into hardware claims.

Direct-mode tests construct the real PyCozmo codecs with an intercepted connection;
spawn/pipe/watchdog tests use a fake transport. They never connect to robot Wi-Fi.
Install `espeak-ng` to run the real local speech-encoding test (required in Linux CI).
`--smoke-test` rejects `--backend direct` before creating any robot connection.
