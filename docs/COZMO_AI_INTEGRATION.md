# Cozmo.AI modernization

Inspected c64-dev/Cozmo.AI at c8646f0a84faabd1b7f8f195bed416cf20bdcf67 before coding.
Its LICENSE is GPL version 3; `main.py` explicitly grants version 3 or later and
credits c64-dev. This project chooses GPL-3.0-or-later. No upstream application
code, images, clock faces, sounds or command lists have been copied or adapted.
Only the standard GPL license text is reproduced verbatim.

| Upstream concept/source | Modernization decision | 0.3.0 status |
| --- | --- | --- |
| `listen_robot`, `recognize_google` | Optional STT service with explicit microphone state/consent | Planned |
| `AIBot` + Firefox/Selenium/Pandorabots | Replace scraping with optional local Ollama | Text-only local provider implemented |
| `check_time`, `check_weather` | Deterministic command router, optional weather provider with timeouts | Planned |
| Music/photo/dance/song checks | Capability-driven activities; no shell or browser command execution | Snapshot UI implemented; command routing planned |
| `freeplay`, `random_anim`, `bored_anim` | Cancellable personality service, stationary by default | Procedural expression/sound director plus explicit floor-only motion |
| Chat reply to `say_text` | Validate structured speech/emotion/action before dispatch | Local reply speaks and changes eyes; all model actions rejected |

The current PrimTux milestone adds a dedicated loopback-only Ollama provider and
optional local Vosk push-to-talk. The table above records the older 0.3.0 baseline.
Responses are never evaluated as code. Structured output permits only safe eye,
head/lift and sound reactions through `RobotController`; it cannot command wheels.
See [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) for the current pipeline and open
hardware-validation boundary.

If upstream code is later incorporated, preserve its GPL notices and authorship,
list exact files/changes in THIRD_PARTY.md, and keep the combined work compatible.
