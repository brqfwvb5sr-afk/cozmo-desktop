"""One command owner for GUI, sequences and future AI providers."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cozmo_desktop.robot.base import RobotBackend, RobotError
from cozmo_desktop.robot.simulator import MAX_SPEED, bounded

logger = logging.getLogger(__name__)


class RobotController:
    def __init__(self, backend: RobotBackend, speed_limit: float = 40) -> None:
        self.backend = backend
        self.speed_limit = bounded(speed_limit, 10, MAX_SPEED)
        self.latched = False
        self.message = "Connect to meet your simulated Cozmo."
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stop_task: asyncio.Task[None] | None = None
        self.closing = False
        self._stop_epoch = 0

    def submit(self, name: str, operation: Callable[[], Awaitable[None]]) -> None:
        """Drop repeated in-flight requests; never build up a hardware command queue."""
        if self.closing or self.latched:
            if self.latched:
                self.message = "Emergency stop is active. Select Resume controls to continue."
            return
        if name in self._tasks and not self._tasks[name].done():
            return
        self._tasks[name] = asyncio.create_task(self._execute(name, operation))

    async def _execute(self, name: str, operation: Callable[[], Awaitable[None]]) -> None:
        try:
            async with asyncio.timeout(15):
                if self._stop_task is not None and not self._stop_task.done():
                    await asyncio.shield(self._stop_task)
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

    def _cancel_commands(self) -> None:
        current = asyncio.current_task()
        for task in tuple(self._tasks.values()):
            if task is not current:
                task.cancel()

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
        await self.backend.disconnect()
        self.message = "Disconnected. No movement is active."

    async def shutdown(self) -> None:
        self._stop_epoch += 1
        self.closing = True
        self.latched = True
        self._cancel_commands()
        await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
        if self._stop_task is not None:
            await self._stop_task
        await self._safe_stop()
        try:
            async with asyncio.timeout(3):
                await self.backend.disconnect()
        except Exception as exc:
            logger.error("disconnect_failed error_type=%s", type(exc).__name__)
