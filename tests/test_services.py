import asyncio
import json

import pytest

from cozmo_desktop.ai.actions import validate_response
from cozmo_desktop.animations.sequences import Sequence
from cozmo_desktop.face.expressions import NAMES, Expression, apply_expression, render_face
from cozmo_desktop.robot.base import RobotState
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.services.diagnostics import export_report
from cozmo_desktop.storage.settings import Settings


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    assert Settings.load(path).speed_limit == 40
    expected = Settings(30, str(tmp_path / "photos"), ["Hello, friend"])
    expected.save(path)
    assert Settings.load(path) == expected
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(
    "content",
    [
        "bad",
        "[]",
        '{"speed_limit":900}',
        '{"speed_limit":true}',
        '{"favorites":[42]}',
        '{"snapshots_directory":""}',
    ],
)
def test_invalid_settings_not_overwritten(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        Settings.load(path)
    assert path.read_text() == content


@pytest.mark.parametrize("name", NAMES)
def test_expression_loading_and_original_pixels(name):
    expression = Expression.from_json(json.dumps({"name": name, "head_angle": 25, "lift": 0.2}))
    assert expression.name == name
    assert render_face(name).size == (128, 64)
    assert len(render_face(name).getcolors()) > 1


@pytest.mark.parametrize(
    "payload",
    [
        '{"name":"Unknown"}',
        '{"name":"Happy","shell":"x"}',
        '{"name":"Happy","head_angle":99}',
        '{"name":"Happy","lift":2}',
    ],
)
def test_invalid_expression(payload):
    with pytest.raises(ValueError):
        Expression.from_json(payload)


async def test_sequence_persistence_and_emergency_cancellation(tmp_path):
    controller = RobotController(SimulatorBackend())
    await controller.backend.connect()
    path = tmp_path / "sequence.json"
    sequence = Sequence("Hello", ("Hello, friend", "Curious glance"))
    sequence.save(path)
    assert Sequence.load(path) == sequence
    controller.submit("sequence", lambda: sequence.play(controller))
    await asyncio.sleep(0)
    controller.emergency_stop()
    await asyncio.sleep(0.01)
    assert controller.backend.state.animation is None
    assert not any("Curious glance" in item for item in controller.backend.events)
    await apply_expression(controller, Expression("Angry"))
    assert controller.backend.state.expression != "Angry"
    await controller.shutdown()


async def test_unavailable_sequence_validated_before_first_action():
    controller = RobotController(SimulatorBackend())
    await controller.backend.connect()
    with pytest.raises(ValueError):
        await Sequence("Bad", ("Hello, friend", "missing")).play(controller)
    assert controller.backend.state.animation is None
    await controller.shutdown()


def test_ai_allowlist():
    assert (
        validate_response('{"speech":"Hello!","emotion":"Happy","action":"greet"}').action
        == "greet"
    )


@pytest.mark.parametrize(
    "payload",
    [
        '{"speech":"hi","action":"drive"}',
        '{"speech":"hi","shell":"ls"}',
        '{"speech":"hi","emotion":"evil"}',
        '{"speech":"hi","action":[]}',
        '{"speech":"hi","emotion":{}}',
        '{"speech":""}',
        "[]",
        "x" * 5000,
    ],
)
def test_ai_rejects_untrusted_actions(payload):
    with pytest.raises(ValueError):
        validate_response(payload)


def test_diagnostics_exclude_private_data(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    path = tmp_path / "report.json"
    export_report(path, RobotState(speech="private-conversation"), True)
    text = path.read_text()
    assert "secret-value" not in text and "private-conversation" not in text
    assert json.loads(text)["emergency_stop"] is True
