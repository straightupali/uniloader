"""Download engine: builds yt-dlp options, runs the queue, fetches previews."""
import copy
import hashlib
import json
import os
import re
import secrets
import socket
import shutil
import threading
import time
import urllib.request
import uuid
from urllib.parse import urlparse
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp
from yt_dlp.downloader import external as _external
from yt_dlp.cookies import YoutubeDLCookieJar
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import DownloadCancelled, download_range_func, parse_bytes

from .paths import DATA_DIR, aria2c_path, deno_path, ffmpeg_dir

FORMATS = ["MP4 (video)", "MKV (video)", "MP3 (audio)", "M4A (audio)"]
VIDEO_QUALITIES = ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
AUDIO_QUALITIES = {"High (320 kbps)": "320", "Medium (192 kbps)": "192", "Low (128 kbps)": "128"}
COOKIE_BROWSERS = ["No login", "Firefox", "Chrome", "Edge", "Brave", "Opera", "Vivaldi"]
TEMPLATES = {
    "Title": "%(title)s.%(ext)s",
    "Title [id]": "%(title)s [%(id)s].%(ext)s",
    "Channel - Title": "%(uploader)s - %(title)s.%(ext)s",
    "Date - Title": "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s",
}
PP_LABELS = {
    "Merger": "Merging video + audio", "ExtractAudio": "Converting audio",
    "FFmpegExtractAudio": "Converting audio", "VideoRemuxer": "Remuxing",
    "EmbedSubtitle": "Embedding subtitles", "Metadata": "Adding metadata",
    "EmbedThumbnail": "Embedding thumbnail", "ThumbnailsConvertor": "Converting thumbnail",
    "ModifyChapters": "Cutting clip",
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


# Remember the aria2c process each worker thread starts, so Cancel can stop it.
_procs = {}


class _TrackedPopen(_external.Popen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _procs[threading.get_ident()] = self


_external.Popen = _TrackedPopen


def _kill_downloader(thread_id):
    proc = _procs.get(thread_id)
    if proc is not None and proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass


# ---------- small helpers ----------
def is_audio(fmt):
    return "audio" in fmt


def height_of(label):
    m = re.match(r"(\d+)p", label or "")
    return int(m.group(1)) if m else None


def parse_time(text):
    """'1:20' -> 80.0, '1:02:03' -> 3723.0, '' -> None. Raises ValueError."""
    text = (text or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(text)
    secs = 0.0
    for p in parts:
        secs = secs * 60 + float(p)
    if secs < 0:
        raise ValueError(text)
    return secs


def fmt_time(secs):
    if secs is None:
        return ""
    secs = int(secs)
    h, m, s = secs // 3600, secs % 3600 // 60, secs % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _tag_time(secs):  # file-name safe: 1m20s, 1h02m03s
    h, rest = divmod(int(secs), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def fmt_bytes(n):
    if not n:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def clean_error(msg):
    msg = ANSI.sub("", str(msg)).replace("ERROR: ", "").strip()
    return msg.splitlines()[0][:300] if msg else "Unknown error"


def valid_speed(text):
    return not text.strip() or parse_bytes(text.strip()) is not None


def valid_template(text):
    return yt_dlp.YoutubeDL.validate_outtmpl(text) is None


def format_label(o):
    q = o["audio_quality"].split()[0] if is_audio(o["format"]) else o["video_quality"]
    label = f'{o["format"].split()[0]} {q}'
    if o.get("clip_start") is not None or o.get("clip_end") is not None:
        label += f' · clip {fmt_time(o.get("clip_start") or 0)}-{fmt_time(o.get("clip_end")) or "end"}'
    return label


# ---------- shared pieces (speed) ----------
REUSE_SECONDS = 20 * 60  # video info from a preview/prefetch is reused for this long


def base_options():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "color": {"stdout": "no_color", "stderr": "no_color"},
        "remote_components": ["ejs:github"],
        # keeps YouTube's solved player challenges between runs (skips Deno work next time)
        "cachedir": str(DATA_DIR / "cache"),
    }
    if deno_path():
        opts["js_runtimes"] = {"deno": {"path": deno_path()}}
    return opts


def _browser(cookies):
    return cookies.lower() if cookies and cookies != COOKIE_BROWSERS[0] else None


_cookie_lock = threading.Lock()
_cookie_jars = {}  # browser -> (time loaded, jar)


def _cookie_jar(browser):
    """Reading browser cookies is slow (decrypting), so do it once per 15 minutes."""
    with _cookie_lock:
        loaded, jar = _cookie_jars.get(browser, (0, None))
        if jar is None or time.time() - loaded > 900:
            from yt_dlp.cookies import extract_cookies_from_browser
            jar = extract_cookies_from_browser(browser)
            _cookie_jars[browser] = (time.time(), jar)
        private = YoutubeDLCookieJar()  # each download gets its own copy
        for c in jar:
            private.set_cookie(c)
        return private


def open_ydl(opts, cookies=None):
    ydl = yt_dlp.YoutubeDL(opts)
    browser = _browser(cookies)
    if browser:
        ydl.__dict__["cookiejar"] = _cookie_jar(browser)  # use the cached cookies
    return ydl


class _InfoCache:
    """Video info fetched by Preview / clipboard pop-up / queue prefetch, so the
    download itself can skip the slow 'getting video info' step."""

    def __init__(self):
        self.lock = threading.Lock()
        self.items, self.pending = {}, {}

    @staticmethod
    def key(url, o):
        return url, _browser(o.get("cookies")) or "", bool(o.get("playlist"))

    def get(self, url, o):
        with self.lock:
            hit = self.items.get(self.key(url, o))
        if hit and time.time() - hit[0] < REUSE_SECONDS:
            return copy.deepcopy(hit[1])
        return None

    def put(self, url, o, info):
        if not info or info.get("_type", "video") != "video":
            return  # playlists are fetched again (their entries change)
        with self.lock:
            self.items[self.key(url, o)] = (time.time(), info)
            while len(self.items) > 50:
                self.items.pop(next(iter(self.items)))

    def drop(self, url, o):
        with self.lock:
            self.items.pop(self.key(url, o), None)

    def is_pending(self, url, o):
        with self.lock:
            return self.key(url, o) in self.pending

    def wait(self, url, o, timeout=120):
        with self.lock:
            ev = self.pending.get(self.key(url, o))
        if ev:
            ev.wait(timeout)

    def fetch(self, url, o):
        k = self.key(url, o)
        with self.lock:
            if k in self.pending:
                return
            self.pending[k] = threading.Event()
        try:
            self.put(url, o, extract_raw(url, o))
        except Exception:
            pass
        finally:
            with self.lock:
                self.pending.pop(k).set()

    def prefetch(self, url, o):
        if self.get(url, o) is None and not self.is_pending(url, o):
            threading.Thread(target=self.fetch, args=(url, o), daemon=True).start()


info_cache = _InfoCache()


def _clean(ydl, info):
    return ydl.sanitize_info(info, remove_private_keys=True) if info else None


def extract_raw(url, o):
    opts = dict(base_options(), skip_download=True, noplaylist=not o.get("playlist"),
                ignore_no_formats_error=True, logger=_Logger(Job("", {})))
    with open_ydl(opts, o.get("cookies")) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
        return _clean(ydl, info) if info and info.get("_type", "video") == "video" else None


def warm_up(cookies=None):
    """Load yt-dlp's 1,800 site extractors, Deno and cookies while the app opens,
    so the first download doesn't pay for it."""
    def work():
        try:
            yt_dlp.YoutubeDL(base_options())
            is_supported("https://www.youtube.com/watch?v=aaaaaaaaaaa")
            if deno_path():
                import subprocess
                subprocess.run([deno_path(), "--version"], capture_output=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if _browser(cookies):
                _cookie_jar(_browser(cookies))
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


# ---------- yt-dlp options ----------
def temp_dir(url, o):
    """Private workspace per download, inside the target folder (same drive = instant move).
    Parallel jobs of the same video don't collide, a retried download resumes,
    and yt-dlp never touches files that are already in your folder."""
    key = f'{url}|{o["format"]}|{o.get("clip_start")}|{o.get("clip_end")}|{o.get("playlist")}'
    root = Path(o["folder"]) / ".partial"
    root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(root), 0x2)  # hidden
        except Exception:
            pass
    return root / hashlib.sha1(key.encode()).hexdigest()[:12]


def _unique(path):
    if not path.exists():
        return path
    for i in range(2, 1000):
        p = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not p.exists():
            return p
    return path


def deliver(src, out_root, folder):
    """Move a finished file from the workspace into the real folder (never overwrites)."""
    src = Path(src)
    try:
        rel = src.relative_to(out_root)
    except ValueError:
        return str(src)
    dest = _unique(Path(folder) / rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return str(dest)


def cleanup_temp(tmp):
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        Path(tmp).parent.rmdir()  # remove .partial when empty
    except OSError:
        pass


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def uses_fast_mode(o):
    clip = o.get("clip_start") is not None or o.get("clip_end") is not None
    return int(o.get("connections", 8)) > 1 and bool(aria2c_path()) and not clip


def build_options(o, *, force=False, temp=None, fast=None, rpc=None):
    """Turn a job's settings dict into yt-dlp options (without hooks)."""
    fmt = o["format"].split()[0]  # MP4 / MKV / MP3 / M4A
    audio = is_audio(o["format"])

    tmpl = (o.get("template") or "").strip() or "%(title)s.%(ext)s"
    if "%(ext)s" not in tmpl:
        tmpl += ".%(ext)s"
    start, end = o.get("clip_start"), o.get("clip_end")
    clip = start is not None or end is not None
    if clip:
        tag = f" (clip {_tag_time(start or 0)}-{_tag_time(end) if end is not None else 'end'})"
        tmpl = tmpl.replace(".%(ext)s", tag + ".%(ext)s")
    if o.get("playlist"):  # "My Playlist/003 - Title.mp4" (plain name for single videos)
        tmpl = "%(playlist_title&{}/|)s%(playlist_index&{:03d} - |)s" + tmpl

    opts = {
        "paths": ({"home": str(Path(temp) / "out"), "temp": str(Path(temp) / "work")} if temp
                  else {"home": str(Path(o["folder"]))}),
        "outtmpl": tmpl,
        "windowsfilenames": True,
        "noplaylist": not o.get("playlist"),
        "ignoreerrors": "only_download" if o.get("playlist") else False,
        "retries": int(o.get("retries", 10)),
        "fragment_retries": int(o.get("retries", 10)),
        "extractor_retries": 3,
        "file_access_retries": 3,
        "concurrent_fragment_downloads": 8,  # HLS/DASH sites: 8 pieces at once
        **base_options(),
    }
    if ffmpeg_dir():
        opts["ffmpeg_location"] = ffmpeg_dir()
    speed = (o.get("speed_limit") or "").strip()
    if speed and parse_bytes(speed):
        opts["ratelimit"] = parse_bytes(speed)
    if o.get("skip_existing") and not force and not clip:  # one archive per format: MP3 after MP4 still works
        opts["download_archive"] = str(DATA_DIR / f"archive-{fmt.lower()}.txt")
    if clip:
        opts["download_ranges"] = download_range_func(
            None, [(start or 0, end if end is not None else float("inf"))])
        # precise = re-encode the clip (slow); fast = cut at the nearest keyframe (instant)
        opts["force_keyframes_at_cuts"] = bool(o.get("precise_cuts"))
    if fast is None:
        fast = uses_fast_mode(o)
    if fast:
        n = str(min(16, int(o.get("connections", 8))))
        opts["external_downloader"] = {"http": aria2c_path()}
        opts["external_downloader_args"] = {"aria2c": [
            f"--max-connection-per-server={n}", f"--split={n}", "--min-split-size=1M",
            "--connect-timeout=10", "--max-tries=5", "--retry-wait=1",
            # IPv4 only + system DNS: avoids long waits on networks without working IPv6
            "--disable-ipv6=true", "--async-dns=false"]}
        if rpc:  # lets the app read live progress from aria2c
            port, secret = rpc
            opts["external_downloader_args"]["aria2c"] += [
                "--enable-rpc", "--rpc-listen-all=false", f"--rpc-listen-port={port}",
                f"--rpc-secret={secret}"]

    pps = []
    if o.get("embed_thumbnail"):
        opts["writethumbnail"] = True
        pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
    if audio:
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best" if fmt == "M4A" else "bestaudio/best"
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": fmt.lower(),
                    "preferredquality": AUDIO_QUALITIES.get(o["audio_quality"], "192")})
    else:
        h = height_of(o["video_quality"])
        cap = f"[height<={h}]" if h else ""
        opts["format"] = f"bv*{cap}+ba/b{cap}/bv*+ba/b"
        if fmt == "MP4":
            # H.264 + AAC plays everywhere; turn off in Settings to allow 4K VP9/AV1 in MP4
            opts["format_sort"] = ["vcodec:h264", "acodec:aac"] if o.get("mp4_compat") else ["acodec:aac"]
        opts["merge_output_format"] = fmt.lower()
        pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": fmt.lower()})
        if o.get("subtitles"):
            langs = [x.strip() for x in (o.get("sub_langs") or "en").split(",") if x.strip()]
            opts.update(writesubtitles=True, writeautomaticsub=True,
                        subtitleslangs=[f"{x}.*" for x in langs] + ["-live_chat"])
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
    if o.get("embed_metadata"):
        pps.append({"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": True})
    if o.get("embed_thumbnail"):
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    opts["postprocessors"] = pps
    return opts


# ---------- jobs ----------
@dataclass
class Job:
    url: str
    opts: dict
    force: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    title: str = ""
    status: str = "Queued"  # Queued Starting Downloading Processing Done Skipped Failed Cancelled
    progress: float = 0.0
    detail: str = ""
    item: str = ""
    error: str = ""
    files: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    skipped: int = 0
    cancel: bool = False

    @property
    def active(self):
        return self.status in ("Starting", "Downloading", "Processing")

    @property
    def finished(self):
        return self.status in ("Done", "Skipped", "Failed", "Cancelled")

    def to_saved(self):
        return {"url": self.url, "opts": self.opts, "force": self.force, "title": self.title}


class _Logger:
    def __init__(self, job):
        self.job = job

    def debug(self, msg):
        if "has already been recorded in the archive" in msg:
            self.job.skipped += 1

    info = debug

    def warning(self, msg):
        pass

    def error(self, msg):
        self.job.errors.append(clean_error(msg))


class DownloadManager:
    def __init__(self, get_parallel, on_file, on_finished):
        self.jobs = []
        self.cv = threading.Condition()
        self.get_parallel = get_parallel
        self.on_file = on_file          # (job, path, title)   - called from worker threads
        self.on_finished = on_finished  # (job)                - called from worker threads
        threading.Thread(target=self._dispatch, daemon=True).start()
        threading.Thread(target=self._prefetch_loop, daemon=True).start()

    # ----- public -----
    def add(self, url, opts, force=False, title=""):
        job = Job(url=url, opts=opts, force=force, title=title)
        with self.cv:
            self.jobs.append(job)
            self.cv.notify_all()
        return job

    def retry(self, job):
        with self.cv:
            job.status, job.progress, job.detail, job.error, job.item = "Queued", 0.0, "", "", ""
            job.cancel, job.errors, job.files, job.skipped = False, [], [], 0
            self.cv.notify_all()

    def cancel(self, job):
        with self.cv:
            job.cancel = True
            if job.status == "Queued":
                job.status = "Cancelled"
            self.cv.notify_all()

    def remove(self, job):
        with self.cv:
            if job in self.jobs and not job.active:
                self.jobs.remove(job)

    def clear_finished(self):
        with self.cv:
            self.jobs = [j for j in self.jobs if not j.finished]

    def unfinished(self):
        return [j for j in self.jobs if not j.finished]

    def active_count(self):
        return sum(1 for j in self.jobs if j.active)

    def has_url(self, url):
        return any(j.url == url and not j.finished for j in self.jobs)

    # ----- worker side -----
    def _prefetch_loop(self):
        """Fetch info for the next waiting links while others download."""
        while True:
            time.sleep(1.0)
            waiting = [j for j in list(self.jobs) if j.status == "Queued"][:2]
            for j in waiting:
                if not j.opts.get("playlist") and info_cache.get(j.url, j.opts) is None:
                    j.detail = "Getting video info in advance..."
                    info_cache.fetch(j.url, j.opts)
                    if j.status == "Queued":
                        j.detail = "Ready" if info_cache.get(j.url, j.opts) else ""
                    break

    def _dispatch(self):
        while True:
            with self.cv:
                while True:
                    nxt = next((j for j in self.jobs if j.status == "Queued"), None)
                    if nxt and self.active_count() < max(1, int(self.get_parallel())):
                        break
                    self.cv.wait(1.0)
                nxt.status = "Starting"
                nxt.detail = "Getting video info..."
            threading.Thread(target=self._run, args=(nxt,), daemon=True).start()

    def _run(self, job):
        state = {"title": job.title, "url": job.url}
        fast = uses_fast_mode(job.opts)
        tmp = None
        try:
            tmp = temp_dir(job.url, job.opts)
            info_cache.wait(job.url, job.opts)  # a prefetch for this link is running
            cached = info_cache.get(job.url, job.opts)
            # 1) reuse fetched info  2) fresh info  3) normal downloader (if fast mode failed)
            plans = ([(fast, cached)] if cached else []) + [(fast, None)] + ([(False, None)] if fast else [])
            for i, (use_fast, info) in enumerate(plans):
                last = i == len(plans) - 1
                if i:
                    job.errors, job.progress, job.status = [], 0.0, "Starting"
                    job.detail = ("Retrying with the normal downloader..." if fast and not use_fast
                                  else "Getting fresh video info...")
                try:
                    self._attempt(job, state, tmp, use_fast, info)
                except DownloadCancelled:
                    raise
                except Exception:
                    if last or job.cancel or job.files:
                        raise
                    if info is not None:
                        info_cache.drop(job.url, job.opts)
                    continue
                if job.cancel or job.files or job.skipped or not job.errors or last:
                    break
                if info is not None:
                    info_cache.drop(job.url, job.opts)

            if job.cancel:
                job.status, job.detail = "Cancelled", ""
            elif job.files:
                job.status, job.progress = "Done", 1.0
                extra = f" · {job.skipped} already had" if job.skipped else ""
                extra += f" · {len(job.errors)} failed" if job.errors else ""
                job.detail = (f"{len(job.files)} files" if len(job.files) > 1 else "Saved") + extra
            elif job.skipped:
                job.status, job.progress, job.detail = "Skipped", 1.0, "Already downloaded"
            elif job.errors:
                job.status, job.error = "Failed", job.errors[-1]
                job.detail = job.error
            else:
                job.status, job.detail = "Done", "Nothing new to download"
        except DownloadCancelled:
            job.status, job.detail = "Cancelled", ""
        except Exception as e:
            job.status = "Cancelled" if job.cancel else "Failed"
            job.error = clean_error(job.errors[-1] if job.errors else e)
            job.detail = "" if job.cancel else job.error
        finally:
            _procs.pop(threading.get_ident(), None)
            if tmp and job.status != "Failed":  # keep partial files only for a retry
                cleanup_temp(tmp)
            try:
                self.on_finished(job)
            except Exception:
                pass
            with self.cv:
                self.cv.notify_all()

    def _attempt(self, job, state, tmp, fast, info=None):
        watcher = _FastWatcher(job) if fast else None

        def progress(d):
            if job.cancel:
                raise DownloadCancelled("Cancelled")
            info = d.get("info_dict") or {}
            state["title"] = info.get("title") or state["title"]
            state["url"] = info.get("webpage_url") or state["url"]
            if not job.title or job.opts.get("playlist"):
                job.title = info.get("playlist_title") or state["title"] or job.title
            idx, n = info.get("playlist_index"), info.get("n_entries") or info.get("playlist_count")
            job.item = f"{idx}/{n}" if idx and n else ""
            if d["status"] == "downloading":  # the normal downloader reports live progress
                if watcher:
                    watcher.active = False
                job.status = "Downloading"
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                frag, frags = d.get("fragment_index"), d.get("fragment_count")
                if total:
                    job.progress = min(1.0, d.get("downloaded_bytes", 0) / total)
                elif frag and frags:
                    job.progress = min(1.0, frag / frags)
                part = "audio" if info.get("vcodec") == "none" and not is_audio(job.opts["format"]) else ""
                speed = f'{fmt_bytes(d.get("speed"))}/s' if d.get("speed") else ""
                eta = f'{fmt_time(d["eta"])} left' if d.get("eta") is not None else ""
                job.detail = " · ".join(x for x in (part, speed, eta, fmt_bytes(total) if total else "") if x)
            elif d["status"] == "finished" and not (watcher and watcher.active):
                job.status, job.progress = "Processing", 1.0
                job.detail = "Finishing..."

        def pp_hook(d):
            name = d.get("postprocessor", "")
            if name == "VDCapture":
                return
            info = d.get("info_dict") or {}
            state["title"] = info.get("title") or state["title"]
            if not job.title and state["title"]:
                job.title = state["title"]
            if d["status"] == "started":
                if watcher:
                    watcher.active = False
                job.status, job.progress = "Processing", 1.0
                job.detail = PP_LABELS.get(name, PP_LABELS.get(name.replace("FFmpeg", ""), "Processing..."))

        def post_hook(path):
            path = deliver(path, Path(tmp) / "out", job.opts["folder"])
            job.files.append(path)
            title = state["title"] or Path(path).stem
            if not job.title:
                job.title = title
            try:
                self.on_file(job, path, title, state["url"])
            except Exception:
                pass

        opts = build_options(job.opts, force=job.force, temp=tmp, fast=fast,
                             rpc=(watcher.port, watcher.secret) if watcher else None)
        opts.update(logger=_Logger(job), progress_hooks=[progress],
                    postprocessor_hooks=[pp_hook], post_hooks=[post_hook])
        if info is not None:
            job.detail = "Starting download..."
        with open_ydl(opts, job.opts.get("cookies")) as ydl:
            if watcher:
                ydl.add_post_processor(VDCapturePP(watcher), when="before_dl")
                watcher.start()
            try:
                if info is not None:  # info already fetched: skip extraction
                    ydl.process_ie_result(info, download=True)
                else:
                    ydl.download([job.url])
            finally:
                if watcher:
                    watcher.stop()
        if job.cancel:
            raise DownloadCancelled("Cancelled")


class VDCapturePP(PostProcessor):
    """Runs just before each video downloads: tells the watcher the expected size."""

    def __init__(self, watcher):
        super().__init__(None)
        self.watcher = watcher

    def run(self, info):
        self.watcher.begin(info)
        return [], info


class _FastWatcher:
    """aria2c prints no progress for yt-dlp, so ask it over its local control port
    (JSON-RPC) for bytes done / speed / connections. When a file finishes, tell
    aria2c to exit so yt-dlp continues. Also stops aria2c on Cancel."""

    def __init__(self, job):
        self.job = job
        self.owner = threading.get_ident()
        self.port, self.secret = _free_port(), secrets.token_hex(8)
        self.active = False
        self.expected = self.done_bytes = 0
        self.handled = set()
        self._stop = threading.Event()
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _rpc(self, method, *params):
        body = json.dumps({"jsonrpc": "2.0", "id": "vd", "method": method,
                           "params": [f"token:{self.secret}", *params]}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/jsonrpc", body,
                                     {"Content-Type": "application/json"})
        with self._opener.open(req, timeout=2) as r:
            return json.load(r)["result"]

    def begin(self, info):  # called just before each video downloads
        fmts = info.get("requested_formats") or [info]
        self.expected = sum(f.get("filesize") or f.get("filesize_approx") or 0 for f in fmts)
        self.done_bytes, self.speed = 0, 0.0
        self.active = all(str(f.get("protocol", "")).startswith("http")
                          and "dash" not in str(f.get("protocol")) for f in fmts)
        if self.active:
            self.job.status, self.job.progress = "Downloading", 0.0
            self.job.detail = "Connecting..."

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(0.25):
            try:
                self._tick()
            except Exception:
                pass  # aria2c not running at this moment

    def _tick(self):
        job = self.job
        if job.cancel:
            _kill_downloader(self.owner)
            return
        active = self._rpc("aria2.tellActive", ["completedLength", "totalLength",
                                                "downloadSpeed", "connections"])
        stopped = self._rpc("aria2.tellStopped", 0, 100, ["gid", "status", "totalLength"])
        new = [x for x in stopped if x["gid"] not in self.handled]
        if not active and new:  # file finished (or failed): let aria2c exit
            for x in new:
                self.handled.add(x["gid"])
                if x["status"] == "complete":
                    self.done_bytes += int(x["totalLength"] or 0)
            self._rpc("aria2.shutdown")
            return
        if not active or not self.active or job.status != "Downloading":
            return
        a = active[0]
        done, total = int(a["completedLength"]), int(a["totalLength"])
        speed, conns = int(a["downloadSpeed"]), a.get("connections", "?")
        grand = max(self.expected, self.done_bytes + total)
        got = self.done_bytes + done
        bits = [f"{fmt_bytes(speed)}/s" if speed else "Connecting..."]
        if grand:
            job.progress = min(got / grand, 0.99)
            if speed:
                bits.append(f"{fmt_time((grand - got) / speed)} left")
            bits.append(fmt_bytes(grand))
        bits.append(f"{conns} connections")
        job.detail = " · ".join(bits)


# ---------- preview ----------
def fetch_preview(url, playlist=False, cookies=None):
    """Quick info for the preview card. Raises on error. The info is cached so
    pressing Download right after doesn't fetch it again."""
    o = {"playlist": playlist, "cookies": cookies}
    opts = dict(base_options(), skip_download=True, extract_flat="in_playlist",
                noplaylist=not playlist, ignore_no_formats_error=True,
                logger=_Logger(Job("", {})))
    with open_ydl(opts, cookies) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
        if info and info.get("_type", "video") == "video":
            info_cache.put(url, o, _clean(ydl, info))
        elif info:
            info = ydl.process_ie_result(info, download=False)  # playlist / redirect
    if not info:
        raise RuntimeError("No video found at this link")
    entries = info.get("entries")
    if entries is not None:
        entries = list(entries)
        return {"kind": "playlist", "title": info.get("title") or "Playlist",
                "uploader": info.get("uploader") or info.get("channel") or "",
                "count": info.get("playlist_count") or len(entries),
                "thumb": _pick_thumb(info) or next((_pick_thumb(e) for e in entries if _pick_thumb(e)), None),
                "heights": []}
    heights = sorted({f["height"] for f in info.get("formats") or []
                      if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)
    return {"kind": "video", "title": info.get("title") or url,
            "uploader": info.get("uploader") or info.get("channel") or urlparse(url).netloc,
            "duration": info.get("duration"), "thumb": _pick_thumb(info), "heights": heights}


def _pick_thumb(info):
    thumbs = [t for t in info.get("thumbnails") or [] if t.get("url")]
    good = [t for t in thumbs if 300 <= (t.get("width") or 0) <= 800 and ".webp" not in t["url"]]
    if good:
        return good[-1]["url"]
    return info.get("thumbnail") or (thumbs[-1]["url"] if thumbs else None)


def fetch_bytes(url, limit=5_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read(limit)


# ---------- link detection (clipboard watcher) ----------
_extractors = None
_ext_lock = threading.Lock()


def is_supported(url):
    """True if a specific yt-dlp extractor (not the generic one) handles this URL."""
    global _extractors
    if not re.match(r"https?://\S+$", url or ""):
        return False
    with _ext_lock:
        if _extractors is None:
            from yt_dlp.extractor import gen_extractor_classes
            _extractors = [ie for ie in gen_extractor_classes() if ie.ie_key() != "Generic"]
    return any(ie.suitable(url) for ie in _extractors)
