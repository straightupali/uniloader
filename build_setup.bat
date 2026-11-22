@echo off
setlocal
cd /d "%~dp0"
title Uniloader - Build Setup.exe
echo ==========================================
echo   Builds Output\Uniloader-Setup.exe
echo   (one-time, takes about 5 minutes)
echo ==========================================
echo.

set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY ( echo Python not found. Run install.bat first or install Python 3.12. & pause & exit /b 1 )

echo [1/4] Build environment...
if not exist build_env\Scripts\python.exe %PY% -m venv build_env || goto :fail
build_env\Scripts\python -m pip install --upgrade --disable-pip-version-check pip >nul
build_env\Scripts\python -m pip install --upgrade --disable-pip-version-check -r requirements.txt pyinstaller || goto :fail

echo [2/4] Packing the app with PyInstaller...
build_env\Scripts\pyinstaller --noconfirm --clean --windowed --name Uniloader ^
  --icon assets\Uniloader.ico --add-data "assets;assets" ^
  --collect-data customtkinter --hidden-import pystray._win32 ytdl.py || goto :fail

echo [3/4] Adding FFmpeg, Deno and the Chrome extension...
powershell -NoProfile -ExecutionPolicy Bypass -File get_tools.ps1 -App "%cd%\dist\Uniloader" || goto :fail
xcopy /E /I /Y chrome_extension "dist\Uniloader\chrome_extension" >nul

echo [4/4] Making the installer with Inno Setup...
call :find_iscc
if not defined ISCC (
    echo Inno Setup not found, installing it with winget...
    winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
    call :find_iscc
)
if not defined ISCC ( echo Couldn't find Inno Setup. Install it from jrsoftware.org and run this again. & goto :fail )
"%ISCC%" setup.iss || goto :fail

echo.
echo Done! Your installer is: %cd%\Output\Uniloader-Setup.exe
echo You can copy it to any Windows PC. No Python needed there.
pause
exit /b 0

:find_iscc
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
exit /b 0

:fail
echo.
echo Build failed. Scroll up to see the error.
pause
exit /b 1
