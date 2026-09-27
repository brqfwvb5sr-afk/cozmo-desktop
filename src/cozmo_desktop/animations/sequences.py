import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.storage.settings import atomic_json


@dataclass(frozen=True)
class Sequence:
    name: str
    animations: tuple[str, ...]

    def save(self, path: Path) -> None:
        atomic_json(path, asdict(self))

    @classmethod
    def load(cls, path: Path) -> "Sequence":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            raise ValueError("Invalid sequence.")
        items = data.get("animations")
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValueError("A sequence needs 1 to 20 animations.")
        if any(not isinstance(item, str) for item in items):
            raise ValueError("Invalid animation names.")
        return cls(data["name"], tuple(items))

    async def play(self, controller: RobotController) -> None:
        available = {a.name for a in controller.backend.animations}
        if not 1 <= len(self.animations) <= 20 or any(a not in available for a in self.animations):
            raise ValueError("Sequence contains unavailable animations.")
        for name in self.animations:
            if controller.latched:
                return
            await controller.backend.play_animation(name)
