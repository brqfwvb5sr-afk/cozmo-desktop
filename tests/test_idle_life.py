"""Idle life (ambient personality) ownership, recovery and user-facing status."""

import asyncio
from dataclasses import replace

import pytest

from cozmo_desktop.robot.base import OutputActivity, RobotError
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services import controller as controller_module
from cozmo_desktop.services.activity import describe_output
from cozmo_desktop.services.controller import RobotController


@pytest.fixture
async def controller(monkeypatch):
    monkeypatch.setattr(controller_module, "AMBIENT_RESUME_DELAY", 0.05)
    monkeypatch.setattr(controller_module, "AMBIENT_RETRY_DELAY", 0.05)
    robot = SimulatorBackend()
    await robot.connect()
    controller = RobotController(robot)
    yield controller
    await controller.shutdown()


async def until(predicate, seconds=2.0):
    async with asyncio.timeout(seconds):
        while not predicate():  # noqa: ASYNC110 - wait for background tasks
            await asyncio.sleep(0.01)


async def test_key_release_before_drive_task_starts_does_not_kill_idle_life(controller):
    controller.start_ambient()
    await until(lambda: controller.ambient_running)

    async def drive():
        await controller.drive(10, 10)

    # A UI refresh queues a drive; the key release is handled before it runs once.
    controller.submit("drive", drive)
    controller.stop_motion()
    await until(lambda: controller.ambient_running)
    assert not controller._tasks
    assert controller.ambient_status().startswith("Idle life is running")


async def test_single_refused_face_is_skipped_and_repeated_refusals_retry(controller, monkeypatch):
    robot = controller.backend
    original_face, original_sound = robot.display_face, robot.play_sound
    refusing = True

    async def face(frame, name="Custom"):
        if refusing:
            raise RobotError("face: Expired command discarded.")
        await original_face(frame, name)

    async def sound(kind):
        if refusing:
            raise RobotError("audio: Expired command discarded.")
        await original_sound(kind)

    monkeypatch.setattr(robot, "display_face", face)
    monkeypatch.setattr(robot, "play_sound", sound)
    controller.start_ambient()
    # One refusal is skipped and shown while idle life keeps running.
    await until(lambda: controller.ambient_running)
    await until(lambda: "was refused" in controller.ambient_status(), 4)
    # Three in a row end the run; it is reported plainly and retried automatically.
    await until(lambda: "Expired command discarded" in controller.ambient_problem, 8)
    assert not controller.latched  # A cosmetic refusal never latches STOP.
    refusing = False
    await until(lambda: controller.ambient_running and robot.output.faces >= 1, 6)
    assert "refused" not in controller.ambient_status()


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        (lambda c: setattr(c, "latched", True), "Paused by STOP"),
        (lambda c: setattr(c, "code_mode", True), "Code Lab"),
        (
            lambda c: setattr(c.backend, "_state", replace(c.backend.state, freeplay=True)),
            "Freeplay is running",
        ),
        (
            lambda c: setattr(c.backend, "_state", replace(c.backend.state, connected=False)),
            "Connect Cozmo",
        ),
    ],
)
async def test_idle_life_status_explains_why_it_is_off(controller, setup, reason):
    setup(controller)
    controller.start_ambient()
    assert not controller.ambient_running
    assert reason in controller.ambient_status()


async def test_busy_command_is_named_in_status(controller):
    gate = asyncio.Event()
    controller.submit("speech", gate.wait)
    await asyncio.sleep(0)
    assert "Paused during speech" in controller.ambient_status()
    gate.set()
    await until(lambda: controller.ambient_running)


def test_output_description_separates_sent_from_confirmed():
    state = replace(SimulatorBackend().state, connected=True, motors_enabled=False)
    fresh = OutputActivity(faces=3, sounds=1, last_face=98.0, last_sound=90.0)
    text = describe_output(fresh, state, 100.0, simulation=False)
    assert "Last face sent 2 s ago" in text and "last sound sent 10 s ago" in text
    assert "no playback confirmation from Cozmo yet" in text
    assert "head moves need Clear floor + Enable motors" in text
    stalled = replace(fresh, stream_running=False)
    assert "NOT running" in describe_output(stalled, state, 100.0, simulation=False)
    confirmed = replace(
        fresh, stream_running=True, robot_audio_frames=900, rejected="face: x", last_rejected=99.0
    )
    text = describe_output(confirmed, state, 100.0, simulation=False)
    assert "Cozmo confirms playback (900 audio frames)" in text
    assert "last refused 1 s ago: face: x" in text
    assert "last refused" not in describe_output(confirmed, state, 400.0, simulation=False)
    assert "simulator only" in describe_output(fresh, state, 100.0, simulation=True)
    offline = replace(state, connected=False)
    assert describe_output(fresh, offline, 100.0, simulation=False).endswith("not connected.")
