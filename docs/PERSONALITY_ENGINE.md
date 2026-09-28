# Personality direction

Version 0.3.0 adds a controller-owned personality director. It changes original
procedural eyes, blinks, shifts gaze and makes five original short synthesized
sounds. The chirp, grumble, question, happy and sleepy sounds are generated as
small PCM clips without proprietary samples and selected from the current mood.
Cube tap/movement events, hazard flags and battery voltage influence the mood.
Cube taps and movement receive prompt happy/question sounds, with a short reaction
cooldown. A continuing hazard changes the face once instead of flooding the OLED;
charging gives Cozmo a sleepy expression while blinking continues.
The director runs in both simulator and experimental direct Wi-Fi mode. A
stationary ambient session now starts automatically when Cozmo connects and
resumes after individual commands. It does not require pressing Start Freeplay.
Manual commands, games, Code Lab and STOP preempt it. It blinks, shifts gaze,
changes mood and makes occasional sounds; small head and lift gestures require
motor arming, a clear-floor selection and no active hazard. The grumpy lift
gesture is a small original motion, not the mobile app's animation.
With a connected Power Cube, it occasionally lights one cube blue as an invitation.
A tap changes the cube briefly to green and Cozmo's eyes to Happy. The light is
cleared on timeout, cancellation, disconnect or game handoff.

Random and clock inputs are injected in tests. These behaviors are original-code
recreations, not the official Freeplay engine or proprietary animations/sounds.
There is no face identification, navigation map or automatic docking.

Default behavior is stationary. Checking **Let Cozmo roam on a clear floor**
starts movement-enabled Freeplay without a separate Start Freeplay click once
the robot is connected, motors are armed and **Clear floor** is selected. If
the checkbox is set first, arming motors starts roaming after those checks pass.
The checkbox can be cleared to stop roaming while ambient expressions continue.
Short forward, arc and turn movements remain slow and interruptible.
Cube taps and movement interrupt a roaming pulse; active cube invitations pause
roaming until the invitation is resolved or times out.
Table/unknown surface selections lock wheels at the worker. Manual action, STOP,
disconnect, focus loss and navigation cancel wheel behavior. On connection,
the wake sequence uses original eyes and sounds but never drives off a charger.
Automatic undocking awaits physical validation. Manual speed remains capped at
40 mm/s on the experimental direct backend; the Control slider selects up to
that cap. No claim of table-edge safety or physical validation is made.
# Local Ollama integration

The personality director continues to own autonomous moods, blinks, sounds and
optional floor roaming. Conversation temporarily preempts Freeplay through
`RobotController`, then resumes it only when connected, unlatched and safe. The
model receives structured state and can suggest allowlisted eyes/head/lift reactions
through the same controller. Spontaneous cube-event speech is opt-in, probabilistic
and cooldown-limited. No AI wheel commands or continuous camera frames are used.
See [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md).
