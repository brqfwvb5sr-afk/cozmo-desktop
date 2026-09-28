# Local Ollama conversation

The application calls only a configured **loopback HTTP** Ollama server (default
`http://127.0.0.1:11434`). Proxies and HTTP redirects are disabled. It uses
Ollama's [model list](https://docs.ollama.com/api/tags) and
[chat API](https://docs.ollama.com/api/chat) with JSON output, a short token limit and
a 25-second HTTP timeout. It does not require an external API key. Existing robot
features keep working if Ollama is missing.

Install Ollama separately after reading its [official Linux instructions](https://docs.ollama.com/linux).
The project scripts never install or start it without an explicit user action.
Check `ollama --version` and `curl --noproxy '*' http://127.0.0.1:11434/api/tags`.
Download a model while Internet is available, then press **Refresh models** in Talk
with Cozmo. A candidate for weaker hardware is `gemma3:1b`; a larger candidate is
`gemma3:4b` ([official sizes](https://ollama.com/library/gemma3)). Model suitability
depends on the measured available RAM and CPU. The application warns if the selected
model file is larger than available RAM; this is only a heuristic. Neither model has
been tested on the owner's PrimTux PC.

## Offline microphone recognition

The optional voice extra uses local [Vosk](https://alphacephei.com/vosk/) with a
16 kHz mono microphone. On a compatible installation, install it into the project
environment while online:

```bash
.venv312/bin/python -m pip install -e '.[voice]'
```

If that environment uses uv without pip, use:

```bash
.venv-tools/bin/uv pip install --python .venv312/bin/python -e '.[voice]'
```

Download and extract separate Vosk model folders from the
[official model list](https://alphacephei.com/vosk/models), for example
`vosk-model-small-de-0.15` and `vosk-model-small-en-us-0.15` (about 45/40 MB
download; Vosk says small models commonly use about 300 MB at runtime). Set their
folder paths in Settings. No model is bundled or downloaded automatically. Microphone
and model performance remain unverified on PrimTux. French can be added later.

Conversation history is held only in memory during this session, capped at 20 turns;
Settings provides **Clear conversation memory**. When conversation memory is off,
only the current message and robot context are sent. The model sees structured state
such as charger, cube events and mood, never continuous camera frames. Stop response
or STOP cancels pending output. After all software and models are installed, this
path is designed to work while the only network is Cozmo Wi-Fi, but that exact
offline hardware setup still needs a physical test.
