"""Optional local Ollama conversation. Model output can only affect eyes and speech."""

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from cozmo_desktop.ai.actions import AIResponse, validate_response
from cozmo_desktop.robot.base import RobotError

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
SYSTEM_MESSAGE = (
    "You are Cozmo, a small, curious desktop robot. Reply to the user's message "
    "briefly in the same language. Return only one JSON object with keys speech, "
    "emotion, action. speech must be under 500 characters; emotion must be one of "
    "Neutral, Happy, Sad, Angry, Surprised, Curious, Sleepy, Confused, Excited; "
    "action must always be none. Never claim to see, hear or do anything you cannot."
)


@dataclass(frozen=True)
class ChatTurn:
    role: str
    text: str


def _request(model: str, turns: tuple[ChatTurn, ...]) -> AIResponse:
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                *({"role": turn.role, "content": turn.text} for turn in turns[-10:]),
            ],
            "options": {"num_predict": 180},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        # Ignore HTTP_PROXY: conversation must remain on the loopback interface.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=25) as response:
            raw = response.read(8193)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise RobotError(
            "Local conversation unavailable. Start Ollama and check the installed model."
        ) from exc
    if len(raw) > 8192:
        raise RobotError("Local model returned too much data.")
    try:
        content = json.loads(raw)["message"]["content"]
        result = validate_response(content)
    except (UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise RobotError("Local model returned an invalid reply.") from exc
    if result.action != "none":
        raise RobotError("Local model requested an unsupported action.")
    return result


async def local_reply(model: str, turns: tuple[ChatTurn, ...]) -> AIResponse:
    if not 1 <= len(model) <= 80 or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for c in model
    ):
        raise RobotError("Enter a valid installed Ollama model name.")
    if not turns or turns[-1].role != "user":
        raise RobotError("Enter a message first.")
    return await asyncio.to_thread(_request, model, turns)
