# Cozmo Scratch extension

The Cozmo category is a built-in Scratch VM extension from `frontend/scratch/cozmo-extension/index.js`. The custom source is part of this repository and is bundled into the pinned upstream editor during the release build. It uses Scratch's normal `getInfo()` API, block types and project serialization. German and French strings are in `frontend/scratch/translations.json`; English is the default. The language follows the editor's locale.

Initial blocks: move distance, turn, timed drive, stop, head angle, lift percent, expression, clear face, say and wait, sound, animation, cube color; connection/pickup/cliff/person/cube event hats; connection, battery, pickup, cliff, cube connection/tap/motion, person, head, lift and last-error reporters; optional AI question, AI speech and last answer. The generated category has 35 blocks. Standard Scratch loops, conditions, variables, broadcasts and custom blocks are upstream functionality and remain available.

Movement limits are enforced in Python, even if a project edits block arguments: distance −50 to 50 cm, turn −180 to 180 degrees, speed −20 to 20 mm/s, timed drive 0 to 3 seconds, head −25 to 44.5 degrees, lift 0 to 100%. Wheels are renewed at 100 ms intervals and stopped in a `finally` block. Physical movement still requires explicit motor arming on a clear floor. The distance and turn timing is approximate; it is not physically calibrated.

Expressions are restricted to the procedural faces in the app. Animations come only from the selected backend's existing list. Cube colors currently support red, green, blue and off; yellow needs backend support before a traffic-light example can claim it. No original game assets are copied. `ask Cozmo AI` returns only validated speech from the existing Ollama service; it does not perform AI-selected robot actions. `Cozmo AI say` speaks that validated answer. If Ollama is unavailable, blocks fail gracefully and the message reporter explains why.

The event poll uses the existing `RobotState`, including cube tap/move sequence counters. A connected cube is **not** called visually seen. Cube-seen and cube-visible blocks remain pending because the direct backend does not expose reliable visual cube detection. Battery can be unknown in direct mode, so the reporter returns 0 when unavailable; a future block should distinguish unknown from an empty battery.

The Scratch green flag starts Scratch scripts; it does not arm physical motors. The native desktop STOP remains above the embedded editor and latches robot control even if Scratch scripts keep running visually. Changing pages or manual input cancels Scratch robot actions.

## Original lesson projects

Seven `.sb3` lessons are in `examples/scratch/`: Hello Cozmo, Square Drive,
Cube Reaction, Traffic Light, Mood Machine, AI Conversation and Safe Explorer.
The package installs them in `/usr/share/cozmo-desktop/examples/`; open one with
**File → Load from your computer** and save with Scratch's normal **Save to your
computer** action. Their SVG stage/sprite assets are original. The traffic-light
lesson uses red, green and blue because the backend does not yet support yellow.
AI Conversation requires a local Ollama model; other lessons do not. Square Drive
and Safe Explorer are for simulator or controlled **floor** testing only. The
generator `frontend/scratch/create_examples.py` creates standard Scratch project
archives and can be rerun by maintainers.
