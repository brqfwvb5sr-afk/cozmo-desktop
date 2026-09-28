"""A separate process owns the transport and expires missing GUI/motor commands.

IPC is an inherited local multiprocessing pipe, never a network listener.
"""

import logging
import math
import threading
import time
from dataclasses import replace
from multiprocessing.connection import Connection
from queue import Full, Queue
from typing import Any

from cozmo_desktop.robot.base import RobotError

from .safety import DRIVE_TIMEOUT, GUI_TIMEOUT, SafetyGuard
from .transport import PyCozmoTransport


def number(value: Any, low: float, high: float) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise RobotError("Invalid control value.")
    return max(low, min(high, float(value)))


class WorkerSession:
    def __init__(self, driver: Any, now: float) -> None:
        self.driver = driver
        self.guard = SafetyGuard(last_gui=now)
        self.generation = 0
        self.closing = False
        self.expression = "Neutral"
        self.surface = "unknown"

    def stop(self, *, lock: bool = False) -> None:
        self.driver.stop()
        self.guard.wheel_deadline = None
        if lock:
            self.guard.armed = False

    def tick(self, now: float) -> None:
        self.guard.last_state = self.driver.last_state
        self.guard.hazard = self.driver.hazard
        reason = self.guard.expired(now)
        if reason:
            self.guard.trip(reason)
            self.stop(lock=True)
            if "lost" in reason:
                self.closing = True

    def command(self, message: dict[str, Any], now: float) -> None:
        command = message.get("command")
        generation = message.get("generation", -1)
        if type(generation) is not int:
            raise RobotError("Invalid command generation.")
        if generation < self.generation:
            if command == "heartbeat":
                return  # An in-flight heartbeat may cross STOP; never rewind the epoch.
            raise RobotError("Cancelled command discarded.")
        self.generation = generation
        if command == "stop":
            self.stop()
            return
        if command == "disconnect":
            self.stop(lock=True)
            self.closing = True
            return
        deadline = message.get("expires", 0)
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or now > deadline:
            raise RobotError("Expired command discarded.")
        self.guard.last_gui = now
        if command == "heartbeat":
            return
        if command == "surface":
            surface = message.get("mode")
            if surface not in ("unknown", "table", "floor"):
                raise RobotError("Unknown play surface.")
            self.stop(lock=True)
            self.surface = surface
            self.guard.reason = (
                "Surface set to floor. Enable motors after checking the play area."
                if surface == "floor"
                else "Wheel control locked on an unverified or elevated surface."
            )
        elif command == "arm":
            if self.surface != "floor":
                raise RobotError("Wheel control requires the clear-floor surface setting.")
            self.guard.arm(now)
        elif command in {"drive", "head", "lift"}:
            self.guard.require_motion(now)
            if command == "drive":
                left = number(message.get("left"), -40, 40)
                right = number(message.get("right"), -40, 40)
                self.driver.drive(left, right)
                self.guard.wheel_deadline = now + DRIVE_TIMEOUT if left or right else None
            elif command == "head":
                self.driver.head(number(message.get("value"), -25, 44.5))
            else:
                self.driver.lift(number(message.get("value"), 0, 1))
        elif command == "face":
            pixels = message.get("pixels")
            if not isinstance(pixels, bytes) or len(pixels) != 8192:
                raise RobotError("Invalid face frame.")
            self.driver.face(pixels)
            self.expression = str(message.get("name", "Custom"))[:40]
        elif command == "audio":
            data = message.get("data")
            if not isinstance(data, bytes) or len(data) > 1_400_000:
                raise RobotError("Invalid speech audio.")
            self.driver.stop_motors()
            self.guard.wheel_deadline = None
            self.driver.audio(data)
        elif command == "cube":
            cube = message.get("number")
            if type(cube) is not int or cube not in (1, 2, 3):
                raise RobotError("Unknown cube.")
            self.driver.cube_lights(cube)
        elif command == "cube_color":
            cube, color = message.get("number"), message.get("color")
            if type(cube) is not int or cube not in (1, 2, 3):
                raise RobotError("Unknown cube.")
            if color not in ("off", "red", "green", "blue"):
                raise RobotError("Unknown cube light color.")
            self.driver.cube_lights(cube, color)
        else:
            raise RobotError("Unsupported robot command.")


def run_worker(pipe: Connection) -> None:
    logging.getLogger("pycozmo").addHandler(logging.NullHandler())
    outgoing: Queue[dict[str, Any]] = Queue(maxsize=8)

    def emit(value: dict[str, Any]) -> None:
        try:
            outgoing.put_nowait(value)
        except Full as exc:
            raise RobotError(
                "Desktop is not reading telemetry. Closing the robot connection."
            ) from exc

    def writer() -> None:
        try:
            while True:
                pipe.send(outgoing.get())
        except (EOFError, OSError):
            return

    threading.Thread(target=writer, daemon=True, name="cozmo-ipc-output").start()
    driver = None
    try:
        driver = PyCozmoTransport()
        driver.start()
        started = time.monotonic()
        session = WorkerSession(driver, started)
        published = camera_published = 0.0
        ready = False
        while not session.closing:
            now = time.monotonic()
            if pipe.poll(0.02):
                message = pipe.recv()
                request_id = message.get("id")
                try:
                    session.guard.last_state = driver.last_state
                    session.guard.hazard = driver.hazard
                    session.command(message, now)
                    if request_id is not None:
                        emit({"reply": request_id})
                except RobotError as exc:
                    session.guard.trip(str(exc))
                    session.stop(lock=True)
                    if request_id is not None:
                        emit({"reply": request_id, "error": str(exc)})
            if not ready:
                if driver.ready and driver.snapshot().connected and driver.last_state > started:
                    ready = True
                    session.guard.last_state = driver.last_state
                    emit({"ready": True})
                elif now - started > 8:
                    raise RobotError(
                        "No Cozmo telemetry. Join Cozmo Wi-Fi in Ubuntu and close the phone app."
                    )
                if now - session.guard.last_gui > GUI_TIMEOUT:
                    break
                continue
            session.tick(now)
            if session.closing:
                emit({"error": session.guard.reason})
                break
            if now - published >= 0.1:
                state = replace(
                    driver.snapshot(),
                    motors_enabled=session.guard.armed,
                    safety_status=session.guard.reason,
                    expression=session.expression,
                    surface_mode=session.surface,
                )
                emit({"state": state})
                published = now
            if now - camera_published >= 0.2:
                frame = driver.camera_jpeg()
                if frame:
                    emit({"camera": frame})
                camera_published = now
    except (EOFError, BrokenPipeError, OSError):
        pass  # Parent disappeared: finally stops motors and closes UDP.
    except Exception as exc:
        text = (
            str(exc)
            if isinstance(exc, RobotError)
            else (
                "Direct transport failed. Install .[direct] with Python 3.12 and check diagnostics."
            )
        )
        try:
            emit({"error": text})
        except (OSError, EOFError, RobotError):
            pass  # Receiving process already exited.
        logging.getLogger(__name__).error("worker_failed error_type=%s", type(exc).__name__)
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception as exc:
                logging.getLogger(__name__).error(
                    "worker_close_failed error_type=%s", type(exc).__name__
                )
        pipe.close()
