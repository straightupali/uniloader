"""System tray icon (Windows/Linux). Callbacks are passed through `call_soon`
so they run on the Tk thread."""
import sys

from .icon import icon_image


class Tray:
    def __init__(self, call_soon, on_show, on_clipboard, on_folder, on_quit):
        self.ok = False
        self.icon = None
        if sys.platform == "darwin":  # pystray needs the main thread on macOS
            return
        try:
            import pystray
            item = pystray.MenuItem
            menu = pystray.Menu(
                item("Show Video Downloader", lambda: call_soon(on_show), default=True),
                item("Download link from clipboard", lambda: call_soon(on_clipboard)),
                item("Open downloads folder", lambda: call_soon(on_folder)),
                pystray.Menu.SEPARATOR,
                item("Quit", lambda: call_soon(on_quit)),
            )
            self.icon = pystray.Icon("VideoDownloader", icon_image(64), "Video Downloader", menu)
            self.icon.run_detached()
            self.ok = True
        except Exception:
            self.icon = None

    def notify(self, message, title="Video Downloader"):
        if self.ok:
            try:
                self.icon.notify(message[:250], title)
            except Exception:
                pass

    def stop(self):
        if self.ok:
            try:
                self.icon.stop()
            except Exception:
                pass
