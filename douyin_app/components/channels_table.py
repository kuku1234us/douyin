from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QPixmap, QIcon, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from qt_base_app.components.base_table import BaseTableModel, BaseTableView, ColumnDefinition

from douyin_app.models.database import DatabaseManager


@dataclass
class ChannelItem:
    id: int
    url: str
    title: str
    note: str
    avatar_path: str
    avatar_url: str
    sec_user_id: str
    latest_download_unix: int


class ChannelsModel(BaseTableModel):
    def __init__(self, source_objects: Optional[List[ChannelItem]] = None):
        # Thumbnail target size (pixels)
        self.THUMB_SIZE = 48
        columns = [
            ColumnDefinition(header="Thumbnail", data_key=lambda o: o.avatar_path, width=74, alignment=Qt.AlignmentFlag.AlignCenter),
            ColumnDefinition(header="Channel", data_key=lambda o: o.title or o.url, tooltip_key=lambda o: o.url, stretch=1),
            ColumnDefinition(header="Latest Download", data_key=lambda o: o.latest_download_unix, display_formatter=lambda x: ChannelsModel._fmt_unix(x), width=160),
        ]
        super().__init__(source_objects=source_objects or [], column_definitions=columns)

    def data(self, index, role: int = Qt.ItemDataRole.DisplayRole):
        # Add icon for thumbnail column
        if index.isValid() and role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            obj: ChannelItem = self._source_objects[index.row()]
            if obj.avatar_path:
                pm = QPixmap(obj.avatar_path)
                if not pm.isNull():
                    scaled = pm.scaled(self.THUMB_SIZE, self.THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    return QIcon(scaled)
        if role == Qt.ItemDataRole.UserRole:
            # Return the source object for selection and deletion logic
            if index.isValid() and 0 <= index.row() < len(self._source_objects):
                return self._source_objects[index.row()]
        return super().data(index, role)

    @staticmethod
    def _fmt_unix(val) -> str:
        try:
            v = int(val)
            if v <= 0:
                return "—"
            from datetime import datetime
            dt = datetime.fromtimestamp(v)
            return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return "—"


class ChannelsTable(QWidget):
    """
    Styled channels table leveraging BaseTableView/Model and ThemeManager.
    Delete key removes rows locally and we mirror deletions to DB.
    """

    rows_deleted = pyqtSignal(list)  # emits list of deleted IDs

    def __init__(self, parent=None):
        super().__init__(parent)
        self._working_dir: Optional[Path] = None

        self.view = BaseTableView(table_name="channels_table", parent=self)
        self.model = ChannelsModel([])
        self.view.setModel(self.model)
        self.view.items_removed.connect(self._on_items_removed)
        # Configure icon size and proportionally smaller row height
        thumb = self.model.THUMB_SIZE
        self.view.setIconSize(QSize(thumb, thumb))
        # Add padding to row height for visual spacing (scaled ~2/3 of previous padding)
        self.view.verticalHeader().setDefaultSectionSize(thumb + 11)
        try:
            # Adjust thumbnail column width to comfortably fit the icon
            self.view.horizontalHeader().resizeSection(0, thumb + 26)
        except Exception:
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        # Shortcut: Ctrl+0 resets latest download timestamps for selected channels
        self._reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self.view)
        self._reset_shortcut.activated.connect(self._reset_selected_timestamps)

    def set_working_dir(self, working_dir: Path):
        self._working_dir = Path(working_dir)

    def set_rows(self, rows: List[tuple]):
        # rows: [(id, url, title, note, avatar_path, avatar_url, sec_user_id, latest_download_unix), ...]
        def _resolve_avatar_path(stored: str) -> str:
            try:
                if not stored:
                    return ""
                p = Path(stored)
                if p.is_absolute():
                    return str(p)
                base_dir = (self._working_dir or Path.home())
                return str((base_dir / p))
            except Exception:
                return stored or ""

        items = [
            ChannelItem(
                id=r[0], url=r[1], title=r[2], note=r[3], avatar_path=_resolve_avatar_path(r[4]), avatar_url=r[5], sec_user_id=r[6], latest_download_unix=r[7]
            ) for r in rows
        ]
        self.model.set_source_objects(items)

    def _on_items_removed(self, removed_objects: List[ChannelItem]):
        try:
            ids = [obj.id for obj in removed_objects]
            if self._working_dir and ids:
                DatabaseManager.delete_channels_by_ids(self._working_dir, ids)
            self.rows_deleted.emit(ids)
        except Exception:
            # Swallow errors here; parent page can always refresh from DB on its side.
            pass

    def get_selected_items(self) -> List[ChannelItem]:
        try:
            selection_model = self.view.selectionModel()
            if not selection_model:
                return []
            # Get selected rows (prefer column 0 indexes)
            indexes = selection_model.selectedRows(0)
            selected: List[ChannelItem] = []
            for idx in indexes:
                obj = self.model.data(idx, Qt.ItemDataRole.UserRole)
                if isinstance(obj, ChannelItem):
                    selected.append(obj)
            return selected
        except Exception:
            return []

    def _reset_selected_timestamps(self) -> None:
        try:
            if not self._working_dir:
                return
            selected = self.get_selected_items()
            if not selected:
                return
            for item in selected:
                if item.sec_user_id:
                    DatabaseManager.set_latest_download_unix_by_secuid(self._working_dir, item.sec_user_id, 0)
                else:
                    DatabaseManager.set_latest_download_unix_by_url(self._working_dir, item.url, 0)
            # Reload rows to reflect changes
            rows = DatabaseManager.list_channels(self._working_dir)
            self.set_rows(rows)
        except Exception:
            pass


