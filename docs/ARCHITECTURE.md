# Architecture

Qt widgets → RobotController → RobotBackend → SimulatorBackend (milestone 1).

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
AI response validation is a pure allowlist boundary; no provider or network service
is enabled in this milestone. Planned modules are documented rather than exposed
as pretend-working screens. See ROADMAP.md.
