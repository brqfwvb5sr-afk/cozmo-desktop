from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from cozmo_desktop.robot.base import RobotState
from cozmo_desktop.services.controller import RobotController

from .widgets import card, label


class ControlPage(QWidget):
    def __init__(self, controller: RobotController, release: Callable[[], None]) -> None:
        super().__init__()
        self.controller = controller
        self.mouse_direction: str | None = None
        root = QVBoxLayout(self)
        root.setSpacing(22)
        root.addWidget(label("Hold to move. Release to stop.", "title"))
        root.addWidget(
            label(
                "WASD  ·  Arrows: head  ·  R / F: lift  ·  Space: emergency stop\n"
                "Keyboard driving works only on this page, outside text fields.",
                "muted",
                True,
            )
        )
        columns = QHBoxLayout()
        drive_card, self.speed_label = card("Wheel speed", "0 / 0 mm/s")
        drive_card.setMinimumHeight(340)
        drive_layout = drive_card.layout()
        assert isinstance(drive_layout, QVBoxLayout)
        pad = QGridLayout()
        self.direction_buttons: dict[str, QPushButton] = {}
        for name, text, row, col in (
            ("w", "↑  W", 0, 1),
            ("a", "←  A", 1, 0),
            ("s", "↓  S", 1, 1),
            ("d", "D  →", 1, 2),
        ):
            button = QPushButton(text)
            button.setObjectName("drive")
            button.setAccessibleName(
                {"w": "Forward", "a": "Left", "s": "Backward", "d": "Right"}[name]
            )
            button.pressed.connect(lambda direction=name: self._press(direction))
            button.released.connect(release)
            self.direction_buttons[name] = button
            pad.addWidget(button, row, col)
        drive_layout.addLayout(pad)
        self.limit = QSlider(Qt.Orientation.Horizontal)
        self.limit.setRange(10, 80)
        self.limit.setValue(int(controller.speed_limit))
        self.limit.setAccessibleName("Speed limit in millimeters per second")
        self.limit_text = label(f"Speed limit  {int(controller.speed_limit)} mm/s", "muted")
        self.limit.valueChanged.connect(self._limit_changed)
        drive_layout.addWidget(self.limit_text)
        drive_layout.addWidget(self.limit)
        columns.addWidget(drive_card, 3)
        posture, self.posture_label = card("Posture", "Head 0°  ·  Lift 0%")
        self.posture_label.setStyleSheet("font-size: 20px;")
        posture_layout = posture.layout()
        assert isinstance(posture_layout, QVBoxLayout)
        posture_layout.addWidget(label("HEAD ANGLE", "eyebrow"))
        self.head = QSlider(Qt.Orientation.Horizontal)
        self.head.setRange(-25, 44)
        self.head.setAccessibleName("Head angle")
        self.head.valueChanged.connect(
            lambda value: controller.submit(
                "head", lambda: controller.backend.set_head_angle(value)
            )
        )
        posture_layout.addWidget(self.head)
        posture_layout.addWidget(label("LIFT HEIGHT", "eyebrow"))
        self.lift = QSlider(Qt.Orientation.Horizontal)
        self.lift.setRange(0, 100)
        self.lift.setAccessibleName("Lift height")
        self.lift.valueChanged.connect(
            lambda value: controller.submit(
                "lift", lambda: controller.backend.set_lift_height(value / 100)
            )
        )
        posture_layout.addWidget(self.lift)
        posture_layout.addStretch()
        columns.addWidget(posture, 2)
        root.addLayout(columns)
        root.addWidget(label("Something to say", "title"))
        self.speech_description = label("Simulated speech appears as text.", "muted", True)
        root.addWidget(self.speech_description)
        speech_row = QHBoxLayout()
        self.speech = QLineEdit()
        self.speech.setPlaceholderText("Hello! Ready for a little adventure?")
        self.speech.setMaxLength(500)
        self.speech.setAccessibleName("Speech text")
        self.speak = QPushButton("Speak")
        self.speak.setObjectName("primary")
        self.speak.clicked.connect(self._speak)
        self.speech.returnPressed.connect(self._speak)
        speech_row.addWidget(self.speech)
        speech_row.addWidget(self.speak)
        root.addLayout(speech_row)
        self.last_speech = label("No speech yet.", "notice", True)
        root.addWidget(self.last_speech)
        root.addStretch()

    def _press(self, direction: str) -> None:
        if not self.controller.latched:
            self.mouse_direction = direction

    def _speak(self) -> None:
        text = self.speech.text()
        self.controller.submit("speech", lambda: self.controller.backend.speak(text))

    def _limit_changed(self, value: int) -> None:
        self.controller.speed_limit = value
        self.limit_text.setText(f"Speed limit  {value} mm/s")

    def refresh(self, state: RobotState) -> None:
        self.speed_label.setText(f"{state.left_speed:.0f} / {state.right_speed:.0f} mm/s")
        self.posture_label.setText(f"Head {state.head_angle:.0f}°  ·  Lift {state.lift_height:.0%}")
        self.last_speech.setText(state.speech or "No speech yet.")
        for slider, value in (
            (self.head, round(state.head_angle)),
            (self.lift, round(state.lift_height * 100)),
        ):
            if not slider.isSliderDown() and not slider.hasFocus():
                slider.blockSignals(True)
                slider.setValue(value)
                slider.blockSignals(False)
        for widget in (*self.direction_buttons.values(), self.head, self.lift):
            widget.setEnabled(
                state.connected and state.motors_enabled and not self.controller.latched
            )
        self.speak.setEnabled(state.connected and not self.controller.latched)
