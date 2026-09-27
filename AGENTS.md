# Cozmo Desktop contributor guide

Build an honest, polished Ubuntu companion for Cozmo. Direct Wi-Fi is experimental.
Never claim hardware support based on a mock or source inspection.

- `src/cozmo_desktop/robot`: asynchronous backend contract and simulator. No Qt here.
- `services`: safety and command ownership; every UI/AI action goes through this layer.
- `ui`: Qt widgets; never import a vendor robot SDK.
- `storage`, `face`, `animations`, `ai`: small independent, typed services.
- `docs/CONNECTION_RESEARCH.md`: pinned evidence, facts versus open questions.
- `tests`: hardware-free unit and Qt interaction tests.

Develop on Python 3.11/3.12: `pip install -e ".[dev,direct]"`.
Run `pytest`, `ruff check .`, `mypy src`, `python -m build`.
Linux headless tests: `QT_QPA_PLATFORM=offscreen pytest`.
Launch: `python -m cozmo_desktop`. Ubuntu packaging: see `docs/PACKAGING.md`.

Use type hints, dataclasses, small modules, explicit errors, bounded background tasks.
Keep Qt responsive with qasync. Never block its event loop with SDK or network calls.
Document architecture changes and test meaningful failure paths before committing.

Safety: conservative speed cap, expiring drive lease, stop on key release, focus/page
loss, disconnect, command error, shutdown. Emergency stop must cancel ongoing work,
clear held controls, and latch until explicitly resumed. No auto-drive on connect.
Future hardware adapters need their own watchdog; a GUI timer cannot protect against
a process crash. Never run hardware tests unattended or disable cliff detection.

License: GPL-3.0-or-later. Preserve upstream attribution if code is adapted.
No proprietary app assets, downloaded animation packs, API keys, profiles, or private
logs in Git. Document every dependency/adaptation in `docs/THIRD_PARTY.md`.
Direct communication is an explicit experimental opt-in requested by the owner.
Keep the simulator default. Never auto-connect, auto-arm or silently fall back.
Automated tests must use a fake transport; hardware validation requires supervision.
Do not claim physical validation until results are recorded in DIRECT_CONNECTION.md.
