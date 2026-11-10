@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Carina's Video Editor
cd /d "%~dp0"

echo.
echo   ==============================================
echo     Starting Carina's Video Editor ...
echo   ==============================================
echo.

rem ---- 1. uv (holt Python und alle Bausteine) ----
where uv >nul 2>nul
if errorlevel 1 (
  if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  ) else (
    echo   [1/4] One time only: downloading the install helper "uv" ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  )
)
where uv >nul 2>nul
if errorlevel 1 (
  echo.
  echo   ERROR: The install helper "uv" could not be installed.
  echo   Please check your internet connection and run start.bat again.
  pause
  exit /b 1
)

rem ---- 2. ffmpeg (schneiden und umwandeln) ----
if not exist "tools\ffmpeg\bin\ffmpeg.exe" (
  where ffmpeg >nul 2>nul
  if errorlevel 1 (
    echo   [2/4] One time only: downloading ffmpeg (about 100 MB, can take a few minutes^) ...
    if not exist tools mkdir tools
    curl.exe -L -# -o "tools\ffmpeg.zip" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    if errorlevel 1 (
      powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'tools\ffmpeg.zip'"
    )
    echo         Unpacking ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ProgressPreference='SilentlyContinue';" ^
      "Expand-Archive 'tools\ffmpeg.zip' -DestinationPath 'tools\ffmpeg_tmp' -Force;" ^
      "$inner = Get-ChildItem 'tools\ffmpeg_tmp' -Directory | Select-Object -First 1;" ^
      "Move-Item $inner.FullName 'tools\ffmpeg';" ^
      "Remove-Item 'tools\ffmpeg_tmp','tools\ffmpeg.zip' -Recurse -Force"
    if not exist "tools\ffmpeg\bin\ffmpeg.exe" (
      echo.
      echo   ERROR: ffmpeg could not be downloaded. Please check your internet and start again.
      pause
      exit /b 1
    )
  )
)

:bausteine
rem ---- 3. Python-Bausteine (mit Grafikkarten-Unterstuetzung, wenn Nvidia da ist) ----
echo   [3/4] Checking components (takes a few minutes the first time) ...
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  uv sync --quiet
) else (
  echo         Nvidia graphics card found: it will be used for speech recognition.
  uv sync --quiet --extra gpu
  if errorlevel 1 (
    echo         Graphics card components did not work. The app starts anyway, using the processor.
    uv sync --quiet
  )
)
if errorlevel 1 (
  echo.
  echo   ERROR: The components could not be installed.
  echo   Please check your internet connection and run start.bat again.
  pause
  exit /b 1
)

rem ---- 4. Starten ----
echo   [4/4] The app opens in your browser in a moment: http://127.0.0.1:8000
echo.
echo   Please keep this window open while you work with the app.
echo   To stop the app, just close this window.
echo.
uv run backend\app.py
if "%ERRORLEVEL%"=="3" (
  echo.
  echo   Update downloaded - the app is restarting ...
  echo.
  set "EDITOR_NO_BROWSER=1"
  goto bausteine
)
if errorlevel 1 (
  echo.
  echo   The app stopped with an error. Please send Claude a screenshot of this window.
  pause
)
