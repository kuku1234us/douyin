"""
Channels page: add new Douyin channels and list them.
"""
from pathlib import Path
import threading
import asyncio

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QMessageBox, QHBoxLayout, QLabel, QSpinBox
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from qt_base_app.models.settings_manager import SettingsManager, SettingType
from qt_base_app.theme.theme_manager import ThemeManager
from qt_base_app.components.round_button import RoundButton
from douyin_app.components.download_progress_overlay import DownloadProgressOverlay

from douyin_app.models.database import DatabaseManager
from douyin_app.components.channels_table import ChannelsTable, ChannelItem
from douyin_app.models.download_manager import DownloadManager
from douyin_app.models.download_workers import ChannelTask
from crawlers.douyin.web.web_crawler import DouyinWebCrawler


class ChannelsPage(QWidget):
    downloads_completed = pyqtSignal()
    progress_signal = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("channelsPage")
        self.setProperty('page_id', 'channels')

        self.settings = SettingsManager.instance()
        self.theme = ThemeManager.instance()

        self._setup_ui()
        self._ensure_db()
        self._reload()
        self.downloads_completed.connect(self._reload)
        self.downloads_completed.connect(self._on_downloads_complete)
        self.progress_signal.connect(self._on_progress_update)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        input_style = f"""
            background-color: {self.theme.get_color('background', 'tertiary')};
            color: {self.theme.get_color('text', 'primary')};
            border: 1px solid {self.theme.get_color('border', 'primary')};
            border-radius: 4px;
            padding: 8px;
        """

        # Top row: URL input + small concurrency control
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste Douyin user URL and press Enter…")
        self.url_input.setStyleSheet(input_style)
        self.url_input.returnPressed.connect(self._add_channel)

        max_label = QLabel("Max")
        max_label.setStyleSheet(f"color: {self.theme.get_color('text', 'secondary')};")

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setMinimum(1)
        self.concurrent_spin.setMaximum(8)
        saved_concurrency = self.settings.get('downloads/max_concurrency', 1, SettingType.INT)
        try:
            saved_val = int(saved_concurrency) if saved_concurrency is not None else 1
        except Exception:
            saved_val = 1
        if saved_val < 1:
            saved_val = 1
        self.concurrent_spin.setValue(saved_val)
        self.concurrent_spin.setToolTip("Max concurrent downloads")
        self.concurrent_spin.setFixedWidth(60)
        # Style spinbox to match inputs
        self.concurrent_spin.setStyleSheet(input_style)
        self.concurrent_spin.valueChanged.connect(lambda v: (self.settings.set('downloads/max_concurrency', int(v), SettingType.INT), self.settings.sync()))

        row_layout.addWidget(self.url_input, 1)
        row_layout.addWidget(max_label)
        row_layout.addWidget(self.concurrent_spin)

        self.table = ChannelsTable(self)
        self.table.rows_deleted.connect(lambda _ids: self._reload())

        layout.addWidget(row)
        layout.addWidget(self.table, 1)

        # Floating download button at bottom-right
        self.download_button = RoundButton(parent=self, icon_name='fa5s.download', diameter=48, icon_size=20, bg_opacity=0.5)
        self.download_button.setToolTip("Download selected channels")
        self.download_button.clicked.connect(self._on_download_clicked)

        # Temp Stop button (hidden initially)
        self.stop_button = RoundButton(parent=self, icon_name='fa5s.stop', diameter=48, icon_size=20, bg_opacity=0.5)
        self.stop_button.setToolTip("Stop downloads")
        self.stop_button.hide()
        self.stop_button.clicked.connect(self._on_stop_clicked)

        # Progress overlay
        self.progress_overlay = DownloadProgressOverlay(self)

    def _working_dir(self) -> Path:
        default_path = str(Path.home())
        return Path(self.settings.get('preferences/working_dir', default_path, SettingType.PATH))

    def _ensure_db(self):
        try:
            DatabaseManager.init_database(self._working_dir())
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to initialize DB:\n{e}")

    def _add_channel(self):
        url = self.url_input.text().strip()
        if not url:
            return
        try:
            # Insert or ensure row exists quickly
            DatabaseManager.add_channel(self._working_dir(), url=url)
            # Fetch metadata asynchronously (run in a Qt-safe way)
            self._fetch_and_update_metadata(url)
            self.url_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to add channel:\n{e}")

    def _reload(self):
        try:
            wd = self._working_dir()
            self.table.set_working_dir(wd)
            rows = DatabaseManager.list_channels(wd)
            self.table.set_rows(rows)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load channels:\n{e}")

    def _fetch_and_update_metadata(self, url: str):
        # Since our stack isn't using Qt threads here, do a simple asyncio run in thread if needed.
        # Use DouyinWebCrawler to derive sec_user_id and profile info; then store avatar and title.
        import asyncio, httpx, os

        async def run():
            crawler = DouyinWebCrawler()
            # Extract sec_user_id from profile URL
            try:
                sec = await crawler.get_sec_user_id(url)
            except Exception:
                sec = None

            title = None
            avatar_url = None
            if sec:
                try:
                    profile = await crawler.handler_user_profile(sec)
                    # Best-effort extraction
                    user = profile.get('user', {}) if isinstance(profile, dict) else {}
                    title = user.get('nickname') or user.get('unique_id')
                    avatar_url = (
                        (user.get('avatar_larger') or {}).get('url_list', [None])[0]
                        or (user.get('avatar_thumb') or {}).get('url_list', [None])[0]
                    )
                except Exception:
                    pass

            avatar_path = None
            if avatar_url:
                headers = (await crawler.get_douyin_headers())["headers"]
                # Save avatars under <working_dir>/avatars
                base_dir = self._working_dir()
                target_dir = base_dir / "avatars"
                target_dir.mkdir(parents=True, exist_ok=True)
                filename = (sec or 'unknown') + ".jpg"
                avatar_path = target_dir / filename
                try:
                    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
                        r = await client.get(avatar_url)
                        r.raise_for_status()
                        with open(avatar_path, 'wb') as f:
                            f.write(r.content)
                except Exception:
                    avatar_path = None

            DatabaseManager.upsert_channel_metadata(
                self._working_dir(),
                url=url,
                title=title,
                sec_user_id=sec,
                avatar_url=avatar_url,
                # Store relative path (under working_dir) instead of absolute
                avatar_path=(str(avatar_path.relative_to(base_dir)) if avatar_path else None),
            )

        # Execute and refresh
        try:
            asyncio.run(run())
        except RuntimeError:
            # If already in an event loop, fallback to creating a new loop
            loop = asyncio.new_event_loop()
            loop.run_until_complete(run())
            loop.close()

        self._reload()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            margin = 20
            btn_w = self.download_button.width()
            btn_h = self.download_button.height()
            self.download_button.move(self.width() - margin - btn_w, self.height() - margin - btn_h)
            self.download_button.raise_()
            # position stop button above download button when visible
            # always position stop button next to download button (to the left with a gap)
            s_w = self.stop_button.width()
            s_h = self.stop_button.height()
            gap = 10
            self.stop_button.move(self.width() - margin - btn_w - gap - s_w, self.height() - margin - s_h)
            if self.stop_button.isVisible():
                self.stop_button.raise_()
            # center overlay
            if self.progress_overlay.isVisible():
                self.progress_overlay.adjustSize()
                ow = self.progress_overlay.width()
                oh = self.progress_overlay.height()
                ox = (self.width() - ow) // 2
                oy = 60
                self.progress_overlay.setGeometry(ox, oy, ow, oh)
                self.progress_overlay.raise_()
        except Exception:
            pass

    # --- Downloads ---
    def _on_download_clicked(self):
        try:
            max_c = int(self.concurrent_spin.value()) if self.concurrent_spin.value() else 1
        except Exception:
            max_c = 1
        wd = self._working_dir()
        # Build tasks from selection or all rows
        items = self.table.get_selected_items()
        if not items:
            rows = DatabaseManager.list_channels(wd)
            items = [
                ChannelItem(id=r[0], url=r[1], title=r[2], note=r[3], avatar_path=r[4], avatar_url=r[5], sec_user_id=r[6], latest_download_unix=r[7])
                for r in rows
            ]
        tasks = [ChannelTask(id=it.id, url=it.url, title=it.title, sec_user_id=it.sec_user_id or None, latest_download_unix=it.latest_download_unix) for it in items]
        self._dl_manager = DownloadManager(wd, max_concurrency=max_c)
        # show stop button + overlay during run
        self.stop_button.show()
        try:
            self.progress_overlay.set_status("Preparing…")
            self.progress_overlay.set_channels_progress(0, 1)
            self.progress_overlay.set_videos_progress(0, 1)
            self.progress_overlay.show_overlay()
        except Exception:
            pass
        self._dl_manager.start_downloads(
            tasks,
            on_complete=lambda: self.downloads_completed.emit(),
            on_progress=lambda msg: self.progress_signal.emit(msg),
        )

    def _on_progress_update(self, text: str):
        # For now, no dedicated overlay widget exists; we can update window title subtly.
        # Expect structured messages like: "Preparing channel i/n: ..." or "Downloaded k/m for ..."
        try:
            if text and text.startswith("Preparing channel "):
                # parse i/n
                part = text.split(':', 1)[0]
                frac = part.replace("Preparing channel ", "").strip()
                cur, total = frac.split('/')
                # Preparing does not advance the channels-completed bar
                self.progress_overlay.set_status(text)
            elif text and text.startswith("Downloaded ") and " for " in text:
                # "Downloaded k/m for ..."
                head = text.split(' for ', 1)[0]
                nums = head.replace("Downloaded ", "").strip()
                cur, total = nums.split('/')
                self.progress_overlay.set_status(text)
                self.progress_overlay.set_videos_progress(int(cur), int(total))
            elif text and text.startswith("Channel completed "):
                # Update top bar on channel completion
                part = text.split(':', 1)[0]
                frac = part.replace("Channel completed ", "").strip()
                cur, total = frac.split('/')
                self.progress_overlay.set_status(text)
                self.progress_overlay.set_channels_progress(int(cur), int(total))
            else:
                self.progress_overlay.set_status(text)
        except Exception:
            self.progress_overlay.set_status(text)

    def _on_downloads_complete(self):
        # Hide stop button, emit completion for table refresh
        try:
            self.stop_button.hide()
        except Exception:
            pass
        try:
            self.progress_overlay.hide_overlay()
        except Exception:
            pass
        # Do NOT re-emit downloads_completed here to avoid recursive signal loops

    def _on_stop_clicked(self):
        try:
            if hasattr(self, '_dl_manager') and self._dl_manager:
                self._dl_manager.cancel()
        except Exception:
            pass



