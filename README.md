### Douyin Desktop Downloader

Modern Qt desktop app for managing Douyin/TikTok channel downloads with a local SQLite database.

### Features

- Add Douyin channels by profile URL
- Download new posts per channel with progress UI
- Store per-channel metadata and latest download timestamp
- Avatars and media folders inside your working directory

### Requirements

- Python 3.11+
- Windows 10/11 recommended
- Poetry or pip (we use Poetry in development)

### Quick Start

1. Install dependencies

```bash
poetry install
```

2. Run the desktop app

```bash
poetry run python run.py
```

### Working Directory (UNC recommended)

- Set your working directory in Preferences to a UNC path to avoid drive-letter changes, e.g.:
  - `\\\\server\\share\\WorkingDirectory\\`
- The app normalizes mapped drives (like `X:`) to UNC on startup and when saving preferences.

Directory layout created under working directory:

- `douyin.sqlite3` — app database
- `avatars/` — channel thumbnails
- `portrait/`, `landscape/` — downloaded media

### Database and Paths

- Database file: `<working_dir>/douyin.sqlite3`
- Thumbnails are stored as relative paths (e.g., `avatars/<sec_user_id>.jpg`).
- App resolves relative paths against the working directory at runtime.

### One-time Migrations

- Convert existing absolute avatar paths to relative:

```bash
poetry run python -m douyin_app.models.migrate_avatar_paths
```

- Verify paths:

```bash
poetry run python -m douyin_app.models.print_avatar_paths
```

### Troubleshooting

- If icons or thumbnails don’t show, ensure `avatars/` exists under your working directory and the DB contains relative paths (run the migration above).
- If your working directory points to a mapped drive letter, open Preferences and reselect the UNC path.

### License

This codebase includes components inspired by or derived from open-source projects. See `LICENSE` for details.
