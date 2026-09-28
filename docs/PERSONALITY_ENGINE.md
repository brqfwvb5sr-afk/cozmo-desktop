# Personality direction

Version 0.3.0 adds a controller-owned personality director. It changes original
procedural eyes, blinks, shifts gaze and makes original short synthesized sounds.
Cube tap/movement events, hazard flags and battery voltage influence the mood.
The director runs in both simulator and experimental direct Wi-Fi mode.

Random and clock inputs are injected in tests. These behaviors are original-code
recreations, not the official Freeplay engine or proprietary animations/sounds.
There is no face identification, navigation map or automatic docking.

Default behavior is stationary. Slow straight wheel nudges require a separate
Freeplay movement checkbox plus a connected, motor-armed robot on a clear floor.
Table/unknown surface selections lock wheels at the worker. Manual action, STOP,
disconnect, focus loss and navigation cancel behavior. No claim of table-edge
safety or physical validation is made.
