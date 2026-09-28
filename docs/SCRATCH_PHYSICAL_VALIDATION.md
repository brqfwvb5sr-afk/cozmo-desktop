# Scratch Code Lab physical validation

Status: **not performed**. Automated simulator and browser tests do not validate real Cozmo hardware, the owner's PrimTux device, or cliff protection at an edge.

Record the actual PrimTux version, architecture, RAM, kernel, desktop, QtWebEngine version, USB Wi-Fi interface and package build first. Then, with an adult supervising and Cozmo on a clear **floor**, record date, firmware, Cozmo connection and each result:

1. Connect and disconnect; confirm the Code page status updates.
2. Test speech, face, head and lift blocks with motors still locked.
3. Test cube colors, tap/move events and connection reporters.
4. Test native STOP while a non-moving script runs; verify cancellation and latch.
5. Pick up Cozmo during a short, slow floor drive; verify immediate stop.
6. Run a short, slow drive and turn on the floor; measure distance and angle error.
7. Run a Scratch repeat loop on the floor and press STOP mid-loop.
8. Observe cliff flags with **wheels locked**. Do not run an autonomous table-edge script to test the sensors.
9. Only after the earlier protections are confirmed, design any controlled edge test with a human ready to catch the robot.

For every test, record expected/observed behavior, the STOP response, and whether a command was rejected. A pass requires real measurements on the named hardware; leave unrun items pending. The direct worker watchdog and cliff controls require separate physical checks in [PHYSICAL_VALIDATION.md](PHYSICAL_VALIDATION.md).
