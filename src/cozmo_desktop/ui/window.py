import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cozmo_desktop import __version__
from cozmo_desktop.ai.providers.ollama import OllamaProvider, validate_endpoint
from cozmo_desktop.ai.resources import detect_resources, model_memory_warning
from cozmo_desktop.ai.speech import VoskPushToTalk
from cozmo_desktop.code_lab.server import CodeLabServer
from cozmo_desktop.face.expressions import NAMES, Expression, apply_expression, render_face
from cozmo_desktop.robot.base import RobotError
from cozmo_desktop.robot.direct.backend import DirectBackend
from cozmo_desktop.robot.simulator import SimulatorBackend
from cozmo_desktop.services.cliff_trace import LABELS, MAX_SAMPLES, CliffTrace, analyze_trace
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.services.diagnostics import export_report
from cozmo_desktop.services.games import GAME_NAMES
from cozmo_desktop.storage.settings import Settings

from .animations import AnimationsPage
from .control import ControlPage
from .theme import STYLE
from .widgets import RobotPreview, card, label, pixmap

PAGES = (
    "Home",
    "Control",
    "Expressions",
    "Animations",
    "Camera",
    "Connection",
    "Settings",
    "Cubes",
    "Games",
    "Conversation",
    "Code",
)
KEYS: dict[int, str] = {Qt.Key.Key_W: "w", Qt.Key.Key_A: "a", Qt.Key.Key_S: "s", Qt.Key.Key_D: "d"}


def embed_code_lab() -> bool:
    """Avoid a native QtWebEngine abort in Linux desktop processes by default."""
    return sys.platform != "linux" or os.environ.get("COZMO_CODE_EMBEDDED") == "1"


def open_code_url(url: QUrl) -> bool:
    return QDesktopServices.openUrl(url)


class MainWindow(QMainWindow):
    def __init__(self, controller: RobotController, settings: Settings, directory: Path) -> None:
        super().__init__()
        self.controller, self.settings, self.directory = controller, settings, directory
        self.keys: set[str] = set()
        self._closed = False
        self._closing_task: asyncio.Task[None] | None = None
        self._resume_task: asyncio.Task[None] | None = None
        self._last_frame: Image.Image | None = None
        self._mode_task: asyncio.Task[None] | None = None
        self._connection_task: asyncio.Task[None] | None = None
        self._was_connected = False
        self._ollama_checked = False
        self._ollama_health_label = "Checking local Ollama…"
        self._ollama_task: asyncio.Task[None] | None = None
        self._microphone_task: asyncio.Task[None] | None = None
        self._code_start_task: asyncio.Task[None] | None = None
        self.code_server: CodeLabServer | None = None
        self.code_view: QWidget | None = None
        self.recognizer = VoskPushToTalk()
        self.listening = False
        self.cliff_trace = CliffTrace()
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
        self.mode_label = label("SIMULATION MODE", "eyebrow")
        side.addWidget(self.mode_label)
        self.mode_detail = label("No robot required.", "muted", True)
        side.addWidget(self.mode_detail)
        side.addSpacing(20)
        side.addWidget(label(f"Version {__version__}", "muted"))
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
        self.banner = label("", "notice", True)
        main.addWidget(self.banner)
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
            self.cubes_page(),
            self.games_page(),
            self.conversation_page(),
        ):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        self.stack.addWidget(self.code_page())
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
        self.apply_mode()

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
            "Camera offline · Local chat optional · Autonomous driving off", "muted", True
        )
        activity_layout.addWidget(self.home_detail)
        row = QHBoxLayout()
        self.freeplay = QPushButton("Start Freeplay")
        self.freeplay.clicked.connect(self.toggle_idle)
        row.addWidget(self.freeplay)
        self.freeplay_movement = QCheckBox("Self-directed movement on a clear floor")
        self.freeplay_movement.setAccessibleName("Allow supervised floor roaming")
        explore = QPushButton("Browse expressions")
        explore.clicked.connect(lambda: self.navigation.setCurrentRow(2))
        row.addWidget(explore)
        camera = QPushButton("Open camera")
        camera.clicked.connect(lambda: self.navigation.setCurrentRow(4))
        row.addWidget(camera)
        activity_layout.addLayout(row)
        activity_layout.addWidget(self.freeplay_movement)
        games = QPushButton("Play cube games")
        games.clicked.connect(lambda: self.navigation.setCurrentRow(8))
        activity_layout.addWidget(games)
        conversation = QPushButton("Talk with Cozmo")
        conversation.clicked.connect(lambda: self.navigation.setCurrentRow(9))
        activity_layout.addWidget(conversation)
        code = QPushButton("Open Cozmo Code Lab")
        code.clicked.connect(lambda: self.navigation.setCurrentRow(10))
        activity_layout.addWidget(code)
        layout.addWidget(activity)
        layout.addStretch()
        return page

    def expressions_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("A face for every feeling.", "title"))
        self.expression_description = label("", "muted", True)
        layout.addWidget(self.expression_description)
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
        self.camera_description = label("", "muted", True)
        layout.addWidget(self.camera_description)
        self.camera = label("Connect to see the camera.", "notice")
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
        layout.setSpacing(18)
        layout.addWidget(label("Connect your real Cozmo.", "title"))
        self.backend_choice = QComboBox()
        self.backend_choice.addItems(["Simulation Mode", "Direct Wi-Fi — experimental"])
        self.backend_choice.setCurrentIndex(0 if self.controller.backend.is_simulation else 1)
        self.backend_choice.currentIndexChanged.connect(self.select_backend)
        layout.addWidget(self.backend_choice)
        layout.addWidget(
            label(
                "Direct Wi-Fi sends real commands to your robot. This adapter has automated "
                "transport tests but has not yet been verified with physical hardware.",
                "notice",
                True,
            )
        )
        layout.addWidget(
            label(
                "1. Install the direct extra and eSpeak NG while Internet is available.\n"
                "2. In VMware: attach the USB Wi-Fi adapter to the Ubuntu guest.\n"
                "3. Put Cozmo on his charger; raise/lower the lift to display the Wi-Fi key.\n"
                "4. In Ubuntu Wi-Fi settings, join Cozmo_XXXXXX using that key.\n"
                "5. Close the mobile Cozmo app. Select Direct Wi-Fi here, then Connect Cozmo.\n"
                "6. Check live state. Put Cozmo on a clear floor, choose Clear floor, "
                "then Enable motors.\n\n"
                "No phone is needed. Ubuntu should receive a 172.31.1.x address. "
                "Do not drive on a desk. Cozmo may calibrate during protocol initialization.",
                "muted",
                True,
            )
        )
        layout.addWidget(label("PLAY SURFACE", "eyebrow"))
        self.surface_choice = QComboBox()
        self.surface_choice.addItems(
            ["Unselected — wheels locked", "Elevated/table — wheels locked", "Clear floor"]
        )
        self.surface_choice.setAccessibleName("Physical play surface")
        self.surface_choice.currentIndexChanged.connect(self.select_surface)
        layout.addWidget(self.surface_choice)
        layout.addWidget(
            label(
                "Select Clear floor only after placing Cozmo on a spacious floor. "
                "The cliff sensor is visible below, but cannot prove a table edge is safe.",
                "notice",
                True,
            )
        )
        self.cliff_status = label("Cliff sensor: no real reading yet.", "muted", True)
        layout.addWidget(self.cliff_status)
        self.arm_button = QPushButton("Enable motors")
        self.arm_button.setObjectName("primary")
        self.arm_button.clicked.connect(
            lambda: self.controller.submit("arm", self.controller.backend.arm_motors)
        )
        layout.addWidget(self.arm_button)
        self.motor_status = label("Motor control is locked.", "notice", True)
        layout.addWidget(self.motor_status)
        layout.addWidget(label("MOTOR-LOCKED CLIFF SENSOR TRACE", "eyebrow"))
        layout.addWidget(
            label(
                "Observe Cozmo with wheels locked. Mark center or an edge while "
                "supporting him by hand. This trace cannot certify safe table driving.",
                "muted",
                True,
            )
        )
        self.trace_position = QComboBox()
        self.trace_position.addItems(LABELS)
        self.trace_position.setAccessibleName("Cliff trace position label")
        self.trace_position.currentTextChanged.connect(self.set_trace_position)
        layout.addWidget(self.trace_position)
        trace_buttons = QHBoxLayout()
        self.trace_toggle = QPushButton("Start sensor trace")
        self.trace_toggle.clicked.connect(self.toggle_cliff_trace)
        trace_buttons.addWidget(self.trace_toggle)
        self.trace_export = QPushButton("Export trace…")
        self.trace_export.clicked.connect(self.export_cliff_trace)
        trace_buttons.addWidget(self.trace_export)
        layout.addLayout(trace_buttons)
        self.trace_status = label(self.cliff_trace.message, "muted", True)
        layout.addWidget(self.trace_status)
        layout.addWidget(
            label(
                "STOP cancels commands. Pickup, cliff/charger state or an expired drive command "
                "locks motors again. The SDK/phone bridge is not implemented.",
                "muted",
                True,
            )
        )
        layout.addStretch()
        return page

    def cubes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Your little playmates.", "title"))
        layout.addWidget(
            label(
                "Direct mode: first request connects a detected cube; press again to turn its LEDs "
                "green. Only received connection/tap/movement events are shown. "
                "Battery percentage and orientation are not available.",
                "muted",
                True,
            )
        )
        self.cube_labels = []
        self.cube_buttons = []
        for number in range(1, 4):
            text = label(f"Cube {number} · disconnected", "notice", True)
            self.cube_labels.append(text)
            layout.addWidget(text)
            button = QPushButton(f"Connect / light Cube {number}")
            button.clicked.connect(
                lambda checked=False, value=number: self.controller.submit(
                    "cube", lambda: self.controller.backend.cube_lights(value)
                )
            )
            self.cube_buttons.append(button)
            layout.addWidget(button)
        layout.addStretch()
        return page

    def games_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Play with Cozmo's Power Cubes.", "title"))
        layout.addWidget(
            label(
                "Quick Tap, Memory Match and Keepaway are original-code recreations "
                "based on cube taps, movement and lights. The original mobile app's "
                "animations, unlocks and game engine are not part of direct Wi-Fi.",
                "notice",
                True,
            )
        )
        layout.addWidget(
            label(
                "Connect Cubes 1–3 on the Cubes page first. Quick Tap and Memory Match "
                "need all three; Keepaway needs Cube 1. Games keep wheels still.",
                "muted",
                True,
            )
        )
        self.game_choice = QComboBox()
        self.game_choice.addItems(GAME_NAMES)
        self.game_choice.setAccessibleName("Choose a Power Cube game")
        layout.addWidget(self.game_choice)
        buttons = QHBoxLayout()
        self.game_start = QPushButton("Start game")
        self.game_start.setObjectName("primary")
        self.game_start.clicked.connect(self.start_game)
        self.game_stop = QPushButton("Stop game")
        self.game_stop.clicked.connect(
            lambda: self.controller.submit("game", self.controller.stop_game)
        )
        buttons.addWidget(self.game_start)
        buttons.addWidget(self.game_stop)
        layout.addLayout(buttons)
        self.game_score = label("You 0 · Cozmo 0", "title")
        self.game_status = label(
            "Choose a game to play with connected Power Cubes.", "notice", True
        )
        layout.addWidget(self.game_score)
        layout.addWidget(self.game_status)
        layout.addStretch()
        return page

    def conversation_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Talk with Cozmo.", "title"))
        layout.addWidget(
            label(
                "Use a local Ollama model by typing or pressing the microphone button. "
                "Cozmo speaks through his speaker in direct mode. Microphone recognition "
                "needs an optional local Vosk model; no cloud account is required.",
                "notice",
                True,
            )
        )
        self.ollama_status = label("Checking local Ollama…", "muted", True)
        layout.addWidget(self.ollama_status)
        self.ai_resources = label("Checking CPU and memory…", "muted", True)
        layout.addWidget(self.ai_resources)
        model_row = QHBoxLayout()
        self.chat_model = QComboBox()
        self.chat_model.setAccessibleName("Installed Ollama model")
        if self.settings.ollama_model:
            self.chat_model.addItem(self.settings.ollama_model)
        model_row.addWidget(self.chat_model)
        refresh_models = QPushButton("Refresh models")
        refresh_models.clicked.connect(self.refresh_ollama)
        model_row.addWidget(refresh_models)
        layout.addLayout(model_row)
        self.chat_transcript = QListWidget()
        self.chat_transcript.setAccessibleName("Conversation transcript")
        layout.addWidget(self.chat_transcript, 1)
        self.chat_status = label(self.controller.chat_status, "muted", True)
        layout.addWidget(self.chat_status)
        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setMaxLength(400)
        self.chat_input.setPlaceholderText("Type a message to Cozmo")
        self.chat_input.setAccessibleName("Message to Cozmo")
        self.chat_input.returnPressed.connect(self.send_chat)
        row.addWidget(self.chat_input)
        self.chat_send = QPushButton("Send")
        self.chat_send.setObjectName("primary")
        self.chat_send.clicked.connect(self.send_chat)
        row.addWidget(self.chat_send)
        layout.addLayout(row)
        voice_row = QHBoxLayout()
        self.chat_language = QComboBox()
        self.chat_language.addItems(["German", "English"])
        self.chat_language.setAccessibleName("Microphone language")
        voice_row.addWidget(self.chat_language)
        self.microphone = QPushButton("Start microphone")
        self.microphone.clicked.connect(self.toggle_microphone)
        voice_row.addWidget(self.microphone)
        self.chat_stop = QPushButton("Stop response")
        self.chat_stop.clicked.connect(self.controller.stop_response)
        voice_row.addWidget(self.chat_stop)
        layout.addLayout(voice_row)
        layout.addWidget(
            label(
                "Download Ollama, a model and optional Vosk speech models while online. "
                "Then conversation can run locally while connected only to Cozmo Wi-Fi.",
                "muted",
                True,
            )
        )
        return page

    def send_chat(self) -> None:
        if self.controller.chat_busy or self.controller.latched:
            return
        text = self.chat_input.text().strip()
        if not text:
            self.controller.chat_status = "Type a message first."
            return
        model = self.chat_model.currentText().strip()
        if not model:
            self.controller.chat_status = "Select an installed Ollama model first."
            return
        self.settings.ollama_model = model
        self.controller.submit("chat", lambda: self.controller.send_chat(text, model))
        self.chat_input.clear()

    def refresh_ollama(self) -> None:
        if self._ollama_task is None or self._ollama_task.done():
            self._ollama_task = asyncio.create_task(self._check_ollama())

    async def _check_ollama(self) -> None:
        self.ollama_status.setText("Checking local Ollama…")
        resources = await asyncio.to_thread(detect_resources)
        health = await OllamaProvider(self.settings.ollama_server).health()
        self._ollama_health_label = f"Ollama: {health.status}"
        self.ollama_status.setText(self._ollama_health_label)
        selected = self.settings.ollama_model or self.chat_model.currentText()
        self.chat_model.clear()
        for item in health.models:
            self.chat_model.addItem(item.name)
        index = self.chat_model.findText(selected)
        if index >= 0:
            self.chat_model.setCurrentIndex(index)
        if health.models:
            self.settings.ollama_model = self.chat_model.currentText()
        model = next((item for item in health.models if item.name == selected), None)
        available = resources.available_ram_bytes
        available_text = f"{available / 1024**3:.1f} GiB available" if available else "RAM unknown"
        warning = model_memory_warning(model.size_bytes, available) if model else ""
        self.ai_resources.setText(
            f"{resources.architecture} · {resources.cpu_threads or '?'} CPU threads · "
            f"{available_text}" + (f" · {warning}" if warning else "")
        )
        if health.status == "No model installed":
            self.controller.chat_status = "Download a local model first: ollama pull gemma3:1b"

    def toggle_microphone(self) -> None:
        if self._microphone_task is not None and not self._microphone_task.done():
            return
        self.release_controls()
        self._microphone_task = asyncio.create_task(self._microphone_step())

    async def _microphone_step(self) -> None:
        if self.controller.latched or not self.controller.backend.state.connected:
            self.controller.chat_status = "Connect to Cozmo before speaking."
            return
        if self.listening:
            self.controller.chat_status = "Transcribing locally…"
            self.microphone.setEnabled(False)
            try:
                text = await self.recognizer.stop()
            except RobotError as exc:
                self.controller.chat_status = str(exc)
            else:
                self.chat_input.setText(text)
                self.send_chat()
            finally:
                self.listening = False
                self.microphone.setText("Start microphone")
                self.microphone.setEnabled(True)
            return
        path = (
            self.settings.stt_model_de
            if self.chat_language.currentIndex() == 0
            else self.settings.stt_model_en
        )
        if not path:
            self.controller.chat_status = "Choose a local Vosk model folder in Settings first."
            return
        self.controller.chat_status = "Opening microphone…"
        self.microphone.setEnabled(False)
        try:
            await self.recognizer.start(Path(path))
        except RobotError as exc:
            self.controller.chat_status = str(exc)
        else:
            self.listening = True
            self.microphone.setText("Stop and transcribe")
            self.controller.chat_status = "Listening… click again to transcribe."
        finally:
            self.microphone.setEnabled(True)

    def start_game(self) -> None:
        name = self.game_choice.currentText()
        required = {"Quick Tap": 3, "Memory Match": 3, "Keepaway": 1}[name]
        if not all(c.connected for c in self.controller.backend.state.cubes[:required]):
            self.controller.message = f"Connect Cubes 1–{required} before playing {name}."
            return
        self.controller.submit("game", lambda: self.controller.start_game(name))

    def select_backend(self, index: int) -> None:
        self.release_controls()
        if self._mode_task is None or self._mode_task.done():
            self._mode_task = asyncio.create_task(self._switch_backend(index))

    async def _switch_backend(self, index: int) -> None:
        self.backend_choice.setEnabled(False)
        self.connect_button.setEnabled(False)
        try:
            if self._connection_task is not None:
                self._connection_task.cancel()
                await asyncio.gather(self._connection_task, return_exceptions=True)
            backend = DirectBackend() if index else SimulatorBackend()
            await self.controller.change_backend(backend)
            self._last_frame = None
            self._was_connected = False
            self.surface_choice.blockSignals(True)
            self.surface_choice.setCurrentIndex(0)
            self.surface_choice.blockSignals(False)
            self.animations.filter()
            self.control.limit.setMaximum(backend.speed_cap)
            self.control.limit.setValue(int(self.controller.speed_limit))
            self.apply_mode()
        except Exception:
            self.controller.emergency_stop()
            self.controller.message = "Could not change connection mode. Restart the application."
        finally:
            self.backend_choice.setEnabled(True)

    def apply_mode(self) -> None:
        simulated = self.controller.backend.is_simulation
        self.setWindowTitle(
            "Cozmo Desktop · " + ("Simulation Mode" if simulated else "Direct Wi-Fi")
        )
        self.mode_label.setText("SIMULATION MODE" if simulated else "DIRECT WI-FI")
        self.mode_detail.setText(
            "No robot required." if simulated else "Physical robot · experimental"
        )
        self.banner.setText(
            "SIMULATION MODE / Every reading and action is synthetic."
            if simulated
            else "REAL COZMO / Experimental direct Wi-Fi. Enable motors explicitly to drive."
        )
        self.camera_description.setText(
            "Synthetic scene · Test face/cube overlays"
            if simulated
            else "Live Cozmo camera · grayscale · up to 5 previews/second · no simulated overlays"
        )
        self.control.speech_description.setText(
            "Simulated speech appears as text; no audio output."
            if simulated
            else "Speech uses local eSpeak NG and Cozmo’s speaker. Microphone is opt-in on Talk."
        )
        self.animations.description.setText(
            "Original simulator animations."
            if simulated
            else "Original OLED eye animations. No proprietary mobile app animation packs."
        )
        self.expression_description.setText(
            "Original procedural eyes with simulated head and lift poses."
            if simulated
            else "Original OLED eyes. Head/lift poses run only when motors are enabled."
        )
        self.control.limit.setMaximum(self.controller.backend.speed_cap)
        self.control.limit.setValue(int(self.controller.speed_limit))

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
        layout.addWidget(label("LOCAL AI · OLLAMA", "eyebrow"))
        self.ai_enabled = QCheckBox("Enable local AI conversation")
        self.ai_enabled.setChecked(self.settings.ai_enabled)
        layout.addWidget(self.ai_enabled)
        self.ollama_server = QLineEdit(self.settings.ollama_server)
        self.ollama_server.setAccessibleName("Ollama server address")
        layout.addWidget(self.ollama_server)
        self.memory_enabled = QCheckBox("Remember recent conversation in this session")
        self.memory_enabled.setChecked(self.settings.memory_enabled)
        layout.addWidget(self.memory_enabled)
        self.spontaneous_ai = QCheckBox("Spontaneous AI speech during Freeplay")
        self.spontaneous_ai.setChecked(self.settings.spontaneous_ai)
        layout.addWidget(self.spontaneous_ai)
        advanced = QHBoxLayout()
        advanced.addWidget(label("Temperature", "muted"))
        self.ai_temperature = QDoubleSpinBox()
        self.ai_temperature.setRange(0, 1)
        self.ai_temperature.setSingleStep(0.1)
        self.ai_temperature.setValue(self.settings.temperature)
        advanced.addWidget(self.ai_temperature)
        advanced.addWidget(label("Max tokens", "muted"))
        self.ai_max_tokens = QSpinBox()
        self.ai_max_tokens.setRange(32, 400)
        self.ai_max_tokens.setValue(self.settings.max_tokens)
        advanced.addWidget(self.ai_max_tokens)
        layout.addLayout(advanced)
        layout.addWidget(label("LOCAL VOSK MODEL FOLDERS", "eyebrow"))
        self.stt_de = QLineEdit(self.settings.stt_model_de)
        self.stt_de.setPlaceholderText("German model folder (optional)")
        self.stt_en = QLineEdit(self.settings.stt_model_en)
        self.stt_en.setPlaceholderText("English model folder (optional)")
        layout.addWidget(self.stt_de)
        layout.addWidget(self.stt_en)
        clear_memory = QPushButton("Clear conversation memory")
        clear_memory.clicked.connect(self.controller.clear_chat_memory)
        layout.addWidget(clear_memory)
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
                "Microphone speech recognition is optional and local. Original app "
                "assets are not included. Physical control remains experimental.",
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
        await self.controller.backend.display_face(render_face("Happy"), "Happy")
        self.controller.message = "Connected. Physical motors remain locked until enabled."

    def toggle_connection(self) -> None:
        self.release_controls()
        if self._connection_task is None or self._connection_task.done():
            self._connection_task = asyncio.create_task(self._toggle_connection())

    async def _toggle_connection(self) -> None:
        try:
            if self.controller.backend.state.connected:
                self._was_connected = False
                await self.controller.disconnect()
                return
            self.controller.message = "Connecting…"
            if self.controller.latched:
                await self.controller.backend.disconnect()
                await self.controller.resume()
            if not self.controller.latched:
                await self.controller.backend.connect()
                self.controller.message = "Connected. Check Connection for motor status."
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.controller.emergency_stop(preserve_message=True)
            self.controller.message = (
                str(exc) if isinstance(exc, RobotError) else "Connection failed. Check Diagnostics."
            )

    def toggle_idle(self) -> None:
        backend = self.controller.backend
        self.controller.submit(
            "freeplay",
            self.controller.disable_freeplay
            if backend.state.freeplay
            else lambda: self.controller.enable_freeplay(
                allow_movement=self.freeplay_movement.isChecked()
            ),
        )

    def select_surface(self, index: int) -> None:
        if self.controller.backend.is_simulation or not self.controller.backend.state.connected:
            return
        mode = ("unknown", "table", "floor")[index]
        self.controller.submit("surface", lambda: self.controller.backend.set_surface(mode))

    def set_trace_position(self, value: str) -> None:
        if value in LABELS:
            self.cliff_trace.label = value

    def toggle_cliff_trace(self) -> None:
        if self.cliff_trace.active:
            self.cliff_trace.stop()
            return
        try:
            self.cliff_trace.start(self.controller.backend.state)
            self.trace_position.setCurrentText("center")
        except RobotError as exc:
            self.cliff_trace.message = str(exc)

    def export_cliff_trace(self) -> None:
        if not self.cliff_trace.samples:
            return
        self.cliff_trace.stop()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export motor-locked cliff trace", "cozmo-cliff-trace.json", "JSON (*.json)"
        )
        if path:
            try:
                self.cliff_trace.export(Path(path))
                status = analyze_trace(self.cliff_trace.samples)["status"]
                self.cliff_trace.message = (
                    "Sensor trace exported with diagnostic comparison; table driving stays locked."
                    if status == "comparison_only"
                    else "Trace exported; measurements incomplete. Table driving stays locked."
                )
            except OSError:
                self.cliff_trace.message = "Could not export sensor trace. Choose another folder."

    def navigate(self, index: int) -> None:
        self.release_controls()
        self.stack.setCurrentIndex(index)
        self.page_title.setText(PAGES[index])
        if index == 10 and (self._code_start_task is None or self._code_start_task.done()):
            try:
                self._code_start_task = asyncio.create_task(self._start_code_lab())
            except RuntimeError:
                pass

    def code_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Cozmo Code Lab", "title"))
        self.code_status = label(
            "Unofficial Code Lab, built with open-source Scratch editor technology.",
            "muted",
            True,
        )
        layout.addWidget(self.code_status)
        self.code_live_status = label("Cozmo: Disconnected · Safety: Waiting", "muted", True)
        layout.addWidget(self.code_live_status)
        self.code_open_button = QPushButton("Open Code Lab in browser")
        self.code_open_button.clicked.connect(self.open_code_browser)
        self.code_open_button.hide()
        layout.addWidget(self.code_open_button)
        self.code_container = QVBoxLayout()
        layout.addLayout(self.code_container, 1)
        return page

    async def _start_code_lab(self) -> None:
        if self.code_server is not None:
            return
        static_dir = await asyncio.to_thread(
            lambda: Path(__file__).resolve().parents[1] / "code_lab" / "static"
        )
        try:
            server = CodeLabServer(self.controller.code_lab, static_dir)
            await server.start()
            self.code_server = server
            if not embed_code_lab():
                self.code_open_button.show()
                self.open_code_browser()
                return
            from PySide6.QtWebEngineWidgets import QWebEngineView

            view = QWebEngineView(self)
            self.code_container.addWidget(view)
            self.code_view = view
            view.setUrl(QUrl(server.url))
            self.code_status.setText(
                "Local editor ready. Connect Cozmo or the simulator; STOP stays above."
            )
        except (ImportError, FileNotFoundError, OSError, RuntimeError) as exc:
            self.code_status.setText(
                "Code Lab editor is not installed. Build Scratch and install QtWebEngine."
            )
            self.controller.message = str(exc)

    def open_code_browser(self) -> None:
        if self.code_server is None:
            return
        if open_code_url(QUrl(self.code_server.url)):
            self.code_status.setText(
                "Code Lab opened in your browser. Emergency STOP is also inside the editor."
            )
        else:
            self.code_status.setText(
                "No browser opened. Install or select a default browser on this computer."
            )

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
        if self._microphone_task is not None and not self._microphone_task.done():
            self._microphone_task.cancel()
        if self.listening:
            self.listening = False
            self.microphone.setText("Start microphone")
            asyncio.create_task(self.recognizer.cancel())

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
            if (
                self.stack.currentIndex() == 1
                and not self.controller.latched
                and self.controller.backend.state.motors_enabled
            ):
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
        if not self._ollama_checked:
            self._ollama_checked = True
            self.refresh_ollama()
        state = self.controller.backend.state
        self.cliff_trace.observe(state)
        if (
            self._was_connected
            and not state.connected
            and not self.controller.backend.is_simulation
        ):
            self.controller.emergency_stop(preserve_message=True)
            self.controller.message = state.safety_status or "Connection lost. Motors locked."
        self._was_connected = state.connected
        if self.controller.latched or not state.connected or not state.motors_enabled:
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
            ("●  Simulator" if self.controller.backend.is_simulation else "●  Cozmo Wi-Fi")
            if state.connected
            else "○  Disconnected"
        )
        battery = f"{state.battery:.0f}%" if state.battery is not None else "unknown"
        mode = (
            "Scratch"
            if self.controller.code_lab.active
            else ("Freeplay" if state.freeplay else "Ready")
        )
        safety = "STOP" if self.controller.latched else state.safety_status or "OK"
        self.code_live_status.setText(
            f"Cozmo: {'Connected' if state.connected else 'Disconnected'} · "
            f"Battery: {battery} · Mode: {mode} · Safety: {safety} · "
            f"{self._ollama_health_label}"
        )
        self.connect_button.setText(
            "Disconnect"
            if state.connected
            else ("Connect simulator" if self.controller.backend.is_simulation else "Connect Cozmo")
        )
        self.connect_button.setEnabled(
            (self._mode_task is None or self._mode_task.done())
            and (self._connection_task is None or self._connection_task.done())
        )
        self.resume_button.setVisible(self.controller.latched)
        self.feedback.setText(self.controller.message)
        self.preview.state = state
        self.preview.update()
        self.battery.setText(
            f"{state.battery:.0f}%"
            if state.battery is not None
            else (
                f"{state.battery_voltage:.2f} V" if state.battery_voltage is not None else "Unknown"
            )
        )
        self.mood.setText(state.expression)
        self.cubes.setText(f"{sum(c.connected for c in state.cubes)} / 3")
        self.activity.setText(
            state.animation
            or (
                "Freeplay · slow floor roaming"
                if state.freeplay and self.controller.freeplay_allows_motion
                else ("Freeplay · eyes and sounds" if state.freeplay else "Ready when you are")
            )
        )
        self.freeplay.setText("Stop Freeplay" if state.freeplay else "Start Freeplay")
        self.freeplay_movement.setEnabled(
            state.connected and not state.freeplay and not self.controller.latched
        )
        moving = state.freeplay and self.controller.freeplay_allows_motion
        self.home_detail.setText(
            f"Camera {'ready' if state.camera_available else 'offline'} · "
            f"{'Test face detected' if state.face_detected else 'Face recognition off'} · "
            f"{'Charging' if state.charging else 'Not charging'} · Local chat optional · "
            f"Autonomous movement {'on' if moving else 'off'}"
        )
        self.control.refresh(state)
        game = self.controller.game_state
        self.game_score.setText(f"You {game.player_score} · Cozmo {game.cozmo_score}")
        self.game_status.setText(f"{game.name} · Round {game.round} · {game.instruction}")
        self.game_start.setEnabled(state.connected and not self.controller.latched)
        self.game_stop.setEnabled(game.phase not in ("idle", "finished", "cancelled", "failed"))
        if self.chat_transcript.count() != len(self.controller.chat_turns):
            self.chat_transcript.clear()
            for chat_turn in self.controller.chat_turns:
                self.chat_transcript.addItem(
                    ("You: " if chat_turn.role == "user" else "Cozmo: ") + chat_turn.text
                )
            self.chat_transcript.scrollToBottom()
        self.chat_status.setText(self.controller.chat_status)
        self.ollama_status.setText(
            "Ollama: Generating" if self.controller.chat_busy else self._ollama_health_label
        )
        self.chat_send.setEnabled(
            state.connected and not self.controller.latched and not self.controller.chat_busy
        )
        self.chat_stop.setEnabled(self.controller.chat_busy)
        self.microphone.setEnabled(
            state.connected
            and not self.controller.latched
            and (self._microphone_task is None or self._microphone_task.done())
        )
        self.surface_choice.setEnabled(
            state.connected and not self.controller.backend.is_simulation
        )
        surface_index = {"unknown": 0, "table": 1, "floor": 2}.get(state.surface_mode, 0)
        if self.surface_choice.currentIndex() != surface_index:
            self.surface_choice.blockSignals(True)
            self.surface_choice.setCurrentIndex(surface_index)
            self.surface_choice.blockSignals(False)
        self.arm_button.setEnabled(
            state.connected
            and state.surface_mode == "floor"
            and not state.motors_enabled
            and not self.controller.latched
        )
        self.trace_toggle.setText(
            "Stop sensor trace" if self.cliff_trace.active else "Start sensor trace"
        )
        self.trace_toggle.setEnabled(
            self.cliff_trace.active
            or (
                state.connected
                and not self.controller.backend.is_simulation
                and not state.motors_enabled
                and state.left_speed == 0
                and state.right_speed == 0
            )
        )
        self.trace_export.setEnabled(bool(self.cliff_trace.samples))
        self.trace_status.setText(
            f"{self.cliff_trace.message} Samples: {len(self.cliff_trace.samples)}/{MAX_SAMPLES}."
        )
        if self.controller.backend.is_simulation:
            self.cliff_status.setText("Synthetic mode: no physical cliff sensor.")
        else:
            raw = (
                "unavailable"
                if state.cliff_raw is None
                else ", ".join(str(value) for value in state.cliff_raw)
            )
            self.cliff_status.setText(
                f"Cliff: {'DETECTED' if state.cliff_detected else 'not flagged'}"
                f" · raw {raw} · pickup {'yes' if state.picked_up else 'no'}"
            )
        self.motor_status.setText(
            state.safety_status
            or (
                "Simulator motor controls are available."
                if self.controller.backend.is_simulation
                else "Motor control locked. Connect first, then select Enable motors."
            )
        )
        for cube, text, button in zip(
            state.cubes, self.cube_labels, self.cube_buttons, strict=True
        ):
            text.setText(
                f"Cube {cube.number} · {'connected' if cube.connected else 'disconnected'}"
                f" · {'tapped' if cube.tapped else 'no tap'}"
                f" · {'moving' if cube.moved else 'still'}"
            )
            button.setEnabled(
                state.connected
                and not self.controller.backend.is_simulation
                and not self.controller.latched
            )
        if state.connected and state.camera_available and self.stack.currentIndex() == 4:
            self.controller.submit("camera", self.update_camera)
        elif not state.connected or not state.camera_available:
            self._last_frame = None
            self.camera.setText(
                "Waiting for camera frames." if state.connected else "Connect to see the camera."
            )

    async def update_camera(self) -> None:
        try:
            self._last_frame = await self.controller.backend.get_camera_frame()
        except RobotError as exc:
            self.camera.setText(str(exc))
            return
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
            mode = self.controller.backend.state.backend_name
            path = directory / f"cozmo-{mode}-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
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
            endpoint = validate_endpoint(self.ollama_server.text())
        except ValueError as exc:
            self.controller.message = str(exc)
            return
        self.settings.ai_enabled = self.ai_enabled.isChecked()
        self.settings.ollama_server = endpoint
        self.settings.ollama_model = self.chat_model.currentText()
        self.settings.temperature = self.ai_temperature.value()
        self.settings.max_tokens = self.ai_max_tokens.value()
        self.settings.memory_enabled = self.memory_enabled.isChecked()
        self.settings.spontaneous_ai = self.spontaneous_ai.isChecked()
        self.settings.stt_model_de = self.stt_de.text().strip()
        self.settings.stt_model_en = self.stt_en.text().strip()
        self.controller.conversation.provider = OllamaProvider(endpoint)
        try:
            self.settings.save(self.directory / "settings.json")
            self.controller.message = "Settings saved on this computer."
            self.refresh_ollama()
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
        if self._code_start_task is not None:
            await asyncio.gather(self._code_start_task, return_exceptions=True)
        if self.code_server is not None:
            await self.code_server.close()
        if self._ollama_task is not None:
            self._ollama_task.cancel()
            await asyncio.gather(self._ollama_task, return_exceptions=True)
        if self._microphone_task is not None:
            self._microphone_task.cancel()
            await asyncio.gather(self._microphone_task, return_exceptions=True)
        try:
            await self.recognizer.cancel()
        except Exception:
            # Audio cleanup must never prevent the independent robot STOP/shutdown.
            pass
        if self._connection_task is not None:
            self._connection_task.cancel()
            await asyncio.gather(self._connection_task, return_exceptions=True)
        if self._mode_task is not None:
            await self._mode_task
        await self.controller.shutdown()
        self._closed = True
        self.close()
