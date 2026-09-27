"""Run the production worker loop and spawn/pipe lifecycle against a fake transport."""

import asyncio
import time
from dataclasses import replace

import pytest

from cozmo_desktop.robot.base import RobotState
from cozmo_desktop.robot.direct import backend as endpoint
from cozmo_desktop.robot.direct.backend import DirectBackend


class FakeTransport:
    ready = True
    hazard = False

    def __init__(self):
        self.state = RobotState(connected=True, battery=None, backend_name="direct")

    @property
    def last_state(self):
        return time.monotonic()

    def start(self):
        pass

    def stop(self):
        self.state = replace(self.state, left_speed=0, right_speed=0)

    def close(self):
        self.stop()

    def snapshot(self):
        return self.state

    def camera_jpeg(self):
        return None

    def drive(self, left, right):
        self.state = replace(self.state, left_speed=left, right_speed=right)


def fake_worker(pipe):
    from cozmo_desktop.robot.direct import worker

    worker.PyCozmoTransport = FakeTransport
    worker.run_worker(pipe)


class LargeCameraTransport(FakeTransport):
    def camera_jpeg(self):
        return b"x" * 1_000_000


def large_camera_worker(pipe):
    from cozmo_desktop.robot.direct import worker

    worker.PyCozmoTransport = LargeCameraTransport
    worker.run_worker(pipe)


@pytest.fixture
async def backend(monkeypatch):
    monkeypatch.setattr(endpoint, "run_worker", fake_worker)
    monkeypatch.setattr(endpoint, "check_route", lambda: "172.31.1.2")
    monkeypatch.setattr(endpoint.importlib.util, "find_spec", lambda _: True)
    backend = DirectBackend()
    yield backend
    await backend.disconnect()


async def until(predicate):
    async with asyncio.timeout(4):
        while not predicate():  # noqa: ASYNC110 - observe another process, no local event
            await asyncio.sleep(0.02)


async def test_spawn_connect_drive_expiry_and_reconnect(backend):
    # Connect and Home/Wake can be clicked close together; share one session.
    await asyncio.gather(backend.connect(), backend.connect())
    assert backend.state.connected and not backend.state.motors_enabled
    assert backend.state.battery is None
    await backend.arm_motors()
    await backend.drive(200, -200)
    await until(lambda: backend.state.left_speed == 40)
    assert backend.state.right_speed == -40
    await until(lambda: not backend.state.motors_enabled)
    assert backend.state.left_speed == 0
    assert "expired" in backend.state.safety_status
    await backend.disconnect()
    assert backend._process is None and not backend.state.connected
    await backend.connect()
    assert backend.state.connected and not backend.state.motors_enabled


async def test_missing_gui_heartbeat_shuts_down_worker(backend):
    await backend.connect()
    await backend.arm_motors()
    backend._heartbeat.cancel()
    await asyncio.gather(backend._heartbeat, return_exceptions=True)
    await until(lambda: not backend._process.is_alive())
    await until(lambda: not backend.state.connected)
    assert not backend.state.motors_enabled


async def test_worker_process_crash_marks_session_disconnected(backend):
    await backend.connect()
    backend._process.terminate()
    await until(lambda: not backend.state.connected)
    assert not backend.state.motors_enabled


async def test_pipe_eof_stops_worker(backend):
    await backend.connect()
    backend._heartbeat.cancel()
    backend._listener.cancel()
    await asyncio.gather(backend._heartbeat, backend._listener, return_exceptions=True)
    backend._pipe.close()
    backend._pipe = None
    await until(lambda: not backend._process.is_alive())


async def test_full_output_pipe_does_not_block_worker_watchdog(backend, monkeypatch):
    monkeypatch.setattr(endpoint, "run_worker", large_camera_worker)
    await backend.connect()
    backend._listener.cancel()
    backend._heartbeat.cancel()
    await asyncio.gather(backend._listener, backend._heartbeat, return_exceptions=True)
    # Keep the input alive, but do not read any replies/camera bytes.
    async with asyncio.timeout(4):
        while backend._process.is_alive():
            try:
                backend._pipe.send(
                    {
                        "command": "heartbeat",
                        "generation": backend._generation,
                        "expires": time.monotonic() + 1,
                    }
                )
            except (EOFError, OSError):
                break
            await asyncio.sleep(0.1)
        await until(lambda: not backend._process.is_alive())
