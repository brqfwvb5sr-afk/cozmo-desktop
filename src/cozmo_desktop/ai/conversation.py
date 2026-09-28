"""Conversation orchestration. Provider output is parsed before any robot action."""

import asyncio

from cozmo_desktop.ai.actions import AIResponse, validate_response
from cozmo_desktop.ai.local_chat import ChatTurn
from cozmo_desktop.ai.memory import ConversationMemory
from cozmo_desktop.ai.prompts import SYSTEM_PROMPT, state_context
from cozmo_desktop.ai.providers.base import AIProvider
from cozmo_desktop.robot.base import RobotError, RobotState


class ConversationService:
    def __init__(self, provider: AIProvider, *, memory_limit: int = 20) -> None:
        self.provider = provider
        self.memory = ConversationMemory(memory_limit)

    async def reply(
        self,
        text: str,
        model: str,
        state: RobotState,
        *,
        temperature: float = 0.5,
        max_tokens: int = 180,
        remember: bool = True,
        generation_seconds: float = 30,
    ) -> AIResponse:
        text = text.strip()
        if not 1 <= len(text) <= 400:
            raise RobotError("Enter a message of 1–400 characters.")
        turns = (
            ChatTurn("system", SYSTEM_PROMPT),
            ChatTurn("system", state_context(state)),
            *(self.memory.turns if remember else ()),
            ChatTurn("user", text),
        )
        try:
            async with asyncio.timeout(generation_seconds):
                raw = await self.provider.generate(
                    model, turns, temperature=temperature, max_tokens=max_tokens
                )
        except TimeoutError as exc:
            raise RobotError("Local model took too long; Cozmo is still ready.") from exc
        try:
            response = validate_response(raw)
        except (ValueError, TypeError) as exc:
            raise RobotError("Local model returned an invalid reply.") from exc
        if remember:
            self.memory.add(text, response.speech)
        return response
