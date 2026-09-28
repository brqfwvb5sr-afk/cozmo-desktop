# Changelog

## Unreleased — PrimTux / local AI milestone

- Fix idle life (ambient personality) silently stopping for good when a queued command
  was cancelled before it ran (for example releasing a drive key right after a UI
  refresh); the Home page also no longer claims "eyes and sounds" when nothing runs.
- Resume idle life 2 s after manual, Code Lab or UI commands instead of restarting it
  between every 100 ms drive renewal; waking Cozmo still starts it immediately.
- A single refused face/sound frame no longer ends idle life; three in a row pause it
  with a plain reason and an automatic retry after 10 s. It never latches STOP.
- Direct worker: stale (pre-STOP) commands are discarded without disarming motors;
  refused face/sound/cube-light commands no longer lock the wheels; SDK faults in
  display/audio calls are reported instead of ending the robot session.
- Direct worker: a sound no longer sends StopAllMotors, which cut head/lift gestures
  short; it still stops wheels that are running.
- Show on Home whether idle life runs (or why not), when a face and a sound were last
  sent, whether PyCozmo's face/sound stream runs, Cozmo's own played-audio counter and
  the last refused command. The same safe fields are in the diagnostics export and
  refusals are logged.
- Add eyes-only glances between blinks and a short sound when Cozmo is set back down.
- Explain the 40 mm/s desktop speed cap on Control; the cap itself is unchanged.
- Physical validation of these changes on a real Cozmo is pending.

- Make PrimTux the primary target while retaining shared Ubuntu direct Wi-Fi code.
- Add read-only target inventory and honest PrimTux compatibility/validation docs.
- Add a configurable loopback-only Ollama provider, installed-model discovery,
  bounded conversation memory and validated safe reactions.
- Add optional local Vosk push-to-talk, stop-response control, model/resource status,
  and conservative opt-in cube-event speech during Freeplay.
- Physical PrimTux, microphone, offline Ollama and real Cozmo validation remain pending.

## 0.3.0 — 2026-09-28

- Add spontaneous procedural moods, gaze, blinking, five synthesized vocalizations and
  tappable cube-light invitations.
- React immediately to cube interactions and keep charging/hazard expressions stable.
- Preempt Freeplay roaming for cube interactions and pause it during cube invitations.
- Add an explicitly enabled slow floor-roaming mode; elevated surfaces keep wheels locked.
- Expose raw cliff telemetry and pickup/fall/charger flags for supervised checks.
- Include privacy-limited Ubuntu route and adapter details in the direct connection check.
- Reject HTTP redirects from the local Ollama chat endpoint so messages stay on loopback.
- Add a motor-locked cliff sensor trace for physical calibration.
- Add a channel-by-channel diagnostic comparison to exported cliff traces without unlocking table driving.
- Add original-code Quick Tap, Memory Match and Keepaway rule recreations with cube LEDs.
- Let Quick Tap's virtual Cozmo opponent respond on a timer and mark failed games clearly.
- Add optional local Ollama text conversation with bounded speech and emotion output.
- Animate Cozmo's eyes while a local conversation reply is pending; STOP cancels the animation.
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
