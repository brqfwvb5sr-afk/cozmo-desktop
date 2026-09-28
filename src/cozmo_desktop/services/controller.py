"""One command owner for GUI, sequences and future AI providers."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cozmo_desktop.ai.local_chat import ChatTurn, local_reply
from cozmo_desktop.robot.base import RobotBackend, RobotError
from cozmo_desktop.robot.simulator import MAX_SPEED, bounded
from cozmo_desktop.services.games import GAME_NAMES, GameDirector, GameState

logger = logging.getLogger(__name__)


class RobotController:
    def __init__(self, backend: RobotBackend, speed_limit: float = 40) -> None:
        self.backend = backend
        self.speed_limit = bounded(speed_limit, 10, min(MAX_SPEED, backend.speed_cap))
        self.latched = False
        self.message = "Choose a connection mode, then connect to Cozmo."
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stop_task: asyncio.Task[None] | None = None
        self.closing = False
        self._stop_epoch = 0
        self._freeplay_task: asyncio.Task[None] | None = None
        self.freeplay_allows_motion = False
        self._game_task: asyncio.Task[None] | None = None
        self._game_director: GameDirector | None = None

        self.chat_turns: list[ChatTurn] = []

        self.chat_status = "Enter an installed Ollama model and type a message."

    @property
    def game_state(self) -> GameState:
        return self._game_director.state if self._game_director is not None else GameState()

    @property
    def chat_busy(self) -> bool:
        task = self._tasks.get("chat")
        return task is not None and not task.done()

    def submit(self, name: str, operation: Callable[[], Awaitable[None]]) -> None:
        """Drop repeated in-flight requests; never build up a hardware command queue."""
        if self.closing or self.latched:
            if self.latched:
                self.message = "Emergency stop is active. Select Resume controls to continue."
            return
        if name in self._tasks and not self._tasks[name].done():
            return
        if name not in ("camera", "freeplay", "game") and self._freeplay_task is not None:
            if not self._freeplay_task.done():
                self._freeplay_task.cancel()
                self._schedule_stop()
        if name not in ("camera", "game") and self._game_task is not None:
            if not self._game_task.done():
                self._game_task.cancel()
                self._schedule_stop()
        self._tasks[name] = asyncio.create_task(self._execute(name, operation))

    async def _execute(self, name: str, operation: Callable[[], Awaitable[None]]) -> None:
        try:
            async with asyncio.timeout(40 if name == "chat" else 15):
                if self._stop_task is not None and not self._stop_task.done():
                    await asyncio.shield(self._stop_task)
                if name not in ("camera", "freeplay", "game") and self._freeplay_task:
                    await asyncio.gather(self._freeplay_task, return_exceptions=True)
                if name not in ("camera", "game") and self._game_task:
                    await asyncio.gather(self._game_task, return_exceptions=True)
                if self.latched or self.closing:
                    return
                await operation()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Deliberately exclude exception text: SDK/provider errors may contain keys.
            logger.error("command_failed operation=%s error_type=%s", name, type(exc).__name__)
            self.message = (
                str(exc)
                if isinstance(exc, RobotError)
                else ("That operation failed. Controls have stopped; see Diagnostics.")
            )
            self.emergency_stop(preserve_message=True)
        finally:
            if self._tasks.get(name) is asyncio.current_task():
                self._tasks.pop(name, None)

    async def send_chat(self, text: str, model: str) -> None:
        from cozmo_desktop.face.expressions import render_face

        text = text.strip()
        if not 1 <= len(text) <= 400:
            self.chat_status = "Enter a message of 1–400 characters."
            return
        if not self.backend.state.connected:
            self.chat_status = "Connect to Cozmo first."
            return
        turn = ChatTurn("user", text)
        self.chat_status = "Thinking locally…"
        try:
            reply = await local_reply(model.strip(), (*self.chat_turns, turn))
        except asyncio.CancelledError:
            self.chat_status = "Conversation stopped."
            raise
        except RobotError as exc:
            self.chat_status = str(exc)
            return
        await self.backend.display_face(render_face(reply.emotion), reply.emotion)
        self.chat_turns.append(turn)
        self.chat_turns.append(ChatTurn("assistant", reply.speech))
        self.chat_status = "Reply ready."
        await self.backend.speak(reply.speech)

    def _cancel_commands(self) -> None:
        current = asyncio.current_task()
        for task in tuple(self._tasks.values()):
            if task is not current:
                task.cancel()
        if self._freeplay_task is not None and not self._freeplay_task.done():
            self._freeplay_task.cancel()
        if self._game_task is not None and not self._game_task.done():
            self._game_task.cancel()

    async def start_game(self, name: str) -> None:
        if name not in GAME_NAMES:
            raise RobotError("Unknown Power Cube game.")
        if self._game_task is not None and not self._game_task.done():
            await self.stop_game()
        if self._freeplay_task is not None and not self._freeplay_task.done():
            self._freeplay_task.cancel()
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
        await self.backend.stop()
        director = GameDirector(self.backend)
        director._check({"Quick Tap": 2, "Memory Match": 3, "Keepaway": 1}[name])
        self._game_director = director
        self._game_task = asyncio.create_task(director.run(name))
        self._game_task.add_done_callback(self._game_finished)

    def _game_finished(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and not self.closing:
            logger.error("game_failed error_type=%s", type(error).__name__)
            self.message = "Game stopped after a cube or robot error. Controls are locked."
            self.emergency_stop(preserve_message=True)

    async def stop_game(self) -> None:
        if self._game_task is not None:
            self._game_task.cancel()
            await asyncio.gather(self._game_task, return_exceptions=True)
            self._game_task = None
        await self.backend.stop()

    async def enable_freeplay(self, *, allow_movement: bool = False) -> None:
        from cozmo_desktop.services.personality import PersonalityDirector

        state = self.backend.state
        if allow_movement and (not state.motors_enabled or state.surface_mode != "floor"):
            raise RobotError("Self-directed movement requires enabled motors on a clear floor.")
        await self.backend.enable_freeplay()
        self.freeplay_allows_motion = allow_movement
        director = PersonalityDirector(self.backend)
        self._freeplay_task = asyncio.create_task(director.run(allow_movement=allow_movement))
        self._freeplay_task.add_done_callback(self._freeplay_finished)

    def _freeplay_finished(self, task: asyncio.Task[None]) -> None:
        self.freeplay_allows_motion = False
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and not self.closing:
            logger.error("freeplay_failed error_type=%s", type(error).__name__)
            self.message = "Freeplay stopped after a robot error. Controls are locked."
            self.emergency_stop(preserve_message=True)

    async def disable_freeplay(self) -> None:
        self.freeplay_allows_motion = False
        if self._freeplay_task is not None:
            self._freeplay_task.cancel()
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
            self._freeplay_task = None
        await self.backend.stop()

    def emergency_stop(self, *, preserve_message: bool = False) -> None:
        self._stop_epoch += 1
        self.latched = True  # Synchronous: blocks commands even before stop coroutine runs.
        self._cancel_commands()
        if not preserve_message:
            self.message = "Emergency stop active. All actions cancelled."
        self._schedule_stop()

    def stop_motion(self) -> None:
        self._cancel_commands()
        self._schedule_stop()

    def _schedule_stop(self) -> None:
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self._safe_stop())

    async def _safe_stop(self) -> None:
        try:
            async with asyncio.timeout(2):
                await self.backend.stop()
        except Exception as exc:
            self.latched = True
            self.message = "Stop could not be confirmed. Controls remain locked."
            logger.error("stop_failed error_type=%s", type(exc).__name__)

    async def resume(self) -> None:
        epoch = self._stop_epoch
        if self._stop_task is not None:
            await self._stop_task
        # Reconfirm STOP before unlocking; errors leave the latch in place.
        try:
            async with asyncio.timeout(2):
                await self.backend.stop()
        except Exception as exc:
            logger.error("resume_failed error_type=%s", type(exc).__name__)
            self.message = "Unable to confirm stop. Reconnect before resuming."
            return
        if epoch == self._stop_epoch and not self.closing:
            self.latched = False
            self.message = "Controls ready. Hold a direction to drive."

    async def drive(self, left: float, right: float) -> None:
        if self.latched or self.closing:
            return
        if self._stop_task is not None and not self._stop_task.done():
            return
        await self.backend.drive(
            bounded(left, -self.speed_limit, self.speed_limit),
            bounded(right, -self.speed_limit, self.speed_limit),
        )

    async def disconnect(self) -> None:
        self._cancel_commands()
        if self._freeplay_task is not None:
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
        if self._game_task is not None:
            await asyncio.gather(self._game_task, return_exceptions=True)
        await self.backend.disconnect()
        self.message = "Disconnected. No movement is active."

    async def change_backend(self, backend: RobotBackend) -> None:
        """Stop and retire the old backend before exposing a new one to widgets."""
        self._stop_epoch += 1
        epoch = self._stop_epoch
        self.latched = True
        self._cancel_commands()
        await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
        if self._freeplay_task is not None:
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
        if self._game_task is not None:
            await asyncio.gather(self._game_task, return_exceptions=True)
        if self._stop_task is not None:
            await self._stop_task
        await self.backend.disconnect()
        self.chat_turns.clear()
        self.chat_status = "Enter an installed Ollama model and type a message."
        self.backend = backend
        self.speed_limit = min(
            self.speed_limit, backend.speed_cap, 20 if not backend.is_simulation else 40
        )
        if epoch == self._stop_epoch and not self.closing:
            self.latched = False
        self.message = "Mode changed. Connect when ready; physical motors start locked."

    async def shutdown(self) -> None:
        self._stop_epoch += 1
        self.closing = True
        self.latched = True
        self._cancel_commands()
        await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
        if self._freeplay_task is not None:
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
        if self._game_task is not None:
            await asyncio.gather(self._game_task, return_exceptions=True)
        if self._stop_task is not None:
            await self._stop_task
        await self._safe_stop()
        try:
            async with asyncio.timeout(3):
                await self.backend.disconnect()
        except Exception as exc:
            logger.error("disconnect_failed error_type=%s", type(exc).__name__)
