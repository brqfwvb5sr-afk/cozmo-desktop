# Cozmo.AI modernization

Inspected c64-dev/Cozmo.AI at c8646f0a84faabd1b7f8f195bed416cf20bdcf67 before coding.
Its LICENSE is GPL version 3; `main.py` explicitly grants version 3 or later and
credits c64-dev. This project chooses GPL-3.0-or-later. No upstream application
code, images, clock faces, sounds or command lists have been copied or adapted.
Only the standard GPL license text is reproduced verbatim.

| Upstream concept/source | Modernization decision | 0.1.0 status |
| --- | --- | --- |
| `listen_robot`, `recognize_google` | Optional STT service with explicit microphone state/consent | Planned |
| `AIBot` + Firefox/Selenium/Pandorabots | Replace scraping with an async provider interface | Planned |
| `check_time`, `check_weather` | Deterministic command router, optional weather provider with timeouts | Planned |
| Music/photo/dance/song checks | Capability-driven activities; no shell or browser command execution | Snapshot UI implemented; command routing planned |
| `freeplay`, `random_anim`, `bored_anim` | Cancellable personality service, stationary by default | Simple simulated idle expressions only |
| Chat reply to `say_text` | Validate structured speech/emotion/action before dispatch | Pure strict allowlist parser implemented and tested; no AI provider |

Future module boundary: `ai/providers/base.py` → optional `openai.py` and `local.py`;
`voice` handles capture/transcription separately. No provider packages, API calls,
keys or microphone dependency are required at startup. Responses must never be
evaluated as code. The current parser permits only `none`, `greet`, `stop`, known
emotions and bounded speech. It does not execute any actions.

If upstream code is later incorporated, preserve its GPL notices and authorship,
list exact files/changes in THIRD_PARTY.md, and keep the combined work compatible.
