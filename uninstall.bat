@echo off
title Uniloader - Uninstall
cd /d "%TEMP%"
echo Quit Uniloader first (tray icon, right-click, Quit).
pause
powershell -NoProfile -Command "foreach ($d in [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) { Remove-Item (Join-Path $d 'Uniloader.lnk') -ErrorAction SilentlyContinue }"
reg delete "HKCU\Software\Classes\ytdl" /f >nul 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Uniloader /f >nul 2>nul
rmdir /s /q "%LOCALAPPDATA%\Uniloader" 2>nul
rmdir /s /q "%APPDATA%\Uniloader" 2>nul
echo Uniloader removed (settings and history too).
echo Your downloaded videos were not touched.
echo Remove the Chrome extension from chrome://extensions if you added it.
pause
