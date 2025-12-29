from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem
from PyQt6.QtGui import QPixmap, QIcon, QShortcut, QKeySequence, QColor, QBrush, QPalette
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer

from qt_base_app.components.base_table import BaseTableModel, BaseTableView, ColumnDefinition

from douyin_app.models.database import DatabaseManager

# Optional icon library
try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except Exception:
    HAS_QTAWESOME = False


class _ChannelsTitleDelegate(QStyledItemDelegate):
    def __init__(self, model: 'ChannelsModel', parent=None):
        super().__init__(parent)
        self._model = model

    def paint(self, painter, option, index):
        if index.column() == 1 and hasattr(self._model, 'get_flash_color'):
            color = self._model.get_flash_color(index.row())
            if isinstance(color, QColor):
                pal = QPalette(option.palette)
                for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
                    pal.setColor(group, QPalette.ColorRole.Text, color)
                    pal.setColor(group, QPalette.ColorRole.HighlightedText, color)
                opt = QStyleOptionViewItem(option)
                opt.palette = pal
                return super().paint(painter, opt, index)
        return super().paint(painter, option, index)


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
        # Flash animation state for title column
        self._flash_states: dict[int, dict] = {}
        self._flash_timer = QTimer()
        self._flash_timer.setInterval(50)  # 10 ticks total for ~0.5s animation
        self._flash_timer.timeout.connect(self._advance_flash)
        columns = [
            ColumnDefinition(header="Thumbnail", data_key=lambda o: o.avatar_path, width=74, alignment=Qt.AlignmentFlag.AlignCenter),
            ColumnDefinition(header="Channel", data_key=lambda o: o.title or o.url, tooltip_key=lambda o: o.url, stretch=1),
            ColumnDefinition(header="Latest Download", data_key=lambda o: o.latest_download_unix, display_formatter=lambda x: ChannelsModel._fmt_unix(x), width=160),
            ColumnDefinition(header="", data_key=lambda o: "↺", width=60, alignment=Qt.AlignmentFlag.AlignCenter, tooltip_key=lambda o: "Reset latest download time"),
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
        # Use unicode glyph for reset column via DisplayRole (no DecorationRole override)
        # Foreground animation for channel title when copied
        if index.isValid() and role == Qt.ItemDataRole.ForegroundRole and index.column() == 1:
            row = index.row()
            state = self._flash_states.get(row)
            if state is not None:
                t = max(0.0, min(1.0, float(state.get('t', 0.0))))
                # Blend from white to green based on t
                base = QColor(255, 255, 255)
                green = QColor(0, 200, 83)
                r = int(base.red() + (green.red() - base.red()) * t)
                g = int(base.green() + (green.green() - base.green()) * t)
                b = int(base.blue() + (green.blue() - base.blue()) * t)
                return QBrush(QColor(r, g, b))

        if role == Qt.ItemDataRole.UserRole:
            # Return the source object for selection and deletion logic
            if index.isValid() and 0 <= index.row() < len(self._source_objects):
                return self._source_objects[index.row()]
        return super().data(index, role)

    def get_flash_color(self, row: int) -> Optional[QColor]:
        try:
            state = self._flash_states.get(row)
            if state is None:
                return None
            t = max(0.0, min(1.0, float(state.get('t', 0.0))))
            base = QColor(255, 255, 255)
            green = QColor(0, 200, 83)
            r = int(base.red() + (green.red() - base.red()) * t)
            g = int(base.green() + (green.green() - base.green()) * t)
            b = int(base.blue() + (green.blue() - base.blue()) * t)
            return QColor(r, g, b)
        except Exception:
            return None

    def flash_row(self, row: int) -> None:
        try:
            if row < 0 or row >= len(self._source_objects):
                return
            self._flash_states[row] = {'t': 0.0, 'dir': 1}
            if not self._flash_timer.isActive():
                self._flash_timer.start()
            idx = self.index(row, 1)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.ForegroundRole])
        except Exception:
            pass

    def _advance_flash(self) -> None:
        try:
            if not self._flash_states:
                self._flash_timer.stop()
                return
            step = 0.2  # 5 ticks to peak (250ms), 5 ticks back
            finished: List[int] = []
            for row, state in list(self._flash_states.items()):
                t = float(state.get('t', 0.0))
                d = int(state.get('dir', 1))
                t += step * d
                if t >= 1.0:
                    t = 1.0
                    state['dir'] = -1
                elif t <= 0.0 and d < 0:
                    finished.append(row)
                    continue
                state['t'] = t
                idx = self.index(row, 1)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.ForegroundRole])
            for row in finished:
                self._flash_states.pop(row, None)
            if not self._flash_states:
                self._flash_timer.stop()
        except Exception:
            self._flash_timer.stop()

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
        try:
            # Ensure our title color flash is visible even when the row is selected
            self.view.setItemDelegateForColumn(1, _ChannelsTitleDelegate(self.model, self.view))
        except Exception:
            pass
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

        # Handle clicks on reset column
        try:
            self.view.clicked.connect(self._on_cell_clicked)
        except Exception:
            pass

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

    def _on_cell_clicked(self, index):
        try:
            if not index.isValid():
                return
            # If clicked on the reset column
            if index.column() == len(self.model.column_definitions) - 1:
                obj = self.model.data(index, Qt.ItemDataRole.UserRole)
                if not obj or not self._working_dir:
                    return
                if getattr(obj, 'sec_user_id', None):
                    DatabaseManager.set_latest_download_unix_by_secuid(self._working_dir, obj.sec_user_id, 0)
                else:
                    DatabaseManager.set_latest_download_unix_by_url(self._working_dir, obj.url, 0)
                # Refresh table
                rows = DatabaseManager.list_channels(self._working_dir)
                self.set_rows(rows)
            # If clicked on the channel name column, copy title to clipboard
            elif index.column() == 1:
                obj = self.model.data(index, Qt.ItemDataRole.UserRole)
                if not obj:
                    return
                text = (obj.title or '').strip() or (obj.url or '')
                try:
                    QApplication.clipboard().setText(text)
                    # Trigger a brief green flash animation on the title cell
                    try:
                        self.model.flash_row(index.row())
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass


