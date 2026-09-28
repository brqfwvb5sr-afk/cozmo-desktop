# Freeplay and games implementation plan

The owner wants a lively physical Cozmo: spontaneous mood changes, blinking, gaze,
vocalizations, self-directed movement, conversational play, the familiar cube games,
and protection at table edges. This is the end state, not a simulator-only milestone.

## Acceptance work

1. **Independent personality.** A controller-owned, cancellable state machine
   reacts to real cube events and robot state, blinks, shifts gaze, changes mood,
   makes original synthesized vocalizations, and looks around. No proprietary
   animations/sounds. Unit tests inject a clock/random stream and real SDK codecs.
2. **Autonomous movement.** Explicitly opt in, separate from motor arming. Slow,
   short, renewed wheel commands only while fresh state shows no cliff, pickup,
   fall or charger. Manual action, STOP, disconnect, focus loss and mode change
   preempt Freeplay. Floor-only until a physical safety gate is measured.
3. **Table-edge handling.** Surface selector and raw sensor diagnostics. Keep the
   robot's EnableStopOnCliff and worker watchdog active. Table mode must fail
   closed for wheel commands until a supervised hardware measurement establishes
   safe detection/stopping; no code-only claim that a fall is impossible. Record
   approach directions, surface types, sensor data, delays and measured stop
   distances. Add regression tests for missing/stale/hazardous readings.
4. **Games.** Build original-code gameplay for Quick Tap, Memory Match and
   Keepaway around connected Power Cube LEDs and timestamped tap/move events.
   Quick Tap uses matching colors, a red no-tap rule and a third countdown cube.
   Use deterministic rule tests, game cancellation and UI score/state. Identify
   these as community recreations; the official app's graphics, engine, unlock
   state and proprietary content are not distributable here.
5. **Conversation.** Provide typed, local interaction that affects Cozmo's mood
   and speaks through his speaker. Microphone remains a subsequent opt-in, as
   requested. Do not imply a scripted responder is open-ended AI. Add a provider
   boundary for optional local/API language models without requiring keys.
6. **Verification.** Run unit/Qt/spawned-worker tests, Windows and Ubuntu CI,
   source/.deb builds. Supervised physical checks are necessary for actual
   motion, cliff detection, cube gameplay timing and audio fidelity. Record
   results in DIRECT_CONNECTION.md before marking those requirements verified.

Primary references: [PyCozmo cliff sensor and stop protocol](https://pycozmo.readthedocs.io/en/stable/external/functions.html),
[official Cozmo play-space caution](https://support.anki.bot/article/236-where-to-play-with-cozmo),
[official introduction to Quick Tap, Keepaway, Memory Match](https://anki.bot/pages/life-with-cozmo-1),
and the [Apache-licensed SDK Quick Tap example](https://github.com/anki/cozmo-python-sdk/blob/master/examples/apps/quick_tap.py)
for game-rule comparison. No example source code or animation assets are copied.
