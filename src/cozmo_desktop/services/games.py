"""Open-source recreations of three classic Power Cube play patterns.

The original mobile app's engine, graphics, progress and licensed assets are not
available to direct Wi-Fi clients. This module uses received cube events and LEDs.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from cozmo_desktop.robot.base import RobotBackend, RobotError, RobotState

GAME_NAMES = ("Quick Tap", "Memory Match", "Keepaway")
COLORS = ("red", "green", "blue")


@dataclass(frozen=True)
class GameState:
    name: str = ""
    phase: str = "idle"
    round: int = 0
    player_score: int = 0
    cozmo_score: int = 0
    instruction: str = "Choose a game to play with connected Power Cubes."


class GameDirector:
    def __init__(
        self,
        backend: RobotBackend,
        *,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
        pause: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.backend = backend
        self.rng = rng or random.Random()
        self.clock = clock
        self.pause = pause
        self.state = GameState()

    def _check(self, required: int) -> RobotState:
        state = self.backend.state
        if not state.connected or any(
            (state.cliff_detected, state.picked_up, state.falling, state.on_charger)
        ):
            raise RobotError("Game stopped: robot disconnected or an unsafe state was detected.")
        if not all(c.connected for c in state.cubes[:required]):
            raise RobotError(f"Connect {required} Power Cubes before playing this game.")
        return state

    def _score(self, *, player: bool) -> None:
        self.state = replace(
            self.state,
            player_score=self.state.player_score + int(player),
            cozmo_score=self.state.cozmo_score + int(not player),
        )

    async def _wait_for(self, number: int, sequence: int, seconds: float, *, tap: bool) -> bool:
        deadline = self.clock() + seconds
        while self.clock() < deadline:
            state = self._check(number)
            cube = state.cubes[number - 1]
            current = cube.tap_sequence if tap else cube.move_sequence
            if current > sequence:
                return True
            await self.pause(0.05)
        return False

    async def _quick_tap(self) -> None:
        self._check(2)
        for round_number in range(1, 6):
            state = self._check(2)
            self.state = replace(self.state, round=round_number, phase="watch")
            player_color = self.rng.choice(COLORS)
            match = bool(self.rng.randrange(2))
            other_color = (
                player_color
                if match
                else self.rng.choice(tuple(c for c in COLORS if c != player_color))
            )
            first_tap = state.cubes[0].tap_sequence
            await self.backend.set_cube_color(1, player_color)
            await self.backend.set_cube_color(2, other_color)
            self.state = replace(
                self.state,
                instruction=("Tap Cube 1 when both colors match. Cozmo reacts after 1.5 seconds."),
            )
            tapped = await self._wait_for(1, first_tap, 1.5, tap=True)
            if tapped == match:
                if tapped:
                    self._score(player=True)
                    await self.backend.play_sound("chirp")
            elif match or tapped:
                self._score(player=False)
                await self.backend.play_sound("grumble")
            await self.backend.set_cube_color(1, "off")
            await self.backend.set_cube_color(2, "off")
            await self.pause(0.3)

    async def _memory_match(self) -> None:
        self._check(3)
        sequence: list[int] = []
        for round_number in range(1, 5):
            self._check(3)
            sequence.append(self.rng.choice((1, 2, 3)))
            self.state = replace(
                self.state,
                round=round_number,
                phase="show",
                instruction="Watch the blue cube sequence, then tap the same cubes in order.",
            )
            for number in sequence:
                await self.backend.set_cube_color(number, "blue")
                await self.pause(0.45)
                await self.backend.set_cube_color(number, "off")
                await self.pause(0.2)
            self.state = replace(self.state, phase="answer", instruction="Now repeat the sequence.")
            events = self.backend.state.cube_events
            seen_ordinal = events[-1].ordinal if events else 0
            correct = True
            for expected in sequence:
                deadline = self.clock() + 5
                actual = 0
                while self.clock() < deadline:
                    state = self._check(3)
                    events = state.cube_events
                    if events and events[0].ordinal > seen_ordinal + 1:
                        raise RobotError("Cube event stream overflowed during Memory Match.")
                    for event in events:
                        if event.ordinal > seen_ordinal:
                            seen_ordinal = event.ordinal
                            if event.kind == "tap":
                                actual = event.number
                                break
                    if actual:
                        break
                    await self.pause(0.05)
                if actual != expected:
                    correct = False
                    break
            self._score(player=correct)
            await self.backend.play_sound("chirp" if correct else "grumble")
            if not correct:
                self.state = replace(self.state, instruction="Wrong sequence or time expired.")
                await self.pause(0.5)

    async def _keepaway(self) -> None:
        self._check(1)
        await self.backend.set_cube_color(1, "green")
        for round_number in range(1, 6):
            state = self._check(1)
            self.state = replace(
                self.state,
                round=round_number,
                phase="watch",
                instruction="Move Cube 1, then move it again before Cozmo reacts.",
            )
            if not await self._wait_for(1, state.cubes[0].move_sequence, 5, tap=False):
                self.state = replace(self.state, instruction="Move the cube to begin a round.")
                continue
            await self.backend.play_sound("chirp")
            count = self.backend.state.cubes[0].move_sequence
            self.state = replace(self.state, phase="react", instruction="Pull it away now!")
            player = await self._wait_for(1, count, 1.4, tap=False)
            self._score(player=player)
            await self.backend.play_sound("chirp" if player else "grumble")
            await self.pause(0.35)

    async def run(self, name: str) -> None:
        if name not in GAME_NAMES:
            raise RobotError("Unknown Power Cube game.")
        required = {"Quick Tap": 2, "Memory Match": 3, "Keepaway": 1}[name]
        self._check(required)
        self.state = GameState(name=name, phase="starting")
        try:
            if name == "Quick Tap":
                await self._quick_tap()
            elif name == "Memory Match":
                await self._memory_match()
            else:
                await self._keepaway()
            self.state = replace(self.state, phase="finished", instruction="Game complete.")
        except asyncio.CancelledError:
            self.state = replace(self.state, phase="cancelled", instruction="Game stopped.")
            raise
        finally:
            if self.backend.state.connected:
                for number in range(1, required + 1):
                    try:
                        await self.backend.set_cube_color(number, "off")
                    except RobotError:
                        pass
