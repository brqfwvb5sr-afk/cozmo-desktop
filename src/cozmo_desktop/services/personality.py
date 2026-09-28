"""Original, event-driven companion behavior owned by RobotController.

Only the direct transport process can send hardware packets. This service never
uses upstream animation assets and never grants itself motor permissions.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable

from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import RobotBackend, RobotError, RobotState

HAZARDS = ("cliff_detected", "picked_up", "falling", "on_charger")


def safe_to_move(state: RobotState) -> bool:
    return (
        state.connected
        and state.freeplay
        and state.motors_enabled
        and state.surface_mode == "floor"
        and not any(getattr(state, flag) for flag in HAZARDS)
    )


class PersonalityDirector:
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
        self.mood = "Neutral"
        self.gaze = 0
        self.last_taps = tuple(c.tap_sequence for c in backend.state.cubes)
        self.last_moves = tuple(c.move_sequence for c in backend.state.cubes)
        self.recent_taps: frozenset[int] = frozenset()
        self.hazard_mood: str | None = None
        self.next_mood = 0.0
        self.next_blink = 0.0
        self.next_sound = 0.0
        self.next_reaction_sound = 0.0
        self.next_head = 0.0
        self.next_roam = 0.0
        self.next_invite = 0.0
        self.invite_cube = 0
        self.invite_until = 0.0
        self.invite_succeeded = False

    def _event_mood(self, state: RobotState) -> str | None:
        taps = tuple(c.tap_sequence for c in state.cubes)
        moves = tuple(c.move_sequence for c in state.cubes)
        self.recent_taps = frozenset(
            number
            for number, (current, prior) in enumerate(
                zip(taps, self.last_taps, strict=True), start=1
            )
            if current > prior
        )
        tapped = bool(self.recent_taps)
        moved = any(current > prior for current, prior in zip(moves, self.last_moves, strict=True))
        self.last_taps, self.last_moves = taps, moves
        if state.cliff_detected or state.picked_up or state.falling:
            hazard_mood = "Surprised"
        elif state.on_charger:
            hazard_mood = "Sleepy"
        else:
            hazard_mood = None
        if hazard_mood is not None:
            if self.hazard_mood != hazard_mood:
                self.hazard_mood = hazard_mood
                return hazard_mood
            return None
        if self.hazard_mood is not None:
            self.hazard_mood = None
            return "Neutral"
        if tapped:
            return "Happy"
        if moved:
            return "Curious"
        if state.battery_voltage is not None and state.battery_voltage < 3.5:
            return "Sleepy"
        return None

    async def _roam(self) -> None:
        """A bounded floor-only move; each pulse renews the worker's short lease."""
        left, right = self.rng.choice(((18, 18), (8, 18), (18, 8), (-12, 12), (12, -12)))
        pulses = 10 if left * right >= 0 else 8
        try:
            for _ in range(pulses):
                if not safe_to_move(self.backend.state):
                    return
                await self.backend.drive(left, right)
                await self.pause(0.08)
        finally:
            state = self.backend.state
            if state.connected and state.motors_enabled and state.surface_mode == "floor":
                try:
                    await self.backend.drive(0, 0)
                except RobotError:
                    pass  # The independent worker also locks/halts on sensor faults.

    async def run(self, *, allow_movement: bool = False) -> None:
        now = self.clock()
        self.next_mood = now
        self.next_blink = now + 3
        self.next_sound = now + 5
        self.next_head = now + 4
        self.next_roam = now + 4
        self.next_invite = now + 8
        try:
            while self.backend.state.connected and self.backend.state.freeplay:
                state = self.backend.state
                now = self.clock()
                event = self._event_mood(state)
                hazardous = self.hazard_mood is not None
                invitation_announced = False
                if self.invite_cube:
                    cube_connected = state.cubes[self.invite_cube - 1].connected
                    hazardous = any(getattr(state, flag) for flag in HAZARDS)
                    if now >= self.invite_until or not cube_connected or hazardous:
                        if cube_connected:
                            await self.backend.set_cube_color(self.invite_cube, "off")
                        self.invite_cube = 0
                    elif self.invite_cube in self.recent_taps and not self.invite_succeeded:
                        await self.backend.set_cube_color(self.invite_cube, "green")
                        self.invite_succeeded = True
                        self.invite_until = now + 0.6
                        event = "Happy"
                elif (
                    now >= self.next_invite
                    and not any(getattr(state, flag) for flag in HAZARDS)
                    and (state.battery_voltage is None or state.battery_voltage >= 3.5)
                ):
                    connected = tuple(c.number for c in state.cubes if c.connected)
                    if connected:
                        self.invite_cube = self.rng.choice(connected)
                        self.invite_succeeded = False
                        self.invite_until = now + 4
                        self.next_invite = now + self.rng.uniform(22, 36)
                        await self.backend.set_cube_color(self.invite_cube, "blue")
                        await self.backend.play_sound("question")
                        invitation_announced = True
                        self.next_sound = max(self.next_sound, now + 4)
                        event = "Curious"
                if event or (not hazardous and now >= self.next_mood):
                    self.mood = event or self.rng.choice(
                        ("Neutral", "Curious", "Happy", "Sleepy", "Confused", "Angry")
                    )
                    self.gaze = self.rng.choice((-5, 0, 5))
                    await self.backend.display_face(
                        render_face(self.mood, gaze=self.gaze), self.mood
                    )
                    self.next_mood = now + self.rng.uniform(4, 9)
                if (
                    event in ("Happy", "Curious")
                    and not invitation_announced
                    and now >= self.next_reaction_sound
                ):
                    await self.backend.play_sound("happy" if event == "Happy" else "question")
                    self.next_reaction_sound = now + 1
                    self.next_sound = max(self.next_sound, now + 4)
                if now >= self.next_blink:
                    await self.backend.display_face(
                        render_face(self.mood, gaze=self.gaze, blink=True), self.mood
                    )
                    await self.pause(0.12)
                    await self.backend.display_face(
                        render_face(self.mood, gaze=self.gaze), self.mood
                    )
                    self.next_blink = now + self.rng.uniform(3, 7)
                if now >= self.next_sound and not (
                    state.cliff_detected or state.picked_up or state.falling
                ):
                    sound = {
                        "Angry": "grumble",
                        "Happy": "happy",
                        "Excited": "happy",
                        "Curious": "question",
                        "Confused": "question",
                        "Sleepy": "sleepy",
                    }.get(self.mood, "chirp")
                    await self.backend.play_sound(sound)
                    self.next_sound = now + self.rng.uniform(12, 22)
                if now >= self.next_head:
                    if safe_to_move(state):
                        await self.backend.set_head_angle(self.rng.choice((-5, 5, 12)))
                    self.next_head = now + self.rng.uniform(7, 12)
                if allow_movement and now >= self.next_roam:
                    if safe_to_move(state):
                        await self._roam()
                    self.next_roam = now + self.rng.uniform(6, 12)
                await self.pause(0.1)
        finally:
            if (
                self.invite_cube
                and self.backend.state.connected
                and self.backend.state.cubes[self.invite_cube - 1].connected
            ):
                try:
                    await self.backend.set_cube_color(self.invite_cube, "off")
                except RobotError:
                    pass
            await self.backend.disable_freeplay()
