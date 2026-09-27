"""Strict, non-executing parser. Deliberately excludes driving and arbitrary code."""

import json
from dataclasses import dataclass

from cozmo_desktop.face.expressions import NAMES


@dataclass(frozen=True)
class AIResponse:
    speech: str
    emotion: str
    action: str


def validate_response(payload: str) -> AIResponse:
    if len(payload) > 4096:
        raise ValueError("Response is too large.")
    data = json.loads(payload)
    if not isinstance(data, dict) or set(data) - {"speech", "emotion", "action"}:
        raise ValueError("Unsupported AI fields.")
    speech, emotion, action = (
        data.get("speech"),
        data.get("emotion", "Neutral"),
        data.get("action", "none"),
    )
    if not isinstance(speech, str) or not 1 <= len(speech.strip()) <= 500:
        raise ValueError("Invalid speech.")
    if not isinstance(emotion, str) or emotion not in NAMES:
        raise ValueError("Invalid emotion.")
    if not isinstance(action, str) or action not in {"none", "greet", "stop"}:
        raise ValueError("Action is not allowed.")
    return AIResponse(speech.strip(), emotion, action)
