"""Strict, non-executing parser. Deliberately excludes driving and arbitrary code."""

import json
from dataclasses import dataclass

from cozmo_desktop.face.expressions import NAMES
from cozmo_desktop.robot.base import VOCALIZATIONS

SAFE_ACTIONS = frozenset(
    (
        "none",
        "greet",
        "stop",
        "look_left",
        "look_right",
        "look_up",
        "small_head_tilt",
        "small_lift_move",
        "happy_reaction",
        "curious_reaction",
        "confused_reaction",
    )
)


@dataclass(frozen=True)
class AIResponse:
    speech: str
    emotion: str
    action: str
    expression: str | None = None
    sound: str | None = None


def validate_response(payload: str) -> AIResponse:
    if len(payload) > 4096:
        raise ValueError("Response is too large.")
    data = json.loads(payload)
    if not isinstance(data, dict) or set(data) - {
        "speech",
        "emotion",
        "expression",
        "action",
        "sound",
    }:
        raise ValueError("Unsupported AI fields.")
    speech, emotion, action = (
        data.get("speech"),
        data.get("emotion", "Neutral"),
        data.get("action", "none"),
    )
    if not isinstance(speech, str) or not 1 <= len(speech.strip()) <= 500:
        raise ValueError("Invalid speech.")
    if not isinstance(emotion, str) or emotion.title() not in NAMES:
        raise ValueError("Invalid emotion.")
    if not isinstance(action, str) or action not in SAFE_ACTIONS:
        raise ValueError("Action is not allowed.")
    expression = data.get("expression")
    if expression is not None and (
        not isinstance(expression, str) or expression.title() not in NAMES
    ):
        raise ValueError("Expression is not allowed.")
    sound = data.get("sound")
    if sound is not None and (not isinstance(sound, str) or sound not in VOCALIZATIONS):
        raise ValueError("Sound is not allowed.")
    return AIResponse(
        speech.strip(), emotion.title(), action, expression.title() if expression else None, sound
    )
