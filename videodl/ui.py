"""Main window (customtkinter): sidebar + Download, Queue, History and Settings pages."""
import io
import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from . import __version__, engine, ipc, system, updater
from .engine import AUDIO_QUALITIES, COOKIE_BROWSERS, FORMATS, TEMPLATES, VIDEO_QUALITIES
from .icon import icon_image
from .paths import ASSETS, DATA_DIR, DEFAULT_FOLDER, EXTENSION_DIR, aria2c_path, deno_path, has_ffmpeg
from .settings import config, history, saved_queue
from .tray import Tray

BOOKMARKLET = "javascript:location.href='ytdl://?u='+encodeURIComponent(location.href)"
THUMB = (176, 99)
FONT = "Segoe UI" if os.name == "nt" else "Inter"

# (light, dark) colour pairs
C = {
    "bg": ("#F4F5F9", "#0F1117"),
    "side": ("#FFFFFF", "#14161E"),
    "card": ("#FFFFFF", "#191C25"),
    "field": ("#F0F2F7", "#22262F"),
    "border": ("#E3E6EE", "#2A2E3A"),
    "hover": ("#E9ECF3", "#2A2F3B"),
    "text": ("#151821", "#E8EAF0"),
    "muted": ("#6B7183", "#8C92A4"),
    "accent": ("#5B5BEF", "#6E6BF7"),
    "accent_h": ("#4B4AD9", "#5D59E8"),
    "soft": ("#E2E2FD", "#2C2D63"),
    "ok": ("#15A34A", "#4ADE80"),
    "bad": ("#DC2626", "#F87171"),
}
BASE_C = dict(C)
# Colour themes (Settings > Appearance). Each one overrides the accent colours;
# Midnight also makes the dark mode pure black.
THEMES = {
    "Indigo": {"accent": ("#5B5BEF", "#6E6BF7"), "accent_h": ("#4B4AD9", "#5D59E8"), "soft": ("#E2E2FD", "#2C2D63")},
    "Ocean": {"accent": ("#0B72D9", "#2F8CF5"), "accent_h": ("#095FB5", "#1F78DB"), "soft": ("#DBEAFC", "#132F55")},
    "Emerald": {"accent": ("#05875F", "#10A877"), "accent_h": ("#046E4D", "#0C8F65"), "soft": ("#D3F2E6", "#113A2E")},
    "Sunset": {"accent": ("#E0560B", "#F2701F"), "accent_h": ("#BF470A", "#D95F14"), "soft": ("#FCE4D4", "#46240F")},
    "Rose": {"accent": ("#DB2050", "#F0466E"), "accent_h": ("#BA1641", "#D63459"), "soft": ("#FBDDE5", "#491A27")},
    "Midnight": {"accent": ("#5B5BEF", "#7C79FF"), "accent_h": ("#4B4AD9", "#6A66F0"), "soft": ("#E2E2FD", "#1E1F4A"),
                 "bg": ("#F4F5F9", "#000000"), "side": ("#FFFFFF", "#07080B"), "card": ("#FFFFFF", "#0D0E13"),
                 "field": ("#F0F2F7", "#17191F"), "border": ("#E3E6EE", "#1F222B"), "hover": ("#E9ECF3", "#1C1F28")},
}


def apply_theme(name):
    C.clear()
    C.update(BASE_C)
    C.update(THEMES.get(name, THEMES["Indigo"]))


# What each control does (shown when hovering)
TIPS = {
    "MP4": "MP4 video plays everywhere: phones, TVs, PCs and WhatsApp. The best choice for most downloads.",
    "MKV": "MKV video keeps everything: 4K/HDR and all audio and subtitle tracks. Plays on PCs (e.g. VLC), "
           "but some phones and TVs can't open it.",
    "MP3": "MP3 is audio only and plays on everything. Good for music and podcasts.",
    "M4A": "M4A is audio only (AAC). It sounds better than MP3 at the same size and is usually faster, "
           "because it often needs no converting. Plays on phones and most players.",
    "quality_video": "The highest resolution to download. 'Best' takes the top one available. "
                     "Lower = smaller file and faster download.",
    "quality_audio": "Audio quality (bitrate). 320 kbps is the best MP3 quality; 128 kbps makes small files.",
    "folder": "Where finished files are saved. Partial downloads stay hidden until they finish.",
    "paste": "Paste the link from your clipboard. You can also press Ctrl+V or right-click the box.",
    "preview": "Check the title, length and available qualities first. The download then starts faster, "
               "because the video info is already fetched.",
    "playlist": "If the link is a playlist or channel, download every video into its own folder, numbered in order.",
    "subtitles": "Put subtitles inside the video (pick languages in Settings). You can turn them on or off in your player.",
    "embed_thumbnail": "Use the video's thumbnail as the file's cover picture, shown in File Explorer and music players.",
    "embed_metadata": "Save the title, channel, date, description and chapters inside the file.",
    "clip": "Download only part of the video, e.g. 1:20 to 2:45. Use minutes:seconds or plain seconds.",
    "login": "Use your logged-in browser session for videos that need an account: private, age-restricted, "
             "X, Instagram, Facebook. Firefox works best.",
    "download": "Add the link to the queue. It starts right away, or as soon as a download slot is free.",
    "retry_failed": "Try every failed download again.",
    "clear_finished": "Remove finished items from this list. Your files stay where they are.",
    "mode": "Dark, Light, or follow your Windows setting.",
    "color_theme": "The accent colour used for buttons and highlights. Midnight also makes dark mode pure black.",
    "tooltips": "Show these small explanations when you hover over something.",
    "template": "How files are named. 'Title [id]' avoids two different videos with the same name "
                "overwriting each other.",
    "sub_langs": "Which subtitle languages to download when Subtitles is on. Use codes like en, ar, fr.",
    "skip": "Remembers what you've downloaded, so the same video isn't downloaded twice in the same format.",
    "h264": "On: MP4s use H.264, which every device can play (YouTube offers it up to 1080p). "
            "Off: allows 4K, but older devices may not play it.",
    "precise": "Off: cuts instantly at the nearest keyframe (may start a second early). "
               "On: cuts exactly, but re-encodes the clip, which is slower.",
    "connections": "Splits each file into parts that download at the same time. Usually much faster. "
                   "If a site has trouble with it, the app retries with 1 connection automatically.",
    "parallel": "How many videos download at the same time. 1–2 is best on slower connections.",
    "retries": "How many times to try again when the connection drops before giving up.",
    "speed_limit": "Cap the download speed so games, calls and browsing stay smooth. Empty = no limit.",
    "clipboard": "When you copy a video link anywhere, a small pop-up offers to download it.",
    "tray": "Closing the window keeps the app running next to the clock, so the Chrome button and "
            "clipboard pop-up keep working.",
    "autostart": "Start the app hidden in the tray when Windows starts.",
    "autoupdate": "Sites change often; this keeps the downloader working by updating yt-dlp once a day.",
    "save_folder": "Change where downloads go, or reset to Downloads\\Video Downloader.",
}

STATUS_STYLE = {  # status -> (dot colour, label)
    "Queued": ("muted", "Waiting"), "Starting": ("accent", "Starting"),
    "Downloading": ("accent", "Downloading"), "Processing": ("accent", "Processing"),
    "Done": ("ok", "Done"), "Skipped": ("muted", "Skipped"),
    "Failed": ("bad", "Failed"), "Cancelled": ("muted", "Cancelled"),
}
NAV = [("Download", "↓"), ("Queue", "≡"), ("History", "◷"), ("Settings", "⚙")]


# ---------------- small styled widgets ----------------
def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def label(parent, text="", size=13, weight="normal", muted=False, **kw):
    return ctk.CTkLabel(parent, text=text, font=font(size, weight), anchor="w", justify="left",
                        text_color=C["muted"] if muted else C["text"], **kw)


def primary(parent, text, command, height=38, size=13, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=6,
                         fg_color=C["accent"], hover_color=C["accent_h"], text_color="#FFFFFF",
                         font=font(size, "bold"), **kw)


def ghost(parent, text, command, width=0, height=32, danger=False, border=True, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width or 10, height=height,
                         corner_radius=5, fg_color="transparent", hover_color=C["hover"],
                         border_width=1 if border else 0, border_color=C["border"],
                         text_color=C["bad"] if danger else C["text"], font=font(12), **kw)


def entry(parent, placeholder="", width=200, height=38, **kw):
    return ctk.CTkEntry(parent, placeholder_text=placeholder, width=width, height=height,
                        corner_radius=6, border_width=1, fg_color=C["field"], border_color=C["border"],
                        text_color=C["text"], placeholder_text_color=C["muted"], font=font(13), **kw)


def option(parent, values, command, width=150):
    return ctk.CTkOptionMenu(parent, values=values, command=command, width=width, height=34,
                             corner_radius=5, fg_color=C["field"], button_color=C["field"],
                             button_hover_color=C["hover"], text_color=C["text"],
                             dropdown_fg_color=C["card"], dropdown_hover_color=C["hover"],
                             dropdown_text_color=C["text"], font=font(13), dropdown_font=font(13))


SWITCH_OFF = ("#7C8499", "#3B404D")  # darker in light mode so the white knob stands out
SWITCH_RING = SWITCH_OFF  # track edge matches the track, so the knob looks inset


def switch(parent, var, command):
    """On/off switch. The white knob has an outline (grey when off, accent when on)
    so it stays visible on white cards in light mode."""
    accent = C["accent"]
    s = ctk.CTkSwitch(parent, text="", variable=var, command=command, width=48,
                      progress_color=accent, fg_color=SWITCH_OFF, button_color="#FFFFFF",
                      button_hover_color="#F2F2F2", border_width=3,
                      border_color=accent if var.get() else SWITCH_RING)

    def ring(*_):
        try:
            s.configure(border_color=accent if var.get() else SWITCH_RING)
        except Exception:
            pass  # switch was rebuilt (theme change)
    var.trace_add("write", ring)
    return s


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=8, border_width=1,
                        border_color=C["border"], **kw)


def scroll(parent):
    return ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=C["border"],
                                  scrollbar_button_hover_color=C["muted"])


def set_entry(widget, text):
    widget.delete(0, "end")
    if text:
        widget.insert(0, text)
    elif hasattr(widget, "_activate_placeholder") and widget.focus_get() is not widget._entry:
        widget._activate_placeholder()  # bring back the grey hint text


def short(text, n=80):
    return text if len(text) <= n else text[: n - 1] + "…"


def short_path(p, n=58):
    p = str(p)
    return p if len(p) <= n else p[:20] + "…" + p[-(n - 21):]


def _mode_index():
    return 1 if ctk.get_appearance_mode() == "Dark" else 0


class Tooltip:
    """Small explanation that appears when the mouse rests on a widget."""

    def __init__(self, widget, text, wrap=300):
        self.w, self.text, self.wrap = widget, text, wrap
        self.tip = self._show_job = self._hide_job = None
        for seq, fn in (("<Enter>", self._enter), ("<Leave>", self._leave), ("<ButtonPress>", self.hide)):
            try:
                widget.bind(seq, fn, add="+")
            except Exception:
                pass

    def _cancel(self, attr):
        job = getattr(self, attr)
        if job:
            try:
                self.w.after_cancel(job)
            except Exception:
                pass
            setattr(self, attr, None)

    def _enter(self, _e=None):
        self._cancel("_hide_job")
        if self.tip is None and self._show_job is None:
            self._show_job = self.w.after(450, self._show)

    def _leave(self, _e=None):
        self._cancel("_show_job")
        self._hide_job = self.w.after(80, self.hide)

    def _show(self):
        self._show_job = None
        if not config.get("tooltips", True):
            return
        try:
            i = _mode_index()
            tw = tk.Toplevel(self.w)
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)
            outer = tk.Frame(tw, bg=C["border"][i])
            outer.pack()
            tk.Label(outer, text=self.text, justify="left", wraplength=self.wrap, bg=C["card"][i],
                     fg=C["text"][i], font=(FONT, 10), padx=11, pady=8).pack(padx=1, pady=1)
            tw.update_idletasks()
            x = self.w.winfo_pointerx() + 14
            y = self.w.winfo_rooty() + self.w.winfo_height() + 6
            x = min(x, self.w.winfo_screenwidth() - tw.winfo_width() - 8)
            if y + tw.winfo_height() > self.w.winfo_screenheight() - 40:
                y = self.w.winfo_rooty() - tw.winfo_height() - 6
            tw.geometry(f"+{x}+{y}")
            self.tip = tw
        except Exception:
            self.tip = None

    def hide(self, _e=None):
        self._cancel("_show_job")
        self._cancel("_hide_job")
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


def tip(widget, key_or_text):
    Tooltip(widget, TIPS.get(key_or_text, key_or_text))
    return widget


def add_context_menu(app, box, on_paste=None):
    """Right-click menu for a text box: Paste / Cut / Copy / Select all (and Clear)."""
    inner = box._entry

    def paste():
        try:
            text = app.clipboard_get()
        except tk.TclError:
            return
        if on_paste:  # link box: replace everything with the link, then preview
            set_entry(box, text.strip())
            on_paste()
            return
        if not box.get() and hasattr(box, "_deactivate_placeholder"):
            box._deactivate_placeholder()
        try:
            if inner.selection_present():
                inner.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        inner.insert("insert", text)

    def select_all():
        inner.focus_set()
        inner.select_range(0, "end")
        inner.icursor("end")

    def popup(e):
        i = _mode_index()
        m = tk.Menu(app, tearoff=0, bg=C["card"][i], fg=C["text"][i], activebackground=C["soft"][i],
                    activeforeground=C["text"][i], disabledforeground=C["muted"][i], bd=1,
                    font=(FONT, 10))
        has_sel = bool(box.get()) and inner.selection_present()
        try:
            has_clip = bool(app.clipboard_get().strip())
        except tk.TclError:
            has_clip = False
        m.add_command(label="Paste link" if on_paste else "Paste", command=paste,
                      state="normal" if has_clip else "disabled")
        m.add_command(label="Cut", command=lambda: inner.event_generate("<<Cut>>"),
                      state="normal" if has_sel else "disabled")
        m.add_command(label="Copy", command=lambda: inner.event_generate("<<Copy>>"),
                      state="normal" if has_sel else "disabled")
        m.add_separator()
        m.add_command(label="Select all", command=select_all, state="normal" if box.get() else "disabled")
        if on_paste:
            m.add_command(label="Clear", command=lambda: set_entry(box, ""),
                          state="normal" if box.get() else "disabled")
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    seqs = ["<Button-3>"] + (["<Button-2>", "<Control-Button-1>"] if sys.platform == "darwin" else [])
    for seq in seqs:
        box.bind(seq, popup, add="+")
    return box


class Pages:
    """Stacks page frames in one spot and raises the selected one."""

    def __init__(self, app, parent):
        self.app, self.parent = app, parent
        self.frames, self.current = {}, None

    def add(self, name):
        f = ctk.CTkFrame(self.parent, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames[name] = f
        return f

    def tab(self, name):
        return self.frames[name]

    def get(self):
        return self.current

    def set(self, name):
        self.current = name
        self.frames[name].tkraise()
        self.app._nav_changed(name)


class App(ctk.CTk):
    def __init__(self, incoming=None, start_hidden=False, restarted=False):
        ctk.set_appearance_mode(config["theme"])
        ctk.set_default_color_theme("blue")
        apply_theme(config.get("color_theme", "Indigo"))
        super().__init__(fg_color=C["bg"])
        self.title("Video Downloader")
        self.geometry("1020x700")
        self.minsize(900, 620)
        self._set_icon()

        self._calls = queue.Queue()
        self._rows, self._row_order = {}, None
        self._heights = []
        self._preview_token, self._preview = 0, None
        self._clip_last, self._offered, self._toast = None, set(), None
        self._updating = self._update_ready = self._quitting = False
        self._history_job = None
        self._more_open = False

        self.manager = engine.DownloadManager(
            get_parallel=lambda: config["parallel"],
            on_file=lambda job, path, title, url: self.call_soon(self._file_done, job, path, title, url),
            on_finished=lambda job: self.call_soon(self._job_finished, job))
        self.tray = Tray(self.call_soon, self.show, self.download_clipboard,
                         self.open_folder, self.quit_app)
        self._build()

        self.ipc = ipc.Server(lambda m: self.call_soon(self.handle_message, m))
        self.ipc.start(wait=10 if restarted else 0)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        for s in saved_queue.load():  # downloads left over from last time
            self.manager.add(s["url"], s["opts"], s.get("force", False), s.get("title", ""))
        if start_hidden and self.tray.ok:
            self.withdraw()
        if incoming:
            self.handle_message(incoming)

        self._check_tools()
        engine.warm_up(config["cookies"])
        self.after(100, self._pump)
        self.after(400, self._refresh_queue)
        self.after(1500, self._watch_clipboard)
        self.after(4000, self._auto_update)

    # ================= plumbing =================
    def _set_icon(self):
        try:
            ico = ASSETS / "VideoDownloader.ico"
            if os.name == "nt" and ico.exists():
                # set it right away (so CustomTkinter never puts its own icon on the taskbar) and once more later
                self.iconbitmap(str(ico), default=str(ico))
                self.after(300, lambda: self.iconbitmap(str(ico), default=str(ico)))
            else:
                from PIL import ImageTk
                self._icon_photo = ImageTk.PhotoImage(icon_image(64))
                self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    def call_soon(self, fn, *args):
        """Thread-safe: run fn on the Tk thread."""
        self._calls.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self._calls.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    self.report_callback_exception(*sys.exc_info())
        except queue.Empty:
            pass
        if not self._quitting:
            self.after(100, self._pump)

    def report_callback_exception(self, exc, val, tb):
        traceback.print_exception(exc, val, tb)
        self.set_status(f"Error: {val}")

    def set_status(self, text):
        self.status.configure(text=text)

    def _hidden(self):
        return self.state() == "withdrawn"

    def show(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _check_tools(self):
        missing = [n for n, ok in (("FFmpeg", has_ffmpeg()), ("Deno", deno_path())) if not ok]
        if missing:
            self.set_status(f"Missing {' and '.join(missing)}: run install.bat again "
                            "(MP4/MP3 need FFmpeg, YouTube needs Deno)")

    # ================= layout =================
    def _build(self):
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- sidebar ----
        side = ctk.CTkFrame(self, fg_color=C["side"], corner_radius=0, width=220)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        ctk.CTkFrame(self, fg_color=C["border"], width=1, corner_radius=0).grid(row=0, column=1, sticky="ns")

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(22, 26))
        logo = ctk.CTkImage(icon_image(64), size=(34, 34))
        ctk.CTkLabel(brand, text="", image=logo).pack(side="left")
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=10)
        label(names, "Video", 14, "bold").pack(anchor="w")
        label(names, "Downloader", 14, "bold").pack(anchor="w")

        self.nav = {}
        for name, glyph in NAV:
            b = ctk.CTkButton(side, text=f"   {glyph}    {name}", anchor="w", height=40, corner_radius=6,
                              fg_color="transparent", hover_color=C["hover"], text_color=C["text"],
                              font=font(13), command=lambda n=name: self.tabs.set(n))
            b.pack(fill="x", padx=12, pady=2)
            self.nav[name] = b

        foot = ctk.CTkFrame(side, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=20, pady=18)
        label(foot, f"Version {__version__}", 11, muted=True).pack(anchor="w")
        label(foot, f"yt-dlp {updater.current_version()}", 11, muted=True).pack(anchor="w")

        # ---- content ----
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=2, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.grid(row=0, column=0, sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)

        self.tabs = Pages(self, holder)
        for name, _ in NAV:
            self.tabs.add(name)
        self._build_download(self.tabs.tab("Download"))
        self._build_queue(self.tabs.tab("Queue"))
        self._build_history(self.tabs.tab("History"))
        self._build_settings(self.tabs.tab("Settings"))

        bar = ctk.CTkFrame(content, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=32, pady=(0, 12))
        bar.grid_columnconfigure(0, weight=1)
        self.status = label(bar, "Ready", 12, muted=True)
        self.status.grid(row=0, column=0, sticky="ew")
        self.restart_btn = primary(bar, "Restart to finish update", self.restart_app, height=30, width=190)
        self.tabs.set("Download")

    def _nav_changed(self, name):
        for n, b in self.nav.items():
            on = n == name
            b.configure(fg_color=C["soft"] if on else "transparent",
                        text_color=C["accent"] if on else C["text"],
                        font=font(13, "bold" if on else "normal"))
        if name == "History":
            self._render_history()

    def _page_header(self, parent, title, subtitle=""):
        h = ctk.CTkFrame(parent, fg_color="transparent")
        h.grid(row=0, column=0, sticky="ew", padx=32, pady=(26, 16))
        h.grid_columnconfigure(0, weight=1)
        label(h, title, 24, "bold").grid(row=0, column=0, sticky="w")
        sub = label(h, subtitle, 13, muted=True)
        sub.grid(row=1, column=0, sticky="w", pady=(2, 0))
        actions = ctk.CTkFrame(h, fg_color="transparent", width=1, height=1)
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        return sub, actions

    # ---------- Download page ----------
    def _build_download(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._page_header(page, "Download", "Paste a link from YouTube, X, TikTok, Instagram and 1,000+ other sites.")
        body = scroll(page)
        body.grid(row=1, column=0, sticky="nsew", padx=(20, 12))
        body.grid_columnconfigure(0, weight=1)

        # link
        lc = card(body)
        lc.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 12))
        lc.grid_columnconfigure(0, weight=1)
        self.url_entry = entry(lc, "Paste a video, playlist or channel link…", height=46)
        self.url_entry.configure(font=font(14))
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=16)
        self.url_entry.bind("<Return>", lambda e: self.preview())
        self.url_entry.bind("<<Paste>>", lambda e: self.after(80, self.preview))  # Ctrl+V = auto preview
        add_context_menu(self, self.url_entry, on_paste=self.preview)
        tip(ghost(lc, "Paste", self.paste, width=72, height=40), "paste").grid(row=0, column=1, padx=(0, 6))
        tip(ghost(lc, "Preview", self.preview, width=84, height=40), "preview").grid(row=0, column=2, padx=(0, 16))

        # preview (shown after Preview / paste)
        self.p_card = card(body)
        self.p_card.grid_columnconfigure(1, weight=1)
        self._blank = ctk.CTkImage(Image.new("RGBA", THUMB, (0, 0, 0, 0)), size=THUMB)
        self.thumb = ctk.CTkLabel(self.p_card, text="", image=self._blank, width=THUMB[0], height=THUMB[1],
                                  fg_color=C["field"], corner_radius=6)
        self.thumb.grid(row=0, column=0, rowspan=2, padx=14, pady=14)
        self.p_title = label(self.p_card, "", 15, "bold", wraplength=520)
        self.p_title.grid(row=0, column=1, sticky="sw", padx=(0, 16), pady=(16, 0))
        self.p_info = label(self.p_card, "", 12, muted=True, wraplength=520)
        self.p_info.grid(row=1, column=1, sticky="nw", padx=(0, 16), pady=(4, 16))

        # options
        oc = card(body)
        oc.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        oc.grid_columnconfigure(1, weight=1)
        label(oc, "Format", 12, muted=True).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 6))
        label(oc, "Quality", 12, muted=True).grid(row=0, column=1, sticky="w", padx=8, pady=(16, 6))
        self.fmt_seg = ctk.CTkSegmentedButton(
            oc, values=[f.split()[0] for f in FORMATS], command=self._format_changed, height=34,
            corner_radius=5, font=font(13), fg_color=C["field"], selected_color=C["soft"],
            selected_hover_color=C["soft"], unselected_color=C["field"], unselected_hover_color=C["hover"],
            text_color=C["text"])
        fmt = config["format"] if config["format"] in FORMATS else FORMATS[0]
        self.fmt_seg.set(fmt.split()[0])
        self.fmt_seg.grid(row=1, column=0, sticky="w", padx=18)
        for name, btn in self.fmt_seg._buttons_dict.items():
            tip(btn, name)
        self.q_menu = option(oc, VIDEO_QUALITIES, self._quality_changed, width=170)
        self._q_tip = Tooltip(self.q_menu, TIPS["quality_video"])
        self.q_menu.grid(row=1, column=1, sticky="w", padx=8)

        label(oc, "Save to", 12, muted=True).grid(row=2, column=0, sticky="w", padx=18, pady=(16, 6))
        fr = ctk.CTkFrame(oc, fg_color="transparent")
        fr.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18)
        fr.grid_columnconfigure(0, weight=1)
        self.folder_label = ctk.CTkLabel(fr, text="", anchor="w", height=34, corner_radius=5,
                                         fg_color=C["field"], text_color=C["text"], font=font(13))
        self.folder_label.grid(row=0, column=0, sticky="ew")
        tip(self.folder_label, "folder")
        ghost(fr, "Change…", self.browse, width=86, height=34).grid(row=0, column=1, padx=(8, 0))
        ghost(fr, "Open", self.open_folder, width=64, height=34).grid(row=0, column=2, padx=(6, 0))
        self._show_folder()

        self.more_btn = ctk.CTkButton(oc, text="More options  ▾", command=self._toggle_more, width=10,
                                      height=28, fg_color="transparent", hover_color=C["hover"],
                                      text_color=C["accent"], font=font(12, "bold"), anchor="w")
        self.more_btn.grid(row=4, column=0, sticky="w", padx=12, pady=(14, 12))

        self.more = ctk.CTkFrame(oc, fg_color="transparent")
        self.more.grid_columnconfigure((1, 3), weight=1)
        self.v_playlist = self._toggle(self.more, 0, 0, "Whole playlist / channel", "playlist")
        self._toggle(self.more, 0, 2, "Subtitles", "subtitles")
        self._toggle(self.more, 1, 0, "Embed thumbnail", "embed_thumbnail")
        self._toggle(self.more, 1, 2, "Title / artist info", "embed_metadata")
        clip = ctk.CTkFrame(self.more, fg_color="transparent")
        clip.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        tip(label(clip, "Clip", 13), "clip").pack(side="left", padx=(0, 12))
        self.clip_from = add_context_menu(self, tip(entry(clip, "0:00", width=80, height=34), "clip"))
        self.clip_from.pack(side="left")
        label(clip, "to", 13, muted=True).pack(side="left", padx=8)
        self.clip_to = add_context_menu(self, tip(entry(clip, "end", width=80, height=34), "clip"))
        self.clip_to.pack(side="left")
        label(clip, "Leave empty for the full video", 12, muted=True).pack(side="left", padx=12)
        lg = ctk.CTkFrame(self.more, fg_color="transparent")
        lg.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
        tip(label(lg, "Login from", 13), "login").pack(side="left", padx=(0, 12))
        self.cookie_menu = option(lg, COOKIE_BROWSERS, lambda v: config.set("cookies", v), width=150)
        self.cookie_menu.set(config["cookies"] if config["cookies"] in COOKIE_BROWSERS else COOKIE_BROWSERS[0])
        self.cookie_menu.pack(side="left")
        tip(self.cookie_menu, "login")
        label(lg, "For private, age-restricted, X, Instagram, Facebook", 12, muted=True).pack(side="left", padx=12)
        self._refresh_quality()

        tip(primary(body, "Download", self.add_from_form, height=50, size=15), "download").grid(
            row=3, column=0, sticky="ew", padx=12, pady=(4, 8))
        self.form_msg = label(body, "", 12, muted=True)
        self.form_msg.grid(row=4, column=0, sticky="w", padx=16)

    def _toggle(self, parent, row, col, text, key):
        var = tk.BooleanVar(value=bool(config[key]))
        tip(switch(parent, var, lambda: config.set(key, var.get())), key).grid(
            row=row, column=col, sticky="w", padx=(0, 10), pady=6)
        tip(label(parent, text, 13), key).grid(row=row, column=col + 1, sticky="w", padx=(0, 20))
        return var

    def _toggle_more(self):
        self._more_open = not self._more_open
        if self._more_open:
            self.more.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))
            self.more_btn.configure(text="Fewer options  ▴")
        else:
            self.more.grid_forget()
            self.more_btn.configure(text="More options  ▾")

    def _format(self):
        return next(f for f in FORMATS if f.startswith(self.fmt_seg.get()))

    def _format_changed(self, short_name):
        config.set("format", self._format())
        self._refresh_quality()

    def _quality_changed(self, value):
        config.set("audio_quality" if engine.is_audio(self._format()) else "video_quality", value)

    def _refresh_quality(self):
        if engine.is_audio(self._format()):
            values, current = list(AUDIO_QUALITIES), config["audio_quality"]
        else:
            values = ["Best"] + [f"{h}p" for h in self._heights] if self._heights else VIDEO_QUALITIES
            current = config["video_quality"]
        self.q_menu.configure(values=values)
        self.q_menu.set(current if current in values else values[0])
        if hasattr(self, "_q_tip"):
            self._q_tip.text = TIPS["quality_audio" if engine.is_audio(self._format()) else "quality_video"]

    # ---------- folder ----------
    def _show_folder(self):
        self.folder_label.configure(text="   " + short_path(config["folder"]))

    def _prepare_folder(self):
        p = config["folder"] or str(DEFAULT_FOLDER)
        try:
            Path(p).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Folder error", f"Can't use that folder:\n{e}")
            return False
        return True

    def browse(self):
        d = filedialog.askdirectory(initialdir=config["folder"] or str(Path.home()),
                                    title="Choose where to save")
        if d:
            config.set("folder", str(Path(d)))
            self._show_folder()

    def reset_folder(self):
        config.set("folder", str(DEFAULT_FOLDER))
        self._show_folder()
        self.set_status("Save folder reset to Downloads\\Video Downloader")

    def open_folder(self):
        p = Path(config["folder"])
        p.mkdir(parents=True, exist_ok=True)
        system.open_path(p)

    # ---------- preview ----------
    def paste(self):
        try:
            set_entry(self.url_entry, self.clipboard_get().strip())
        except tk.TclError:
            return
        self.preview()

    def _reset_preview(self):
        self._preview_token += 1
        self._preview, self._heights = None, []
        self.thumb.configure(image=self._blank, text="▶", text_color=C["muted"], font=font(28))
        self.p_card.grid_forget()
        self._refresh_quality()

    def preview(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        self._reset_preview()
        tok = self._preview_token
        self.p_card.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.p_title.configure(text="Loading preview…")
        self.p_info.configure(text=short(url, 90))
        playlist, cookies = config["playlist"], config["cookies"]

        def work():
            try:
                info = engine.fetch_preview(url, playlist, cookies)
                img = None
                if info.get("thumb"):
                    try:
                        img = Image.open(io.BytesIO(engine.fetch_bytes(info["thumb"]))).convert("RGB")
                    except Exception:
                        img = None
                self.call_soon(self._show_preview, tok, url, info, img)
            except Exception as e:
                self.call_soon(self._preview_failed, tok, engine.clean_error(e))

        threading.Thread(target=work, daemon=True).start()

    def _show_preview(self, tok, url, info, img):
        if tok != self._preview_token:
            return
        self._preview = {"url": url, "title": info["title"]}
        self.p_title.configure(text=short(info["title"], 140))
        if info["kind"] == "playlist":
            bits = [f'Playlist · {info["count"]} videos', info["uploader"]]
            if not self.v_playlist.get():  # it's a playlist link, so turn the switch on
                self.v_playlist.set(True)
                config.set("playlist", True)
            self._heights = []
        else:
            bits = [info["uploader"],
                    engine.fmt_time(info["duration"]) if info.get("duration") else "",
                    f'up to {info["heights"][0]}p' if info["heights"] else ""]
            self._heights = info["heights"]
        self.p_info.configure(text="  ·  ".join(b for b in bits if b))
        self._refresh_quality()
        if img:
            img.thumbnail(THUMB)
            self._thumb_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.thumb.configure(image=self._thumb_img, text="")

    def _preview_failed(self, tok, msg):
        if tok == self._preview_token:
            self.p_title.configure(text="Couldn't load the preview")
            self.p_info.configure(text=msg + "\nYou can still try downloading.")

    # ---------- adding downloads ----------
    def add_from_form(self):
        url = self.url_entry.get().strip()
        if not url.lower().startswith(("http://", "https://")):
            self.form_msg.configure(text="Paste a link that starts with http:// or https://", text_color=C["bad"])
            return
        try:
            start = engine.parse_time(self.clip_from.get())
            end = engine.parse_time(self.clip_to.get())
        except ValueError:
            self.form_msg.configure(text="Clip times look wrong. Use 1:20, 1:02:03 or seconds like 80.",
                                    text_color=C["bad"])
            return
        if start is not None and end is not None and end <= start:
            self.form_msg.configure(text="The clip end must be after the start.", text_color=C["bad"])
            return
        if not self._prepare_folder():
            return
        o = config.job_settings()
        o["audio_quality" if engine.is_audio(o["format"]) else "video_quality"] = self.q_menu.get()
        o["clip_start"], o["clip_end"] = start, end
        title = self._preview["title"] if self._preview and self._preview["url"] == url else ""
        self._enqueue(url, o, title=title)
        set_entry(self.url_entry, "")
        set_entry(self.clip_from, "")
        set_entry(self.clip_to, "")
        self._reset_preview()
        n = len(self.manager.unfinished())
        self.form_msg.configure(text=f"✓  Added to the queue ({n} in queue). Paste another link or open Queue.",
                                text_color=C["ok"])

    def _enqueue(self, url, o, force=False, title=""):
        job = self.manager.add(url, o, force, title)
        self._save_queue()
        self.set_status(f"Added: {short(title or url, 70)}")
        return job

    def handle_message(self, m):
        """Links from the Chrome button / a second launch / the clipboard pop-up."""
        links = m.get("links") or []
        if not links:
            if m.get("show", True):
                self.show()
            return
        self._add_links(links)

    def _add_links(self, links):
        added = 0
        for link in links:
            url, mode = link.get("url", ""), link.get("mode", "")
            if not url:
                continue
            if mode == "options":
                self.show()
                self.tabs.set("Download")
                set_entry(self.url_entry, url)
                self.preview()
                continue
            if self.manager.has_url(url):
                continue
            o = config.job_settings()
            if mode == "audio" and not engine.is_audio(o["format"]):
                o["format"] = "MP3 (audio)"
            if mode == "video" and engine.is_audio(o["format"]):
                o["format"] = "MP4 (video)"
            self._enqueue(url, o)
            added += 1
        if added:
            if self._hidden() and self.tray.ok:
                self.tray.notify(f"Added {added} link{'s' if added > 1 else ''} to the queue")
            else:
                self.show()
                self.tabs.set("Queue")

    def download_clipboard(self):
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            text = ""
        if text.lower().startswith(("http://", "https://")):
            self._add_links([{"url": text}])
        else:
            self.tray.notify("There's no link in the clipboard")

    # ---------- Queue page ----------
    def _build_queue(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self.q_summary, actions = self._page_header(page, "Queue", "")
        tip(ghost(actions, "Retry failed", self.retry_failed, width=104), "retry_failed").pack(side="left", padx=(0, 8))
        tip(ghost(actions, "Clear finished", lambda: (self.manager.clear_finished(), self._save_queue()),
                  width=116), "clear_finished").pack(side="left")
        self.q_list = scroll(page)
        self.q_list.grid(row=1, column=0, sticky="nsew", padx=(20, 12), pady=(0, 8))
        self.q_list.grid_columnconfigure(0, weight=1)
        self.q_empty = empty_state(self.q_list, "↓", "Nothing in the queue",
                                   "Add links from the Download page, the Chrome button,\nor just copy a video link.")

    def _refresh_queue(self):
        if self._quitting:
            return
        jobs = list(self.manager.jobs)
        order = [j.id for j in jobs]
        if order != self._row_order:
            for jid in set(self._rows) - set(order):
                self._rows.pop(jid).destroy()
            for i, j in enumerate(jobs):
                if j.id not in self._rows:
                    self._rows[j.id] = JobRow(self.q_list, self, j)
                self._rows[j.id].grid(row=i, column=0, sticky="ew", padx=12, pady=(0, 10))
            self._row_order = order
            if jobs:
                self.q_empty.grid_forget()
            else:
                self.q_empty.grid(row=0, column=0, pady=80)
        for row in self._rows.values():
            row.refresh()

        active = [j for j in jobs if j.active]
        waiting = sum(1 for j in jobs if j.status == "Queued")
        done = sum(1 for j in jobs if j.status in ("Done", "Skipped"))
        failed = sum(1 for j in jobs if j.status == "Failed")
        parts = [f"{len(active)} downloading" if active else "", f"{waiting} waiting" if waiting else "",
                 f"{done} done" if done else "", f"{failed} failed" if failed else ""]
        self.q_summary.configure(text="  ·  ".join(p for p in parts if p) or "Nothing downloading right now")
        busy = len(active) + waiting
        self.nav["Queue"].configure(text="   ≡    Queue" + (f"   ({busy})" if busy else ""))
        if active:
            pct = sum(j.progress for j in active) / len(active) * 100
            self.title(f"Video Downloader · {len(active)} downloading ({pct:.0f}%)")
        else:
            self.title("Video Downloader")
        self.after(400, self._refresh_queue)

    def _save_queue(self):
        saved_queue.save([j.to_saved() for j in self.manager.unfinished()])

    def retry_job(self, job):
        self.manager.retry(job)
        self._save_queue()

    def retry_failed(self):
        for j in list(self.manager.jobs):
            if j.status == "Failed":
                self.manager.retry(j)
        self._save_queue()

    def remove_job(self, job):
        self.manager.remove(job)
        self._save_queue()

    def open_job(self, job):
        files = [f for f in job.files if Path(f).exists()]
        system.open_path(files[-1] if files else job.opts["folder"])

    def reveal_job(self, job):
        files = [f for f in job.files if Path(f).exists()]
        if files:
            system.reveal(files[-1])
        else:
            system.open_path(job.opts["folder"])

    def _job_finished(self, job):
        self._save_queue()
        if self._hidden() or self.focus_displayof() is None:
            name = short(job.title or job.url, 90)
            if job.status == "Done":
                self.tray.notify(name, "Download finished")
            elif job.status == "Failed":
                self.tray.notify(f"{name}\n{job.error}", "Download failed")
        self._maybe_restart_for_update()

    def _file_done(self, job, path, title, url):
        history.add(title, url, path, engine.format_label(job.opts), job.opts)
        if self.tabs.get() == "History":
            self._render_history()

    # ---------- History page ----------
    def _build_history(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self.h_count, actions = self._page_header(page, "History", "")
        self.h_search = add_context_menu(self, entry(actions, "Search…", width=220, height=34))
        self.h_search.pack(side="left", padx=(0, 8))
        self.h_search.bind("<KeyRelease>", lambda e: self._schedule_history())
        ghost(actions, "Clear", self.clear_history, width=64, danger=True).pack(side="left")
        self.h_list = scroll(page)
        self.h_list.grid(row=1, column=0, sticky="nsew", padx=(20, 12), pady=(0, 8))
        self.h_list.grid_columnconfigure(0, weight=1)

    def _schedule_history(self):
        if self._history_job:
            self.after_cancel(self._history_job)
        self._history_job = self.after(250, self._render_history)

    def _render_history(self):
        self._history_job = None
        for w in self.h_list.winfo_children():
            w.destroy()
        q = self.h_search.get().strip().lower()
        items = [e for e in reversed(history.items)
                 if not q or q in e["title"].lower() or q in e["url"].lower()]
        shown = items[:60]
        for i, e in enumerate(shown):
            HistoryRow(self.h_list, self, e).grid(row=i, column=0, sticky="ew", padx=12, pady=(0, 10))
        if not items:
            empty_state(self.h_list, "◷", "No matches" if q else "No downloads yet",
                        "Try another search." if q else "Everything you download shows up here.").grid(
                row=0, column=0, pady=80)
        more = " · search to find older ones" if len(items) > len(shown) else ""
        self.h_count.configure(text=f"{len(items)} download{'s' if len(items) != 1 else ''}{more}")

    def clear_history(self):
        if messagebox.askyesno("Clear history", "Remove all entries from the history?\n"
                                                "Your downloaded files are not deleted."):
            history.clear()
            self._render_history()

    def redownload(self, entry_):
        if entry_.get("opts"):
            o = dict(entry_["opts"], folder=config["folder"])
            self._enqueue(entry_["url"], o, force=True, title=entry_["title"])
            self.tabs.set("Queue")
            return
        o = config.job_settings()
        fmt, _, quality = entry_.get("format", "").partition(" ")
        full = next((f for f in FORMATS if f.startswith(fmt)), None)
        if full:
            o["format"] = full
            if engine.is_audio(full):
                o["audio_quality"] = next((k for k in AUDIO_QUALITIES if k.startswith(quality)),
                                          o["audio_quality"])
            elif quality:
                o["video_quality"] = quality
        self._enqueue(entry_["url"], o, force=True, title=entry_["title"])
        self.tabs.set("Queue")

    # ---------- Settings page ----------
    def _build_settings(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._page_header(page, "Settings", "Changes are saved automatically.")
        body = self._settings_scroll = scroll(page)
        body.grid(row=1, column=0, sticky="nsew", padx=(20, 12), pady=(0, 8))
        body.grid_columnconfigure(0, weight=1)
        r = [0]

        def place(widget, pady=(0, 18)):
            widget.grid(row=r[0], column=0, sticky="ew", padx=12, pady=pady)
            r[0] += 1

        # ---- About ----
        about = card(body)
        about.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(about, text="", image=ctk.CTkImage(icon_image(128), size=(56, 56))).grid(
            row=0, column=0, rowspan=3, padx=18, pady=18)
        label(about, "Video Downloader", 17, "bold").grid(row=0, column=1, sticky="sw", pady=(18, 0))
        label(about, f"Version {__version__}", 13).grid(row=1, column=1, sticky="w")
        self.ver_label = label(about, f"yt-dlp {updater.current_version()}", 12, muted=True)
        self.ver_label.grid(row=2, column=1, sticky="nw", pady=(0, 18))
        ab = ctk.CTkFrame(about, fg_color="transparent")
        ab.grid(row=0, column=2, rowspan=3, padx=18)
        primary(ab, "Check for updates", lambda: self._run_update(auto=False), height=34).pack(side="left")
        ghost(ab, "Restart", self.restart_app, width=72, height=34).pack(side="left", padx=(8, 0))
        self.upd_msg = label(about, "", 12, muted=True)
        self.upd_msg.grid(row=3, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 14))
        self.upd_msg.grid_remove()  # shown when there's an update message
        place(about)

        # ---- sections ----
        def section(title):
            label(body, title.upper(), 11, "bold", muted=True).grid(
                row=r[0], column=0, sticky="w", padx=16, pady=(4, 6))
            r[0] += 1
            c = card(body)
            c.grid_columnconfigure(0, weight=1)
            c._rows = 0
            place(c)
            return c

        def row(c, title, desc, make_control, tip_key=None):
            if c._rows:
                ctk.CTkFrame(c, height=1, fg_color=C["border"], corner_radius=0).grid(
                    row=c._rows * 2 - 1, column=0, columnspan=2, sticky="ew", padx=18)
            f = ctk.CTkFrame(c, fg_color="transparent")
            f.grid(row=c._rows * 2, column=0, sticky="ew", padx=(18, 12), pady=12)
            t = label(f, title, 13)
            t.pack(anchor="w")
            if tip_key:
                tip(t, tip_key)
            if desc:
                d = label(f, desc, 12, muted=True, wraplength=200)
                d.pack(anchor="w", fill="x", pady=(2, 0))
                # wrap to the space actually left next to the control
                f.bind("<Configure>", lambda e, d=d: d.configure(
                    wraplength=max(120, int(e.width / d._get_widget_scaling()) - 4)), add="+")
            ctl = make_control(c)
            ctl.grid(row=c._rows * 2, column=1, sticky="e", padx=18)
            if tip_key:
                tip(ctl, tip_key)
            c._rows += 1
            return ctl

        def sw(key, on_change=None, enabled=True):
            def make(parent):
                var = tk.BooleanVar(value=bool(config[key]))

                def changed():
                    config.set(key, var.get())
                    if on_change:
                        on_change(var.get())

                w = switch(parent, var, changed)
                if not enabled:
                    w.configure(state="disabled")
                return w
            return make

        def menu(values, key, cast=str, width=120):
            def make(parent):
                m = option(parent, values, lambda v: config.set(key, cast(v)), width=width)
                m.set(str(config[key]) if str(config[key]) in values else values[0])
                return m
            return make

        def buttons(*specs):
            def make(parent):
                f = ctk.CTkFrame(parent, fg_color="transparent")
                for text, cmd in specs:
                    ghost(f, text, cmd).pack(side="left", padx=(8, 0))
                return f
            return make

        s = section("Appearance")

        def theme_menu(parent):
            m = option(parent, ["Dark", "Light", "System"],
                       lambda v: (config.set("theme", v), ctk.set_appearance_mode(v)), width=120)
            m.set(config["theme"])
            return m
        row(s, "Mode", "", theme_menu, "mode")

        def swatches(parent):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            current = config.get("color_theme", "Indigo")
            for name, t in THEMES.items():
                fill = t["accent"] if name != "Midnight" else ("#1A1B23", "#000000")
                b = ctk.CTkButton(f, text="", width=30, height=30, corner_radius=15, fg_color=fill,
                                  hover_color=t["accent_h"] if name != "Midnight" else fill,
                                  border_width=3 if name == current else 0, border_color=C["text"],
                                  command=lambda n=name: self._set_color_theme(n))
                if name == "Midnight":  # black swatch with an accent ring
                    b.configure(border_width=3, border_color=C["text"] if name == current else t["accent"])
                b.pack(side="left", padx=(8, 0))
                tip(b, name)
            return f
        row(s, "Color theme", f"Current: {config.get('color_theme', 'Indigo')}", swatches, "color_theme")
        row(s, "Hover tips", "Show short explanations like this one", sw("tooltips"), "tooltips")

        s = section("Downloads")
        row(s, "Save folder", "Reset goes back to Downloads\\Video Downloader",
            buttons(("Change…", self.browse), ("Reset", self.reset_folder)), "save_folder")

        def tmpl(parent):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            self.tmpl_menu = option(f, list(TEMPLATES) + ["Custom"], self._template_preset, width=150)
            self.tmpl_menu.pack(side="left")
            self.tmpl_entry = add_context_menu(self, entry(f, width=230, height=34))
            self.tmpl_entry.pack(side="left", padx=(8, 0))
            self.tmpl_entry.bind("<FocusOut>", lambda e: self._template_typed())
            self.tmpl_entry.bind("<Return>", lambda e: self._template_typed())
            set_entry(self.tmpl_entry, config["template"])
            self.tmpl_menu.set(next((k for k, v in TEMPLATES.items() if v == config["template"]), "Custom"))
            return f
        row(s, "File names", "yt-dlp fields like %(title)s, %(uploader)s, %(id)s", tmpl, "template")

        def subs(parent):
            self.sub_entry = add_context_menu(self, entry(parent, width=140, height=34))
            set_entry(self.sub_entry, config["sub_langs"])
            self.sub_entry.bind("<FocusOut>",
                                lambda e: config.set("sub_langs", self.sub_entry.get().strip() or "en"))
            return self.sub_entry
        row(s, "Subtitle languages", "Comma separated, e.g. en, ar", subs, "sub_langs")
        row(s, "Skip videos I already have", "Checked per format, so an MP3 after the MP4 still downloads",
            sw("skip_existing"), "skip")
        row(s, "MP4: prefer H.264", "Plays everywhere. YouTube then tops out at 1080p; turn off for 4K",
            sw("mp4_compat"), "h264")
        row(s, "Precise clip cuts", "Exact to the second, but slower (re-encodes the clip)", sw("precise_cuts"),
            "precise")

        s = section("Speed")
        row(s, "Connections per download",
            "Fast mode: each file over several connections. 1 = off"
            + ("" if aria2c_path() else " (aria2 missing: run install.bat)"),
            menu(["1", "4", "8", "16"], "connections", int), "connections")
        row(s, "Downloads at once", "", menu(["1", "2", "3"], "parallel", int), "parallel")
        row(s, "Retries", "When the connection drops", menu(["3", "5", "10", "20"], "retries", int), "retries")

        def speed(parent):
            self.speed_entry = add_context_menu(self, entry(parent, "No limit", width=140, height=34))
            set_entry(self.speed_entry, config["speed_limit"])
            self.speed_entry.bind("<FocusOut>", lambda e: self._speed_typed())
            self.speed_entry.bind("<Return>", lambda e: self._speed_typed())
            return self.speed_entry
        row(s, "Speed limit", "e.g. 2M (2 MB/s) or 500K. Empty = full speed", speed, "speed_limit")
        self.set_msg = label(body, "", 12)
        self.set_msg.configure(text_color=C["bad"])
        self.set_msg.grid(row=r[0], column=0, sticky="w", padx=16)
        r[0] += 1

        s = section("Background")
        row(s, "Offer to download links I copy", "A small pop-up appears when you copy a video link",
            sw("clipboard_watch"), "clipboard")
        row(s, "Keep running in the tray", "Closing the window hides it instead of quitting",
            sw("close_to_tray", enabled=self.tray.ok), "tray")
        if system.autostart_supported():
            def autostart(parent):
                var = tk.BooleanVar(value=system.autostart_enabled())

                def toggle():
                    try:
                        system.set_autostart(var.get())
                    except OSError as e:
                        var.set(not var.get())
                        self.set_status(f"Couldn't change startup setting: {e}")
                return switch(parent, var, toggle)
            row(s, "Start with Windows", "Starts hidden in the tray", autostart, "autostart")
        row(s, "Update yt-dlp automatically", "Checks once a day; sites change often", sw("auto_update"), "autoupdate")

        s = section("Chrome button")
        row(s, "Extension", "chrome://extensions → Developer mode → Load unpacked → pick this folder",
            buttons(("Open folder", self._open_extension)))
        row(s, "Bookmarklet", "No extension? Save this as a bookmark and click it on any video page",
            buttons(("Copy", self._copy_bookmarklet)))
        self.chrome_msg = label(body, "", 12, muted=True)
        self.chrome_msg.grid(row=r[0], column=0, sticky="w", padx=16)
        r[0] += 1

        s = section("Tools")
        for name, ok, need in (("FFmpeg", has_ffmpeg(), "merging, MP3 and clips"),
                               ("Deno", deno_path(), "YouTube"),
                               ("aria2", aria2c_path(), "fast mode")):
            row(s, name, f"Needed for {need}",
                lambda p, ok=ok: ctk.CTkLabel(p, text="●  Found" if ok else "●  Missing", font=font(12, "bold"),
                                              text_color=C["ok"] if ok else C["bad"]))
        row(s, "Log file", "Useful when something goes wrong",
            buttons(("Open", lambda: system.open_path(DATA_DIR / "app.log"))))

    def _set_color_theme(self, name):
        config.set("color_theme", name)
        apply_theme(name)
        self._rebuild("Settings")

    def _rebuild(self, page):
        """Recreate the window contents with the new colours (keeps queue, tray, settings)."""
        y = None
        try:
            y = self._settings_scroll._parent_canvas.yview()[0]
        except Exception:
            pass
        if self._toast is not None:
            self._toast.close()
        for w in list(self.winfo_children()):
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self.configure(fg_color=C["bg"])
        self._rows, self._row_order = {}, None
        self._preview_token += 1
        self._preview, self._heights, self._more_open = None, [], False
        self._build()
        self.tabs.set(page)
        if y is not None:
            self.after(50, lambda: self._settings_scroll._parent_canvas.yview_moveto(y))

    def _template_preset(self, name):
        if name in TEMPLATES:
            set_entry(self.tmpl_entry, TEMPLATES[name])
            config.set("template", TEMPLATES[name])
            self.set_msg.configure(text="")
        else:
            self.tmpl_entry.focus_set()

    def _template_typed(self):
        text = self.tmpl_entry.get().strip()
        if not text or not engine.valid_template(text):
            self.set_msg.configure(text="That file name template isn't valid, keeping the old one.")
            set_entry(self.tmpl_entry, config["template"])
            return
        self.set_msg.configure(text="")
        config.set("template", text)
        self.tmpl_menu.set(next((k for k, v in TEMPLATES.items() if v == text), "Custom"))

    def _speed_typed(self):
        text = self.speed_entry.get().strip()
        if not engine.valid_speed(text):
            self.set_msg.configure(text="Speed limit should look like 2M or 500K.")
            return
        self.set_msg.configure(text="")
        config.set("speed_limit", text)

    def _open_extension(self):
        if EXTENSION_DIR.exists():
            system.open_path(EXTENSION_DIR)
        else:
            self.chrome_msg.configure(text="Extension folder not found next to the app.")

    def _copy_bookmarklet(self):
        self.clipboard_clear()
        self.clipboard_append(BOOKMARKLET)
        self._clip_last = BOOKMARKLET  # don't offer our own text
        self.chrome_msg.configure(text="Copied. Make a new bookmark and paste this as its URL.")

    # ================= clipboard watcher =================
    def _watch_clipboard(self):
        if self._quitting:
            return
        self.after(1200, self._watch_clipboard)
        try:
            text = self.clipboard_get()
        except Exception:
            return
        text = text.strip() if isinstance(text, str) else ""
        if text == self._clip_last:
            return
        first, self._clip_last = self._clip_last is None, text
        if first or not config["clipboard_watch"]:
            return
        if len(text) > 2000 or "\n" in text or not text.lower().startswith(("http://", "https://")):
            return
        if text in self._offered or self.manager.has_url(text) or self.url_entry.get().strip() == text:
            return
        self._offered.add(text)

        def check():
            if engine.is_supported(text):
                self.call_soon(self._offer, text)

        threading.Thread(target=check, daemon=True).start()

    def _offer(self, url):
        engine.info_cache.prefetch(url, config.job_settings())  # ready by the time you click
        if self._toast is not None:
            self._toast.close()
        self._toast = Toast(self, url)

    # ================= updates =================
    def _auto_update(self):
        if config["auto_update"] and time.time() - config["last_update_check"] > 20 * 3600:
            self._run_update(auto=True)

    def _run_update(self, auto):
        if self._updating:
            return
        self._updating = True
        self.upd_msg.grid()
        self.upd_msg.configure(text="Checking for a yt-dlp update…")

        def work():
            try:
                changed, ver = updater.update()
                self.call_soon(self._update_done, auto, changed, ver, None)
            except Exception as e:
                self.call_soon(self._update_done, auto, False, None, engine.clean_error(e))

        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, auto, changed, ver, err):
        self._updating = False
        if err:
            self.upd_msg.configure(text=f"Update failed: {err}")
            return
        config.set("last_update_check", time.time())
        if not changed:
            self.upd_msg.configure(text=f"Everything is up to date (yt-dlp {ver}).")
            return
        self._update_ready = True
        self.upd_msg.configure(text=f"yt-dlp {ver} installed. Restart the app to use it.")
        self.restart_btn.grid(row=0, column=1)
        if auto and self._hidden():
            self.tray.notify(f"yt-dlp updated to {ver}. The app will restart when downloads finish.")
        self._maybe_restart_for_update()

    def _maybe_restart_for_update(self):
        """Apply an update silently when the app is in the tray and idle."""
        if self._update_ready and self._hidden() and not self.manager.unfinished():
            self._shutdown()
            system.restart()
            self.destroy()

    def restart_app(self):
        active = self.manager.active_count()
        if active and not messagebox.askyesno(
                "Restart", f"{active} download(s) in progress. Restart now?\n"
                           "They will continue after the restart."):
            return
        self._shutdown()
        system.restart()
        self.destroy()

    # ================= closing =================
    def on_close(self):
        if config["close_to_tray"] and self.tray.ok:
            self.withdraw()
            if not config.get("told_tray"):
                config.set("told_tray", True)
                self.tray.notify("Still running in the tray. Right-click the tray icon to quit.")
            self._maybe_restart_for_update()
        else:
            self.quit_app()

    def quit_app(self):
        active = self.manager.active_count()
        if active and not messagebox.askyesno(
                "Quit", f"{active} download(s) in progress. Quit anyway?\n"
                        "Unfinished downloads continue next time you open the app."):
            return
        self._shutdown()
        self.destroy()

    def _shutdown(self):
        self._quitting = True
        self._save_queue()
        self.ipc.close()
        self.tray.stop()
        if self._toast is not None:
            self._toast.close()


def empty_state(parent, glyph, title, text):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    badge = ctk.CTkFrame(f, width=64, height=64, corner_radius=32, fg_color=C["soft"])
    badge.pack(pady=(0, 14))
    badge.pack_propagate(False)
    ctk.CTkLabel(badge, text=glyph, text_color=C["accent"], font=font(26, "bold")).place(
        relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(f, text=title, font=font(15, "bold"), text_color=C["text"]).pack()
    ctk.CTkLabel(f, text=text, font=font(12), text_color=C["muted"], justify="center").pack(pady=(4, 0))
    return f


class JobRow(ctk.CTkFrame):
    def __init__(self, master, app, job):
        super().__init__(master, fg_color=C["card"], corner_radius=8, border_width=1, border_color=C["border"])
        self.app, self.job = app, job
        self._state = self._btn_state = None
        self.grid_columnconfigure(0, weight=1)
        self.fmt = engine.format_label(job.opts)
        self.title = label(self, "", 13, "bold")
        self.title.grid(row=0, column=0, sticky="ew", padx=(18, 8), pady=(14, 0))
        line = ctk.CTkFrame(self, fg_color="transparent")
        line.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(4, 0))
        self.dot = ctk.CTkLabel(line, text="●", font=font(10), width=10)
        self.dot.pack(side="left")
        self.status = ctk.CTkLabel(line, text="", font=font(12, "bold"))
        self.status.pack(side="left", padx=(6, 8))
        self.info = ctk.CTkLabel(line, text="", font=font(12), text_color=C["muted"], anchor="w", justify="left")
        self.info.pack(side="left", fill="x", expand=True)
        self.bar = ctk.CTkProgressBar(self, height=5, corner_radius=2, fg_color=C["field"],
                                      progress_color=C["accent"])
        self.bar.set(0)
        self.pad = ctk.CTkFrame(self, fg_color="transparent", height=14)
        self.btns = ctk.CTkFrame(self, fg_color="transparent")
        self.btns.grid(row=0, column=1, rowspan=3, padx=14, sticky="e")
        self.b = {
            "cancel": ghost(self.btns, "Cancel", lambda: app.manager.cancel(job), width=70),
            "retry": ghost(self.btns, "Retry", lambda: app.retry_job(job), width=64),
            "open": ghost(self.btns, "Open", lambda: app.open_job(job), width=60),
            "folder": ghost(self.btns, "Folder", lambda: app.reveal_job(job), width=64),
            "remove": ghost(self.btns, "✕", lambda: app.remove_job(job), width=32, border=False),
        }

    def refresh(self):
        j = self.job
        state = (j.status, round(j.progress, 3), j.detail, j.item, j.title)
        if state == self._state:
            return
        self._state = state
        self.title.configure(text=short(j.title or j.url, 70))
        color, name = STATUS_STYLE.get(j.status, ("muted", j.status))
        if j.item:
            name += f" {j.item}"
        if j.status == "Downloading":
            name += f"  {j.progress * 100:.0f}%"
        self.dot.configure(text_color=C[color])
        self.status.configure(text=name, text_color=C[color] if color != "muted" else C["text"])
        detail = j.error if j.status == "Failed" else j.detail
        self.info.configure(text=short("  ·  ".join(x for x in (self.fmt, detail) if x), 110))
        if j.finished:
            self.bar.grid_forget()
            self.pad.grid(row=2, column=0)
        else:
            self.pad.grid_forget()
            self.bar.grid(row=2, column=0, sticky="ew", padx=(18, 8), pady=(10, 16))
            self.bar.set(j.progress)
        show = (not j.finished, j.status in ("Failed", "Cancelled"),
                j.status == "Done" and bool(j.files), j.status in ("Done", "Skipped"), j.finished)
        if show != self._btn_state:
            self._btn_state = show
            for btn in self.b.values():
                btn.pack_forget()
            for visible, key in zip(show, ("cancel", "retry", "open", "folder", "remove")):
                if visible:
                    self.b[key].pack(side="left", padx=(6, 0))


class HistoryRow(ctk.CTkFrame):
    def __init__(self, master, app, e):
        super().__init__(master, fg_color=C["card"], corner_radius=8, border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        exists = bool(e.get("path")) and Path(e["path"]).exists()
        label(self, short(e["title"], 70), 13, "bold").grid(row=0, column=0, sticky="ew", padx=(18, 8), pady=(14, 0))
        info = f'{e["date"]}  ·  {e.get("format", "")}' + ("" if exists else "  ·  file moved or deleted")
        label(self, info, 12, muted=True).grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(4, 14))
        b = ctk.CTkFrame(self, fg_color="transparent")
        b.grid(row=0, column=1, rowspan=2, padx=14)
        ghost(b, "Open", lambda: system.open_path(e["path"]), width=60,
              state="normal" if exists else "disabled").pack(side="left", padx=(6, 0))
        ghost(b, "Folder", lambda: system.reveal(e["path"]), width=64).pack(side="left", padx=(6, 0))
        ghost(b, "Download again", lambda: app.redownload(e), width=118).pack(side="left", padx=(6, 0))


class Toast(ctk.CTkToplevel):
    """Small pop-up in the corner: 'Download this link?'"""

    def __init__(self, app, url):
        super().__init__(app, fg_color=C["card"])
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, border_width=1, border_color=C["border"])
        frame.pack(fill="both", expand=True)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(top, text="", image=ctk.CTkImage(icon_image(48), size=(22, 22))).pack(side="left")
        label(top, "Download this link?", 14, "bold").pack(side="left", padx=10)
        ghost(top, "✕", self.close, width=28, height=28, border=False).pack(side="right")
        label(frame, short(url, 70), 12, muted=True, wraplength=330).pack(anchor="w", padx=16, pady=(6, 12))
        b = ctk.CTkFrame(frame, fg_color="transparent")
        b.pack(fill="x", padx=16, pady=(0, 16))
        primary(b, "Video", lambda: self._go(url, "video"), height=32, width=80).pack(side="left")
        ghost(b, "MP3", lambda: self._go(url, "audio"), width=64).pack(side="left", padx=(8, 0))
        ghost(b, "Options…", lambda: self._go(url, "options"), width=90).pack(side="left", padx=(8, 0))
        self.update_idletasks()
        w, h = 380, self.winfo_reqheight()
        x, y = self.winfo_screenwidth() - w - 24, self.winfo_screenheight() - h - 72
        self.geometry(f"{w}x{h}+{x}+{y}")
        self._timer = self.after(15000, self.close)

    def _go(self, url, mode):
        self.close()
        self.app._add_links([{"url": url, "mode": mode}])

    def close(self):
        try:
            self.after_cancel(self._timer)
        except Exception:
            pass
        if self.app._toast is self:
            self.app._toast = None
        try:
            self.destroy()
        except Exception:
            pass
