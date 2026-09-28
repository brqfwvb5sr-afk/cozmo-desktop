import json
import urllib.error
from io import BytesIO
from unittest.mock import AsyncMock

import pytest

from cozmo_desktop.ai import local_chat
from cozmo_desktop.ai.actions import AIResponse
from cozmo_desktop.ai.local_chat import ChatTurn
from cozmo_desktop.robot.base import RobotError
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController


class Response:
    def __init__(self, payload):
        self.data = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.data

    def __exit__(self, *_):
        return False


class Opener:
    def __init__(self, callback):
        self.callback = callback

    def open(self, request, timeout):
        return self.callback(request, timeout)


def test_local_request_is_loopback_bounded_and_speech_only(monkeypatch):
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data)
        return Response(
            {"message": {"content": '{"speech":"Hallo!","emotion":"Happy","action":"none"}'}}
        )

    def build_opener(proxy):
        assert proxy.proxies == {}
        return Opener(urlopen)

    monkeypatch.setattr(local_chat.urllib.request, "build_opener", build_opener)
    answer = local_chat._request("small:1b", (ChatTurn("user", "Hallo"),))
    assert answer.speech == "Hallo!"
    assert seen["url"] == "http://127.0.0.1:11434/api/chat"
    assert seen["timeout"] == 25
    assert seen["body"]["messages"][-1] == {"role": "user", "content": "Hallo"}
    assert seen["body"]["stream"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"message": {"content": '{"speech":"Drive","action":"greet"}'}},
        {"message": {"content": '{"speech":"ok","emotion":"NotAllowed"}'}},
        {"message": {"content": "not json"}},
    ],
)
def test_model_cannot_issue_actions_or_invalid_face(monkeypatch, payload):
    monkeypatch.setattr(
        local_chat.urllib.request,
        "build_opener",
        lambda _proxy: Opener(lambda *_args, **_kwargs: Response(payload)),
    )
    with pytest.raises(RobotError):
        local_chat._request("small:1b", (ChatTurn("user", "Hello"),))


def test_offline_error_is_user_facing_and_secret_free(monkeypatch):
    def fail(*_args, **_kwargs):
        raise urllib.error.URLError("private detail")

    monkeypatch.setattr(local_chat.urllib.request, "build_opener", lambda _proxy: Opener(fail))
    with pytest.raises(RobotError, match="Start Ollama") as error:
        local_chat._request("small:1b", (ChatTurn("user", "Hello"),))
    assert "private detail" not in str(error.value)


async def test_chat_reply_changes_eyes_and_speaks_but_never_drives(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    drive = AsyncMock(wraps=backend.drive)
    backend.drive = drive
    reply = AsyncMock(return_value=AIResponse("Guten Tag!", "Happy", "none"))
    monkeypatch.setattr("cozmo_desktop.services.controller.local_reply", reply)
    await controller.send_chat("Hallo", "small:1b")
    assert backend.state.expression == "Happy"
    assert backend.state.speech == "Guten Tag!"
    assert [turn.role for turn in controller.chat_turns] == ["user", "assistant"]
    drive.assert_not_called()


async def test_chat_unavailable_does_not_arm_or_latch(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    reply = AsyncMock(side_effect=RobotError("Start Ollama"))
    monkeypatch.setattr("cozmo_desktop.services.controller.local_reply", reply)
    await controller.send_chat("Hallo", "small:1b")
    assert controller.chat_status == "Start Ollama"
    assert not controller.latched
    assert backend.state.speech == ""
