@echo off
title Video Downloader - Uninstall
cd /d "%TEMP%"
echo Quit Video Downloader first (tray icon, right-click, Quit).
pause
powershell -NoProfile -Command "foreach ($d in [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) { Remove-Item (Join-Path $d 'Video Downloader.lnk') -ErrorAction SilentlyContinue }"
reg delete "HKCU\Software\Classes\ytdl" /f >nul 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v VideoDownloader /f >nul 2>nul
rmdir /s /q "%LOCALAPPDATA%\VideoDownloader" 2>nul
rmdir /s /q "%APPDATA%\VideoDownloader" 2>nul
echo Video Downloader removed (settings and history too).
echo Your downloaded videos were not touched.
echo Remove the Chrome extension from chrome://extensions if you added it.
pause
