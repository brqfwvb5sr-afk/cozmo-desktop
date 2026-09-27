from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from cozmo_desktop.animations.sequences import Sequence
from cozmo_desktop.services.controller import RobotController
from cozmo_desktop.storage.settings import Settings

from .widgets import label


class AnimationsPage(QWidget):
    def __init__(self, controller: RobotController, settings: Settings, directory: Path) -> None:
        super().__init__()
        self.controller, self.settings, self.directory = controller, settings, directory
        self.items: list[str] = []
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.addWidget(label("Small moments. Big personality.", "title"))
        root.addWidget(
            label(
                "Original simulator animations. These are not mobile app assets or robot triggers.",
                "muted",
                True,
            )
        )
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search animations or categories…")
        self.search.setAccessibleName("Search animations")
        self.search.textChanged.connect(self.filter)
        root.addWidget(self.search)
        self.list = QListWidget()
        self.list.setAccessibleName("Animation library")
        root.addWidget(self.list)
        buttons = QHBoxLayout()
        for title, callback in (
            ("Play", self.play),
            ("Favorite / unfavorite", self.favorite),
            ("Add to sequence", self.add),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        root.addLayout(buttons)
        root.addWidget(label("Your sequence", "title"))
        self.sequence_label = label("Add animations to build a sequence.", "notice", True)
        root.addWidget(self.sequence_label)
        controls = QHBoxLayout()
        for title, callback in (
            ("Play sequence", self.play_sequence),
            ("Save sequence", self.save),
            ("Load saved", self.load),
            ("Clear", self.clear),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            controls.addWidget(button)
        root.addLayout(controls)
        root.addStretch()
        self.filter()

    def filter(self) -> None:
        self.list.clear()
        text = self.search.text().casefold()
        self.visible_names = []
        for animation in self.controller.backend.animations:
            if text in f"{animation.name} {animation.category}".casefold():
                star = "★" if animation.name in self.settings.favorites else "☆"
                self.list.addItem(
                    f"{star}   {animation.name}     /     {animation.category}"
                    f"     /     {animation.duration:.1f}s"
                )
                self.visible_names.append(animation.name)
        if self.visible_names:
            self.list.setCurrentRow(0)

    def selected(self) -> str | None:
        index = self.list.currentRow()
        return self.visible_names[index] if 0 <= index < len(self.visible_names) else None

    def play(self) -> None:
        name = self.selected()
        if name:
            self.controller.submit(
                "animation", lambda: self.controller.backend.play_animation(name)
            )

    def favorite(self) -> None:
        name = self.selected()
        if name:
            if name in self.settings.favorites:
                self.settings.favorites.remove(name)
            else:
                self.settings.favorites.append(name)
            try:
                self.settings.save(self.directory / "settings.json")
            except OSError:
                self.controller.message = "Could not save favorites. Check directory permissions."
            self.filter()

    def add(self) -> None:
        name = self.selected()
        if name and len(self.items) < 8:
            self.items.append(name)
            self.sequence_label.setText("  →  ".join(self.items))

    def clear(self) -> None:
        self.items.clear()
        self.sequence_label.setText("Add animations to build a sequence.")

    def play_sequence(self) -> None:
        if self.items:
            sequence = Sequence("My sequence", tuple(self.items))
            self.controller.submit("animation", lambda: sequence.play(self.controller))

    def save(self) -> None:
        if not self.items:
            return
        try:
            Sequence("My sequence", tuple(self.items)).save(
                self.directory / "animation_sequences.json"
            )
            self.controller.message = "Sequence saved locally."
        except OSError:
            self.controller.message = "Could not save the sequence. Check directory permissions."

    def load(self) -> None:
        try:
            self.items = list(Sequence.load(self.directory / "animation_sequences.json").animations)
            self.sequence_label.setText("  →  ".join(self.items))
        except (OSError, ValueError):
            self.controller.message = "No valid saved sequence found. Create and save one first."
