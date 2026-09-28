import asyncio
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cozmo_desktop.ai.actions import AIResponse
from cozmo_desktop.robot.base import RobotError
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.storage.settings import Settings
from cozmo_desktop.ui import window as window_module
from cozmo_desktop.ui.window import MainWindow


@pytest.fixture
async def window(qapp, tmp_path):
    controller = RobotController(SimulatorBackend())
    settings = Settings(snapshots_directory=str(tmp_path / "pictures"))
    window = MainWindow(controller, settings, tmp_path)
    # This fixture owns async shutdown. pytest-qt's automatic widget close runs
    # outside asyncio; refresh is driven explicitly in these deterministic tests.
    window.timer.stop()
    window.show()
    QApplication.processEvents()
    await asyncio.sleep(0.01)
    yield window
    await window._shutdown()


async def connect_control(window):
    window.connect_button.click()
    await asyncio.sleep(0.02)
    window.navigation.setCurrentRow(1)
    await asyncio.sleep(0.02)
    window.refresh()
    window.control.setFocus()
    QApplication.processEvents()


async def test_code_lab_browser_fallback_keeps_desktop_alive(window, monkeypatch):
    opened = []
    monkeypatch.setattr(window_module, "embed_code_lab", lambda: False)
    monkeypatch.setattr(window_module, "open_code_url", lambda url: opened.append(url) or True)
    window.navigation.setCurrentRow(10)
    await asyncio.sleep(0.1)
    assert window.code_server is not None
    assert window.code_view is None
    assert window.code_open_button.isVisible()
    assert len(opened) == 1 and opened[0].toString().startswith("http://127.0.0.1:")
    window.stop_button.click()
    await asyncio.sleep(0.01)
    assert window.controller.latched


async def test_buttons_drive_release_posture_speech(window):
    await connect_control(window)
    button = window.control.direction_buttons["w"]
    button.pressed.emit()
    window.refresh()
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.left_speed == 40
    button.released.emit()
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.left_speed == 0
    window.control.head.setValue(25)
    window.control.lift.setValue(60)
    window.control.speech.setText("Hello from Qt")
    window.control.speak.click()
    await asyncio.sleep(0.01)
    state = window.controller.backend.state
    assert state.head_angle == 25 and state.lift_height == 0.6
    assert state.speech == "Hello from Qt"


async def test_keyboard_focus_loss_and_page_change_stop(window):
    await connect_control(window)
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier)
    assert window.eventFilter(window, press)
    window.refresh()
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.left_speed > 0
    window.eventFilter(window, QEvent(QEvent.Type.WindowDeactivate))
    await asyncio.sleep(0.01)
    assert not window.keys and window.controller.backend.state.left_speed == 0
    window.eventFilter(window, press)
    window.refresh()
    await asyncio.sleep(0.01)
    window.navigation.setCurrentRow(0)
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.left_speed == 0


async def test_real_qt_keyboard_events_and_release(window):
    await connect_control(window)
    QTest.keyPress(window.control, Qt.Key.Key_W)
    window.refresh()
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.left_speed == 40
    QTest.keyRelease(window.control, Qt.Key.Key_W)
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.left_speed == 0
    QTest.keyClick(window.control, Qt.Key.Key_Up)
    QTest.keyClick(window.control, Qt.Key.Key_R)
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.head_angle == 5
    assert window.controller.backend.state.lift_height == 0.1
    QTest.keyClick(window.control, Qt.Key.Key_Space)
    await asyncio.sleep(0.01)
    assert window.controller.latched


async def test_typing_focus_clears_held_keys(window):
    await connect_control(window)
    window.keys.add("w")
    window.refresh()
    await asyncio.sleep(0.01)
    window.eventFilter(window.control.speech, QEvent(QEvent.Type.FocusIn))
    await asyncio.sleep(0.01)
    assert not window.keys and window.controller.backend.state.left_speed == 0


async def test_stop_button_cancels_and_requires_resume(window):
    await connect_control(window)
    window.keys.add("w")
    window.refresh()
    await asyncio.sleep(0.01)
    window.stop_button.click()
    await asyncio.sleep(0.01)
    window.refresh()
    assert window.controller.latched and not window.keys
    assert window.resume_button.isVisible()
    window.resume_button.click()
    await asyncio.sleep(0.02)
    assert not window.controller.latched
    assert window.controller.backend.state.left_speed == 0


async def test_expression_animation_camera_snapshot_and_settings(window):
    await connect_control(window)
    window.navigation.setCurrentRow(2)
    await asyncio.sleep(0.01)
    window.expression_buttons["Surprised"].click()
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.expression == "Surprised"
    window.navigation.setCurrentRow(3)
    await asyncio.sleep(0.01)
    window.animations.search.setText("Greeting")
    assert window.animations.list.count() == 1
    window.animations.play()
    await asyncio.sleep(0.01)
    assert window.controller.backend.state.animation == "Hello, friend"
    window.animations.add()
    window.animations.save()
    window.animations.clear()
    window.animations.load()
    assert window.animations.items == ["Hello, friend"]
    window.navigation.setCurrentRow(4)
    await asyncio.sleep(0.01)
    await window.update_camera()
    window.snapshot()
    from pathlib import Path

    snapshots = await asyncio.to_thread(
        lambda: list(Path(window.settings.snapshots_directory).glob("*.png"))
    )
    assert len(snapshots) == 1
    window.save_settings()
    assert Settings.load(window.directory / "settings.json").speed_limit == 40


async def test_switch_to_direct_shows_real_mode_and_locks_motor_controls(window):
    await connect_control(window)
    old = window.controller.backend
    window.backend_choice.setCurrentIndex(1)
    await window._mode_task
    window.refresh()
    assert not old.state.connected
    assert not window.controller.backend.is_simulation
    assert "REAL COZMO" in window.banner.text()
    assert window.battery.text() == "Unknown"
    assert window.controller.speed_limit == 20
    assert window.control.limit.maximum() == 40
    assert not window.control.head.isEnabled()
    backend = window.controller.backend
    backend._state = replace(backend.state, connected=True, battery_voltage=3.92)
    window.refresh()
    assert window.battery.text() == "3.92 V"
    assert window.control.speak.isEnabled() and not window.control.head.isEnabled()
    assert not window.arm_button.isEnabled()
    backend._state = replace(backend.state, surface_mode="floor")
    window.refresh()
    assert window.arm_button.isEnabled()
    QTest.keyPress(window.control, Qt.Key.Key_W)
    assert not window.keys


async def test_unavailable_physical_camera_does_not_latch_or_save_stale_snapshot(window):
    window.backend_choice.setCurrentIndex(1)
    await window._mode_task
    backend = window.controller.backend
    backend._state = replace(backend.state, connected=True)
    backend.get_camera_frame = AsyncMock(side_effect=RobotError("Waiting for Cozmo camera frames."))
    await window.update_camera()
    assert not window.controller.latched
    assert "Waiting" in window.camera.text()
    window.refresh()
    assert window._last_frame is None


async def test_reconnect_button_recovers_after_failed_physical_connection(window):
    window.backend_choice.setCurrentIndex(1)
    await window._mode_task
    window.refresh()
    backend = window.controller.backend
    backend.connect = AsyncMock(side_effect=RobotError("No Cozmo Wi-Fi"))
    window.connect_button.click()
    await window._connection_task
    await asyncio.sleep(0)
    window.refresh()
    assert window.controller.latched and window.connect_button.isEnabled()

    async def connect():
        backend._state = replace(backend.state, connected=True)

    backend.connect = connect
    window.connect_button.click()
    await window._connection_task
    assert backend.state.connected and not window.controller.latched
    assert not backend.state.motors_enabled


async def test_games_page_starts_and_stop_cleans_cube_lights(window):
    window.connect_button.click()
    await asyncio.sleep(0.02)
    window.navigation.setCurrentRow(8)
    await asyncio.sleep(0.02)
    window.refresh()
    assert window.game_start.isEnabled()
    window.game_choice.setCurrentText("Keepaway")
    window.game_start.click()
    await asyncio.sleep(0.05)
    window.refresh()
    assert window.controller.game_state.phase == "watch"
    assert window.controller.backend.state.cubes[0].light_color == "green"
    window.game_stop.click()
    await asyncio.sleep(0.05)
    window.refresh()
    assert window.controller.game_state.phase == "cancelled"
    assert window.controller.backend.state.cubes[0].light_color == "off"
    assert not window.controller.latched


async def test_conversation_page_sends_local_reply_and_speaks(window, monkeypatch):
    await connect_control(window)
    reply = AsyncMock(return_value=AIResponse("Hallo!", "Happy", "none"))
    monkeypatch.setattr(window.controller.conversation, "reply", reply)
    window.navigation.setCurrentRow(9)
    await asyncio.sleep(0.01)
    window.chat_model.addItem("small:1b")
    window.chat_input.setText("Guten Tag")
    window.chat_send.click()
    await window.controller._tasks["chat"]
    window.refresh()
    assert window.chat_transcript.count() == 2
    assert window.chat_transcript.item(1).text() == "Cozmo: Hallo!"
    assert window.controller.backend.state.speech == "Hallo!"
    assert window.controller.backend.state.expression == "Happy"


async def test_microphone_click_transcribes_into_same_local_chat_path(window, monkeypatch):
    await connect_control(window)
    window.settings.stt_model_de = "/models/de"
    window.chat_model.addItem("gemma3:1b")
    start = AsyncMock()
    stop = AsyncMock(return_value="Hallo Cozmo")
    monkeypatch.setattr(window.recognizer, "start", start)
    monkeypatch.setattr(window.recognizer, "stop", stop)
    monkeypatch.setattr(
        window.controller.conversation,
        "reply",
        AsyncMock(return_value=AIResponse("Hallo!", "Happy", "none")),
    )
    window.navigation.setCurrentRow(9)
    window.microphone.click()
    await window._microphone_task
    assert window.listening
    window.microphone.click()
    await window._microphone_task
    assert not window.listening
    assert window.controller.chat_busy
    await window.controller._tasks["chat"]
    assert window.controller.backend.state.speech == "Hallo!"
    start.assert_awaited_once()
    stop.assert_awaited_once()


async def test_stationary_cliff_trace_ui_labels_and_exports(window, monkeypatch, tmp_path):
    window.backend_choice.setCurrentIndex(1)
    await window._mode_task
    backend = window.controller.backend
    backend._state = replace(backend.state, connected=True, cliff_raw=(10, 20, 30, 40))
    window.refresh()
    assert window.trace_toggle.isEnabled()
    window.trace_toggle.click()
    window.refresh()
    window.trace_position.setCurrentText("front edge")
    backend._state = replace(backend.state, cliff_raw=(100, 20, 30, 40))
    window.refresh()
    path = tmp_path / "trace.json"
    monkeypatch.setattr(
        "cozmo_desktop.ui.window.QFileDialog.getSaveFileName",
        lambda *_args: (str(path), "JSON"),
    )
    window.trace_export.click()
    data = json.loads(path.read_text())
    assert data["sample_count"] == 2
    assert data["samples"][-1]["label"] == "front edge"
    assert data["samples"][-1]["raw"] == [100, 20, 30, 40]
    assert not window.cliff_trace.active
