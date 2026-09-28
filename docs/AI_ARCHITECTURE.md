# AI architecture and safety boundary

Code Lab's optional AI blocks call the existing `ConversationService` through
`ScratchCommands`. The validated structured Ollama reply contributes only speech
text to `ask Cozmo AI` or `Cozmo AI say`; model-selected robot actions are ignored
in these blocks. The editor does not load or contact Ollama at startup. Missing
models and timeouts return a safe block error. See [Scratch extension](SCRATCH_EXTENSION.md).

`Talk with Cozmo` → `RobotController` → `ConversationService` → `AIProvider` →
`OllamaProvider` → loopback Ollama. Optional `VoskPushToTalk` produces text for the
same path. The provider knows nothing about the robot backend.

The conversation service sends a character prompt, a bounded 20-turn session
history and structured robot state. Its output passes `validate_response` before
the controller considers a reaction. Unknown JSON keys, raw motor fields, code,
shell/network requests, unknown expressions/sounds/actions and oversized speech
are rejected. The allowlist contains eye gaze and bounded head/lift reactions;
**no AI wheel commands** exist. Head/lift actions require an already armed clear
floor and no hazard; they do not arm motors. STOP, disconnection, pickup, charger,
fall and cliff state suppress AI output. The independent physical worker retains
its own watchdog, lease and cliff stop.

Typed and microphone conversations preempt Freeplay; after the reply or a cancelled
generation, Freeplay resumes only if the controller is still connected and not
latched. User actions take priority. Spontaneous AI speech is disabled by default;
when enabled, it only considers cube events after a long cooldown and a probability
gate. No continuous camera upload or periodic model polling occurs.

The HTTP request is asynchronous relative to Qt and has bounded response bytes and
timeouts. Cancelling the UI task prevents its reply from reaching Cozmo; Python's
background HTTP thread may finish its local request later. Physical timing remains
unverified. See [personality](PERSONALITY_ENGINE.md) and
[validation](PHYSICAL_VALIDATION.md).
