# Safety and control ownership

All motion, including Code Lab, passes through the existing `RobotController` and backend safety controls. The native STOP button remains visible above the embedded Scratch editor. STOP latches synchronously, cancels Scratch tasks, stops backend motion and requires explicit Resume. Direct mode does not arm motors automatically. Floor mode and explicit arming are required before any Scratch wheel command; table and unknown modes stay locked. The direct worker retains its independent drive lease/watchdog.

Scratch can request only allowlisted, bounded high-level actions. Neither Scratch projects nor Ollama may set raw motor speeds, disable cliff protection, or change the STOP latch. Manual controller commands cancel active Scratch commands. Scratch commands pause Freeplay to avoid competing for robot resources. A Scratch stop block interrupts current Scratch actions; the desktop STOP is the emergency control.

The cliff/pickup/worker protections are implemented and tested with mocks or the simulator; physical behavior has **not** been validated. The table-edge policy remains conservative: no autonomous table driving.
