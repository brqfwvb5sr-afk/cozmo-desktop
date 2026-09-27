import argparse
import asyncio
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.services.diagnostics import configure_logging
from cozmo_desktop.storage.settings import Settings, config_directory
from cozmo_desktop.ui.window import MainWindow


async def smoke_test(window: MainWindow, destination: Path) -> None:
    """Exercise the real Qt/asyncio application lifecycle and capture original UI."""
    try:
        await window.wake()
        await window.controller.drive(40, 40)
        await asyncio.sleep(0.15)
        assert window.controller.backend.state.x > 0
        window.emergency_stop()
        await asyncio.sleep(0.1)
        assert window.controller.backend.state.left_speed == 0
        await window.controller.resume()
        await window.controller.backend.speak("Hello! This is my simulated world.")
        await asyncio.to_thread(destination.mkdir, parents=True, exist_ok=True)
        window.refresh()
        await asyncio.sleep(0.15)
        if not window.grab().save(str(destination / "home.png")):
            raise RuntimeError("Screenshot could not be saved")
        window.navigation.setCurrentRow(1)
        await asyncio.sleep(0.15)
        window.grab().save(str(destination / "control.png"))
        window.navigation.setCurrentRow(4)
        await asyncio.sleep(0.25)
        window.grab().save(str(destination / "camera.png"))
        print("Qt smoke test passed: connect, drive, stop, resume, speech, render, shutdown.")
    except Exception:
        logging.getLogger(__name__).exception("smoke_test_failed")
        window.setProperty("smoke_failed", True)
    finally:
        await window._shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cozmo Desktop — simulator-first community edition"
    )
    parser.add_argument(
        "--config-dir", type=Path, default=None, help="Override local settings directory"
    )
    parser.add_argument(
        "--smoke-test", type=Path, metavar="SCREENSHOT_DIR", help="Run UI smoke test and exit"
    )
    args = parser.parse_args()
    directory = args.config_dir or config_directory()
    startup_warning = ""
    try:
        configure_logging(directory / "logs")
    except OSError:
        startup_warning = "Log folder is unavailable. Check directory permissions."
    try:
        settings = Settings.load(directory / "settings.json")
    except (OSError, ValueError):
        settings = Settings()
        startup_warning = (
            "Settings could not be loaded. Safe defaults are active; original file preserved."
        )
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Cozmo Desktop")
    app.setOrganizationName("Cozmo Desktop Community")
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    controller = RobotController(SimulatorBackend(), settings.speed_limit)
    if startup_warning:
        controller.message = startup_warning
    window = MainWindow(controller, settings, directory)
    window.show()
    smoke_task = None
    with loop:
        if args.smoke_test:
            smoke_task = loop.create_task(smoke_test(window, args.smoke_test))
        loop.run_forever()
    if smoke_task is not None and not smoke_task.done():
        return 1
    return 1 if window.property("smoke_failed") else 0
