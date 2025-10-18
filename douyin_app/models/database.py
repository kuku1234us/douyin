from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


class DatabaseManager:
    """
    Simple SQLite database manager for the Douyin app.

    Responsibilities:
    - Create a database file under <working_dir>
    - Initialize base schema (channels table)
    """

    DEFAULT_FILENAME = "douyin.sqlite3"

    @classmethod
    def get_database_path(cls, working_dir: Path) -> Path:
        base_dir = Path(working_dir).expanduser().resolve()
        return base_dir / cls.DEFAULT_FILENAME

    @classmethod
    def init_database(cls, working_dir: Path) -> Path:
        """
        Ensure database directory and file exist, then initialize schema.

        Returns: Path to the database file.
        """
        db_path = cls.get_database_path(working_dir)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            # Base table: channels we follow
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    sec_user_id TEXT,
                    avatar_url TEXT,
                    avatar_path TEXT,
                    latest_download_unix INTEGER,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Ensure columns exist for legacy DBs
            cls._ensure_column(conn, 'channels', 'sec_user_id', 'TEXT')
            cls._ensure_column(conn, 'channels', 'avatar_url', 'TEXT')
            cls._ensure_column(conn, 'channels', 'avatar_path', 'TEXT')
            cls._ensure_column(conn, 'channels', 'latest_download_unix', 'INTEGER')
            conn.commit()

        return db_path

    @classmethod
    def add_channel(cls, working_dir: Path, url: str, title: Optional[str] = None, note: Optional[str] = None) -> None:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO channels (url, title, note) VALUES (?, ?, ?)",
                (url.strip(), title, note)
            )
            conn.commit()

    @classmethod
    def list_channels(cls, working_dir: Path) -> list[tuple]:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT id, url, COALESCE(title, ''), COALESCE(note, ''), COALESCE(avatar_path, ''), COALESCE(avatar_url, ''), COALESCE(sec_user_id, ''), COALESCE(latest_download_unix, 0)\n"
                "FROM channels ORDER BY id DESC"
            )
            return list(cur.fetchall())

    @classmethod
    def upsert_channel_metadata(
        cls,
        working_dir: Path,
        url: str,
        title: Optional[str],
        sec_user_id: Optional[str],
        avatar_url: Optional[str],
        avatar_path: Optional[str],
        note: Optional[str] = None,
    ) -> None:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                (
                    "INSERT INTO channels (url, title, sec_user_id, avatar_url, avatar_path, note)\n"
                    "VALUES (?, ?, ?, ?, ?, ?)\n"
                    "ON CONFLICT(url) DO UPDATE SET\n"
                    "  title=excluded.title,\n"
                    "  sec_user_id=excluded.sec_user_id,\n"
                    "  avatar_url=excluded.avatar_url,\n"
                    "  avatar_path=excluded.avatar_path,\n"
                    "  note=COALESCE(excluded.note, channels.note)"
                ),
                (url.strip(), title, sec_user_id, avatar_url, avatar_path, note)
            )
            conn.commit()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, coltype: str) -> None:
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

    # --- Track latest downloaded video time (epoch seconds) per channel ---
    @classmethod
    def set_latest_download_unix_by_url(cls, working_dir: Path, url: str, unix_ts: int) -> None:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("UPDATE channels SET latest_download_unix=? WHERE url=?", (int(unix_ts), url.strip()))
            if cur.rowcount == 0:
                # Create row if missing
                conn.execute(
                    "INSERT OR IGNORE INTO channels (url, latest_download_unix) VALUES (?, ?)",
                    (url.strip(), int(unix_ts))
                )
            conn.commit()

    @classmethod
    def get_latest_download_unix_by_url(cls, working_dir: Path, url: str) -> Optional[int]:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("SELECT latest_download_unix FROM channels WHERE url=?", (url.strip(),))
            row = cur.fetchone()
            if not row:
                return None
            value = row[0]
            return int(value) if value is not None else None

    @classmethod
    def set_latest_download_unix_by_secuid(cls, working_dir: Path, sec_user_id: str, unix_ts: int) -> None:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE channels SET latest_download_unix=? WHERE sec_user_id=?",
                (int(unix_ts), sec_user_id)
            )
            conn.commit()

    @classmethod
    def get_latest_download_unix_by_secuid(cls, working_dir: Path, sec_user_id: str) -> Optional[int]:
        db_path = cls.get_database_path(working_dir)
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("SELECT latest_download_unix FROM channels WHERE sec_user_id=?", (sec_user_id,))
            row = cur.fetchone()
            if not row:
                return None
            value = row[0]
            return int(value) if value is not None else None

    @classmethod
    def delete_channels_by_ids(cls, working_dir: Path, ids: list[int]) -> None:
        if not ids:
            return
        db_path = cls.get_database_path(working_dir)
        placeholders = ",".join(["?"] * len(ids))
        with sqlite3.connect(db_path) as conn:
            conn.execute(f"DELETE FROM channels WHERE id IN ({placeholders})", ids)
            conn.commit()


