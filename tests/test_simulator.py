import asyncio
import time
from dataclasses import FrozenInstanceError

import pytest

from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import NotConnectedError, RobotBackend, RobotError
from cozmo_desktop.robot.simulator import DRIVE_LEASE, SimulatorBackend


@pytest.fixture
async def robot():
    backend = SimulatorBackend()
    yield backend
    await backend.disconnect()


def test_backend_requires_implementation():
    with pytest.raises(TypeError):
        RobotBackend()


async def test_connect_snapshot_and_disconnect(robot):
    await robot.connect()
    old = robot.state
    assert old.connected and old.camera_available
    assert sum(c.connected for c in old.cubes) == 3
    with pytest.raises(FrozenInstanceError):
        old.connected = False
    await robot.drive(25, 25)
    assert old.left_speed == 0
    await robot.disconnect()
    assert not robot.state.connected
    assert robot.state.left_speed == robot.state.right_speed == 0
    assert not any(c.connected for c in robot.state.cubes)
    await robot.stop()


async def test_connect_is_idempotent(robot):
    await robot.connect()
    task = robot._ticker
    await robot.connect()
    assert robot._ticker is task


@pytest.mark.parametrize(
    "operation,args",
    [
        ("drive", (20, 20)),
        ("speak", ("hello",)),
        ("set_head_angle", (20,)),
        ("set_lift_height", (0.5,)),
        ("play_animation", ("Hello, friend",)),
        ("get_camera_frame", ()),
        ("enable_freeplay", ()),
    ],
)
async def test_disconnected_commands_fail(robot, operation, args):
    with pytest.raises(NotConnectedError):
        await getattr(robot, operation)(*args)


async def test_movement_clamps_and_expires(robot):
    await robot.connect()
    await robot.drive(900, 900)
    assert robot.state.left_speed == 80
    robot.advance(0.1, time.monotonic())
    assert robot.state.x == pytest.approx(8)
    robot.advance(0.1, time.monotonic() + DRIVE_LEASE + 1)
    assert robot.state.left_speed == robot.state.right_speed == 0
    assert robot.state.x == pytest.approx(8)


async def test_watchdog_runs_without_ui(robot):
    await robot.connect()
    await robot.drive(40, 40)
    await asyncio.sleep(DRIVE_LEASE + 0.15)
    assert robot.state.left_speed == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
async def test_invalid_movement_rejected(robot, value):
    await robot.connect()
    with pytest.raises(RobotError):
        await robot.drive(value, 0)


async def test_posture_speech_face_camera_and_events(robot):
    await robot.connect()
    await robot.set_head_angle(100)
    await robot.set_lift_height(-1)
    assert robot.state.head_angle == 44.5 and robot.state.lift_height == 0
    await robot.speak("  Hello!  ")
    assert robot.state.speech == "Hello!"
    await robot.display_face(render_face("Curious"), "Curious")
    assert robot.state.expression == "Curious"
    assert (await robot.get_camera_frame()).size == (640, 360)
    robot.advance(6.1, time.monotonic())
    assert robot.state.face_detected
    assert "Synthetic face appeared" in robot.events
    robot.advance(3, time.monotonic())
    assert robot.state.cubes[2].moved is False


async def test_animation_cancel_and_freeplay_stop(robot):
    await robot.connect()
    task = asyncio.create_task(robot.play_animation("Hello, friend"))
    await asyncio.sleep(0)
    assert robot.state.animation == "Hello, friend"
    await robot.stop()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert robot.state.animation is None
    await robot.enable_freeplay()
    robot.advance(6.5, time.monotonic())
    assert robot.state.freeplay
    assert robot.state.left_speed == 0
    await robot.stop()
    assert not robot.state.freeplay


async def test_unavailable_animation_and_invalid_speech(robot):
    await robot.connect()
    with pytest.raises(RobotError):
        await robot.play_animation("proprietary-asset")
    for text in ("", " ", "x" * 501):
        with pytest.raises(RobotError):
            await robot.speak(text)


async def test_backend_ticker_crash_stops_and_disconnects(robot, monkeypatch):
    await robot.connect()
    await robot.drive(40, 40)

    def fail(*args):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(robot, "advance", fail)
    await asyncio.sleep(0.1)
    assert not robot.state.connected
    assert robot.state.left_speed == robot.state.right_speed == 0
