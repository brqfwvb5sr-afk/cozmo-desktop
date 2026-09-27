# Roadmap and scope

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

## Experience and intelligence

Add real animation enumeration, cube controls, face tracking, activities and a
separate personality engine. Introduce optional STT and API/local AI services,
conversation state and a deterministic voice-command router. Keep weather/music
optional. No docking/return-to-charger claim without an implemented capability.

## Direct connection and distribution

Verify the experimental PyCozmo adapter's protocol/session/motor behavior with
hardware before describing it as stable. Add more Ubuntu versions,
ARM, AppImage, reproducible dependency locking and signed releases after validation.
