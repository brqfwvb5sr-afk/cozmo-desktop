"""Async desktop endpoint for the experimental physical robot worker."""

import asyncio
import importlib.util
import io
import math
import multiprocessing
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import replace
from pathlib import Path
from typing import Any

from PIL import Image

from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import (
    VOCALIZATIONS,
    Animation,
    NotConnectedError,
    RobotBackend,
    RobotError,
    RobotState,
)

from .worker import run_worker


def check_route() -> str:
    """Ask the OS for the route's source IP without sending a robot packet."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("172.31.1.1", 5551))
        address = str(sock.getsockname()[0])
    if not address.startswith("172.31.1."):
        raise RobotError(
            "Ubuntu is not on Cozmo Wi-Fi (expected 172.31.1.x). "
            "Attach the USB Wi-Fi adapter to the VM and join Cozmo_XXXXXX."
        )
    return address


def synthesize(text: str) -> bytes:
    binary = shutil.which("espeak-ng")
    if binary is None:
        raise RobotError("Speech needs eSpeak NG: sudo apt install espeak-ng")
    with tempfile.TemporaryDirectory(prefix="cozmo-speech-") as folder:
        path = Path(folder) / "speech.wav"
        # Fixed executable/arguments, text through stdin; never shell interpretation.
        subprocess.run(
            [binary, "-v", "de", "-s", "155", "-w", str(path), "--stdin"],
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=True,
        )
        data = path.read_bytes()
        if len(data) > 1_400_000:
            raise RobotError("Speech is limited to approximately 30 seconds. Use shorter text.")
        return data


def synthesize_vocalization(kind: str) -> bytes:
    """Generate short emotional robot tones; no sampled assets or eSpeak needed."""
    if kind not in VOCALIZATIONS:
        raise RobotError("Unknown robot vocalization.")
    import array

    rate = 22050
    durations = {"chirp": 0.32, "grumble": 0.42, "question": 0.45, "happy": 0.52, "sleepy": 0.6}
    count = int(rate * durations[kind])
    pcm = array.array("h")
    phase = 0.0
    for sample in range(count):
        progress = sample / count
        envelope = min(1.0, progress * 24, (1 - progress) * 24)
        if kind == "chirp":
            frequency = 550 + 430 * progress
        elif kind == "grumble":
            frequency = 185 + 35 * math.sin(2 * math.pi * progress * 7)
            envelope *= 0.6 + 0.3 * math.sin(2 * math.pi * progress * 11) ** 2
        elif kind == "question":
            frequency = 380 - 100 * progress + 480 * progress**3
        elif kind == "happy":
            syllable = (progress * 2) % 1
            frequency = (580 if progress < 0.5 else 720) + 330 * syllable
            envelope *= min(1.0, syllable * 25, (1 - syllable) * 25)
        else:
            frequency = 340 - 180 * progress + 8 * math.sin(2 * math.pi * progress * 3)
            envelope *= 0.7
        phase += 2 * math.pi * frequency / rate
        value = int(9000 * envelope * (math.sin(phase) + 0.2 * math.sin(2 * phase)))
        pcm.append(value)
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm.tobytes())
    return output.getvalue()


class DirectBackend(RobotBackend):
    is_simulation = False
    speed_cap = 40

    def __init__(self) -> None:
        self._state = RobotState(battery=None, backend_name="direct", motors_enabled=False)
        self._pipe: Any = None  # Windows PipeConnection / POSIX Connection, same duplex API.
        self._process: Any = None
        self._listener: asyncio.Task[None] | None = None
        self._heartbeat: asyncio.Task[None] | None = None
        self._idle: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[None]] = {}
        self._ready: asyncio.Future[None] | None = None
        self._send_lock = threading.Lock()
        self._sequence = 0
        self._generation = 0
        self._camera: bytes | None = None
        self._last_packet = 0.0
        self._closing = False
        self._failed = False
        self._state_received = asyncio.Event()
        self._connect_lock = asyncio.Lock()

    @property
    def state(self) -> RobotState:
        return self._state

    @property
    def animations(self) -> tuple[Animation, ...]:
        return (
            Animation("Friendly eyes", "Greeting", 1.2),
            Animation("Happy eyes", "Happy", 1.5),
            Animation("Curious eyes", "Idle", 1.0),
            Animation("Sleepy eyes", "Sleep", 1.3),
        )

    async def connect(self) -> None:
        async with self._connect_lock:
            await self._connect()

    async def _connect(self) -> None:
        if self._state.connected:
            return
        if importlib.util.find_spec("pycozmo") is None:
            raise RobotError('Install the robot extra first: python -m pip install -e ".[direct]"')
        await asyncio.to_thread(check_route)
        await self.disconnect()
        self._closing = False
        self._failed = False
        self._state_received.clear()
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        self._pipe = parent
        self._ready = asyncio.get_running_loop().create_future()
        self._process = context.Process(target=run_worker, args=(child,), daemon=True)
        self._process.start()
        child.close()
        self._last_packet = time.monotonic()
        self._listener = asyncio.create_task(self._listen())
        self._heartbeat = asyncio.create_task(self._keepalive())
        try:
            async with asyncio.timeout(11):
                await self._ready
                # Connected requires a real, fresh RobotState, not just a UDP socket.
                await self._state_received.wait()
        except BaseException:
            await self.disconnect()
            raise

    def _write(self, payload: dict[str, Any]) -> None:
        with self._send_lock:
            if self._pipe is None:
                raise NotConnectedError()
            self._pipe.send(payload)

    async def _send(self, command: str, **values: Any) -> None:
        if self._pipe is None:
            raise NotConnectedError()
        self._sequence += 1
        request = self._sequence
        future = asyncio.get_running_loop().create_future()
        self._pending[request] = future
        lifetime = 2.0 if command == "heartbeat" else 0.35
        payload = {
            "command": command,
            "generation": self._generation,
            "expires": time.monotonic() + lifetime,
            "id": request,
            **values,
        }
        try:
            async with asyncio.timeout(2):
                await asyncio.to_thread(self._write, payload)
                await future
        except (OSError, EOFError, TimeoutError) as exc:
            self._fail("Robot worker is not responding. Reconnect to Cozmo.")
            raise RobotError("Robot worker is not responding. Reconnect to Cozmo.") from exc
        finally:
            self._pending.pop(request, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Retrieve failure even if pipe.write timed out before awaiting.

    def _read(self) -> dict[str, Any] | None:
        pipe = self._pipe
        if pipe is not None and pipe.poll(0.05):
            result: dict[str, Any] = pipe.recv()
            return result
        return None

    def _fail(self, reason: str) -> None:
        self._failed = True
        self._state = replace(
            self._state,
            connected=False,
            camera_available=False,
            motors_enabled=False,
            safety_status=reason,
            animation=None,
            freeplay=False,
        )
        self._camera = None
        for future in (*self._pending.values(), self._ready):
            if future is not None and not future.done():
                future.set_exception(RobotError(reason))

    async def _listen(self) -> None:
        try:
            while not self._closing:
                message = await asyncio.to_thread(self._read)
                if message is None:
                    if self._process is not None and not self._process.is_alive():
                        self._fail("Robot worker exited. Reconnect to Cozmo.")
                        return
                    continue
                self._last_packet = time.monotonic()
                if "reply" in message:
                    future = self._pending.get(message["reply"])
                    if future is not None and not future.done():
                        if "error" in message:
                            future.set_exception(RobotError(message["error"]))
                        else:
                            future.set_result(None)
                elif "error" in message:
                    self._fail(message["error"])
                    return
                elif "ready" in message:
                    if self._ready is not None and not self._ready.done():
                        self._ready.set_result(None)
                elif "state" in message and not self._failed:
                    self._state = replace(
                        message["state"],
                        speech=self._state.speech,
                        animation=self._state.animation,
                        freeplay=self._state.freeplay,
                    )
                    self._state_received.set()
                elif "camera" in message and not self._failed:
                    self._camera = message["camera"]
        except (EOFError, OSError):
            if not self._closing:
                self._fail("Connection to the robot worker was lost.")

    async def _keepalive(self) -> None:
        try:
            while not self._closing and not self._failed:
                await self._send("heartbeat")
                # Do not keep a physical session alive if telemetry publication stalls.
                if self._state.connected and time.monotonic() - self._last_packet > 1:
                    self._fail("Robot telemetry stalled. Reconnect to Cozmo.")
                    return
                await asyncio.sleep(0.15)
        except (RobotError, OSError):
            if not self._closing:
                self._fail("Robot connection lost. Reconnect to Cozmo.")

    async def disconnect(self) -> None:
        self._closing = True
        await self.disable_freeplay()
        for task in (self._heartbeat, self._listener):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(t for t in (self._heartbeat, self._listener) if t), return_exceptions=True
        )
        self._heartbeat = self._listener = None
        if self._pipe is not None:
            try:
                # Closing the pipe also triggers EOF-based motor stop in the worker.
                self._generation += 1
                await asyncio.wait_for(
                    asyncio.to_thread(
                        self._write,
                        {
                            "command": "disconnect",
                            "generation": self._generation,
                        },
                    ),
                    timeout=0.5,
                )
            except (OSError, RobotError, TimeoutError):
                pass  # Worker may already have shut down after a transport fault.
            self._pipe.close()
            self._pipe = None
        if self._process is not None:
            await asyncio.to_thread(self._process.join, 3)
            if self._process.is_alive():
                self._process.terminate()
                await asyncio.to_thread(self._process.join, 1)
            self._process.close()
            self._process = None
        self._fail("Disconnected. Motor control is locked.")
        self._pending.clear()
        self._ready = None

    def _require(self) -> None:
        if not self._state.connected:
            raise NotConnectedError()

    async def arm_motors(self) -> None:
        self._require()
        await self._send("arm")

    async def set_surface(self, mode: str) -> None:
        self._require()
        if mode not in ("unknown", "table", "floor"):
            raise RobotError("Unknown play surface.")
        await self._send("surface", mode=mode)

    async def drive(self, left: float, right: float) -> None:
        self._require()
        await self._send("drive", left=left, right=right)

    async def stop(self) -> None:
        self._generation += 1
        await self.disable_freeplay()
        self._state = replace(self._state, animation=None)
        if self._pipe is not None and not self._closing:
            await self._send("stop")

    async def set_head_angle(self, angle: float) -> None:
        self._require()
        await self._send("head", value=angle)

    async def set_lift_height(self, height: float) -> None:
        self._require()
        await self._send("lift", value=height)

    async def display_face(self, frame: Image.Image, name: str = "Custom") -> None:
        self._require()
        if frame.size != (128, 64):
            raise RobotError("Face frames must be 128 by 64 pixels.")
        await self._send("face", pixels=frame.convert("L").tobytes(), name=name)

    async def speak(self, text: str) -> None:
        self._require()
        if not text.strip() or len(text) > 500:
            raise RobotError("Enter between 1 and 500 characters.")
        audio = await asyncio.to_thread(synthesize, text)
        self._require()
        await self._send("audio", data=audio)
        self._state = replace(self._state, speech=text.strip())

    async def play_sound(self, kind: str) -> None:
        self._require()
        data = await asyncio.to_thread(synthesize_vocalization, kind)
        self._require()
        await self._send("audio", data=data)

    async def get_camera_frame(self) -> Image.Image:
        self._require()
        if not self._state.camera_available or self._camera is None:
            raise RobotError("Waiting for Cozmo camera frames.")
        return Image.open(io.BytesIO(self._camera)).convert("RGB")

    async def play_animation(self, animation: str) -> None:
        self._require()
        match = next((item for item in self.animations if item.name == animation), None)
        if match is None:
            raise RobotError("Animation unavailable. Direct mode uses original eye animations.")
        faces = {
            "Greeting": ("Neutral", "Happy"),
            "Happy": ("Happy", "Excited"),
            "Idle": ("Neutral", "Curious"),
            "Sleep": ("Neutral", "Sleepy"),
        }
        self._state = replace(self._state, animation=animation)
        try:
            for name in faces[match.category]:
                await self.display_face(render_face(name), name)
                await asyncio.sleep(match.duration / 2)
        finally:
            self._state = replace(self._state, animation=None)

    async def enable_freeplay(self) -> None:
        self._require()
        await self.stop()
        self._state = replace(self._state, freeplay=True)

    async def disable_freeplay(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
            await asyncio.gather(self._idle, return_exceptions=True)
            self._idle = None
        self._state = replace(self._state, freeplay=False)

    async def cube_lights(self, number: int) -> None:
        self._require()
        await self._send("cube", number=number)

    async def set_cube_color(self, number: int, color: str) -> None:
        self._require()
        if color not in ("off", "red", "green", "blue"):
            raise RobotError("Unknown cube light color.")
        await self._send("cube_color", number=number, color=color)
