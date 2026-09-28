"""Bounded, loopback-only Ollama HTTP provider. No robot backend access."""

import asyncio
import json
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from cozmo_desktop.ai.local_chat import ChatTurn
from cozmo_desktop.robot.base import RobotError

from .base import ModelInfo


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, request: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def validate_endpoint(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.port is None
    ):
        raise ValueError("Ollama server must be a local HTTP address with a port.")
    return value.strip().rstrip("/")


@dataclass(frozen=True)
class OllamaHealth:
    status: str
    models: tuple[ModelInfo, ...] = ()


class OllamaProvider:
    def __init__(self, endpoint: str = "http://127.0.0.1:11434") -> None:
        self.endpoint = validate_endpoint(endpoint)

    def _request(self, path: str, body: dict[str, object] | None = None, timeout: int = 5) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.endpoint + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(16385)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise RobotError("Local Ollama service is unavailable or timed out.") from exc
        if len(raw) > 16384:
            raise RobotError("Ollama returned too much data.")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise RobotError("Ollama returned invalid JSON.") from exc

    async def list_models(self) -> tuple[ModelInfo, ...]:
        data = await asyncio.to_thread(self._request, "/api/tags")
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise RobotError("Ollama model list is invalid.")
        models = []
        for item in data["models"][:100]:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                size = item.get("size", 0)
                models.append(
                    ModelInfo(item["name"], size if type(size) is int and size >= 0 else 0)
                )
        return tuple(models)

    async def health(self) -> OllamaHealth:
        try:
            models = await self.list_models()
        except RobotError:
            return OllamaHealth(
                "Ollama service stopped" if shutil.which("ollama") else "Ollama not installed"
            )
        return OllamaHealth("Model ready" if models else "No model installed", models)

    async def generate(
        self,
        model: str,
        turns: tuple[ChatTurn, ...],
        *,
        temperature: float = 0.5,
        max_tokens: int = 180,
    ) -> str:
        if not 1 <= len(model) <= 80 or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
            for c in model
        ):
            raise RobotError("Select an installed Ollama model.")
        if not 0 <= temperature <= 1 or not 32 <= max_tokens <= 400:
            raise RobotError("Invalid AI generation settings.")
        if not turns or turns[-1].role != "user":
            raise RobotError("Enter a message first.")
        body: dict[str, object] = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": turn.role, "content": turn.text}
                for turn in (turns[:2] + turns[-21:] if len(turns) > 21 else turns)
            ],
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        data = await asyncio.to_thread(self._request, "/api/chat", body, 25)
        if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
            raise RobotError("Ollama reply is invalid.")
        content = data["message"].get("content")
        if not isinstance(content, str):
            raise RobotError("Ollama reply is invalid.")
        return content
