# Personality direction

First milestone: stationary simulated idle expressions. Enabling the Home action
sets `freeplay=True`; synthetic face presence selects Curious versus Sleepy.
Drive, STOP, disconnect or navigation cancels it. This is not original Freeplay,
face tracking, autonomous exploration or a complete personality engine.

Next milestone: an event-driven state machine for idle, curious, happy, excited,
bored, sleepy, confused, surprised, annoyed, playful, exploring and social.
Use face/cube observations, elapsed idle time, low battery and conversation events.
Keep transitions deterministic in tests and inject randomness/clock when needed.

All actions must use RobotController. Default behavior must remain stationary;
future autonomous driving requires explicit user enablement, clear status and a
backend capability gate. Stop/disconnect cancels every pending behavior. A low
battery should suggest charging, never pretend to implement docking.
