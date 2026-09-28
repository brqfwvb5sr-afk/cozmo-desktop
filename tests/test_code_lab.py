import asyncio
import json
from dataclasses import replace

import pytest

from cozmo_desktop.ai.actions import AIResponse
from cozmo_desktop.code_lab.commands import ScratchCommandError
from cozmo_desktop.code_lab.server import CodeLabServer
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.ui.window import PAGES


@pytest.fixture
async def controller():
    backend = SimulatorBackend()
    await backend.connect()
    owner = RobotController(backend)
    yield owner
    await owner.shutdown()


async def test_scratch_commands_use_existing_simulator(controller):
    commands = controller.code_lab
    await commands.execute("head", {"angle": 20})
    await commands.execute("lift", {"percent": 50})
    await commands.execute("say", {"text": "Hello!"})
    await commands.execute("expression", {"name": "Happy"})
    await commands.execute("cube_color", {"cube": 1, "color": "red"})
    state = controller.backend.state
    assert (state.head_angle, state.lift_height, state.speech) == (20, 0.5, "Hello!")
    assert state.expression == "Happy" and state.cubes[0].light_color == "red"
    assert commands.state()["simulation"] is True


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("raw_motors", {"left_wheel_speed": 200}),
        ("shell", {"command": "echo bad"}),
        ("drive_timed", {"speed": 90, "seconds": 1}),
        ("drive_distance", {"distance_cm": float("nan")}),
        ("lift", {"percent": 101}),
        ("cube_color", {"cube": 4, "color": "red"}),
    ],
)
async def test_invalid_or_unsafe_commands_rejected(controller, name, arguments):
    with pytest.raises(ScratchCommandError):
        await controller.code_lab.execute(name, arguments)
    assert controller.backend.state.left_speed == 0


async def test_freeplay_yields_and_stop_beats_scratch(controller):
    await controller.enable_freeplay()
    await controller.code_lab.execute("head", {"angle": 5})
    assert not controller.backend.state.freeplay
    task = asyncio.create_task(
        controller.code_lab.execute("drive_timed", {"speed": 10, "seconds": 1})
    )
    await asyncio.sleep(0.05)
    assert controller.backend.state.left_speed == 10
    controller.emergency_stop()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0.01)
    assert controller.latched and controller.backend.state.left_speed == 0
    with pytest.raises(ScratchCommandError):
        await controller.code_lab.execute("head", {"angle": 10})


async def test_game_yields_when_scratch_takes_control(controller):
    await controller.start_game("Quick Tap")
    assert controller._game_task is not None
    await controller.code_lab.execute("head", {"angle": 12})
    assert controller._game_task is None
    assert controller.backend.state.head_angle == 12


@pytest.mark.parametrize("flag", ["cliff_detected", "picked_up", "falling"])
async def test_safety_sensor_beats_scratch(controller, flag):
    controller.backend._state = replace(controller.backend.state, **{flag: True})
    with pytest.raises(ScratchCommandError):
        await controller.code_lab.execute("drive_timed", {"speed": 10, "seconds": 0.1})
    assert controller.backend.state.left_speed == 0


async def request(server, method, path, headers=None, body=b""):
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    fields = {"Host": f"127.0.0.1:{server.port}", **(headers or {})}
    fields["Content-Length"] = str(len(body))
    raw = f"{method} {path} HTTP/1.1\r\n".encode("ascii")
    raw += b"".join(f"{key}: {value}\r\n".encode("ascii") for key, value in fields.items())
    writer.write(raw + b"\r\n" + body)
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


async def test_local_bridge_token_schema_and_static(controller, tmp_path):
    (tmp_path / "index.html").write_text("editor", encoding="utf-8")
    server = CodeLabServer(controller.code_lab, tmp_path)
    await server.start()
    try:
        assert server._server.sockets[0].getsockname()[0] == "127.0.0.1"
        page = await request(server, "GET", "/")
        assert b"200 OK" in page and b"editor" in page
        denied = await request(server, "GET", "/api/state")
        assert b"403 Forbidden" in denied
        state = await request(server, "GET", "/api/state", {"X-Code-Token": server.token})
        assert b'"connected": true' in state
        bad_origin = await request(
            server,
            "GET",
            "/api/state",
            {
                "X-Code-Token": server.token,
                "Origin": "http://evil.example",
            },
        )
        assert b"403 Forbidden" in bad_origin
        bad_host = await request(
            server,
            "GET",
            "/api/state",
            {
                "X-Code-Token": server.token,
                "Host": "example.com",
            },
        )
        assert b"403 Forbidden" in bad_host
        body = json.dumps({"command": "head", "arguments": {"angle": 12}}).encode()
        done = await request(
            server,
            "POST",
            "/api/command",
            {
                "X-Code-Token": server.token,
                "Content-Type": "application/json",
            },
            body,
        )
        assert b"200 OK" in done and controller.backend.state.head_angle == 12
        unknown = await request(
            server,
            "POST",
            "/api/command",
            {
                "X-Code-Token": server.token,
                "Content-Type": "application/json",
            },
            b'{"command":"shell","arguments":{}}',
        )
        assert b"400 Bad Request" in unknown
        malformed = await request(
            server,
            "POST",
            "/api/command",
            {
                "X-Code-Token": server.token,
                "Content-Type": "application/json",
            },
            b"{",
        )
        assert b"400 Bad Request" in malformed
        denied_stop = await request(server, "POST", "/api/emergency-stop")
        assert b"403 Forbidden" in denied_stop and not controller.latched
        emergency = await request(
            server,
            "POST",
            "/api/emergency-stop",
            {"X-Code-Token": server.token},
        )
        await asyncio.sleep(0.01)
        assert b"200 OK" in emergency and controller.latched
        assert controller.backend.state.left_speed == 0
    finally:
        await server.close()


def test_code_is_a_real_navigation_page():
    assert PAGES[-1] == "Code"


async def test_ai_blocks_use_validated_conversation_only(controller, monkeypatch):
    with pytest.raises(ScratchCommandError):
        await controller.code_lab.execute("ai_ask", {"question": "Hello?"})
    controller.settings.ollama_model = "test-model"

    async def valid_reply(*args, **kwargs):
        return AIResponse("Hello from Cozmo", "Happy", "none")

    monkeypatch.setattr(controller.conversation, "reply", valid_reply)
    answer = await controller.code_lab.execute("ai_ask", {"question": "Hello?"})
    assert answer == "Hello from Cozmo"
    assert controller.backend.state.speech == ""
    await controller.code_lab.execute("ai_say", {"question": "Hello?"})
    assert controller.backend.state.speech == "Hello from Cozmo"
