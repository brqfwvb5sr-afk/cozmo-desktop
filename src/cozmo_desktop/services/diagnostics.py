"""Export only an explicit safe set of fields; never export raw logs/settings."""

import json
import logging
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path

from cozmo_desktop import __version__
from cozmo_desktop.robot.base import RobotState
from cozmo_desktop.storage.settings import atomic_json


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"level": record.levelname, "time": self.formatTime(record),
                           "event": record.getMessage()})


def configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "app.log", maxBytes=200_000, backupCount=2)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("cozmo_desktop")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def export_report(path: Path, state: RobotState, latched: bool) -> None:
    atomic_json(path, {
        "application_version": __version__, "os": platform.system(),
        "python": platform.python_version(), "backend": "simulator",
        "connected": state.connected, "emergency_stop": latched,
        "camera_available": state.camera_available,
        "cube_connections": [c.connected for c in state.cubes],
        "hardware_support": "not implemented",
    })
