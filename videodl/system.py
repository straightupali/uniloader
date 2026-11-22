"""OS helpers: open files, show in folder, start with Windows, restart."""
import os
import subprocess
import sys
from pathlib import Path

from .paths import APP_DIR, FROZEN

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "VideoDownloader"


def open_path(p):
    p = str(p)
    if os.name == "nt":
        os.startfile(p)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", p])


def reveal(p):
    p = Path(p)
    if os.name == "nt" and p.exists():
        subprocess.Popen(["explorer", f"/select,{p}"])
    elif sys.platform == "darwin" and p.exists():
        subprocess.Popen(["open", "-R", str(p)])
    else:
        open_path(p.parent if p.suffix else p)


def launch_command(extra=()):
    if FROZEN:
        return [sys.executable, *extra]
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return [str(pyw if pyw.exists() else exe), str(APP_DIR / "ytdl.py"), *extra]


def restart():
    flags = getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(launch_command(["--restart"]), creationflags=flags, close_fds=True)


# ---------- start with Windows ----------
def autostart_supported():
    return os.name == "nt"


def autostart_enabled():
    if not autostart_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            cmd = " ".join(f'"{c}"' for c in launch_command(["--tray"]))
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except OSError:
                pass
