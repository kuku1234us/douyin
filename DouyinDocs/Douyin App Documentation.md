## Introduction

This desktop app is a minimal Douyin client scaffolded on top of the `qt_base_app` framework (PyQt6). It provides a clean starting point with a single sidebar item and a themed dashboard page, plus a packaging pipeline to ship a Windows EXE.

## What’s implemented

- **App shell**: `run.py` wires the framework and loads `DouyinMainWindow` with one sidebar item (Home).
- **Window**: `douyin_app/dashboard.py` defines `DouyinMainWindow` and registers pages.
- **Dashboard page**: `douyin_app/pages/dashboard_page.py` shows a themed title and the message “Welcome to Douyin Framework”.
- **Config**: `resources/douyin_app.yaml` sets app title, window sizing, and sidebar structure.
- **App icon**: `douyin_app/resources/douyin.png` (runtime) and auto-converted `douyin.ico` during build.
- **Build pipeline**: `DouyinFramework.spec` + `build.ps1` (converts PNG→ICO via Pillow, then runs PyInstaller). Output EXE is `dist\DouyinFramework.exe`.
- **Utility scripts**:
  - `test.py`: programmatic Douyin downloader using project crawlers. Also supports getting the latest 3 videos for a user URL.
  - `testcookie.py`: extracts a Douyin cookie from Firefox (with the browser closed) to use in crawler config.

## Run the app (dev)

Prereqs: Poetry (and Python 3.11). From repo root:

```powershell
poetry install --no-root
poetry run python run.py
```

You’ll see one sidebar item “Home” and the dashboard greeting.

## Build the Windows EXE

```powershell
# normal build
./build.ps1

# clean build
./build.ps1 -Clean
```

Results:

- One-file: `dist\DouyinFramework.exe`

`build.ps1` will:

- Ensure PyInstaller is available in the Poetry venv
- Convert `douyin_app/resources/douyin.png` → `douyin_app/resources/douyin.ico` (via Pillow)
- Run `pyinstaller DouyinFramework.spec`

## Key files and structure

- `run.py`: app entrypoint using `qt_base_app.create_application(...)`
- `resources/douyin_app.yaml`: app title, window sizing, sidebar items
- `douyin_app/dashboard.py`: `DouyinMainWindow` (registers pages)
- `douyin_app/pages/dashboard_page.py`: top-level dashboard page
- `douyin_app/resources/douyin.png`: app icon (PNG)
- `DouyinFramework.spec`: PyInstaller spec; bundles `resources/`, `qt_base_app/theme/theme.yaml`, and EXE icon
- `build.ps1`: build script (PNG→ICO + PyInstaller)
- Crawlers (from API project): under `crawlers/...` for programmatic Douyin/TikTok access

## Cookies for Douyin crawlers (optional)

For reliable Douyin API access, set a valid cookie in:

- `crawlers/douyin/web/config.yaml` → `TokenManager -> douyin -> headers -> Cookie`

Helpers:

- Extract from Firefox (closed): `poetry run python testcookie.py` (prints a Cookie header)
- Paste into the YAML; wrap in single quotes

## Programmatic downloads (optional)

- Single video or latest videos sample: see `test.py`
  - Set `userurl` (Douyin profile URL) to fetch latest posts, or pass a single video URL
  - Downloads saved locally; relies on crawler headers from the YAML config

## Next steps

- Add new pages under `douyin_app/pages/` and register them in `DouyinMainWindow.initialize_pages()`
- Add reusable UI pieces under `douyin_app/components/`
- Integrate crawler-powered features (e.g., user feed listing, batch downloads) into dashboard or dedicated pages
