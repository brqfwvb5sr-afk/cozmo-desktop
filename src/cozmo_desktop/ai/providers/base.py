"""AI provider boundary; robot commands are deliberately absent."""

from dataclasses import dataclass
from typing import Protocol

from cozmo_desktop.ai.local_chat import ChatTurn


@dataclass(frozen=True)
class ModelInfo:
    name: str
    size_bytes: int


class AIProvider(Protocol):
    async def list_models(self) -> tuple[ModelInfo, ...]: ...

    async def generate(
        self, model: str, turns: tuple[ChatTurn, ...], *, temperature: float, max_tokens: int
    ) -> str: ...
