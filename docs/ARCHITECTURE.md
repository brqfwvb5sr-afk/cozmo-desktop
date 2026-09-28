# Architecture

Qt widgets → RobotController → RobotBackend → SimulatorBackend or DirectBackend.

DirectBackend uses an inherited local multiprocessing pipe to a spawned worker.
Only that worker imports/constructs the PyCozmo client and owns UDP. A 150-ms desktop
heartbeat, 800-ms telemetry/heartbeat timeouts, 350-ms drive expiry, generation
checks after STOP and explicit motor arming bound command lifetime. The worker
publishes immutable real status snapshots and JPEG previews; a bounded sender queue
prevents a blocked GUI pipe from blocking its watchdog. Pipe EOF stops the session.
Physical STOP delivery and firmware reaction to lost Wi-Fi remain unverified.
See DIRECT_CONNECTION.md for the experimental boundary and supervised test matrix.

Speech is synthesized off the Qt loop by an optional local eSpeak NG executable,
using stdin and fixed arguments. The worker validates WAV format/size, stops motors
before audio encoding, then sends PyCozmo audio packets. No microphone or cloud is used.
OLED eyes are original procedural images; no upstream resource downloader is called.
The personality director and cube-game director are cancellable controller tasks.
Only the worker can send physical commands. Freeplay wheel nudges require explicit
floor selection and arming; the worker independently rejects table/unknown movement.
Raw cliff sensor readings are diagnostic until supervised measurements establish
their behavior. The robot's cliff-stop protocol setting remains enabled.

qasync integrates Qt and asyncio on one event loop. Immutable state snapshots keep
presentation separate from backend mutation. Controller-owned tasks isolate errors,
enforce safety, and allow emergency cancellation without a queued STOP. Widgets
never see vendor SDK classes. Camera frames are Pillow images, not Qt objects.

The simulator publishes connection, battery, pose, wheels, head/lift, speech,
animation, face detection and cube state. All data is explicitly synthetic.
Drive uses a renewable short lease; release/focus loss/navigation ends it.
Emergency stop latches until Resume; errors fail closed. Future hardware backends
must implement independent command expiry and report capabilities accurately.

Settings use atomic JSON writes under XDG_CONFIG_HOME/cozmo-desktop or
~/.config/cozmo-desktop. Diagnostics export an allowlisted report with no settings,
environment, speech content, profile names or raw exceptions. Logs contain operation
and exception type, not user text or secret-bearing provider responses.

Expression and sequence services operate on the controller, never on raw hardware.
Optional local chat uses a bounded POST to Ollama at `127.0.0.1`; it runs in a thread
and only after Send. The strict response validator permits bounded speech and known
emotions. The conversation path refuses every model-requested action. Conversation
history stays in memory and is cleared when switching backend; it is not logged or
exported. No microphone or cloud service is used. See ROADMAP.md.
