#!/usr/bin/env python
import sys
import os

# Ensure project root on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from qt_base_app.app import create_application, run_application
from douyin_app.dashboard import DouyinMainWindow
from qt_base_app.models.settings_manager import SettingsManager, SettingType
from pathlib import Path
from douyin_app.models.path_utils import normalize_to_unc


def main():
    # Ensure working_dir stored as UNC to avoid drive letter remapping issues
    try:
        SettingsManager.initialize("DouyinFramework", "DouyinFramework")
        settings = SettingsManager.instance()
        wd = settings.get('preferences/working_dir', None, SettingType.PATH)
        if wd:
            unc = Path(normalize_to_unc(wd))
            if str(unc) != str(wd):
                settings.set('preferences/working_dir', unc, SettingType.PATH)
                settings.sync()
    except Exception:
        pass

    app, window = create_application(
        window_class=DouyinMainWindow,
        organization_name="DouyinFramework",
        application_name="DouyinFramework",
        config_path=os.path.join("resources", "douyin_app.yaml"),
        icon_paths=[
            os.path.join("douyin_app", "resources", "douyin.png"),
        ],
    )
    return run_application(app, window)


if __name__ == "__main__":
    sys.exit(main())


