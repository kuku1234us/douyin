"""
Preferences page for the Douyin application (minimal version).
Contains one setting: Working Directory.
"""
from pathlib import Path

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
        main_layout.addStretch(1)

    def _load_settings(self):
        default_path = str(Path.home())
        value = self.settings.get('preferences/working_dir', default_path, SettingType.PATH)
        display = normalize_to_unc(value) if value else default_path
        self.working_dir_edit.setText(str(display))

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

    def _create_database(self):
        # Resolve working directory
        working_dir = self.settings.get('preferences/working_dir', str(Path.home()), SettingType.PATH)
        try:
            db_path = DatabaseManager.init_database(Path(working_dir))
            QMessageBox.information(
                self,
                "Database",
                f"Database initialized:\n{db_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to create database:\n{e}"
            )


