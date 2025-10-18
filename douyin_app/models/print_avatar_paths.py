from __future__ import annotations

"""
Utility script to print current avatar path values stored in the database.

Usage:
  python -m douyin_app.models.print_avatar_paths

Behavior:
  - Reads working directory from app settings ('preferences/working_dir'),
    defaults to V:\ if unavailable
  - Prints id, url, avatar_path from channels table
"""

import sqlite3
from pathlib import Path

from .database import DatabaseManager
from qt_base_app.models.settings_manager import SettingsManager, SettingType


def main() -> int:
    # Initialize settings and resolve working directory
    try:
        SettingsManager.initialize("DouyinFramework", "DouyinFramework")
        settings = SettingsManager.instance()
        wd_value = settings.get('preferences/working_dir', str(Path('V:/')), SettingType.PATH)
        working_dir = wd_value if isinstance(wd_value, Path) else Path('V:/')
    except Exception:
        working_dir = Path('V:/')

    db_path = DatabaseManager.get_database_path(working_dir)
    if not db_path.exists():
        print(f"[print_avatar_paths] Database not found at: {db_path}")
        return 1

    print(f"[print_avatar_paths] Using database: {db_path}")
    with sqlite3.connect(db_path) as conn:
        try:
            cur = conn.execute("SELECT id, url, avatar_path FROM channels ORDER BY id DESC")
        except Exception as e:
            print(f"[print_avatar_paths] Failed to query channels: {e}")
            return 1
        rows = list(cur.fetchall())
        if not rows:
            print("[print_avatar_paths] No rows in channels table.")
            return 0
        for row_id, url, avatar_path in rows:
            print(f"id={row_id}\turl={url}\tavatar_path={avatar_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


