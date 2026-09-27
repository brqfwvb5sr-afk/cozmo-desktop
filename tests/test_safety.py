import asyncio

import pytest

from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController


@pytest.fixture
async def controller():
    result = RobotController(SimulatorBackend())
    await result.backend.connect()
    yield result
    await result.shutdown()


async def test_emergency_stop_cancels_and_latches(controller):
    await controller.drive(500, 500)
    assert controller.backend.state.left_speed == 40
    controller.submit("animation", lambda: controller.backend.play_animation("Hello, friend"))
    await asyncio.sleep(0)
    controller.emergency_stop()
    controller.submit("drive", lambda: controller.drive(40, 40))
    await asyncio.sleep(0.02)
    assert controller.latched
    assert controller.backend.state.animation is None
    assert controller.backend.state.left_speed == 0
    await controller.resume()
    await controller.drive(20, 20)
    assert controller.backend.state.left_speed == 20


async def test_command_failure_stops_and_redacts(controller, caplog):
    await controller.drive(20, 20)

    async def broken():
        raise RuntimeError("secret-key-do-not-log")

    controller.submit("provider", broken)
    await asyncio.sleep(0.02)
    assert controller.latched
    assert controller.backend.state.left_speed == 0
    assert "secret-key" not in controller.message + caplog.text
    assert "RuntimeError" in caplog.text


async def test_duplicate_actions_do_not_queue(controller):
    calls = 0
    finish = asyncio.Event()

    async def slow():
        nonlocal calls
        calls += 1
        await finish.wait()

    for _ in range(100):
        controller.submit("slow", slow)
    await asyncio.sleep(0)
    assert calls == 1
    finish.set()
    await asyncio.sleep(0)


async def test_stop_failure_remains_locked(controller, monkeypatch):
    async def fail():
        raise OSError("transport unavailable")

    monkeypatch.setattr(controller.backend, "stop", fail)
    controller.emergency_stop()
    await asyncio.sleep(0.02)
    await controller.resume()
    assert controller.latched
    assert "Unable to confirm" in controller.message


async def test_new_stop_wins_over_inflight_resume(controller, monkeypatch):
    original = controller.backend.stop
    gate = asyncio.Event()

    async def delayed_stop():
        await gate.wait()
        await original()

    controller.emergency_stop()
    await asyncio.sleep(0.01)
    monkeypatch.setattr(controller.backend, "stop", delayed_stop)
    resume = asyncio.create_task(controller.resume())
    await asyncio.sleep(0)
    controller.emergency_stop()
    gate.set()
    await resume
    assert controller.latched


async def test_disconnect_and_shutdown_cancel_pending_work(controller):
    controller.submit("animation", lambda: controller.backend.play_animation("Hello, friend"))
    await asyncio.sleep(0)
    await controller.disconnect()
    await asyncio.sleep(0)
    assert not controller.backend.state.connected
    assert controller.backend.state.animation is None
    await controller.shutdown()
    assert controller.closing and controller.latched
    assert not controller._tasks
