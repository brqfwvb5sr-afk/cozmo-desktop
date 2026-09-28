"""Bounded motor-locked observations for physical cliff-sensor validation."""

import time
from pathlib import Path

from cozmo_desktop.robot.base import RobotError, RobotState
from cozmo_desktop.storage.settings import atomic_json

LABELS = ("center", "front edge", "rear edge", "left edge", "right edge")
MAX_SAMPLES = 300


class CliffTrace:
    def __init__(self) -> None:
        self.active = False
        self.label = "center"
        self.samples: list[dict[str, object]] = []
        self._started = 0.0
        self.message = "Motor-locked cliff trace is idle."

    def start(self, state: RobotState, *, now: float | None = None) -> None:
        if state.backend_name != "direct" or not state.connected:
            raise RobotError("Connect to the physical Cozmo before recording sensor data.")
        if state.motors_enabled or state.left_speed or state.right_speed:
            raise RobotError("Lock motors and stop the wheels before recording cliff data.")
        self.samples.clear()
        self._started = time.monotonic() if now is None else now
        self.active = True
        self.label = "center"
        self.message = "Recording sensor readings with motors locked."

    def stop(self) -> None:
        self.active = False
        self.message = f"Trace stopped: {len(self.samples)} samples."

    def observe(self, state: RobotState, *, now: float | None = None) -> None:
        if not self.active:
            return
        if state.backend_name != "direct" or not state.connected:
            self.stop()
            return
        if state.motors_enabled:
            self.stop()
            self.message = "Recording stopped because motor control was enabled."
            return
        if len(self.samples) >= MAX_SAMPLES:
            self.stop()
            return
        elapsed = (time.monotonic() if now is None else now) - self._started
        self.samples.append(
            {
                "elapsed_ms": max(0, round(elapsed * 1000)),
                "label": self.label,
                "raw": list(state.cliff_raw) if state.cliff_raw is not None else None,
                "cliff_detected": state.cliff_detected,
                "picked_up": state.picked_up,
                "falling": state.falling,
                "on_charger": state.on_charger,
                "left_speed_mm_s": state.left_speed,
                "right_speed_mm_s": state.right_speed,
            }
        )

    def export(self, path: Path) -> None:
        if not self.samples:
            raise RobotError("Record sensor readings before exporting a trace.")
        atomic_json(
            path,
            {
                "schema": "cozmo-cliff-trace-v1",
                "sampling": "manual observation; motors locked",
                "sample_count": len(self.samples),
                "samples": self.samples,
            },
        )
