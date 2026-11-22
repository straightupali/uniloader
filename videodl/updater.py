"""Keeps yt-dlp up to date (sites change often, old versions stop working)."""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

from .paths import FROZEN, YTDLP_ZIP

UA = {"User-Agent": "VideoDownloader"}


def current_version():
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "?"


def update():
    """Returns (changed, version). Raises on failure. Takes effect after a restart."""
    return _update_zip() if FROZEN else _update_pip()


def _pip_version():
    try:
        from importlib.metadata import version
        return version("yt-dlp")
    except Exception:
        return None


def _update_pip():
    before = _pip_version()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "--disable-pip-version-check",
         "yt-dlp[default]"],
        capture_output=True, text=True, creationflags=flags, timeout=600)
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "pip failed")
    after = _pip_version()
    return after != before, after or "?"


def _latest_tag():
    req = urllib.request.Request(
        "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
        headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["tag_name"]


def _update_zip():
    latest = _latest_tag()
    if latest == current_version():
        return False, latest
    tmp = YTDLP_ZIP.with_suffix(".part")
    req = urllib.request.Request(
        "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp", headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if not zipfile.is_zipfile(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("downloaded file is not valid")
    os.replace(tmp, YTDLP_ZIP)
    return True, latest
