import asyncio

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.storage.settings import Settings
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
