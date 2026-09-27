STYLE = """
QWidget { background: #11191f; color: #e5eff2; font-family: 'Segoe UI', 'Ubuntu', sans-serif;
          font-size: 14px; }
QMainWindow { background: #11191f; }
QLabel { background: transparent; }
QLabel#eyebrow { color: #72d7bc; font-size: 11px; font-weight: 700; }
QLabel#title { font-size: 29px; font-weight: 700; }
QLabel#heroTitle { font-size: 34px; font-weight: 700; }
QLabel#muted { color: #98adb8; }
QLabel#metric { font-size: 25px; font-weight: 600; }
QLabel#notice { color: #abd0cc; background: #18332f; border-radius: 8px; padding: 12px; }
QFrame#card { background: #1a252d; border: 1px solid #2b3a43; border-radius: 14px; }
QFrame#card QLabel { background: transparent; }
QFrame#sidebar { background: #0c1318; border-right: 1px solid #29343d; }
QListWidget { background: #142028; border: 1px solid #30444f; border-radius: 9px; padding: 6px; }
QListWidget::item { padding: 12px; border-radius: 7px; }
QListWidget::item:selected { background: #214940; color: #8ff3d5; }
QListWidget#navigation { background: transparent; border: none; }
QListWidget#navigation::item { margin: 3px 0; padding: 13px 16px; }
QPushButton { background: #283943; border: 1px solid #3b4e59; border-radius: 8px;
              padding: 11px 18px; font-weight: 600; }
QPushButton:hover { background: #354b56; border-color: #74998f; }
QPushButton:pressed { background: #407568; }
QPushButton:disabled { color: #687d86; background: #1c2931; border-color: #293a44; }
QPushButton#primary { color: #0d2620; background: #72e1bd; border: 1px solid #72e1bd; }
QPushButton#primary:hover { background: #96f4d4; }
QPushButton#stop { background: #592b35; color: #ffb7bf; border: 1px solid #97505a; }
QPushButton#drive { min-width: 80px; min-height: 58px; font-size: 20px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #101c23; border: 1px solid #3b515b;
    padding: 10px; border-radius: 7px; selection-background-color: #326956; }
QLineEdit:focus, QSpinBox:focus { border-color: #72e1bd; }
QSlider::groove:horizontal { height: 6px; background: #334951; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #72e1bd; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -6px 0; border-radius: 9px; background: #a9ffe4; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 10px; background: #11191f; }
QScrollBar::handle:vertical { background: #3c545f; min-height: 30px; border-radius: 4px; }
QToolTip { background: #27453d; color: white; padding: 6px; border: 1px solid #72e1bd; }
"""
