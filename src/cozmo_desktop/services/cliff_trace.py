"""Bounded motor-locked observations for physical cliff-sensor validation."""

import time
from pathlib import Path

from cozmo_desktop.robot.base import RobotError, RobotState
from cozmo_desktop.storage.settings import atomic_json

LABELS = ("center", "front edge", "rear edge", "left edge", "right edge")
MAX_SAMPLES = 300
MIN_SAMPLES_PER_POSITION = 5


def analyze_trace(samples: list[dict[str, object]]) -> dict[str, object]:
    """Describe stationary sensor separation; this never authorizes wheel motion."""
    values: dict[str, list[tuple[int, int, int, int]]] = {label: [] for label in LABELS}
    flagged = dict.fromkeys(LABELS, 0)
    missing_raw = invalid_state = unknown_label = 0
    for sample in samples:
        label = sample.get("label")
        if not isinstance(label, str) or label not in values:
            unknown_label += 1
            continue
        if any(sample.get(flag) for flag in ("picked_up", "falling", "on_charger")) or any(
            sample.get(speed) for speed in ("left_speed_mm_s", "right_speed_mm_s")
        ):
            invalid_state += 1
            continue
        raw = sample.get("raw")
        if (
            not isinstance(raw, list)
            or len(raw) != 4
            or any(type(value) is not int or value < 0 for value in raw)
        ):
            missing_raw += 1
            continue
        values[label].append((raw[0], raw[1], raw[2], raw[3]))
        if sample.get("cliff_detected"):
            flagged[label] += 1

    ranges: dict[str, list[list[int]] | None] = {}
    for label, rows in values.items():
        ranges[label] = (
            [
                [min(row[index] for row in rows), max(row[index] for row in rows)]
                for index in range(4)
            ]
            if rows
            else None
        )
    center = ranges["center"]
    separation: dict[str, list[dict[str, int | str]]] = {}
    for label in LABELS[1:]:
        edge = ranges[label]
        separated: list[dict[str, int | str]] = []
        if (
            center is not None
            and edge is not None
            and len(values["center"]) >= MIN_SAMPLES_PER_POSITION
            and len(values[label]) >= MIN_SAMPLES_PER_POSITION
        ):
            for index in range(4):
                if edge[index][0] > center[index][1]:
                    separated.append(
                        {
                            "channel": index,
                            "direction": "higher",
                            "gap": edge[index][0] - center[index][1],
                        }
                    )
                elif center[index][0] > edge[index][1]:
                    separated.append(
                        {
                            "channel": index,
                            "direction": "lower",
                            "gap": center[index][0] - edge[index][1],
                        }
                    )
        separation[label] = separated
    insufficient = [label for label in LABELS if len(values[label]) < MIN_SAMPLES_PER_POSITION]
    return {
        "status": "incomplete"
        if insufficient or invalid_state or missing_raw or unknown_label
        else "comparison_only",
        "minimum_samples_per_position": MIN_SAMPLES_PER_POSITION,
        "valid_samples": {label: len(values[label]) for label in LABELS},
        "insufficient_positions": insufficient,
        "excluded_missing_raw": missing_raw,
        "excluded_unsafe_or_moving": invalid_state,
        "excluded_unknown_label": unknown_label,
        "cliff_flagged_samples": flagged,
        "raw_ranges_by_channel": ranges,
        "nonoverlapping_channels_vs_center": separation,
        "table_driving_approved": False,
    }


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
                "analysis": analyze_trace(self.samples),
            },
        )
