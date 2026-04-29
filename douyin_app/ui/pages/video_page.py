"""
Video page: download a single Douyin video by URL.
"""
from pathlib import Path
import threading
import asyncio

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel
from PyQt6.QtCore import pyqtSignal

from qt_base_app.models.settings_manager import SettingsManager, SettingType
from qt_base_app.theme.theme_manager import ThemeManager
from crawlers.douyin.web.web_crawler import DouyinWebCrawler
from douyin_app.models.download_workers import build_headers, download_aweme_video


class VideoPage(QWidget):
    _status_signal = pyqtSignal(str)
    _finished_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoPage")
        self.setProperty('page_id', 'video')

        self.settings = SettingsManager.instance()
        self.theme = ThemeManager.instance()
        self._downloading = False

        self._setup_ui()
        self._status_signal.connect(self._on_status)
        self._finished_signal.connect(self._on_finished)

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

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste Douyin video URL and press Enter\u2026")
        self.url_input.setStyleSheet(input_style)
        self.url_input.returnPressed.connect(self._download_video)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"color: {self.theme.get_color('text', 'secondary')}; font-size: 13px;"
        )

        layout.addWidget(self.url_input)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _working_dir(self) -> Path:
        default_path = str(Path.home())
        value = self.settings.get('preferences/working_dir', default_path, SettingType.PATH)
        return Path(value) if value else Path(default_path)

    def _download_video(self):
        url = self.url_input.text().strip()
        if not url or self._downloading:
            return

        self._downloading = True
        self.url_input.setEnabled(False)
        self._set_status("Resolving video ID\u2026", error=False)

        def runner():
            try:
                asyncio.run(self._async_download(url))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._async_download(url))
                loop.close()
            except Exception as e:
                self._status_signal.emit(f"Error: {e}")
            finally:
                self._finished_signal.emit()

        threading.Thread(target=runner, daemon=True).start()

    async def _async_download(self, url: str):
        crawler = DouyinWebCrawler()

        self._status_signal.emit("Extracting video ID\u2026")
        aweme_id = await crawler.get_aweme_id(url)
        if not aweme_id:
            self._status_signal.emit("Error: Could not extract video ID from URL.")
            return

        self._status_signal.emit(f"Fetching metadata for {aweme_id}\u2026")
        resp = await crawler.fetch_one_video(aweme_id)
        detail = (resp or {}).get("aweme_detail")
        if not detail:
            self._status_signal.emit("Error: Could not fetch video details.")
            return

        video = (detail.get("video") or {})
        width = int(video.get("width") or 0)
        height = int(video.get("height") or 0)
        create_time = int(detail.get("create_time") or 0)

        play_addr = video.get("play_addr") or {}
        uri = play_addr.get("uri")
        if uri:
            nwm_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"
        else:
            url0 = (play_addr.get("url_list") or [None])[0]
            nwm_url = str(url0).replace("playwm", "play") if url0 else None

        if not nwm_url:
            self._status_signal.emit("Error: No download URL found in video data.")
            return

        base_dir = self._working_dir()
        (base_dir / "portrait").mkdir(parents=True, exist_ok=True)
        (base_dir / "landscape").mkdir(parents=True, exist_ok=True)

        desc = detail.get("desc") or aweme_id
        self._status_signal.emit(f"Downloading: {desc}")

        headers = await build_headers(crawler)
        result = await download_aweme_video(
            headers, base_dir, aweme_id, create_time, width, height, nwm_url,
        )

        if result:
            folder = "landscape" if (width and height and width >= height) else "portrait"
            filename = f"{create_time}_{aweme_id}.mp4"
            self._status_signal.emit(f"Saved to {folder}/{filename}")
        else:
            self._status_signal.emit("Error: Download failed.")

    def _set_status(self, text: str, error: bool = False):
        color = "#e57373" if error else self.theme.get_color('text', 'secondary')
        self.status_label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self.status_label.setText(text)

    def _on_status(self, text: str):
        is_error = text.startswith("Error:")
        self._set_status(text, error=is_error)

    def _on_finished(self):
        self._downloading = False
        self.url_input.setEnabled(True)
        if not self.status_label.text().startswith("Error:"):
            self.url_input.clear()
        self.url_input.setFocus()
