import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def config_directory() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "cozmo-desktop"


@dataclass
class Settings:
    speed_limit: int = 40
    snapshots_directory: str = field(default_factory=lambda: str(Path.home() / "Pictures" / "Cozmo"))
    favorites: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Settings must be an object.")
        speed = data.get("speed_limit", 40)
        directory = data.get("snapshots_directory", str(Path.home() / "Pictures" / "Cozmo"))
        favorites = data.get("favorites", [])
        if type(speed) is not int or not 10 <= speed <= 80:
            raise ValueError("Speed must be between 10 and 80 mm/s.")
        if not isinstance(directory, str) or not directory.strip():
            raise ValueError("Choose a snapshot directory.")
        if not isinstance(favorites, list) or any(not isinstance(s, str) for s in favorites):
            raise ValueError("Favorites must be animation names.")
        return cls(speed, directory, favorites)

    def save(self, path: Path) -> None:
        atomic_json(path, asdict(self))


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
