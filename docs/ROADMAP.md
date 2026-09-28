# Roadmap and scope

## Cozmo Code Lab milestone

The pinned real Scratch editor, 35 Cozmo blocks, local bridge, simulator commands,
STOP/Freeplay arbitration and German/French block labels are implemented and
browser/simulator tested. Remaining release gates: `.sb3` round-trip and example
projects, PrimTux/Ubuntu QtWebEngine package validation, performance measurement,
additional child-friendly blocks and physical robot validation. See
[Scratch architecture](SCRATCH_ARCHITECTURE.md) and
[physical validation](SCRATCH_PHYSICAL_VALIDATION.md). Do not present this milestone
as physically validated until those gates pass.

PrimTux is now the primary target and Ubuntu remains supported. The first
PrimTux/Ollama implementation adds local provider discovery, bounded conversation,
allowlisted reactions, optional Vosk push-to-talk, opt-in cube-event speech and
read-only platform inventory. Physical PrimTux, microphone, offline Wi-Fi and robot
validation are still pending; see [PHYSICAL_VALIDATION.md](PHYSICAL_VALIDATION.md).

## Implemented first milestone

- Native dark Qt shell with Home, Control, Expressions, Animations, Camera,
  Connection information, Settings and diagnostic export.
- Asynchronous simulator contract, conservative speed cap, drive lease, cancellation,
  latched stop, keyboard/mouse control, synthetic camera and robot state.
- Original expressions, simulated speech events, synthetic animations, favorites and
  one saved sequence. Camera snapshot destination is configurable.
- Unit/Qt tests, Linux CI, wheel/source build, Ubuntu 24.04 package recipe.

## Implemented 0.2.0: experimental direct adapter

- Explicit direct Wi-Fi mode, no phone, no automatic fallback or auto-arm.
- PyCozmo wheel/head/lift commands, OLED eyes, grayscale camera, eSpeak NG output.
- Detected cube connection/green LEDs and received tap/movement events.
- Separate worker with heartbeat/telemetry/drive expiry and process-failure tests.
- Ubuntu source setup using isolated Python 3.12; VMware USB-WLAN instructions.
- Physical validation is pending; no full Freeplay, AI, docking or original games.

## Next: hardware validation and optional bridge

Prove c64 SDK compatibility with modern Python, add a real adapter, ADB discovery,
connection wizard states, disconnection tests and capability discovery. Record
hardware results. Do not substitute the simulator on a hardware connection failure.

## Implemented 0.3.0: personality, game recreations and local text chat

- Original procedural mood, gaze, blinking and synthesized vocalizations.
- Explicitly enabled slow floor roaming; table/unknown modes keep wheels locked.
- Raw cliff telemetry and real status flags exposed for supervised observation.
- Quick Tap, Memory Match and Keepaway community rule recreations using cube events.
- Optional local Ollama text conversation limited to eyes and speech.
- Real robot behavior, table-edge safety and cube-game timing remain unverified.

## Experience and intelligence

Add real animation enumeration, face tracking and activities. Introduce optional
STT, richer local/API providers and a deterministic voice-command router. Keep
weather/music optional. No docking/return-to-charger claim without a capability.

## Direct connection and distribution

Verify the experimental PyCozmo adapter's protocol/session/motor behavior with
hardware before describing it as stable. Add more Ubuntu versions,
ARM, AppImage, reproducible dependency locking and signed releases after validation.
