import asyncio
import random
from dataclasses import replace

import pytest

from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import CubeState, RobotError
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.services.personality import PersonalityDirector, safe_to_move, safe_to_pose


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
    double_tap = replace(
        tapped,
        cubes=(CubeState(1, tap_sequence=2), CubeState(2, tap_sequence=1), state.cubes[2]),
    )
    assert director._event_mood(double_tap) == "Happy"
    assert director.recent_taps == frozenset((1, 2))
    moved = replace(tapped, cubes=(CubeState(1, tap_sequence=1, move_sequence=1), *state.cubes[1:]))
    assert director._event_mood(moved) == "Curious"
    for flag in ("cliff_detected", "picked_up", "falling", "on_charger"):
        hazard = replace(moved, **{flag: True})
        assert not safe_to_move(hazard)
        assert director._event_mood(hazard) == ("Sleepy" if flag == "on_charger" else "Surprised")
        assert director._event_mood(hazard) is None
        assert director._event_mood(moved) == "Neutral"
    for mode in ("table", "unknown"):
        assert not safe_to_move(replace(state, surface_mode=mode))
        assert not safe_to_pose(replace(state, surface_mode=mode))


async def test_ambient_blinks_and_sounds_without_freeplay_or_wheel_motion(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    clock = VirtualClock()
    reached = asyncio.Event()
    clock.hook = lambda: reached.set() if clock.now >= 108 else None
    wheels = []
    frames = []
    original_display = robot.display_face

    async def display(frame, name="Custom"):
        frames.append(frame.tobytes())
        await original_display(frame, name)

    async def drive(left, right):
        wheels.append((left, right))

    monkeypatch.setattr(robot, "display_face", display)
    monkeypatch.setattr(robot, "drive", drive)
    director = PersonalityDirector(robot, rng=random.Random(4), clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run(ambient=True))
    async with asyncio.timeout(2):
        await reached.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert len(set(frames)) > 1
    assert any("vocalization" in event for event in robot.events)
    assert not wheels and not robot.state.freeplay
    await robot.disconnect()


async def test_grumpy_lift_gesture_requires_safe_floor(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    director = PersonalityDirector(robot, pause=lambda _seconds: asyncio.sleep(0))
    heights = []
    original_lift = robot.set_lift_height

    async def lift(height):
        heights.append(height)
        await original_lift(height)

    monkeypatch.setattr(robot, "set_lift_height", lift)
    await director._grumpy_arm()
    assert heights == [0.35, 0.08]
    assert "Simulated vocalization: grumble" in robot.events
    robot._state = replace(robot.state, picked_up=True)
    await director._grumpy_arm()
    assert heights == [0.35, 0.08]
    await robot.disconnect()


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


async def test_cube_tap_gets_an_immediate_happy_sound(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    clock = VirtualClock()
    tapped = False

    def tap_once():
        nonlocal tapped
        if not tapped:
            robot._state = replace(
                robot.state,
                cubes=(replace(robot.state.cubes[0], tap_sequence=1), *robot.state.cubes[1:]),
            )
            tapped = True

    clock.hook = tap_once
    director = PersonalityDirector(robot, clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run())
    async with asyncio.timeout(2):
        while clock.now < 101:  # noqa: ASYNC110 - wait for the director's injected clock
            await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert tapped
    assert "Simulated vocalization: happy" in robot.events
    await robot.disconnect()


async def test_sustained_hazard_does_not_flood_face_updates(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    robot._state = replace(robot.state, picked_up=True)
    clock = VirtualClock()
    faces = []
    original_display = robot.display_face

    async def display(frame, name="Custom"):
        faces.append((name, frame.tobytes()))
        await original_display(frame, name)

    monkeypatch.setattr(robot, "display_face", display)
    director = PersonalityDirector(robot, clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run())
    async with asyncio.timeout(2):
        while clock.now < 102:  # noqa: ASYNC110 - wait for the director's injected clock
            await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    normal = render_face("Surprised", gaze=director.gaze).tobytes()
    blink = render_face("Surprised", gaze=director.gaze, blink=True).tobytes()
    assert faces[0] == ("Surprised", normal)
    # Stable hazard mood may still blink; only alternating blink/restoration is allowed.
    for index, frame in enumerate(faces[1:]):
        assert frame == ("Surprised", blink if index % 2 == 0 else normal)
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


async def test_roam_stops_for_cube_interaction_before_reacting(monkeypatch):
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

    def tap_during_motion():
        if len(wheels) == 2:
            robot._state = replace(
                robot.state,
                cubes=(replace(robot.state.cubes[0], tap_sequence=1), *robot.state.cubes[1:]),
            )

    clock.hook = tap_during_motion
    await director._roam()
    assert wheels == [(18, 18)] * 2 + [(0, 0)]
    assert director._event_mood(robot.state) == "Happy"
    await robot.disconnect()


async def test_freeplay_invites_cube_and_reacts_to_a_real_tap(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    robot._state = replace(robot.state, surface_mode="table")
    clock = VirtualClock()
    lights = []
    original_set_color = robot.set_cube_color

    async def color(number, value):
        lights.append((number, value))
        await original_set_color(number, value)

    monkeypatch.setattr(robot, "set_cube_color", color)
    tapped = [False]

    def tap_invited_cube():
        if tapped[0]:
            return
        invited = next((cube for cube in robot.state.cubes if cube.light_color == "blue"), None)
        if invited:
            robot._state = replace(
                robot.state,
                cubes=tuple(
                    replace(cube, tap_sequence=cube.tap_sequence + 1)
                    if cube.number == invited.number
                    else cube
                    for cube in robot.state.cubes
                ),
            )
            tapped[0] = True

    clock.hook = tap_invited_cube
    director = PersonalityDirector(robot, clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run())
    async with asyncio.timeout(2):
        while clock.now < 111:  # noqa: ASYNC110 - wait for the injected clock
            await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert tapped[0]
    assert any(color == "green" for _, color in lights)
    assert lights[-1][1] == "off"
    assert all(cube.light_color == "off" for cube in robot.state.cubes)
    await robot.disconnect()


async def test_freeplay_waits_for_cube_invitation_before_roaming(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    clock = VirtualClock()
    moved_during_invitation = []
    movement = []
    invitations = []
    original_drive = robot.drive
    original_set_color = robot.set_cube_color

    async def drive(left, right):
        if left or right:
            movement.append(clock.now)
            if any(cube.light_color == "blue" for cube in robot.state.cubes):
                moved_during_invitation.append(clock.now)
        await original_drive(left, right)

    async def color(number, value):
        if value == "blue":
            invitations.append(clock.now)
        await original_set_color(number, value)

    monkeypatch.setattr(robot, "drive", drive)
    monkeypatch.setattr(robot, "set_cube_color", color)
    director = PersonalityDirector(robot, rng=random.Random(4), clock=clock.time, pause=clock.pause)
    director.rng.uniform = lambda low, high: low
    task = asyncio.create_task(director.run(allow_movement=True))
    async with asyncio.timeout(2):
        while clock.now < 114:  # noqa: ASYNC110 - wait for the director's injected clock
            await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert invitations and movement
    assert movement[0] < invitations[0]
    assert not moved_during_invitation
    await robot.disconnect()


async def test_cancelling_freeplay_clears_an_unanswered_invitation(monkeypatch):
    robot = SimulatorBackend()
    await robot.connect()
    await robot.enable_freeplay()
    lit = asyncio.Event()
    original_set_color = robot.set_cube_color

    async def color(number, value):
        await original_set_color(number, value)
        if value == "blue":
            lit.set()

    monkeypatch.setattr(robot, "set_cube_color", color)
    clock = VirtualClock()
    director = PersonalityDirector(robot, clock=clock.time, pause=clock.pause)
    task = asyncio.create_task(director.run())
    await asyncio.wait_for(lit.wait(), 2)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert all(c.light_color == "off" for c in robot.state.cubes)
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
