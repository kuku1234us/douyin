"""
Dashboard page for the Douyin application.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from qt_base_app.theme.theme_manager import ThemeManager


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Douyin Dashboard", self)
        title.setObjectName("douyinDashboardTitle")
        title.setStyleSheet(f"""
            color: {self.theme.get_color('text', 'primary')};
            font-size: 22px;
            font-weight: 600;
        """)
        layout.addWidget(title)

        subtitle = QLabel("Welcome to Douyin Framework", self)
        subtitle.setObjectName("douyinDashboardSubtitle")
        subtitle.setStyleSheet(f"""
            color: {self.theme.get_color('text', 'secondary')};
            font-size: 14px;
            margin-top: 4px;
        """)
        layout.addWidget(subtitle)

        layout.addStretch(1)


