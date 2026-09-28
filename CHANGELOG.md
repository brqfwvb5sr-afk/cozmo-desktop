# Changelog

## 0.3.0 — 2026-09-28

- Add spontaneous procedural moods, gaze, blinking, five synthesized vocalizations and
  tappable cube-light invitations.
- React immediately to cube interactions and keep charging/hazard expressions stable.
- Add an explicitly enabled slow floor-roaming mode; elevated surfaces keep wheels locked.
- Expose raw cliff telemetry and pickup/fall/charger flags for supervised checks.
- Add a motor-locked cliff sensor trace for physical calibration.
- Add a channel-by-channel diagnostic comparison to exported cliff traces without unlocking table driving.
- Add original-code Quick Tap, Memory Match and Keepaway rule recreations with cube LEDs.
- Add optional local Ollama text conversation with bounded speech and emotion output.
- Extend tests for cube event ordering, safety gates, personality and conversation.
- Physical robot, table-edge stopping and game timing validation remain pending.

## 0.2.0 — 2026-09-27

- Add opt-in experimental physical Wi-Fi adapter using PyCozmo 0.8.0.
- Wire wheels, head/lift, original OLED eyes, camera, eSpeak NG speech and cube LEDs.
- Isolate transport in a worker with explicit motor arming and command/telemetry expiry.
- Add real-codec, fake-transport process/pipe and Qt mode/reconnection tests.
- Add Python 3.12 source setup/start scripts and German VMware USB-WLAN instructions.
- Physical robot validation remains pending; no full Freeplay, AI or game engine.

## 0.1.0 — 2026-09-27

- Initial simulator-first milestone, connection research and native Qt foundation.
- Hardware bridge, direct protocol and external AI remain future work.
