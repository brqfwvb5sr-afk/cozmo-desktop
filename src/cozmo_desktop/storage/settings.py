import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cozmo_desktop.ai.providers.ollama import validate_endpoint


def config_directory() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "cozmo-desktop"


@dataclass
class Settings:
    speed_limit: int = 40
    snapshots_directory: str = field(
        default_factory=lambda: str(Path.home() / "Pictures" / "Cozmo")
    )
    favorites: list[str] = field(default_factory=list)
    ai_enabled: bool = True
    ollama_server: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    temperature: float = 0.5
    max_tokens: int = 180
    memory_enabled: bool = True
    spontaneous_ai: bool = False
    stt_model_de: str = ""
    stt_model_en: str = ""

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
        result = cls(speed, directory, favorites)
        for key in ("ai_enabled", "memory_enabled", "spontaneous_ai"):
            value = data.get(key, getattr(result, key))
            if type(value) is not bool:
                raise ValueError(f"Invalid {key} setting.")
            setattr(result, key, value)
        endpoint = data.get("ollama_server", result.ollama_server)
        if not isinstance(endpoint, str):
            raise ValueError("Invalid Ollama server.")
        result.ollama_server = validate_endpoint(endpoint)
        for key in ("ollama_model", "stt_model_de", "stt_model_en"):
            value = data.get(key, "")
            if not isinstance(value, str) or len(value) > 500:
                raise ValueError(f"Invalid {key} setting.")
            setattr(result, key, value)
        temp = data.get("temperature", result.temperature)
        length = data.get("max_tokens", result.max_tokens)
        if type(temp) not in (float, int) or not 0 <= temp <= 1:
            raise ValueError("Invalid AI temperature.")
        if type(length) is not int or not 32 <= length <= 400:
            raise ValueError("Invalid maximum response length.")
        result.temperature = float(temp)
        result.max_tokens = length
        return result

    def save(self, path: Path) -> None:
        atomic_json(path, asdict(self))


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
