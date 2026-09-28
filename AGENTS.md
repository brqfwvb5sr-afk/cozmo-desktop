# Cozmo Desktop contributor guide

Build an honest, polished PrimTux-first companion for Cozmo. Ubuntu remains supported.
The exact PrimTux base/version must be inventoried, never guessed. Ollama on localhost
is the primary AI provider; offline use after model installation is a major goal.
No mandatory cloud APIs or API keys. AI output is untrusted and can never bypass
the controller, motor arming, STOP, cliff/pickup safety or worker watchdog.
Direct Wi-Fi is experimental.
Never claim hardware support based on a mock or source inspection.
Code Lab uses the real Scratch 3 open-source editor from the pinned Scratch Foundation
monorepo. Never substitute a custom Blockly clone without explicit instruction.
PrimTux remains primary; Ubuntu remains supported. Scratch and Ollama must not
require Internet for normal use after installation. Never add a mandatory cloud API.
The Scratch extension uses only the token-protected local API and existing robot
controller; it must never bypass STOP, arming, cliff/pickup protection or watchdogs.
Respect Scratch AGPL source obligations and trademarks. Do not copy proprietary
Anki/Digital Dream Labs assets. Never claim physical validation without a real test.

- `src/cozmo_desktop/robot`: asynchronous backend contract and simulator. No Qt here.
- `services`: safety and command ownership; every UI/AI action goes through this layer.
- `ui`: Qt widgets; never import a vendor robot SDK.
- `storage`, `face`, `animations`, `ai`: small independent, typed services.
- `code_lab`: allowlisted local bridge and bundled upstream Scratch editor.
- `frontend/scratch`: pinned upstream build overlay, extension and translations.
- `docs/CONNECTION_RESEARCH.md`: pinned evidence, facts versus open questions.
- `tests`: hardware-free unit and Qt interaction tests.

Develop on Python 3.11/3.12: `pip install -e ".[dev,direct]"`.
Run `pytest`, `ruff check .`, `mypy src`, `python -m build`.
Linux headless tests: `QT_QPA_PLATFORM=offscreen pytest`.
Launch: `python -m cozmo_desktop`. Ubuntu packaging: see `docs/PACKAGING.md`.
Rebuild the editor: `bash scripts/build-scratch.sh` on a Linux build host with
Node 24 and network access. Use the pinned upstream commit; keep generated runtime
assets and complete corresponding source available for distributed builds.

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
