from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt

from qt_base_app.theme.theme_manager import ThemeManager


class DownloadProgressOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("downloadProgressOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.theme = ThemeManager.instance()

        self._build_ui()
        # Ensure a reasonable default size so contents are visible initially
        self.setMinimumSize(520, 140)
        self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Simple card-like background
        self.setStyleSheet(
            f"""
            QWidget#downloadProgressOverlay {{
                background-color: rgba(0, 0, 0, 0.65);
                border: 1px solid #555555;
                border-radius: 8px;
            }}
            QLabel {{ color: #FFFFFF; }}
            QProgressBar {{
                color: #FFFFFF;
                background-color: #333333;
                border: 1px solid #666666;
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: #4CAF50;
            }}
            """
        )

        self.status_label = QLabel("Preparing…", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.channels_bar = QProgressBar(self)
        self.channels_bar.setRange(0, 100)
        self.channels_bar.setValue(0)
        self.channels_bar.setMinimumWidth(420)
        layout.addWidget(self.channels_bar)

        self.videos_bar = QProgressBar(self)
        self.videos_bar.setRange(0, 100)
        self.videos_bar.setValue(0)
        self.videos_bar.setMinimumWidth(420)
        layout.addWidget(self.videos_bar)

    def show_overlay(self):
        self.adjustSize()
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()

    def set_status(self, text: str):
        # Update text safely, avoid recursive repaint cascades
        self.status_label.blockSignals(True)
        self.status_label.setText(text)
        self.status_label.blockSignals(False)
        self.updateGeometry()

    def set_channels_progress(self, current: int, total: int):
        val = 0 if total <= 0 else int(current * 100 / max(1, total))
        self.channels_bar.blockSignals(True)
        self.channels_bar.setValue(max(0, min(100, val)))
        self.channels_bar.blockSignals(False)
        self.updateGeometry()

    def set_videos_progress(self, current: int, total: int):
        val = 0 if total <= 0 else int(current * 100 / max(1, total))
        self.videos_bar.blockSignals(True)
        self.videos_bar.setValue(max(0, min(100, val)))
        self.videos_bar.blockSignals(False)
        self.updateGeometry()


