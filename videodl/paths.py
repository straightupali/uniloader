"""Where things live: app files, user data, bundled tools."""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Video Downloader"
FROZEN = getattr(sys, "frozen", False)  # True inside the Setup.exe build

# Folder that holds the app (and the ffmpeg/, deno/, chrome_extension/ folders)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
# Folder that holds bundled resources (PyInstaller unpacks them to _MEIPASS)
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ASSETS = RES_DIR / "assets"
EXTENSION_DIR = APP_DIR / "chrome_extension"


def _data_dir():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "VideoDownloader"


DATA_DIR = _data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
OLD_CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "YTDownloader" / "config.json"
DEFAULT_FOLDER = Path.home() / "Downloads" / "Video Downloader"
YTDLP_ZIP = DATA_DIR / "yt-dlp.zip"  # updated yt-dlp for the Setup.exe build

EXE = ".exe" if os.name == "nt" else ""


def ffmpeg_dir():
    """Bundled ffmpeg folder, or None to use the one on PATH."""
    local = APP_DIR / "ffmpeg"
    return str(local) if (local / f"ffmpeg{EXE}").exists() else None


def has_ffmpeg():
    return bool(ffmpeg_dir() or shutil.which("ffmpeg"))


def deno_path():
    """Deno is the JavaScript runtime yt-dlp needs for YouTube."""
    local = APP_DIR / "deno" / f"deno{EXE}"
    if local.exists():
        return str(local)
    return shutil.which("deno")


def aria2c_path():
    """aria2c downloads one file over several connections at once (much faster)."""
    local = APP_DIR / "aria2" / f"aria2c{EXE}"
    if local.exists():
        return str(local)
    return shutil.which("aria2c")
