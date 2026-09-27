import asyncio
from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cozmo_desktop.face.expressions import NAMES, Expression, apply_expression, render_face
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.services.diagnostics import export_report
from cozmo_desktop.storage.settings import Settings

from .animations import AnimationsPage
from .control import ControlPage
from .theme import STYLE
from .widgets import RobotPreview, card, label, pixmap

PAGES = ("Home", "Control", "Expressions", "Animations", "Camera", "Connection", "Settings")
KEYS: dict[int, str] = {Qt.Key.Key_W: "w", Qt.Key.Key_A: "a", Qt.Key.Key_S: "s", Qt.Key.Key_D: "d"}


class MainWindow(QMainWindow):
    def __init__(self, controller: RobotController, settings: Settings, directory: Path) -> None:
        super().__init__()
        self.controller, self.settings, self.directory = controller, settings, directory
        self.keys: set[str] = set()
        self._closed = False
        self._closing_task: asyncio.Task[None] | None = None
        self._resume_task: asyncio.Task[None] | None = None
        self._last_frame: Image.Image | None = None
        self.setWindowTitle("Cozmo Desktop · Simulation Mode")
        self.resize(1220, 840)
        self.setMinimumSize(1000, 760)
        self.setStyleSheet(STYLE)
        shell = QWidget()
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(215)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 30, 18, 24)
        side.addWidget(label("cozmo", "heroTitle"))
        side.addWidget(label("D E S K T O P", "eyebrow"))
        side.addSpacing(34)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setAccessibleName("Main navigation")
        self.navigation.addItems(PAGES)
        side.addWidget(self.navigation, 1)
        side.addWidget(label("SIMULATION MODE", "eyebrow"))
        side.addWidget(label("A safe place to explore.\nNo robot required.", "muted", True))
        side.addSpacing(20)
        side.addWidget(label("Community edition · 0.1.0", "muted"))
        root.addWidget(sidebar)
        main = QVBoxLayout()
        main.setContentsMargins(30, 24, 30, 18)
        main.setSpacing(18)
        header = QHBoxLayout()
        self.page_title = label("Home", "title")
        header.addWidget(self.page_title)
        header.addStretch()
        self.connection_status = label("○  Disconnected", "muted")
        header.addWidget(self.connection_status)
        self.connect_button = QPushButton("Connect simulator")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self.toggle_connection)
        header.addWidget(self.connect_button)
        self.resume_button = QPushButton("Resume controls")
        self.resume_button.clicked.connect(self.resume)
        self.resume_button.hide()
        header.addWidget(self.resume_button)
        self.stop_button = QPushButton("■  STOP")
        self.stop_button.setObjectName("stop")
        self.stop_button.setAccessibleName("Emergency stop")
        self.stop_button.clicked.connect(self.emergency_stop)
        header.addWidget(self.stop_button)
        main.addLayout(header)
        main.addWidget(
            label(
                "SIMULATION MODE   /   Every reading and robot action below is synthetic.",
                "notice",
                True,
            )
        )
        self.stack = QStackedWidget()
        self.control = ControlPage(controller, self.release_controls)
        self.animations = AnimationsPage(controller, settings, directory)
        for page in (
            self.home_page(),
            self.control,
            self.expressions_page(),
            self.animations,
            self.camera_page(),
            self.connection_page(),
            self.settings_page(),
        ):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        main.addWidget(self.stack, 1)
        self.feedback = label(controller.message, "muted", True)
        self.feedback.setMinimumHeight(38)
        main.addWidget(self.feedback)
        root.addLayout(main, 1)
        self.navigation.currentRowChanged.connect(self.navigate)
        self.navigation.setCurrentRow(0)
        application = QApplication.instance()
        assert isinstance(application, QApplication)
        application.installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)

    def home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        hero = QHBoxLayout()
        copy = QVBoxLayout()
        copy.addStretch()
        copy.addWidget(label("YOUR LITTLE COMPANION", "eyebrow"))
        copy.addWidget(label("A little curiosity.\nA lot of character.", "heroTitle"))
        copy.addWidget(
            label(
                "Get to know Cozmo in a world built for play.\n"
                "Start with a hello, then take the controls.",
                "muted",
                True,
            )
        )
        copy.addSpacing(14)
        actions = QHBoxLayout()
        wake = QPushButton("Wake Cozmo")
        wake.setObjectName("primary")
        wake.clicked.connect(lambda: self.controller.submit("wake", self.wake))
        actions.addWidget(wake)
        drive = QPushButton("Take the controls  →")
        drive.clicked.connect(lambda: self.navigation.setCurrentRow(1))
        actions.addWidget(drive)
        copy.addLayout(actions)
        copy.addStretch()
        hero.addLayout(copy, 5)
        self.preview = RobotPreview()
        hero.addWidget(self.preview, 5)
        layout.addLayout(hero)
        metrics = QHBoxLayout()
        battery, self.battery = card("Battery", "87%")
        mood, self.mood = card("Current expression", "Neutral")
        cubes, self.cubes = card("Cubes", "0 / 3")
        for item in (battery, mood, cubes):
            metrics.addWidget(item)
        layout.addLayout(metrics)
        activity, self.activity = card("Right now", "Ready when you are")
        activity_layout = activity.layout()
        assert isinstance(activity_layout, QVBoxLayout)
        self.home_detail = label(
            "Camera offline · AI not configured · Autonomous driving off", "muted", True
        )
        activity_layout.addWidget(self.home_detail)
        row = QHBoxLayout()
        self.freeplay = QPushButton("Start idle expressions")
        self.freeplay.clicked.connect(self.toggle_idle)
        row.addWidget(self.freeplay)
        explore = QPushButton("Browse expressions")
        explore.clicked.connect(lambda: self.navigation.setCurrentRow(2))
        row.addWidget(explore)
        camera = QPushButton("Open camera")
        camera.clicked.connect(lambda: self.navigation.setCurrentRow(4))
        row.addWidget(camera)
        activity_layout.addLayout(row)
        layout.addWidget(activity)
        layout.addStretch()
        return page

    def expressions_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("A face for every feeling.", "title"))
        layout.addWidget(
            label("Original procedural eyes with simulated head and lift poses.", "muted", True)
        )
        grid = QGridLayout()
        grid.setSpacing(16)
        self.expression_buttons: dict[str, QPushButton] = {}
        for index, name in enumerate(NAMES):
            frame = QFrame()
            frame.setObjectName("card")
            inner = QVBoxLayout(frame)
            preview = QLabel()
            preview.setPixmap(
                pixmap(render_face(name)).scaled(
                    180,
                    90,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(preview)
            button = QPushButton(name)
            button.clicked.connect(
                lambda checked=False, value=name: self.controller.submit(
                    "expression", lambda: apply_expression(self.controller, Expression(value))
                )
            )
            inner.addWidget(button)
            self.expression_buttons[name] = button
            grid.addWidget(frame, index // 3, index % 3)
        layout.addLayout(grid)
        layout.addStretch()
        return page

    def camera_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("A view into his world.", "title"))
        layout.addWidget(
            label(
                "Synthetic test scene · 10 FPS target · Test face and cube overlays", "muted", True
            )
        )
        self.camera = label("Connect the simulator to see the camera.", "notice")
        self.camera.setMinimumHeight(360)
        self.camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.camera, 1)
        row = QHBoxLayout()
        snapshot = QPushButton("Save snapshot")
        snapshot.clicked.connect(self.snapshot)
        fullscreen = QPushButton("Toggle fullscreen")
        fullscreen.clicked.connect(
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen()
        )
        row.addWidget(snapshot)
        row.addWidget(fullscreen)
        row.addStretch()
        layout.addLayout(row)
        return page

    def connection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(22)
        layout.addWidget(label("Choose how you connect.", "title"))
        layout.addWidget(label("Available now", "eyebrow"))
        layout.addWidget(
            label(
                "Simulator — complete hardware-free workspace. Use Connect simulator above.",
                "notice",
                True,
            )
        )
        backend = QComboBox()
        backend.addItems(
            ["Simulation Mode", "SDK bridge — not implemented", "Direct Wi-Fi — research only"]
        )
        for row in (1, 2):
            backend.model().item(row).setEnabled(False)  # type: ignore[attr-defined]
        layout.addWidget(backend)
        layout.addWidget(label("Connecting a real Cozmo · future milestone", "title"))
        layout.addWidget(
            label(
                "The SDK bridge requires the official phone app:\n\n"
                "1. Connect your phone to Ubuntu by USB and authorize it.\n"
                "2. Connect the phone to Cozmo’s Wi-Fi.\n"
                "3. Open the Cozmo app and connect to your robot.\n"
                "4. Enable SDK mode in the app.\n"
                "5. A future bridge adapter will connect from this desktop app.\n\n"
                "These steps do not enable hardware support in version 0.1.0.\n"
                "ADB detection and bridge diagnostics are not implemented yet.",
                "muted",
                True,
            )
        )
        layout.addWidget(
            label(
                "Direct Wi-Fi: PyCozmo provides an upstream implementation. Our adapter remains "
                "disabled pending compatibility and supervised hardware tests. "
                "See docs/CONNECTION_RESEARCH.md.",
                "notice",
                True,
            )
        )
        layout.addStretch()
        return page

    def settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.addWidget(label("Make room for your companion.", "title"))
        layout.addWidget(
            label(
                "Defaults stay local. No accounts, cloud services or API keys are needed.",
                "muted",
                True,
            )
        )
        layout.addWidget(label("SNAPSHOT FOLDER", "eyebrow"))
        self.snapshot_folder = QLineEdit(self.settings.snapshots_directory)
        self.snapshot_folder.setAccessibleName("Snapshot folder")
        layout.addWidget(self.snapshot_folder)
        layout.addWidget(
            label(
                "The speed limiter on Control is saved with these settings. Dark theme and "
                "English UI are the available appearance options in this milestone.",
                "muted",
                True,
            )
        )
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save)
        layout.addSpacing(20)
        layout.addWidget(label("Diagnostics", "title"))
        layout.addWidget(
            label(
                "Export app version, connection status and safety state. Reports exclude "
                "speech, paths, environment variables, API keys and raw logs.",
                "muted",
                True,
            )
        )
        export = QPushButton("Export diagnostic report…")
        export.clicked.connect(self.export_diagnostics)
        layout.addWidget(export)
        layout.addWidget(
            label(
                "AI conversation, voice recognition, real Freeplay, games and hardware "
                "connections are planned. This version does not collect microphone input.",
                "notice",
                True,
            )
        )
        layout.addStretch()
        layout.addWidget(
            label(
                "Unofficial community project. Not affiliated with Anki or Digital Dream Labs.",
                "muted",
                True,
            )
        )
        return page

    async def wake(self) -> None:
        await self.controller.backend.connect()
        await apply_expression(self.controller, Expression("Happy", 25, 0.2))
        self.controller.message = "Hello, friend. Your simulated Cozmo is awake."

    def toggle_connection(self) -> None:
        self.release_controls()
        if self.controller.backend.state.connected:
            self.controller.submit("connection", self.controller.disconnect)
        else:
            self.controller.submit("connection", self.controller.backend.connect)

    def toggle_idle(self) -> None:
        backend = self.controller.backend
        self.controller.submit(
            "idle", backend.disable_freeplay if backend.state.freeplay else backend.enable_freeplay
        )

    def navigate(self, index: int) -> None:
        self.release_controls()
        self.stack.setCurrentIndex(index)
        self.page_title.setText(PAGES[index])

    def release_controls(self) -> None:
        self.keys.clear()
        self.control.mouse_direction = None
        # Construction/navigation may happen before the asyncio loop starts.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self.controller.stop_motion()

    def emergency_stop(self) -> None:
        self.keys.clear()
        self.control.mouse_direction = None
        self.controller.emergency_stop()

    def resume(self) -> None:
        self.keys.clear()
        self.control.mouse_direction = None
        if self._resume_task is None or self._resume_task.done():
            self._resume_task = asyncio.create_task(self.controller.resume())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate and watched is self:
            self.release_controls()
        if event.type() == QEvent.Type.FocusIn and isinstance(
            watched, (QLineEdit, QAbstractSpinBox)
        ):
            self.release_controls()
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and isinstance(
            event, QKeyEvent
        ):
            focus = QApplication.focusWidget()
            if isinstance(focus, (QLineEdit, QAbstractSpinBox)):
                return super().eventFilter(watched, event)
            if event.isAutoRepeat():
                return event.key() in KEYS
            pressed = event.type() == QEvent.Type.KeyPress
            if event.key() == Qt.Key.Key_Space and pressed:
                self.emergency_stop()
                return True
            if self.stack.currentIndex() == 1 and not self.controller.latched:
                if event.key() in KEYS:
                    if pressed:
                        self.keys.add(KEYS[event.key()])
                    else:
                        self.release_controls()
                    return True
                state = self.controller.backend.state
                if pressed and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    delta = 5.0 if event.key() == Qt.Key.Key_Up else -5.0
                    self.controller.submit(
                        "head",
                        lambda: self.controller.backend.set_head_angle(state.head_angle + delta),
                    )
                    return True
                if pressed and event.key() in (Qt.Key.Key_R, Qt.Key.Key_F):
                    delta = 0.1 if event.key() == Qt.Key.Key_R else -0.1
                    self.controller.submit(
                        "lift",
                        lambda: self.controller.backend.set_lift_height(state.lift_height + delta),
                    )
                    return True
        return super().eventFilter(watched, event)

    def refresh(self) -> None:
        if self.controller.closing:
            return
        state = self.controller.backend.state
        if self.controller.latched or not state.connected:
            self.keys.clear()
            self.control.mouse_direction = None
        directions = self.keys | (
            {self.control.mouse_direction} if self.control.mouse_direction else set()
        )
        if directions and self.stack.currentIndex() == 1:
            speed = self.controller.speed_limit
            forward = int("w" in directions) - int("s" in directions)
            turn = int("d" in directions) - int("a" in directions)
            self.controller.submit(
                "drive",
                lambda: self.controller.drive((forward + turn) * speed, (forward - turn) * speed),
            )
        self.connection_status.setText(
            "●  Simulated connection" if state.connected else "○  Disconnected"
        )
        self.connect_button.setText("Disconnect" if state.connected else "Connect simulator")
        self.connect_button.setEnabled(not self.controller.latched)
        self.resume_button.setVisible(self.controller.latched)
        self.feedback.setText(self.controller.message)
        self.preview.state = state
        self.preview.update()
        self.battery.setText(f"{state.battery:.0f}%")
        self.mood.setText(state.expression)
        self.cubes.setText(f"{sum(c.connected for c in state.cubes)} / 3")
        self.activity.setText(
            state.animation
            or ("Idle expressions · stationary" if state.freeplay else "Ready when you are")
        )
        self.freeplay.setText(
            "Stop idle expressions" if state.freeplay else "Start idle expressions"
        )
        self.home_detail.setText(
            f"Camera {'ready' if state.camera_available else 'offline'} · "
            f"{'Test face detected' if state.face_detected else 'No test face'} · "
            f"{'Charging' if state.charging else 'Not charging'} · AI off · Autonomous driving off"
        )
        self.control.refresh(state)
        if state.connected and self.stack.currentIndex() == 4:
            self.controller.submit("camera", self.update_camera)
        elif not state.connected:
            self._last_frame = None
            self.camera.setText("Connect the simulator to see the camera.")

    async def update_camera(self) -> None:
        self._last_frame = await self.controller.backend.get_camera_frame()
        self.camera.setPixmap(
            pixmap(self._last_frame).scaled(
                self.camera.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def snapshot(self) -> None:
        if self._last_frame is None:
            self.controller.message = "Open a connected camera preview before taking a snapshot."
            return
        try:
            directory = Path(self.settings.snapshots_directory).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"cozmo-simulation-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
            self._last_frame.save(path)
            self.controller.message = f"Snapshot saved to {path.name}."
        except OSError:
            self.controller.message = "Could not save the snapshot. Check the folder in Settings."

    def save_settings(self) -> None:
        directory = self.snapshot_folder.text().strip()
        if not directory:
            self.controller.message = "Choose a snapshot folder first."
            return
        self.settings.snapshots_directory = directory
        self.settings.speed_limit = int(self.controller.speed_limit)
        try:
            self.settings.save(self.directory / "settings.json")
            self.controller.message = "Settings saved on this computer."
        except OSError:
            self.controller.message = "Could not save settings. Check directory permissions."

    def export_diagnostics(self) -> None:
        self.release_controls()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export diagnostics", "cozmo-diagnostics.json", "JSON (*.json)"
        )
        if path:
            try:
                export_report(Path(path), self.controller.backend.state, self.controller.latched)
                self.controller.message = "Diagnostic report exported without personal data."
            except OSError:
                self.controller.message = "Could not export the report. Choose another folder."

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closed:
            application = QApplication.instance()
            if isinstance(application, QApplication):
                application.removeEventFilter(self)
            event.accept()
            return
        event.ignore()
        if self._closing_task is None:
            self._closing_task = asyncio.create_task(self._shutdown())

    async def _shutdown(self) -> None:
        self.timer.stop()
        await self.controller.shutdown()
        self._closed = True
        self.close()
