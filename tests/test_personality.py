import asyncio
import random
from dataclasses import replace

import pytest

from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import CubeState, RobotError
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.services.personality import PersonalityDirector, safe_to_move


class VirtualClock:
    def __init__(self):
        self.now = 100.0
        self.hook = None

    def time(self):
        return self.now

    async def pause(self, seconds):
        self.now += seconds
        if self.hook is not None:
            self.hook()
        await asyncio.sleep(0)


def test_original_eyes_blink_and_move():
    normal = render_face("Curious")
    assert render_face("Curious", blink=True).tobytes() != normal.tobytes()
    assert render_face("Curious", gaze=5).tobytes() != normal.tobytes()
    with pytest.raises(RobotError):
        render_face("Curious", gaze=99)


def test_event_driven_mood_and_safety_gate():
    robot = SimulatorBackend()
    director = PersonalityDirector(robot, rng=random.Random(3))
    state = replace(robot.state, connected=True, freeplay=True, motors_enabled=True)
    assert safe_to_move(state)
    tapped = replace(state, cubes=(CubeState(1, tap_sequence=1), *state.cubes[1:]))
    assert director._event_mood(tapped) == "Happy"
    assert director._event_mood(tapped) is None
    moved = replace(tapped, cubes=(CubeState(1, tap_sequence=1, move_sequence=1), *state.cubes[1:]))
    assert director._event_mood(moved) == "Curious"
    for flag in ("cliff_detected", "picked_up", "falling", "on_charger"):
        hazard = replace(moved, **{flag: True})
        assert not safe_to_move(hazard)
        assert director._event_mood(hazard) == "Surprised"
    for mode in ("table", "unknown"):
        assert not safe_to_move(replace(state, surface_mode=mode))


async def test_spontaneous_moods_blinks_sounds_and_floor_roaming(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    clock = VirtualClock()
    frames = []
    wheels = []
    original_display = robot.display_face
    original_drive = robot.drive

    async def display(frame, name="Custom"):
        frames.append(frame.tobytes())
        await original_display(frame, name)

    async def drive(left, right):
        wheels.append((left, right))
        await original_drive(left, right)

    monkeypatch.setattr(robot, "display_face", display)
    monkeypatch.setattr(robot, "drive", drive)
    director = PersonalityDirector(robot, rng=random.Random(4), clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run(allow_movement=True))
    async with asyncio.timeout(2):
        while clock.now < 114:  # noqa: ASYNC110 - wait for the director's injected clock
            await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert len(frames) >= 4 and len(set(frames)) > 1
    assert any("vocalization" in event for event in robot.events)
    assert any(left or right for left, right in wheels) and (0, 0) in wheels
    assert max(abs(speed) for pair in wheels for speed in pair) <= 18
    assert not robot.state.freeplay
    await robot.disconnect()


async def test_table_mode_has_emotions_but_never_roams(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    robot._state = replace(robot.state, surface_mode="table")
    clock = VirtualClock()
    wheels = []

    async def drive(left, right):
        wheels.append((left, right))

    monkeypatch.setattr(robot, "drive", drive)
    director = PersonalityDirector(robot, clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run(allow_movement=True))
    async with asyncio.timeout(2):
        while clock.now < 116:  # noqa: ASYNC110 - wait for the director's injected clock
            await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert not wheels
    assert any("Expression" in event for event in robot.events)
    await robot.disconnect()


async def test_roam_halts_when_a_hazard_appears_mid_move(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    clock = VirtualClock()
    wheels = []
    original_drive = robot.drive

    async def drive(left, right):
        wheels.append((left, right))
        await original_drive(left, right)

    monkeypatch.setattr(robot, "drive", drive)
    director = PersonalityDirector(robot, clock=clock.time, pause=clock.pause)
    director.rng.choice = lambda choices: choices[0]

    def detect_hazard():
        if len(wheels) == 3:
            robot._state = replace(robot.state, cliff_detected=True)

    clock.hook = detect_hazard
    await director._roam()
    assert wheels == [(18, 18)] * 3 + [(0, 0)]
    await robot.disconnect()


async def test_manual_action_and_stop_preempt_freeplay():
    robot = SimulatorBackend()
    await robot.connect()
    controller = RobotController(robot)
    await controller.enable_freeplay(allow_movement=False)
    await asyncio.sleep(0.01)
    assert robot.state.freeplay
    controller.submit("head", lambda: robot.set_head_angle(12))
    await asyncio.sleep(0.05)
    assert robot.state.head_angle == 12
    assert not robot.state.freeplay
    await controller.enable_freeplay()
    await asyncio.sleep(0.01)
    controller.emergency_stop()
    await asyncio.sleep(0.05)
    assert controller.latched and not robot.state.freeplay
    await controller.shutdown()


async def test_roaming_requires_explicit_motor_and_floor_opt_in():
    robot = SimulatorBackend()
    await robot.connect()
    controller = RobotController(robot)
    robot._state = replace(robot.state, surface_mode="table")
    with pytest.raises(RobotError, match="clear floor"):
        await controller.enable_freeplay(allow_movement=True)
    assert not robot.state.freeplay
    await controller.shutdown()
