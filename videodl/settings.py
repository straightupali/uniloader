"""Settings, download history and the saved queue (JSON files in the user data folder)."""
import json
import os
import threading
import time

from .paths import DATA_DIR, DEFAULT_FOLDER, OLD_CONFIG

DEFAULTS = {
    # Download tab (also used for Chrome / clipboard downloads)
    "folder": str(DEFAULT_FOLDER),
    "format": "MP4 (video)",
    "video_quality": "Best",
    "audio_quality": "High (320 kbps)",
    "cookies": "No login",
    "playlist": False,
    "subtitles": False,
    "embed_thumbnail": True,
    "embed_metadata": True,
    # Settings tab
    "theme": "Dark",
    "color_theme": "Indigo",
    "tooltips": True,
    "template": "%(title)s.%(ext)s",
    "sub_langs": "en",
    "speed_limit": "",
    "retries": 10,
    "parallel": 1,
    "skip_existing": True,
    "mp4_compat": True,
    "connections": 8,
    "precise_cuts": False,
    "clipboard_watch": True,
    "auto_update": True,
    "close_to_tray": True,
    "last_update_check": 0,
}

# Keys copied into every download job
JOB_KEYS = ["folder", "format", "video_quality", "audio_quality", "cookies", "playlist",
            "subtitles", "embed_thumbnail", "embed_metadata", "template", "sub_langs",
            "speed_limit", "retries", "skip_existing", "mp4_compat", "connections", "precise_cuts"]


class JsonFile:
    def __init__(self, name, default):
        self.path = DATA_DIR / name
        self.default = default
        self.lock = threading.Lock()

    def load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self.default() if callable(self.default) else self.default

    def save(self, data):
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                pass


class Config(dict):
    def __init__(self):
        self._file = JsonFile("config.json", dict)
        data = dict(DEFAULTS)
        if self._file.path.exists():
            data.update(self._file.load())
        else:  # bring over the folder/format from the first version of the app
            try:
                old = json.loads(OLD_CONFIG.read_text(encoding="utf-8"))
                data.update({k: v for k, v in old.items() if k in ("folder", "format", "cookies")})
            except Exception:
                pass
        super().__init__(data)

    def set(self, key, value, save=True):
        self[key] = value
        if save:
            self.save()

    def save(self):
        self._file.save(dict(self))

    def job_settings(self):
        return {k: self[k] for k in JOB_KEYS}


class History:
    MAX = 1000

    def __init__(self):
        self._file = JsonFile("history.json", list)
        self.items = self._file.load()

    def add(self, title, url, path, fmt, opts=None):
        self.items.append({
            "title": title, "url": url, "path": path, "format": fmt, "opts": opts or {},
            "date": time.strftime("%Y-%m-%d %H:%M"),
        })
        self.items = self.items[-self.MAX:]
        self._file.save(self.items)

    def remove(self, entry):
        if entry in self.items:
            self.items.remove(entry)
            self._file.save(self.items)

    def clear(self):
        self.items = []
        self._file.save(self.items)

    def has_url(self, url):
        return any(e["url"] == url for e in self.items)


config = Config()
history = History()
saved_queue = JsonFile("queue.json", list)
