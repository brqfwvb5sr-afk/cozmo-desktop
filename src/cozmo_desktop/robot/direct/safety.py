"""Independent worker safety policy; no Qt or transport dependencies."""

from dataclasses import dataclass

from cozmo_desktop.robot.base import RobotError

GUI_TIMEOUT = 0.8
TELEMETRY_TIMEOUT = 0.8
DRIVE_TIMEOUT = 0.35


@dataclass
class SafetyGuard:
    last_gui: float = 0.0
    last_state: float = 0.0
    wheel_deadline: float | None = None
    armed: bool = False
    hazard: bool = False
    reason: str = "Motor control locked. Select Enable motors after connecting."

    def arm(self, now: float) -> None:
        if self.hazard or now - self.last_state > TELEMETRY_TIMEOUT:
            raise RobotError(
                "Cannot enable motors: stale state, cliff, pickup or charger detected."
            )
        self.armed = True
        self.last_gui = now
        self.reason = "Motor control enabled. Keep Cozmo on a clear floor."

    def require_motion(self, now: float) -> None:
        if not self.armed or self.hazard or now - self.last_state > TELEMETRY_TIMEOUT:
            raise RobotError("Motor control locked. Put Cozmo on the floor, then enable motors.")

    def trip(self, reason: str) -> None:
        self.armed = False
        self.wheel_deadline = None
        self.reason = reason

    def expired(self, now: float) -> str | None:
        if now - self.last_gui > GUI_TIMEOUT:
            return "Desktop heartbeat lost. Reconnect to Cozmo."
        if now - self.last_state > TELEMETRY_TIMEOUT:
            return "Robot telemetry lost. Reconnect to Cozmo."
        if self.armed and self.hazard:
            return "Cliff, pickup, falling or charger detected. Motors locked."
        if self.wheel_deadline is not None and now >= self.wheel_deadline:
            return "Drive command expired. Motors locked."
        return None
