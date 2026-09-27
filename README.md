# Cozmo Desktop

A native, open-source desktop companion for Anki Cozmo, built for Ubuntu with
Python and Qt. A place for controls, expressions, camera and, eventually, personality
and conversation — with a hardware-independent architecture from the start.

**Version 0.2.0 adds opt-in experimental direct Wi-Fi control of a physical Cozmo.**
It is implemented and tested without hardware, but **not yet validated on a real robot**.
Simulation remains the default; no phone or API key is needed.

**Ubuntu / VMware / USB-WLAN: [Einrichtung für deinen echten Cozmo](docs/DIRECT_CONNECTION.md).**
The setup script uses Python 3.12 even if Ubuntu ships Python 3.14.

![Cozmo Desktop Home, running in Simulation Mode](docs/screenshots/home.png)

*Actual application capture on Windows using native Qt. Linux CI also renders the
application; its captures are attached to each successful Actions run.*

## Features

- Native dark desktop workspace with Home, Control, Expressions, Animations,
  Camera, Connection, Cubes and Settings.
- Connect/disconnect a simulated Cozmo; inspect battery, pose, wheels, head, lift,
  synthetic face/cube state and camera readiness.
- Hold graphical controls or WASD to drive. Head arrows and R/F lift controls.
- Conservative 40 mm/s default, 80 mm/s cap, expiring drive lease, stop on release,
  focus/navigation loss, errors and disconnect. Physical mode defaults to 20 mm/s,
  caps at 40 mm/s and requires explicit motor arming. STOP latches desktop controls.
- Nine original procedural expressions, four synthetic animations, search,
  favorites and local sequence save/load.
- Direct mode: local eSpeak NG speech through Cozmo’s speaker; simulator: text events.
- Direct mode: real grayscale camera, OLED faces and cube connect/green LEDs/tap events.
- Simulator: synthetic camera with test overlays. Both modes support PNG snapshots.
- Local settings and allowlisted diagnostic export; no cloud or microphone access.

## Current status and connection support

| Mode | Status | Phone required? |
| --- | --- | --- |
| Simulator | Implemented; automated backend/UI tests | No |
| SDK bridge | Researched; adapter not implemented | Yes, for this connection architecture |
| Direct Wi-Fi | Implemented, opt-in experimental; physical validation pending | No |

The direct adapter sends real robot commands through PyCozmo 0.8.0. It never falls
back to simulation on a connection error. The original SDK talks
to the engine in the mobile app. PyCozmo implements a different, direct protocol.
Read [connection research](docs/CONNECTION_RESEARCH.md) for pinned source evidence,
compatibility concerns, licensing boundaries and unresolved questions.

## Ubuntu requirements and installation

Source/CI targets: Ubuntu 22.04 with Python 3.11, Ubuntu 24.04 with Python 3.12.
Ubuntu 22.04's default Python 3.10 is too old; provide a Python 3.11 interpreter or
use Ubuntu 24.04. Ubuntu 26.04/ARM have not been validated. Python 3.14 is unsupported.

On Ubuntu 24.04:

```bash
sudo apt update
sudo apt install git python3-venv libegl1 libopengl0 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0 libxcb-xinerama0 fonts-dejavu-core

git clone https://github.com/brqfwvb5sr-afk/cozmo-desktop.git
cd cozmo-desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m cozmo_desktop
```

The `cozmo-desktop` launcher is also available after installation. For physical control,
install the `[direct]` extra and eSpeak NG, or use `bash scripts/setup-ubuntu.sh`.
Start with `bash scripts/start-ubuntu.sh` or select Direct Wi-Fi under Connection.
See the [hardware instructions and limitations](docs/DIRECT_CONNECTION.md).

An Ubuntu 24.04 amd64 `.deb` recipe and installation smoke test are included in CI.
Download a successful build's `ubuntu-24.04-amd64-deb` artifact from
[GitHub Actions](https://github.com/brqfwvb5sr-afk/cozmo-desktop/actions), extract it,
then run:

```bash
sudo apt install ./cozmo-desktop_0.2.0_amd64.deb
```

This adds Cozmo Desktop to the application menu. These are development artifacts,
not signed stable releases. See [packaging](docs/PACKAGING.md) for local builds,
source obligations and supported versions. AppImage is planned.

## First connection and simulation mode

1. Launch the app. The persistent **Simulation Mode** banner identifies synthetic data.
2. Select **Connect simulator**, or **Wake Cozmo** on Home.
3. Open **Control**, hold a direction and release it to stop.
4. Adjust head/lift, enter text and select Speak; the simulated utterance appears below.
5. Try Expressions, play an animation, or open the synthetic Camera.
6. Select **STOP** to cancel all activity. Select **Resume controls** to unlock again.

| Key | Behavior on Control page |
| --- | --- |
| W / A / S / D | Hold to drive forward / left / back / right |
| Up / Down | Head angle |
| R / F | Lift up / down |
| Space | Emergency stop (outside text inputs; STOP button is always available) |

Typing in a text field cannot drive the robot. Moving focus to a text field, switching
pages or deactivating the window stops movement. The simulator independently stops
unrenewed wheel commands after 350 ms, checked every 50 ms. This is software simulation,
not a claim of a tested physical safety mechanism.

Home's idle-expression mode changes only the eyes; it is **not** the original
Freeplay engine. No docking, autonomous driving, face identification or cube games
are implemented. Simulated cube tap/movement and face detection events support tests;
the Cubes page additionally exposes real connection, tap/movement events and green LEDs
in direct mode. Cube battery and orientation remain unknown.

## AI configuration and Cozmo.AI integration

No AI provider is enabled in 0.2.0. The application starts without any API key.
A strict, tested structured-response validator establishes the future action
allowlist; it does not make network calls or execute model instructions.

Cozmo.AI was inspected before implementation. Its concepts informed the roadmap,
but no application code/assets were copied and its `main.py` is not launched.
Selenium chatbot scraping will be replaced by optional API/local providers and
separate STT services. See [integration status](docs/COZMO_AI_INTEGRATION.md).

Future OpenAI support will read `OPENAI_API_KEY` from the environment or a secure
credential store. Do not paste keys into tracked settings or commit `.env` files.

## Local data and diagnostics

Settings and the saved sequence live under `$XDG_CONFIG_HOME/cozmo-desktop`, falling
back to `~/.config/cozmo-desktop`. Use `--config-dir PATH` for an isolated instance.
Snapshots default to `~/Pictures/Cozmo/`; change the folder in Settings.

Settings → Diagnostics → Export produces a small JSON report containing only
version, platform, connection and safety flags. Speech, paths, environment variables,
profile information and raw exceptions are excluded. Rotating structured logs record
operation names and error types, never provider response bodies or speech text.

## Development and checks

```bash
pytest -q
ruff check .
ruff format --check .
mypy src
python -m build
QT_QPA_PLATFORM=offscreen python -m cozmo_desktop \
  --config-dir /tmp/cozmo-test --smoke-test build/screenshots
```

See [architecture](docs/ARCHITECTURE.md), [development](docs/DEVELOPMENT.md),
[AGENTS.md](AGENTS.md) and [contributing](CONTRIBUTING.md). Tests require no robot.
Version 0.2.0 local validation: Python 3.12/Windows, 90 passing tests (the eSpeak NG
test is reserved for Linux CI), Ruff, mypy and native Qt smoke test. Tests include real
PyCozmo packet encoding and a spawned worker with fake hardware. Physical validation
is pending. Ubuntu 22.04/Python 3.11 and Ubuntu 24.04/Python 3.12 passed the initial
CI suite and Qt smoke tests; the Ubuntu 24.04 `.deb` built, installed and launched.
Each subsequent commit reruns validation. See the repository Actions page for results
on the exact revision you download, including the installed package's X11 launch check.

## Roadmap

1. Hardware-validate the experimental direct adapter and record actual firmware results.
2. Add animation discovery, cube controls, face tracking and cancellable personality states.
3. Add optional speech recognition, provider-based conversation and safe voice commands.
4. Evaluate an optional modern SDK/phone bridge without proprietary assets.
5. Expand Ubuntu targets, AppImage packaging and release reproducibility.

The detailed [roadmap](docs/ROADMAP.md) distinguishes existing features from planned work.

## Troubleshooting

- **Qt xcb plugin fails to load:** install the Ubuntu libraries listed above and run
  in a desktop session. Use `QT_QPA_PLATFORM=offscreen` only for headless tests.
- **No physical robot detected:** select Direct Wi-Fi, attach the USB Wi-Fi adapter to
  Ubuntu, join Cozmo’s network and close the phone app. See DIRECT_CONNECTION.md.
- **Controls stay stopped:** select Resume controls; in direct mode also Enable motors
  on Connection after putting Cozmo on the floor. Reconnect after a connection failure.
- **Invalid settings:** the app keeps the original file, reports the issue and uses
  safe defaults. Correct it or save new settings explicitly.
- **No voice/audio:** simulator speech is text-only; direct TTS requires `espeak-ng`.
  Speech recognition and AI conversation are not implemented.
- **Snapshots fail:** choose a writable folder in Settings.
- **Windows offscreen screenshots have boxes instead of fonts:** use native Qt rendering.

## Credits, license and disclaimer

Inspired by the Cozmo community, [c64-dev/Cozmo.AI](https://github.com/c64-dev/Cozmo.AI),
the [Anki SDK](https://github.com/anki/cozmo-python-sdk), its c64-dev fork and
[PyCozmo](https://github.com/zayfod/pycozmo). See [third-party details](docs/THIRD_PARTY.md).

Copyright © 2026 Cozmo Desktop contributors. Licensed under
[GPL-3.0-or-later](LICENSE). No proprietary mobile graphics, fonts, sounds or animation
packs are distributed. Cozmo is a product name of its respective owners.

**Unofficial community project. Not affiliated with Anki or Digital Dream Labs.**
