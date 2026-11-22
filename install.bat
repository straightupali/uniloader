@echo off
setlocal
title Uniloader - Installer
set "APP=%LOCALAPPDATA%\Uniloader"
set "OLD=%LOCALAPPDATA%\YTDownloader"

echo ==========================================
echo   Uniloader 2.3.2 - Installer
echo ==========================================
echo Install folder: %APP%
echo If the app is running, quit it first (tray icon, right-click, Quit).
echo.

rem ---- find Python ----
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
    echo Python was not found. Installing Python 3.12 with winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Python installed. Please CLOSE this window and run install.bat again.
    pause
    exit /b 0
)

if not exist "%APP%" mkdir "%APP%"

rem ---- reuse FFmpeg from the first version, then remove it ----
if exist "%OLD%\ffmpeg\ffmpeg.exe" if not exist "%APP%\ffmpeg\ffmpeg.exe" xcopy /E /I /Y "%OLD%\ffmpeg" "%APP%\ffmpeg" >nul
if exist "%OLD%" rmdir /s /q "%OLD%"

copy /Y "%~dp0ytdl.py" "%APP%\" >nul
copy /Y "%~dp0requirements.txt" "%APP%\" >nul
xcopy /E /I /Y "%~dp0videodl" "%APP%\videodl" >nul
xcopy /E /I /Y "%~dp0assets" "%APP%\assets" >nul
xcopy /E /I /Y "%~dp0chrome_extension" "%APP%\chrome_extension" >nul

echo [1/3] Installing Python packages (yt-dlp, customtkinter, pystray, pillow)...
if not exist "%APP%\venv\Scripts\python.exe" %PY% -m venv "%APP%\venv" || goto :fail
"%APP%\venv\Scripts\python.exe" -m pip install --upgrade --disable-pip-version-check pip >nul
"%APP%\venv\Scripts\python.exe" -m pip install --upgrade --disable-pip-version-check -r "%APP%\requirements.txt" || goto :fail

echo [2/3] Getting FFmpeg and Deno...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0get_tools.ps1" -App "%APP%" || goto :fail

echo [3/3] Creating shortcuts and the Chrome link handler...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1" -App "%APP%" || goto :fail

echo.
echo ==========================================
echo Done! Open "Uniloader" from your Desktop or Start menu.
echo.
echo Chrome button: open chrome://extensions, turn on Developer mode,
echo click "Load unpacked" and choose:
echo   %APP%\chrome_extension
echo ==========================================
pause
exit /b 0

:fail
echo.
echo Something went wrong. Check your internet connection and try again.
pause
exit /b 1
