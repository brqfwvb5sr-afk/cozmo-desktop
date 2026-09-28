"""Short session memory; no persistent user profile or unlimited context."""

from cozmo_desktop.ai.local_chat import ChatTurn


class ConversationMemory:
    def __init__(self, limit: int = 20) -> None:
        if not 2 <= limit <= 40:
            raise ValueError("Memory limit must be between 2 and 40 turns.")
        self.limit = limit
        self._turns: list[ChatTurn] = []

    @property
    def turns(self) -> tuple[ChatTurn, ...]:
        return tuple(self._turns)

    def add(self, user: str, assistant: str) -> None:
        self._turns.extend((ChatTurn("user", user), ChatTurn("assistant", assistant)))
        del self._turns[: -self.limit]

    def clear(self) -> None:
        self._turns.clear()
