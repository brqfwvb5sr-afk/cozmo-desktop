from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from cozmo_desktop.face.expressions import render_face
from cozmo_desktop.robot.base import RobotState


def pixmap(image: Image.Image) -> QPixmap:
    rgb = image.convert("RGB")
    raw = rgb.tobytes()
    return QPixmap.fromImage(
        QImage(raw, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()
    )


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setObjectName(role)
    result.setWordWrap(wrap)
    return result


def card(title: str, value: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.addWidget(label(title.upper(), "eyebrow"))
    metric = label(value, "metric")
    layout.addWidget(metric)
    return frame, metric


class RobotPreview(QWidget):
    """Original vector illustration driven by actual simulator state."""

    def __init__(self) -> None:
        super().__init__()
        self.state = RobotState()
        self.setMinimumSize(350, 310)
        self.setAccessibleName("Simulated Cozmo preview")

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.width() / 460, self.height() / 340)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#17332f"))
        painter.drawEllipse(QRectF(76, 10, 310, 310))
        painter.setBrush(QColor("#0a171b"))
        painter.drawEllipse(QRectF(85, 269, 285, 42))
        painter.setPen(QPen(QColor("#31534e"), 1))
        for y in range(55, 315, 45):
            painter.drawLine(40, y, 420, y)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#263a43"))
        for x in (108, 293):
            painter.drawRoundedRect(QRectF(x, 204, 63, 84), 22, 22)
        painter.setBrush(QColor("#c9dadb"))
        painter.drawRoundedRect(QRectF(151, 185, 157, 90), 20, 20)
        head_y = 78 - self.state.head_angle / 3
        painter.setBrush(QColor("#e1edeb"))
        painter.drawRoundedRect(QRectF(117, head_y, 225, 139), 32, 32)
        painter.setBrush(QColor("#10252d"))
        painter.drawRoundedRect(QRectF(132, head_y + 16, 195, 99), 23, 23)
        face = pixmap(render_face(self.state.expression))
        painter.drawPixmap(140, int(head_y + 20), 180, 90, face)
        painter.setBrush(QColor("#72e1bd" if self.state.connected else "#61747b"))
        painter.drawRoundedRect(QRectF(206, 222, 47, 7), 3, 3)
        painter.setPen(QPen(QColor("#72989b"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        lift_y = 263 - self.state.lift_height * 60
        painter.drawLine(166, 220, 144, int(lift_y))
        painter.drawLine(292, 220, 314, int(lift_y))
        painter.drawLine(144, int(lift_y), 314, int(lift_y))
        painter.end()
