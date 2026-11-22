"""Lets the Setup.exe build use a newer yt-dlp downloaded by the updater.

The .exe has yt-dlp frozen inside it, so pip can't update it. Instead the updater
downloads yt-dlp's official zip build to the data folder, and this finder makes
Python import yt_dlp from that zip before the frozen copy.
"""
import importlib.abc
import sys
import zipimport

from .paths import FROZEN, YTDLP_ZIP


class _ZipFirst(importlib.abc.MetaPathFinder):
    def __init__(self, archive):
        self.archive = str(archive)

    def find_spec(self, name, path=None, target=None):
        if name == "yt_dlp":
            return zipimport.zipimporter(self.archive).find_spec(name)
        if name.startswith("yt_dlp."):
            for p in path or []:
                if str(p).startswith(self.archive):
                    return zipimport.zipimporter(str(p)).find_spec(name)
        return None


def install(force=False):
    if not (FROZEN or force) or not YTDLP_ZIP.exists():
        return False
    finder = _ZipFirst(YTDLP_ZIP)
    sys.meta_path.insert(0, finder)
    try:
        import yt_dlp
        return bool(yt_dlp)
    except Exception:  # broken download: fall back to the bundled copy
        sys.meta_path.remove(finder)
        for m in [m for m in sys.modules if m == "yt_dlp" or m.startswith("yt_dlp.")]:
            del sys.modules[m]
        try:
            YTDLP_ZIP.unlink()
        except OSError:
            pass
        return False
