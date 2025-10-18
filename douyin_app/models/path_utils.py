from __future__ import annotations

import os
import platform
import ctypes
from ctypes import wintypes
from ctypes import byref, create_unicode_buffer, c_ulong
from pathlib import Path


def normalize_to_unc(path: str | Path) -> str:
    """
    On Windows, convert a drive-letter network path (e.g., V:\\share\folder)
    to its UNC form (e.g., \\server\share\folder). If conversion fails or not
    applicable, return the original path string.
    """
    p = str(path) if isinstance(path, (str, Path)) else str(path)
    if platform.system() != "Windows":
        return p
    # Already a UNC path
    if p.startswith("\\\\"):
        return p
    # Split drive letter from the rest
    drive, tail = os.path.splitdrive(p)
    if not drive:
        return p
    try:
        # Query network mapping for the drive letter (e.g., 'V:')
        WNetGetConnectionW = ctypes.windll.mpr.WNetGetConnectionW
        buf_size = c_ulong(1024)
        remote_name_buf = create_unicode_buffer(buf_size.value)
        result = WNetGetConnectionW(drive, remote_name_buf, byref(buf_size))
        if result == 0:
            remote = remote_name_buf.value  # e.g., \\server\share
            # Ensure tail uses backslashes and is prefixed with a backslash
            tail_norm = tail.replace('/', '\\')
            if tail_norm and not tail_norm.startswith('\\'):
                tail_norm = '\\' + tail_norm
            return remote + tail_norm
        return p
    except Exception:
        return p


