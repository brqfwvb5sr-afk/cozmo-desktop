"""Game rules use event counters and original cube-light commands, not app assets."""

import asyncio
from dataclasses import replace

import pytest

from cozmo_desktop.robot.base import CubeEvent, CubeState, RobotError, RobotState
from cozmo_desktop.services.games import COLORS, GameDirector


class ScriptedRobot:
    def __init__(self, connected=3):
        self.state = RobotState(
            connected=True,
            cubes=tuple(CubeState(number, connected=number <= connected) for number in range(1, 4)),
        )
        self.lights = []
        self.sounds = []
        self.faces = []

    async def set_cube_color(self, number, color):
        self.lights.append((number, color))

    async def play_sound(self, kind):
        self.sounds.append(kind)

    async def display_face(self, frame, name="Custom"):
        self.faces.append(name)

    def event(self, number, kind):
        cubes = list(self.state.cubes)
        cube = cubes[number - 1]
        field = "tap_sequence" if kind == "tap" else "move_sequence"
        cubes[number - 1] = replace(cube, **{field: getattr(cube, field) + 1})
        events = self.state.cube_events
        ordinal = events[-1].ordinal + 1 if events else 1
        self.state = replace(
            self.state,
            cubes=tuple(cubes),
            cube_events=(*events[-31:], CubeEvent(ordinal, number, kind)),
        )


class VirtualClock:
    def __init__(self):
        self.now = 10.0
        self.hook = None

    def time(self):
        return self.now

    async def pause(self, seconds):
        self.now += seconds
        if self.hook is not None:
            self.hook()
        await asyncio.sleep(0)


class PredictableRandom:
    def choice(self, choices):
        return choices[0]

    def randrange(self, count):
        return 1

    def uniform(self, low, high):
        return low

    def random(self):
        return 0.5


def director_for(robot, clock):
    return GameDirector(robot, rng=PredictableRandom(), clock=clock.time, pause=clock.pause)


async def test_quick_tap_five_real_taps_score_and_clear_lights():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    game.rng.choice = lambda choices: "green" if choices == COLORS else choices[0]
    last_round = [0]

    def tap_once():
        if game.state.phase == "watch" and game.state.round > last_round[0]:
            last_round[0] = game.state.round
            robot.event(1, "tap")

    clock.hook = tap_once
    await game.run("Quick Tap")
    assert game.state.phase == "finished"
    assert (game.state.player_score, game.state.cozmo_score) == (5, 0)
    assert robot.lights[0] == (3, "blue") and robot.lights[-1] == (3, "off")
    assert len(robot.sounds) == 5
    assert robot.faces == ["Sad"] * 5


async def test_quick_tap_red_is_never_a_valid_target():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    last_round = [0]

    def tap_red():
        if game.state.phase == "watch" and game.state.round > last_round[0]:
            last_round[0] = game.state.round
            robot.event(1, "tap")

    clock.hook = tap_red
    await game.run("Quick Tap")
    assert (game.state.player_score, game.state.cozmo_score) == (0, 5)
    assert game.state.round == 5
    assert robot.faces == ["Happy"] * 5
    assert all(color == "off" for _, color in robot.lights[-3:])


async def test_quick_tap_cozmo_can_win_a_valid_round_without_player_tap():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    game.rng.choice = lambda choices: "green" if choices == COLORS else choices[0]
    await game.run("Quick Tap")
    assert game.state.phase == "finished"
    assert (game.state.player_score, game.state.cozmo_score) == (0, 5)
    assert game.state.round == 5
    assert robot.faces == ["Happy"] * 5


async def test_quick_tap_cozmo_wrong_red_response_awards_player():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    game.rng.random = lambda: 0.0
    await game.run("Quick Tap")
    assert (game.state.player_score, game.state.cozmo_score) == (5, 0)
    assert game.state.round == 5
    assert robot.faces == ["Sad"] * 5


async def test_quick_tap_correct_abstentions_cannot_create_a_false_winner():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    await game.run("Quick Tap")
    assert (game.state.player_score, game.state.cozmo_score) == (0, 0)
    assert game.state.round == 40
    assert game.state.instruction == "Round limit reached without a winner."


async def test_memory_match_increasing_sequence_and_wrong_or_missing_input():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    answered = [0]

    def tap_sequence():
        if game.state.phase == "answer" and answered[0] < game.state.round:
            answered[0] += 1
            robot.event(1, "tap")
        elif game.state.phase == "show":
            answered[0] = 0

    clock.hook = tap_sequence
    await game.run("Memory Match")
    assert game.state.player_score == 4 and game.state.cozmo_score == 0
    assert sum(number == 1 and color == "blue" for number, color in robot.lights) == 10
    assert all(color == "off" for _, color in robot.lights[-3:])

    robot2, clock2 = ScriptedRobot(), VirtualClock()
    missed = director_for(robot2, clock2)
    await missed.run("Memory Match")
    assert (missed.state.player_score, missed.state.cozmo_score) == (0, 4)


async def test_memory_match_uses_ordered_cross_cube_taps_even_when_events_arrive_together():
    robot, clock = ScriptedRobot(), VirtualClock()
    game = director_for(robot, clock)
    choices = iter((2, 3, 1, 2))
    game.rng.choice = lambda _choices: next(choices)
    answered = set()

    def answer():
        round_number = game.state.round
        if game.state.phase == "answer" and round_number not in answered:
            answered.add(round_number)
            for number in (2, 3, 1, 2)[:round_number]:
                robot.event(number, "tap")

    clock.hook = answer
    await game.run("Memory Match")
    assert (game.state.player_score, game.state.cozmo_score) == (4, 0)


async def test_keepaway_reacts_to_separate_move_events():
    robot, clock = ScriptedRobot(connected=1), VirtualClock()
    game = director_for(robot, clock)
    phases = set()

    def move_twice():
        key = (game.state.round, game.state.phase)
        if key not in phases and game.state.phase in ("watch", "react"):
            phases.add(key)
            robot.event(1, "move")

    clock.hook = move_twice
    await game.run("Keepaway")
    assert game.state.player_score == 5
    assert robot.lights[0] == (1, "green") and robot.lights[-1] == (1, "off")


async def test_preconditions_hazard_and_cancel_clear_lights():
    robot, clock = ScriptedRobot(connected=1), VirtualClock()
    game = director_for(robot, clock)
    with pytest.raises(RobotError, match="Connect 3"):
        await game.run("Memory Match")
    with pytest.raises(RobotError, match="Unknown"):
        await game.run("nonexistent")
    robot.state = replace(robot.state, cliff_detected=True)
    with pytest.raises(RobotError, match="unsafe"):
        await game.run("Keepaway")
    robot.state = replace(robot.state, cliff_detected=False)
    clock.hook = lambda: (_ for _ in ()).throw(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await game.run("Keepaway")
    assert game.state.phase == "cancelled"
    assert robot.lights[-1] == (1, "off")


async def test_game_failure_marks_state_and_clears_cube_lights():
    robot, clock = ScriptedRobot(connected=1), VirtualClock()
    game = director_for(robot, clock)

    def detect_hazard():
        if game.state.phase == "watch":
            robot.state = replace(robot.state, cliff_detected=True)

    clock.hook = detect_hazard
    with pytest.raises(RobotError, match="unsafe"):
        await game.run("Keepaway")
    assert game.state.phase == "failed"
    assert robot.lights[-1] == (1, "off")
