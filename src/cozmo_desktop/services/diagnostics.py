"""Export only an explicit safe set of fields; never export raw logs/settings."""

import json
import logging
import platform
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from cozmo_desktop import __version__
from cozmo_desktop.robot.base import OutputActivity, RobotState
from cozmo_desktop.storage.settings import atomic_json


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "time": self.formatTime(record),
                "event": record.getMessage(),
            }
        )


def configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "app.log", maxBytes=200_000, backupCount=2)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("cozmo_desktop")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def export_report(
    path: Path,
    state: RobotState,
    latched: bool,
    *,
    output: OutputActivity | None = None,
    idle_life: str = "",
) -> None:
    now = time.monotonic()
    activity = output or OutputActivity()

    def age(moment: float | None) -> float | None:
        return None if moment is None else round(now - moment, 1)

    atomic_json(
        path,
        {
            "application_version": __version__,
            "os": platform.system(),
            "python": platform.python_version(),
            "backend": state.backend_name,
            "connected": state.connected,
            "emergency_stop": latched,
            "camera_available": state.camera_available,
            "cube_connections": [c.connected for c in state.cubes],
            "hardware_support": "experimental; physical validation pending",
            "motors_enabled": state.motors_enabled,
            "surface_mode": state.surface_mode,
            "on_charger": state.on_charger,
            "safety_status": state.safety_status,
            "idle_life": idle_life,
            "faces_sent": activity.faces,
            "sounds_sent": activity.sounds,
            "seconds_since_face": age(activity.last_face),
            "seconds_since_sound": age(activity.last_sound),
            "face_sound_stream_running": activity.stream_running,
            "robot_confirmed_audio_frames": activity.robot_audio_frames,
            "last_refused_command": activity.rejected,
            "seconds_since_refusal": age(activity.last_rejected),
        },
    )
