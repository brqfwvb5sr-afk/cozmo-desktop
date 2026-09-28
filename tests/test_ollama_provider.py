"""Mocked local HTTP and safety tests; CI never needs Ollama or a microphone."""

import asyncio
import json
import urllib.error
from io import BytesIO
from unittest.mock import AsyncMock

import pytest

from cozmo_desktop.ai.actions import validate_response
from cozmo_desktop.ai.conversation import ConversationService
from cozmo_desktop.ai.local_chat import ChatTurn
from cozmo_desktop.ai.providers import ollama
from cozmo_desktop.ai.resources import SystemResources, model_memory_warning
from cozmo_desktop.robot.base import RobotError, RobotState
from cozmo_desktop.storage.settings import Settings


class Response:
    def __init__(self, payload):
        self.stream = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.stream

    def __exit__(self, *_):
        return False


def mock_http(monkeypatch, callback):
    class Opener:
        def open(self, request, timeout):
            return callback(request, timeout)

    def build_opener(proxy, redirect):
        assert proxy.proxies == {}
        assert isinstance(redirect, ollama._NoRedirect)
        return Opener()

    monkeypatch.setattr(ollama.urllib.request, "build_opener", build_opener)


def test_provider_local_endpoint_and_redirect_guard():
    for bad in ("https://example.com:443", "http://192.168.1.5:11434", "http://localhost:11434/x"):
        with pytest.raises(ValueError):
            ollama.OllamaProvider(bad)
    assert ollama.OllamaProvider().endpoint == "http://127.0.0.1:11434"
    assert ollama._NoRedirect().redirect_request(None, None, 307, "", {}, "https://x") is None


async def test_provider_lists_models_and_generates_bounded_json(monkeypatch):
    seen = []

    def respond(request, timeout):
        seen.append((request.full_url, timeout, request.data))
        if request.full_url.endswith("/api/tags"):
            return Response({"models": [{"name": "gemma3:1b", "size": 815_000_000}]})
        return Response({"message": {"content": '{"speech":"Hallo!","emotion":"Happy"}'}})

    mock_http(monkeypatch, respond)
    provider = ollama.OllamaProvider()
    assert (await provider.health()).status == "Model ready"
    result = await provider.generate(
        "gemma3:1b", (ChatTurn("user", "Hallo"),), temperature=0.4, max_tokens=100
    )
    assert validate_response(result).speech == "Hallo!"
    body = json.loads(seen[1][2])
    assert body["options"] == {"temperature": 0.4, "num_predict": 100}
    assert seen[0][0] == "http://127.0.0.1:11434/api/tags"


async def test_provider_missing_server_and_empty_models(monkeypatch):
    mock_http(monkeypatch, lambda _request, _timeout: Response({"models": []}))
    assert (await ollama.OllamaProvider().health()).status == "No model installed"

    def fail(_request, _timeout):
        raise urllib.error.URLError("private network error")

    mock_http(monkeypatch, fail)
    with pytest.raises(RobotError, match="unavailable") as error:
        await ollama.OllamaProvider().list_models()
    assert "private network error" not in str(error.value)
    assert (await ollama.OllamaProvider().health()).status in (
        "Ollama service stopped",
        "Ollama not installed",
    )


async def test_conversation_context_memory_timeout_and_invalid_reply():
    provider = AsyncMock()
    provider.generate.return_value = '{"speech":"Want to play?","emotion":"Curious"}'
    service = ConversationService(provider, memory_limit=4)
    for index in range(4):
        await service.reply(f"Message {index}", "gemma3:1b", RobotState(expression="Happy"))
    assert len(service.memory.turns) == 4
    turns = provider.generate.call_args.args[1]
    assert turns[0].role == "system" and "small curious" in turns[0].text
    assert "expression=Happy" in turns[1].text
    service.memory.clear()
    assert service.memory.turns == ()
    provider.generate.return_value = "not json"
    with pytest.raises(RobotError, match="invalid reply"):
        await service.reply("Hello", "gemma3:1b", RobotState())

    async def stall(*_args, **_kwargs):
        await asyncio.sleep(1)

    provider.generate.side_effect = stall
    with pytest.raises(RobotError, match="too long"):
        await service.reply("Hello", "gemma3:1b", RobotState(), generation_seconds=0.001)


async def test_conversation_cancellation_never_records_reply():
    gate = asyncio.Event()

    async def wait(*_args, **_kwargs):
        await gate.wait()
        return '{"speech":"late"}'

    provider = AsyncMock()
    provider.generate.side_effect = wait
    service = ConversationService(provider)
    task = asyncio.create_task(service.reply("Hello", "gemma3:1b", RobotState()))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service.memory.turns == ()


@pytest.mark.parametrize("field", ["left_wheel_speed", "shell", "python", "filesystem"])
def test_model_output_cannot_include_commands(field):
    with pytest.raises(ValueError):
        validate_response(json.dumps({"speech": "hi", field: "danger"}))


def test_safe_expression_and_action_are_allowlisted():
    answer = validate_response(
        '{"speech":"Hi!","emotion":"excited","expression":"happy","action":"look_left","sound":"chirp"}'
    )
    assert (answer.emotion, answer.expression, answer.action, answer.sound) == (
        "Excited",
        "Happy",
        "look_left",
        "chirp",
    )


def test_ai_settings_and_resource_warning(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(ollama_model="gemma3:1b", stt_model_de="/models/de", spontaneous_ai=True)
    settings.save(path)
    assert Settings.load(path) == settings
    assert model_memory_warning(2_000_000, 1_000_000)
    assert not model_memory_warning(1_000_000, 2_000_000)
    assert SystemResources("x86_64", 4, None, None).cpu_threads == 4
    path.write_text('{"ollama_server":"http://example.com:11434"}')
    with pytest.raises(ValueError):
        Settings.load(path)
