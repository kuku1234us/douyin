from __future__ import annotations

"""
One-time migration utility to convert absolute avatar paths stored in the
database into paths relative to <working_dir>/DouyinDirectory.

Usage:
  python -m douyin_app.models.migrate_avatar_paths

Behavior:
  - Reads the working directory from application settings key 'preferences/working_dir'.
  - If unavailable, defaults to V:\\
  - Migrates channels.avatar_path from absolute to relative paths.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Tuple

from .database import DatabaseManager
from qt_base_app.models.settings_manager import SettingsManager, SettingType


def _to_relative_under_base(working_dir: Path, path_str: str) -> str:
    """
    Convert an absolute path to be relative to <working_dir>.
    If already relative, return as-is. If the standard base component
    (DatabaseManager.DEFAULT_SUBDIR) is present in the absolute path, strip up
    to and including that component. Otherwise, best-effort fallback to
    'avatars/<filename>'.
    """
    if not path_str:
        return path_str
    p = Path(path_str)
    if not p.is_absolute():
        return path_str

    # Try relative_to working_dir directly
    try:
        rel = p.relative_to(Path(working_dir))
        return str(rel)
    except Exception:
        # Final fallback: keep only filename under avatars/
        return str(Path("avatars") / p.name)


def migrate_avatar_paths_to_relative(
    working_dir: Path, *, dry_run: bool = False, verbose: bool = True
) -> Tuple[int, int]:
    """
    Migrate existing rows in channels.avatar_path from absolute to relative.

    Returns: (total_rows_scanned, rows_updated)
    """
    db_path = DatabaseManager.get_database_path(working_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at: {db_path}")

    total = 0
    updated = 0

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT id, avatar_path FROM channels")
        rows = list(cur.fetchall())
        total = len(rows)

        to_update: list[tuple[str, int]] = []
        for row_id, avatar_path in rows:
            try:
                stored = avatar_path or ""
                new_rel = _to_relative_under_base(working_dir, stored)
                if new_rel != stored:
                    to_update.append((new_rel, row_id))
                    if verbose:
                        print(f"[migrate] id={row_id}: '{stored}' -> '{new_rel}'")
            except Exception as e:
                if verbose:
                    print(f"[migrate][WARN] id={row_id}: failed to convert '{avatar_path}': {e}")

        if not dry_run and to_update:
            conn.executemany("UPDATE channels SET avatar_path=? WHERE id=?", to_update)
            conn.commit()
            updated = len(to_update)
        else:
            updated = len(to_update)

    return total, updated


def main() -> int:
    # Initialize SettingsManager with the same org/app names as the main app
    try:
        SettingsManager.initialize("DouyinFramework", "DouyinFramework")
        settings = SettingsManager.instance()
        # Try to read working_dir; default to V:\ if missing/invalid
        wd_value = settings.get('preferences/working_dir', str(Path('V:/')), SettingType.PATH)
        working_dir = wd_value if isinstance(wd_value, Path) else Path('V:/')
    except Exception:
        working_dir = Path('V:/')

    total, updated = migrate_avatar_paths_to_relative(working_dir, dry_run=False, verbose=True)
    print(f"Scanned {total} rows; updated {updated} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


