from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import List, Callable, Optional

from douyin_app.models.download_workers import ChannelTask, download_channel_new_items


class DownloadManager:
    """
    Thin manager that runs async downloads in a background thread for UI pages.
    """

    def __init__(self, working_dir: Path, max_concurrency: int = 1):
        self.working_dir = Path(working_dir)
        self.max_concurrency = max(1, int(max_concurrency))
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

    def set_max_concurrency(self, value: int):
        with self._lock:
            self.max_concurrency = max(1, int(value))

    def cancel(self):
        self._cancel_event.set()

    def start_downloads(self, tasks: List[ChannelTask], on_complete: Optional[Callable]=None, on_progress: Optional[Callable[[str], None]]=None):
        # reset cancel state for new run
        self._cancel_event.clear()

        def runner():
            try:
                asyncio.run(self._run(tasks, on_progress))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._run(tasks, on_progress))
                loop.close()
            finally:
                if callable(on_complete):
                    try:
                        on_complete()
                    except Exception:
                        pass

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        self._thread = t

    async def _run(self, tasks: List[ChannelTask], on_progress: Optional[Callable[[str], None]] = None):
        # Iterate channels sequentially; each channel runs bounded concurrency inside
        total = len(tasks)
        channels_completed = 0
        for idx, task in enumerate(tasks, start=1):
            try:
                if callable(on_progress):
                    try:
                        msg = f"Preparing channel {idx}/{total}: {task.title or task.url}"
                        print(f"[DownloadManager] {msg}")
                        on_progress(msg)
                    except Exception:
                        pass
                # if cancelled, stop before starting next channel
                if self._cancel_event.is_set():
                    break
                await download_channel_new_items(
                    self.working_dir,
                    task,
                    self.max_concurrency,
                    should_stop=self._cancel_event.is_set,
                    progress=lambda text: on_progress(text) if callable(on_progress) else None,
                )
                # Mark channel completion
                channels_completed += 1
                if callable(on_progress):
                    try:
                        done_msg = f"Channel completed {channels_completed}/{total}: {task.title or task.url}"
                        print(f"[DownloadManager] {done_msg}")
                        on_progress(done_msg)
                    except Exception:
                        pass
            except Exception:
                # continue to next task on error
                continue


