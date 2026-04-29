"""
Preferences page for the Douyin application (minimal version).
Contains one setting: Working Directory, plus database status.
"""
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

from qt_base_app.theme.theme_manager import ThemeManager
from qt_base_app.models.settings_manager import SettingsManager, SettingType
from douyin_app.models.database import DatabaseManager
from douyin_app.models.path_utils import normalize_to_unc


class PreferencesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preferencesPage")
        self.setProperty('page_id', 'preferences')

        self.theme = ThemeManager.instance()
        self.settings = SettingsManager.instance()

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        label_style = f"color: {self.theme.get_color('text', 'primary')};"
        secondary_style = f"color: {self.theme.get_color('text', 'secondary')}; font-size: 12px;"
        input_style = f"""
            background-color: {self.theme.get_color('background', 'tertiary')};
            color: {self.theme.get_color('text', 'primary')};
            border: 1px solid {self.theme.get_color('border', 'primary')};
            border-radius: 4px;
            padding: 6px;
        """
        button_style = f"""
            background-color: {self.theme.get_color('background', 'tertiary')};
            color: {self.theme.get_color('text', 'primary')};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
        """

        # Working Directory
        working_dir_label = QLabel("Working Directory:")
        working_dir_label.setStyleSheet(label_style)

        self.working_dir_edit = QLineEdit()
        self.working_dir_edit.setReadOnly(True)
        self.working_dir_edit.setPlaceholderText("Choose working directory")
        self.working_dir_edit.setStyleSheet(input_style)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMaximumWidth(100)
        browse_btn.setStyleSheet(button_style)
        browse_btn.clicked.connect(self._browse_working_dir)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self.working_dir_edit)
        row_layout.addWidget(browse_btn)

        main_layout.addWidget(working_dir_label)
        main_layout.addWidget(row)

        # Database section
        db_label = QLabel("Database: create or reinitialize at Working Directory")
        db_label.setStyleSheet(label_style)
        create_btn = QPushButton("Create Database")
        create_btn.setStyleSheet(button_style)
        create_btn.clicked.connect(self._create_database)

        db_row = QWidget()
        db_row_layout = QHBoxLayout(db_row)
        db_row_layout.setContentsMargins(0, 0, 0, 0)
        db_row_layout.setSpacing(8)
        db_row_layout.addWidget(db_label, 1)
        db_row_layout.addWidget(create_btn, 0)

        main_layout.addWidget(db_row)

        # Database status indicator
        self.db_status_label = QLabel("")
        self.db_status_label.setStyleSheet(secondary_style)
        self.db_status_label.setWordWrap(True)
        main_layout.addWidget(self.db_status_label)

        main_layout.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_db_status()

    def _get_working_dir(self) -> Path:
        default_path = str(Path.home())
        value = self.settings.get('preferences/working_dir', default_path, SettingType.PATH)
        return Path(value) if value else Path(default_path)

    def _refresh_db_status(self):
        try:
            working_dir = self._get_working_dir()
            db_path = DatabaseManager.get_database_path(working_dir)
            if db_path.exists():
                size_kb = db_path.stat().st_size / 1024
                modified = datetime.fromtimestamp(db_path.stat().st_mtime)
                channel_count = len(DatabaseManager.list_channels(working_dir))
                self.db_status_label.setText(
                    f"Database found: {db_path.name}  |  "
                    f"{size_kb:.0f} KB  |  "
                    f"{channel_count} channel(s)  |  "
                    f"Modified: {modified:%Y-%m-%d %H:%M}"
                )
                self.db_status_label.setStyleSheet(
                    f"color: {self.theme.get_color('text', 'secondary')}; font-size: 12px;"
                )
            else:
                self.db_status_label.setText(
                    f"No database found at: {db_path}"
                )
                self.db_status_label.setStyleSheet(
                    f"color: #e57373; font-size: 12px;"
                )
        except Exception as e:
            self.db_status_label.setText(f"Database status error: {e}")
            self.db_status_label.setStyleSheet(
                f"color: #e57373; font-size: 12px;"
            )

    def _load_settings(self):
        default_path = str(Path.home())
        value = self.settings.get('preferences/working_dir', default_path, SettingType.PATH)
        display = normalize_to_unc(value) if value else default_path
        self.working_dir_edit.setText(str(display))
        self._refresh_db_status()

    def _browse_working_dir(self):
        current = self.settings.get('preferences/working_dir', str(Path.home()), SettingType.PATH)
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Working Directory",
            str(current),
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            unc = normalize_to_unc(directory)
            self.working_dir_edit.setText(unc)
            self.settings.set('preferences/working_dir', Path(unc), SettingType.PATH)
            self.settings.sync()
            self._refresh_db_status()

    def _create_database(self):
        working_dir = self._get_working_dir()
        try:
            db_path = DatabaseManager.init_database(working_dir)
            QMessageBox.information(
                self,
                "Database",
                f"Database initialized:\n{db_path}"
            )
            self._refresh_db_status()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to create database:\n{e}"
            )


