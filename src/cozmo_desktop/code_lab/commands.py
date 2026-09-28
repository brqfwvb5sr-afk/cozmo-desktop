"""Validated, bounded Scratch commands through the existing robot controller."""

import asyncio
import math
from typing import Any

from cozmo_desktop.face.expressions import NAMES, render_face
from cozmo_desktop.robot.base import VOCALIZATIONS, RobotError
from cozmo_desktop.services.controller import RobotController


class ScratchCommandError(RobotError):
    """A child-friendly command rejection."""


class ScratchCommands:
    def __init__(self, controller: RobotController) -> None:
        self.controller = controller
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()

    def cancel(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()

    @property
    def active(self) -> bool:
        return bool(self._tasks)

    async def execute(self, command: str, arguments: dict[str, Any]) -> Any:
        if not isinstance(command, str) or not isinstance(arguments, dict):
            raise ScratchCommandError("That block has invalid values.")
        if command == "state":
            return self.state()
        if command == "stop":
            self.cancel()
            await self.controller.backend.stop()
            return None
        if command not in {
            "drive_distance",
            "turn",
            "drive_timed",
            "stop",
            "head",
            "lift",
            "expression",
            "clear_face",
            "say",
            "sound",
            "animation",
            "cube_color",
            "ai_ask",
            "ai_say",
        }:
            raise ScratchCommandError("That Cozmo block is not available.")
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        try:
            async with self._lock:
                if self.controller.latched or self.controller.closing:
                    raise ScratchCommandError("Cozmo is stopped. Ask an adult to resume controls.")
                if not self.controller.backend.state.connected:
                    raise ScratchCommandError("Connect Cozmo or the simulator first.")
                state = self.controller.backend.state
                if state.cliff_detected or state.picked_up or state.falling:
                    raise ScratchCommandError("Cozmo stopped because of a safety sensor.")
                await self.controller.stop_ambient()
                if self.controller._game_task is not None:
                    await self.controller.stop_game()
                if self.controller._freeplay_task is not None:
                    await self.controller.disable_freeplay()
                return await self._dispatch(command, arguments)
        finally:
            self._tasks.discard(task)

    def state(self) -> dict[str, Any]:
        state = self.controller.backend.state
        return {
            "connected": state.connected,
            "battery": state.battery,
            "picked_up": state.picked_up,
            "cliff": state.cliff_detected,
            "person_visible": state.face_detected,
            "head_angle": state.head_angle,
            "lift_position": round(state.lift_height * 100),
            "expression": state.expression,
            "speech": state.speech,
            "cubes": [
                {
                    "number": cube.number,
                    "connected": cube.connected,
                    "tapped": cube.tapped,
                    "moving": cube.moved,
                    "tap_sequence": cube.tap_sequence,
                    "move_sequence": cube.move_sequence,
                }
                for cube in state.cubes
            ],
            "stop": self.controller.latched,
            "simulation": self.controller.backend.is_simulation,
        }

    @staticmethod
    def _number(arguments: dict[str, Any], key: str, minimum: float, maximum: float) -> float:
        value = arguments.get(key)
        if value is None or isinstance(value, bool):
            raise ScratchCommandError("Enter a valid number in the Cozmo block.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ScratchCommandError("Enter a valid number in the Cozmo block.") from exc
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise ScratchCommandError("That number is outside Cozmo's safe range.")
        return number

    @staticmethod
    def _text(arguments: dict[str, Any], key: str, maximum: int = 200) -> str:
        value = arguments.get(key)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
            raise ScratchCommandError("Enter a shorter message in the Cozmo block.")
        return value.strip()

    async def _motion(self, left: float, right: float, duration: float) -> None:
        backend = self.controller.backend
        state = backend.state
        if not state.motors_enabled or state.surface_mode != "floor" or state.on_charger:
            raise ScratchCommandError("Driving needs armed motors on a clear floor.")
        try:
            end = asyncio.get_running_loop().time() + duration
            while asyncio.get_running_loop().time() < end:
                state = backend.state
                if (
                    self.controller.latched
                    or not state.connected
                    or state.cliff_detected
                    or state.picked_up
                    or state.falling
                    or state.on_charger
                ):
                    raise ScratchCommandError("Cozmo stopped because of a safety sensor.")
                await self.controller.drive(left, right)
                await asyncio.sleep(min(0.1, max(0, end - asyncio.get_running_loop().time())))
        finally:
            await backend.stop()

    async def _dispatch(self, command: str, args: dict[str, Any]) -> Any:
        backend = self.controller.backend
        if command == "drive_distance":
            distance = self._number(args, "distance_cm", -50, 50)
            speed = min(20, self.controller.speed_limit)
            duration = abs(distance * 10 / speed) if distance else 0
            signed_speed = math.copysign(speed, distance)
            await self._motion(signed_speed, signed_speed, duration)
        elif command == "turn":
            degrees = self._number(args, "degrees", -180, 180)
            speed = min(15, self.controller.speed_limit)
            # Approximate Cozmo wheel track; physical calibration remains required.
            duration = abs(math.radians(degrees) * 70 / (2 * speed)) if degrees else 0
            signed_speed = math.copysign(speed, degrees)
            await self._motion(signed_speed, -signed_speed, duration)
        elif command == "drive_timed":
            speed = self._number(args, "speed", -20, 20)
            duration = self._number(args, "seconds", 0, 3)
            await self._motion(speed, speed, duration)
        elif command == "head":
            await backend.set_head_angle(self._number(args, "angle", -25, 44.5))
        elif command == "lift":
            await backend.set_lift_height(self._number(args, "percent", 0, 100) / 100)
        elif command == "expression":
            name = self._text(args, "name", 30).title()
            if name not in NAMES:
                raise ScratchCommandError("Choose a known Cozmo expression.")
            await backend.display_face(render_face(name), name)
        elif command == "clear_face":
            await backend.display_face(render_face("Neutral"), "Neutral")
        elif command == "say":
            await backend.speak(self._text(args, "text"))
        elif command == "sound":
            kind = self._text(args, "kind", 20)
            if kind not in VOCALIZATIONS:
                raise ScratchCommandError("Choose a known Cozmo sound.")
            await backend.play_sound(kind)
        elif command == "animation":
            name = self._text(args, "name", 80)
            if name not in {item.name for item in backend.animations}:
                raise ScratchCommandError("That animation is unavailable for this Cozmo.")
            await backend.play_animation(name)
        elif command == "cube_color":
            number = self._number(args, "cube", 1, 3)
            color = self._text(args, "color", 10)
            if not number.is_integer() or color not in {"off", "red", "green", "blue"}:
                raise ScratchCommandError("Choose a valid cube and color.")
            await backend.set_cube_color(int(number), color)
        elif command in {"ai_ask", "ai_say"}:
            if not self.controller.settings.ai_enabled or not self.controller.settings.ollama_model:
                raise ScratchCommandError("Choose a local Ollama model in Settings first.")
            reply = await self.controller.conversation.reply(
                self._text(args, "question", 400),
                self.controller.settings.ollama_model,
                backend.state,
                temperature=self.controller.settings.temperature,
                max_tokens=self.controller.settings.max_tokens,
                remember=self.controller.settings.memory_enabled,
            )
            if command == "ai_say":
                await backend.speak(reply.speech)
            return reply.speech
        return None
