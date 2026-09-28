import asyncio
import json
import urllib.error
from dataclasses import replace
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

    def build_opener(proxy, redirects):
        assert proxy.proxies == {}
        assert isinstance(redirects, local_chat._NoRedirect)
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
        lambda _proxy, _redirects: Opener(lambda *_args, **_kwargs: Response(payload)),
    )
    with pytest.raises(RobotError):
        local_chat._request("small:1b", (ChatTurn("user", "Hello"),))


def test_offline_error_is_user_facing_and_secret_free(monkeypatch):
    def fail(*_args, **_kwargs):
        raise urllib.error.URLError("private detail")

    monkeypatch.setattr(
        local_chat.urllib.request, "build_opener", lambda _proxy, _redirects: Opener(fail)
    )
    with pytest.raises(RobotError, match="Start Ollama") as error:
        local_chat._request("small:1b", (ChatTurn("user", "Hello"),))
    assert "private detail" not in str(error.value)


def test_local_chat_rejects_http_redirects():
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), local_chat._NoRedirect())
    request = urllib.request.Request(local_chat.OLLAMA_URL, b"private chat", method="POST")
    handler = next(item for item in opener.handlers if isinstance(item, local_chat._NoRedirect))
    assert (
        handler.redirect_request(
            request, None, 307, "Temporary Redirect", {}, "https://example.com/collect"
        )
        is None
    )


async def test_chat_reply_changes_eyes_and_speaks_but_never_drives(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    drive = AsyncMock(wraps=backend.drive)
    backend.drive = drive
    reply = AsyncMock(return_value=AIResponse("Guten Tag!", "Happy", "none"))
    monkeypatch.setattr(controller.conversation, "reply", reply)
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
    monkeypatch.setattr(controller.conversation, "reply", reply)
    await controller.send_chat("Hallo", "small:1b")
    assert controller.chat_status == "Start Ollama"
    assert not controller.latched
    assert backend.state.speech == ""


async def test_chat_thinking_face_blinks_and_stops_with_conversation(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    gate = asyncio.Event()
    blinked = asyncio.Event()
    frames = []
    original_display = backend.display_face

    async def display(frame, name="Custom"):
        frames.append(frame.tobytes())
        await original_display(frame, name)
        if len(frames) >= 3:
            blinked.set()

    async def delayed_reply(*_args, **_kwargs):
        await gate.wait()
        return AIResponse("Hallo!", "Happy", "none")

    backend.display_face = display
    monkeypatch.setattr(controller.conversation, "reply", delayed_reply)
    controller.submit("chat", lambda: controller.send_chat("Hallo", "small:1b"))
    chat_task = controller._tasks["chat"]
    await asyncio.wait_for(blinked.wait(), 3)
    assert len(set(frames)) > 1
    assert backend.state.expression == "Curious"
    controller.emergency_stop()
    gate.set()
    await asyncio.gather(chat_task, return_exceptions=True)
    assert backend.state.speech == ""
    assert len(frames) == 3
    await controller.shutdown()


async def test_chat_failure_restores_a_valid_expression_after_custom_face(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    backend._state = replace(backend.state, expression="Custom")
    monkeypatch.setattr(
        controller.conversation,
        "reply",
        AsyncMock(side_effect=RobotError("Start Ollama")),
    )
    await controller.send_chat("Hallo", "small:1b")
    assert backend.state.expression == "Neutral"
    assert controller.chat_status == "Start Ollama"


async def test_stop_cancels_pending_model_reply_before_robot_output(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    gate = asyncio.Event()

    async def delayed_reply(*_args, **_kwargs):
        await gate.wait()
        return AIResponse("Too late", "Happy", "none")

    monkeypatch.setattr(controller.conversation, "reply", delayed_reply)
    controller.submit("chat", lambda: controller.send_chat("Hallo", "small:1b"))
    await asyncio.sleep(0)
    controller.emergency_stop()
    gate.set()
    await asyncio.sleep(0.02)
    assert controller.latched
    assert backend.state.speech == ""
    assert not controller.chat_turns
    await controller.shutdown()


async def test_typed_chat_temporarily_pauses_and_restores_freeplay(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    await controller.enable_freeplay()
    monkeypatch.setattr(
        controller.conversation,
        "reply",
        AsyncMock(return_value=AIResponse("Let's play!", "Happy", "none")),
    )
    controller.submit("chat", lambda: controller.send_chat("Hello", "gemma3:1b"))
    task = controller._tasks["chat"]
    await task
    assert backend.state.freeplay
    assert backend.state.speech == "Let's play!"
    await controller.shutdown()


async def test_cliff_state_suppresses_model_call_and_robot_output(monkeypatch):
    backend = SimulatorBackend()
    controller = RobotController(backend)
    await backend.connect()
    backend._state = replace(backend.state, cliff_detected=True)
    reply = AsyncMock(return_value=AIResponse("Ignore cliff", "Happy", "look_up"))
    monkeypatch.setattr(controller.conversation, "reply", reply)
    await controller.send_chat("Hello", "gemma3:1b")
    reply.assert_not_called()
    assert backend.state.speech == ""
    assert controller.chat_status.startswith("Robot safety")
    await controller.shutdown()
