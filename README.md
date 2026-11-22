# Video Downloader 2.3.2

A Windows app for downloading video and audio from YouTube and 1,000+ other sites, built on yt-dlp.

## Install (pick one)

**Quick install:** double-click `install.bat`. It installs Python if needed, the app, FFmpeg, Deno (YouTube needs it) and aria2 (fast mode), plus Desktop/Start-menu shortcuts and the `ytdl://` link used by the Chrome button. Run it again any time to repair or upgrade.

**Real Setup.exe:** double-click `build_setup.bat` once. It builds `Output\VideoDownloader-Setup.exe`, a normal installer you can copy to any Windows PC (no Python needed there). It installs PyInstaller and Inno Setup for the build.

To remove: `uninstall.bat` for the quick install, or *Apps & features* for the Setup.exe install. Your downloaded files are never deleted.

## Chrome button

1. Open `chrome://extensions` and turn on **Developer mode**
2. **Load unpacked**, then choose the `chrome_extension` folder (Settings > Chrome button > *Open extension folder* shows it)
3. Click the toolbar button, or right-click a page/link > **Video Downloader** > Download video / Download audio (MP3) / Download with options...

The first time, Chrome asks "Open Video Downloader?". Tick **Always allow**.

**No extension?** Settings > *Copy bookmarklet*, then make a new bookmark and paste it as the URL. Clicking that bookmark on a video page does the same as the toolbar button.

**Chrome Web Store:** the extension is store-ready (icons, minimal permissions, no data collected), but Google's store policy doesn't allow extensions that download from YouTube, so expect a rejection. Developer mode or the bookmarklet is the practical route. It also works in Edge, Brave and other Chromium browsers.

## Tips

- **Login from:** for private, age-restricted, Instagram or Facebook videos. **Firefox** is the most reliable choice; Chrome on Windows encrypts its cookies in a way yt-dlp often can't read.
- **Downloads failing suddenly?** Settings > *Check for update now*. Sites change and yt-dlp catches up within days. Auto-update does this daily.
- **Speed:** fast mode downloads each file over several connections (Settings > *Connections per download*, default 8). If a site doesn't like it, the app retries that download in normal mode automatically. Also try *Downloads at once* = 2–3 for queues, and leave *Precise clip cuts* off for instant clips.
- **Faster start:** press Preview (or just Ctrl+V into the link box): the download then skips the "getting video info" step. Links waiting in the queue get their info in advance.
- **4K in MP4:** turn off *MP4: prefer H.264* in Settings, or pick MKV.
- **Problems:** Settings > *Open log file*.

Files: settings, history and queue live in `%APPDATA%\VideoDownloader`.
