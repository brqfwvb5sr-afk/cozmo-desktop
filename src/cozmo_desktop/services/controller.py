"""One command owner for GUI, sequences and future AI providers."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

from cozmo_desktop.ai.conversation import ConversationService
from cozmo_desktop.ai.local_chat import ChatTurn
from cozmo_desktop.ai.providers.ollama import OllamaProvider
from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import RobotBackend, RobotError
from cozmo_desktop.robot.simulator import MAX_SPEED, bounded
from cozmo_desktop.services.games import GAME_NAMES, GameDirector, GameState
from cozmo_desktop.storage.settings import Settings

logger = logging.getLogger(__name__)


class RobotController:
    def __init__(
        self, backend: RobotBackend, speed_limit: float = 40, settings: Settings | None = None
    ) -> None:
        self.backend = backend
        self.settings = settings or Settings()
        self.conversation = ConversationService(OllamaProvider(self.settings.ollama_server))
        self.speed_limit = bounded(speed_limit, 10, min(MAX_SPEED, backend.speed_cap))
        self.latched = False
        self.message = "Choose a connection mode, then connect to Cozmo."
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stop_task: asyncio.Task[None] | None = None
        self.closing = False
        self._stop_epoch = 0
        self._freeplay_task: asyncio.Task[None] | None = None
        self._ambient_task: asyncio.Task[None] | None = None
        self.code_mode = False
        self._spontaneous_task: asyncio.Task[None] | None = None
        self.freeplay_allows_motion = False
        self._game_task: asyncio.Task[None] | None = None
        self._game_director: GameDirector | None = None
        self._resume_freeplay_after_chat: tuple[bool, bool] = (False, False)

        self.chat_turns: list[ChatTurn] = []

        self.chat_status = "Enter an installed Ollama model and type a message."
        from cozmo_desktop.code_lab.commands import ScratchCommands

        self.code_lab = ScratchCommands(self)

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
        if name != "camera" and self._ambient_task is not None:
            self._ambient_task.cancel()
        if name != "camera" and self.code_lab.active:
            self.code_lab.cancel()
            self._schedule_stop()
        if name not in ("camera", "chat") and self.chat_busy:
            self._resume_freeplay_after_chat = (False, False)
            self.stop_response()
        if name == "chat" and self._freeplay_task is not None and not self._freeplay_task.done():
            self._resume_freeplay_after_chat = (True, self.freeplay_allows_motion)
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
                if name != "camera" and self._ambient_task is not None:
                    await asyncio.gather(self._ambient_task, return_exceptions=True)
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
            if name == "chat":
                active, movement = self._resume_freeplay_after_chat
                self._resume_freeplay_after_chat = (False, False)
                if (
                    active
                    and not self.latched
                    and not self.closing
                    and self.backend.state.connected
                    and not any(
                        (
                            self.backend.state.cliff_detected,
                            self.backend.state.picked_up,
                            self.backend.state.falling,
                            self.backend.state.on_charger,
                        )
                    )
                ):
                    try:
                        await self.enable_freeplay(allow_movement=movement)
                    except RobotError:
                        self.message = (
                            "Conversation ended; Freeplay needs to be restarted manually."
                        )
            self.start_ambient()

    def start_ambient(self) -> None:
        """Keep eyes and sounds alive outside Freeplay without granting wheel motion."""
        from cozmo_desktop.services.personality import PersonalityDirector

        state = self.backend.state
        if (
            self.closing
            or self.latched
            or not state.connected
            or state.freeplay
            or self.code_mode
            or self.code_lab.active
            or self._tasks
            or (self._game_task is not None and not self._game_task.done())
            or (self._ambient_task is not None and not self._ambient_task.done())
        ):
            return
        director = PersonalityDirector(self.backend)
        self._ambient_task = asyncio.create_task(director.run(ambient=True))
        self._ambient_task.add_done_callback(self._ambient_finished)

    def _ambient_finished(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and not self.closing:
            logger.error("ambient_failed error_type=%s", type(error).__name__)
            self.message = "Cozmo's idle reactions paused. Robot controls remain available."

    async def stop_ambient(self) -> None:
        if self._ambient_task is not None:
            self._ambient_task.cancel()
            await asyncio.gather(self._ambient_task, return_exceptions=True)
            self._ambient_task = None

    async def wake_up(self) -> None:
        """Original eyes/sound wake sequence; a charger never grants wheel motion."""
        if not self.backend.state.connected:
            raise RobotError("Connect Cozmo first.")
        await self.stop_ambient()
        try:
            await self.backend.display_face(render_face("Sleepy"), "Sleepy")
            await self.backend.play_sound("sleepy")
            await asyncio.sleep(0.2)
            if not self.latched and self.backend.state.connected:
                await self.backend.display_face(render_face("Curious"), "Curious")
                await self.backend.play_sound("happy")
        except RobotError as exc:
            logger.warning("wake_effect_unavailable error_type=%s", type(exc).__name__)
        self.message = (
            "Cozmo is awake on the charger. Automatic undocking is not enabled."
            if self.backend.state.on_charger
            else "Cozmo is awake and looking around."
        )
        self.start_ambient()

    async def send_chat(self, text: str, model: str, *, spontaneous: bool = False) -> None:
        from cozmo_desktop.face.expressions import NAMES, render_face

        text = text.strip()
        if not 1 <= len(text) <= 400:
            self.chat_status = "Enter a message of 1–400 characters."
            return
        if not self.backend.state.connected:
            self.chat_status = "Connect to Cozmo first."
            return
        if self.latched or self.closing:
            self.chat_status = "Robot controls are stopped."
            return
        state = self.backend.state
        if state.cliff_detected or state.picked_up or state.falling or state.on_charger:
            self.chat_status = "Robot safety state takes priority over conversation."
            return
        if not self.settings.ai_enabled:
            self.chat_status = "Enable local AI in Settings first."
            return
        turn = ChatTurn("user", text)
        self.chat_status = "Thinking locally…"
        previous_expression = self.backend.state.expression
        if previous_expression not in NAMES:
            previous_expression = "Neutral"
        await self.backend.display_face(render_face("Curious"), "Curious")
        thinking_task = asyncio.create_task(self._animate_thinking())
        try:
            try:
                reply = await self.conversation.reply(
                    text,
                    model.strip(),
                    self.backend.state,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    remember=self.settings.memory_enabled and not spontaneous,
                )
            finally:
                thinking_task.cancel()
                await asyncio.gather(thinking_task, return_exceptions=True)
        except asyncio.CancelledError:
            self.chat_status = "Conversation stopped."
            raise
        except RobotError as exc:
            self.chat_status = str(exc)
            current = self.backend.state
            if current.connected and not any(
                (current.cliff_detected, current.picked_up, current.falling, current.on_charger)
            ):
                await self.backend.display_face(
                    render_face(previous_expression), previous_expression
                )
            return
        if self.latched or not self.backend.state.connected:
            self.chat_status = "Conversation stopped."
            return
        state = self.backend.state
        if state.cliff_detected or state.picked_up or state.falling or state.on_charger:
            self.chat_status = "Robot safety state takes priority over the AI reply."
            return
        expression = reply.expression or reply.emotion
        gaze = {"look_left": -5, "look_right": 5}.get(reply.action, 0)
        await self.backend.display_face(render_face(expression, gaze=gaze), expression)
        if reply.action in ("small_head_tilt", "look_up", "small_lift_move"):
            safe_pose = state.motors_enabled and state.surface_mode == "floor"
            if safe_pose and reply.action == "small_lift_move":
                await self.backend.set_lift_height(min(1, state.lift_height + 0.1))
            elif safe_pose:
                await self.backend.set_head_angle(min(44.5, state.head_angle + 5))
        if reply.sound:
            await self.backend.play_sound(reply.sound)
        if not spontaneous:
            self.chat_turns.append(turn)
        self.chat_turns.append(ChatTurn("assistant", reply.speech))
        del self.chat_turns[:-100]
        self.chat_status = "Reply ready."
        await self.backend.speak(reply.speech)

    def stop_response(self) -> None:
        task = self._tasks.get("chat")
        if task is not None and not task.done():
            task.cancel()
            self.chat_status = "Conversation stopped."

    def clear_chat_memory(self) -> None:
        self.conversation.memory.clear()
        self.chat_turns.clear()
        self.chat_status = "Conversation memory cleared."

    async def _animate_thinking(self) -> None:
        from cozmo_desktop.face.expressions import render_face

        gaze = -5
        while True:
            await asyncio.sleep(1.2)
            await self.backend.display_face(
                render_face("Curious", gaze=gaze, blink=True), "Curious"
            )
            await asyncio.sleep(0.12)
            await self.backend.display_face(render_face("Curious", gaze=gaze), "Curious")
            gaze = -gaze

    def _cancel_commands(self) -> None:
        self.code_lab.cancel()
        if self._ambient_task is not None and not self._ambient_task.done():
            self._ambient_task.cancel()
        current = asyncio.current_task()
        for task in tuple(self._tasks.values()):
            if task is not current:
                task.cancel()
        if self._freeplay_task is not None and not self._freeplay_task.done():
            self._freeplay_task.cancel()
        if self._spontaneous_task is not None and not self._spontaneous_task.done():
            self._spontaneous_task.cancel()
        if self._game_task is not None and not self._game_task.done():
            self._game_task.cancel()

    async def start_game(self, name: str) -> None:
        if name not in GAME_NAMES:
            raise RobotError("Unknown Power Cube game.")
        await self.stop_ambient()
        if self._game_task is not None and not self._game_task.done():
            await self.stop_game()
        if self._freeplay_task is not None and not self._freeplay_task.done():
            self._freeplay_task.cancel()
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
        await self.backend.stop()
        director = GameDirector(self.backend)
        director._check({"Quick Tap": 3, "Memory Match": 3, "Keepaway": 1}[name])
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
        else:
            self.start_ambient()

    async def stop_game(self) -> None:
        if self._game_task is not None:
            self._game_task.cancel()
            await asyncio.gather(self._game_task, return_exceptions=True)
            self._game_task = None
        await self.backend.stop()

    async def enable_freeplay(self, *, allow_movement: bool = False) -> None:
        from cozmo_desktop.services.personality import PersonalityDirector

        state = self.backend.state
        if allow_movement and (
            not state.motors_enabled
            or state.surface_mode != "floor"
            or state.cliff_detected
            or state.picked_up
            or state.falling
            or state.on_charger
        ):
            raise RobotError("Self-directed movement requires enabled motors on a clear floor.")
        await self.stop_ambient()
        await self.backend.enable_freeplay()
        self.freeplay_allows_motion = allow_movement
        director = PersonalityDirector(self.backend)
        self._freeplay_task = asyncio.create_task(director.run(allow_movement=allow_movement))
        self._freeplay_task.add_done_callback(self._freeplay_finished)
        if self.settings.spontaneous_ai and self.settings.ollama_model:
            self._spontaneous_task = asyncio.create_task(self._spontaneous_loop())

    async def _spontaneous_loop(self) -> None:
        """Occasional event-triggered speech; never runs without explicit setting."""
        last_event = (
            self.backend.state.cube_events[-1].ordinal if self.backend.state.cube_events else 0
        )
        last_call = time.monotonic()
        rng = random.Random()
        while self.backend.state.connected and self.backend.state.freeplay and not self.latched:
            await asyncio.sleep(0.5)
            events = self.backend.state.cube_events
            if not events or events[-1].ordinal <= last_event:
                continue
            event = events[-1]
            last_event = event.ordinal
            if self.chat_busy or time.monotonic() - last_call < 90 or rng.random() >= 0.25:
                continue
            if self.backend.state.cliff_detected or self.backend.state.picked_up:
                continue
            last_call = time.monotonic()
            event_text = "tapped" if event.kind == "tap" else "moved"
            prompt = f"Cube {event.number} was {event_text}. React in one short sentence."
            model = self.settings.ollama_model

            async def spontaneous_reply(message: str = prompt, chosen_model: str = model) -> None:
                await self.send_chat(message, chosen_model, spontaneous=True)

            self.submit("chat", spontaneous_reply)
            return

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
        if self._spontaneous_task is not None:
            self._spontaneous_task.cancel()
            await asyncio.gather(self._spontaneous_task, return_exceptions=True)
            self._spontaneous_task = None
        if self._freeplay_task is not None:
            self._freeplay_task.cancel()
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
            self._freeplay_task = None
        await self.backend.stop()
        self.start_ambient()

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
        if self._stop_task is not None:
            self._stop_task.add_done_callback(lambda _task: self.start_ambient())

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
            self.start_ambient()

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
        await self.stop_ambient()
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
        await self.stop_ambient()
        await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
        if self._freeplay_task is not None:
            await asyncio.gather(self._freeplay_task, return_exceptions=True)
        if self._game_task is not None:
            await asyncio.gather(self._game_task, return_exceptions=True)
        if self._stop_task is not None:
            await self._stop_task
        await self.backend.disconnect()
        self.chat_turns.clear()
        self.conversation.memory.clear()
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
        await self.stop_ambient()
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
