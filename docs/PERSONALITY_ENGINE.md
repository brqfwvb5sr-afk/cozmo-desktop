# Personality direction

Version 0.3.0 adds a controller-owned personality director. It changes original
procedural eyes, blinks, shifts gaze and makes five original short synthesized
sounds. The chirp, grumble, question, happy and sleepy sounds are generated as
small PCM clips without proprietary samples and selected from the current mood.
Cube tap/movement events, hazard flags and battery voltage influence the mood.
Cube taps and movement receive prompt happy/question sounds, with a short reaction
cooldown. A continuing hazard changes the face once instead of flooding the OLED;
charging gives Cozmo a sleepy expression while blinking continues.
The director runs in both simulator and experimental direct Wi-Fi mode.
With a connected Power Cube, it occasionally lights one cube blue as an invitation.
A tap changes the cube briefly to green and Cozmo's eyes to Happy. The light is
cleared on timeout, cancellation, disconnect or game handoff.

Random and clock inputs are injected in tests. These behaviors are original-code
recreations, not the official Freeplay engine or proprietary animations/sounds.
There is no face identification, navigation map or automatic docking.

Default behavior is stationary. Short forward, arc and turn movements require a separate
Freeplay movement checkbox plus a connected, motor-armed robot on a clear floor.
Cube taps and movement interrupt a roaming pulse; active cube invitations pause
roaming until the invitation is resolved or times out.
Table/unknown surface selections lock wheels at the worker. Manual action, STOP,
disconnect, focus loss and navigation cancel behavior. No claim of table-edge
safety or physical validation is made.
