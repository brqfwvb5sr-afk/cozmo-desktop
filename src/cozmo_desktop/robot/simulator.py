"""Deterministic synthetic robot. No sockets, USB, microphone or hardware access."""

import asyncio
import logging
import math
import time
from dataclasses import replace

from PIL import Image, ImageDraw

from .base import Animation, CubeState, NotConnectedError, RobotBackend, RobotError, RobotState

MAX_SPEED = 80.0
DRIVE_LEASE = 0.35


def bounded(value: float, low: float, high: float) -> float:
    if not math.isfinite(value):
        raise RobotError("Control values must be finite numbers.")
    return max(low, min(high, value))


class SimulatorBackend(RobotBackend):
    def __init__(self) -> None:
        self._state = RobotState()
        self._ticker: asyncio.Task[None] | None = None
        self._drive_until = 0.0
        self._elapsed = 0.0
        self._face: Image.Image | None = None
        self._animation_generation = 0
        self.events: list[str] = []

    @property
    def state(self) -> RobotState:
        return self._state

    @property
    def animations(self) -> tuple[Animation, ...]:
        return (
            Animation("Hello, friend", "Greeting", 1.2),
            Animation("Little celebration", "Happy", 1.5),
            Animation("Curious glance", "Idle", 1.0),
            Animation("Sleepy eyes", "Sleep", 1.3),
        )

    def _require_connection(self) -> None:
        if not self._state.connected:
            raise NotConnectedError()

    def _event(self, text: str) -> None:
        self.events.append(text)
        del self.events[:-100]

    async def connect(self) -> None:
        if self._state.connected:
            return
        self._state = replace(
            self._state,
            connected=True,
            camera_available=True,
            cubes=tuple(CubeState(n, connected=True) for n in range(1, 4)),
        )
        self._event("Simulation connected")
        self._ticker = asyncio.create_task(self._run())

    async def disconnect(self) -> None:
        await self.stop()
        self._state = replace(
            self._state,
            connected=False,
            camera_available=False,
            face_detected=False,
            cubes=tuple(CubeState(n) for n in range(1, 4)),
        )
        if self._ticker is not None:
            self._ticker.cancel()
            await asyncio.gather(self._ticker, return_exceptions=True)
            self._ticker = None
        self._event("Simulation disconnected")

    async def drive(self, left: float, right: float) -> None:
        self._require_connection()
        self._state = replace(
            self._state,
            left_speed=bounded(left, -MAX_SPEED, MAX_SPEED),
            right_speed=bounded(right, -MAX_SPEED, MAX_SPEED),
            freeplay=False,
        )
        self._drive_until = time.monotonic() + DRIVE_LEASE

    async def stop(self) -> None:
        self._animation_generation += 1
        self._drive_until = 0.0
        self._state = replace(
            self._state,
            left_speed=0.0,
            right_speed=0.0,
            animation=None,
            freeplay=False,
        )

    async def set_head_angle(self, angle: float) -> None:
        self._require_connection()
        self._state = replace(self._state, head_angle=bounded(angle, -25, 44.5))

    async def set_lift_height(self, height: float) -> None:
        self._require_connection()
        self._state = replace(self._state, lift_height=bounded(height, 0, 1))

    async def speak(self, text: str) -> None:
        self._require_connection()
        if not text.strip() or len(text) > 500:
            raise RobotError("Enter between 1 and 500 characters.")
        self._state = replace(self._state, speech=text.strip())
        self._event("Simulated speech event (no audio output)")

    async def play_animation(self, animation: str) -> None:
        self._require_connection()
        match = next((a for a in self.animations if a.name == animation), None)
        if match is None:
            raise RobotError("That animation is unavailable in this backend.")
        self._animation_generation += 1
        generation = self._animation_generation
        expression = {"Greeting": "Happy", "Happy": "Excited", "Idle": "Curious", "Sleep": "Sleepy"}
        self._state = replace(
            self._state,
            animation=animation,
            expression=expression[match.category],
        )
        self._event(f"Animation: {animation}")
        try:
            await asyncio.sleep(match.duration)
        finally:
            if generation == self._animation_generation:
                self._state = replace(self._state, animation=None)

    async def display_face(self, frame: Image.Image, name: str = "Custom") -> None:
        self._require_connection()
        if frame.size != (128, 64):
            raise RobotError("Expression frames must be 128 by 64 pixels.")
        self._face = frame.copy()
        self._state = replace(self._state, expression=name)
        self._event(f"Expression: {name}")

    async def get_camera_frame(self) -> Image.Image:
        self._require_connection()
        frame = Image.new("RGB", (640, 360), "#102c36")
        draw = ImageDraw.Draw(frame)
        for x in range(0, 641, 40):
            draw.line((x, 0, x, 360), fill="#1b3b44")
        for y in range(0, 361, 40):
            draw.line((0, y, 640, y), fill="#1b3b44")
        for index, cube in enumerate(self._state.cubes):
            x = 120 + index * 160 + int(12 * math.sin(self._elapsed))
            draw.rounded_rectangle((x, 170, x + 65, 235), radius=10, outline="#53e0bc", width=3)
            draw.text((x + 10, 195), f"CUBE {cube.number}", fill="white")
        draw.text((20, 20), "SIMULATED CAMERA / SYNTHETIC SCENE", fill="#79ebd1")
        draw.text((20, 330), f"POSE {self._state.x:.0f}, {self._state.y:.0f} mm", fill="white")
        if self._state.face_detected:
            draw.rectangle((275, 50, 355, 140), outline="#d9abff", width=2)
            draw.text((278, 60), "TEST FACE", fill="white")
        return frame

    async def enable_freeplay(self) -> None:
        self._require_connection()
        await self.stop()
        self._state = replace(self._state, freeplay=True)

    async def disable_freeplay(self) -> None:
        self._state = replace(self._state, freeplay=False)

    def advance(self, dt: float, now: float) -> None:
        """Advance synthetic state; public deterministic seam for unit tests."""
        if not self._state.connected:
            return
        self._elapsed += dt
        state = self._state
        if now >= self._drive_until:
            state = replace(state, left_speed=0, right_speed=0)
        heading = state.heading + (state.right_speed - state.left_speed) / 70 * dt
        speed = (state.left_speed + state.right_speed) / 2
        face = int(self._elapsed / 6) % 2 == 1
        cubes = tuple(
            replace(
                c,
                tapped=(int(self._elapsed) % 9 == c.number),
                moved=(int(self._elapsed) % 13 == c.number),
            )
            for c in state.cubes
        )
        if face != state.face_detected:
            self._event("Synthetic face appeared" if face else "Synthetic face left")
        self._state = replace(
            state,
            x=state.x + speed * math.cos(heading) * dt,
            y=state.y + speed * math.sin(heading) * dt,
            heading=heading,
            battery=max(0.0, (state.battery or 0) - dt * 0.003),
            face_detected=face,
            cubes=cubes,
            expression=("Curious" if face else "Sleepy") if state.freeplay else state.expression,
        )

    async def _run(self) -> None:
        previous = time.monotonic()
        try:
            while self._state.connected:
                await asyncio.sleep(0.05)
                now = time.monotonic()
                self.advance(min(now - previous, 0.1), now)
                previous = now
        except Exception as exc:
            logging.getLogger(__name__).error("simulator_failed error_type=%s", type(exc).__name__)
            self._state = replace(
                self._state,
                connected=False,
                camera_available=False,
                face_detected=False,
                cubes=tuple(CubeState(n) for n in range(1, 4)),
            )
            self._event("Simulation interrupted; reconnect to continue")
        finally:
            # Includes unexpected ticker failures and cancellation.
            await self.stop()
