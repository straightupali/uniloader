"""Uniloader - start here.

  ytdl.py                       open the window
  ytdl.py <url | ytdl://...>    add a link (used by the Chrome button)
  ytdl.py --tray                start hidden in the tray (Start with Windows)
"""
import os
import sys
from urllib.parse import parse_qs, urlparse


def parse_link(arg):
    """Plain URL, or ytdl://?u=<url>&m=<video|audio|options> from the Chrome button."""
    mode = ""
    if arg.lower().startswith("ytdl:"):
        q = parse_qs(urlparse(arg).query)
        arg, mode = q.get("u", [""])[0], q.get("m", [""])[0]
    if not arg.lower().startswith(("http://", "https://")):
        return None
    return {"url": arg, "mode": mode if mode in ("video", "audio", "options") else ""}


def _setup_logging():
    """pythonw / the .exe have no console; send output to a log file instead."""
    from videodl.paths import DATA_DIR
    log = DATA_DIR / "app.log"
    try:
        if log.exists() and log.stat().st_size > 1_000_000:
            log.unlink()
        f = open(log, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
    except OSError:
        sys.stdout = sys.stderr = open(os.devnull, "w")


def main():
    args = sys.argv[1:]
    restarted = "--restart" in args
    tray = "--tray" in args
    links = [l for l in (parse_link(a) for a in args if not a.startswith("--")) if l]
    message = {"links": links, "show": not tray}

    if sys.stdout is None or "pythonw" in sys.executable.lower() or getattr(sys, "frozen", False):
        _setup_logging()

    from videodl import ipc
    if not restarted and ipc.send_to_running(message):
        return  # the running app took the links

    if os.name == "nt":  # own taskbar identity: shows our icon instead of Python's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Uniloader.App")
        except Exception:
            pass

    from videodl import ytdlp_loader
    ytdlp_loader.install()

    from videodl.ui import App
    App(incoming=message, start_hidden=tray, restarted=restarted).mainloop()


if __name__ == "__main__":
    main()
