@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Carinas Video-Editor
cd /d "%~dp0"

echo.
echo   ==============================================
echo     Carinas Video-Editor wird gestartet ...
echo   ==============================================
echo.

rem ---- 1. uv (holt Python und alle Bausteine) ----
where uv >nul 2>nul
if errorlevel 1 (
  if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  ) else (
    echo   [1/4] Einmalig: Installationshelfer "uv" wird geladen ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  )
)
where uv >nul 2>nul
if errorlevel 1 (
  echo.
  echo   FEHLER: Der Installationshelfer "uv" konnte nicht installiert werden.
  echo   Bitte pruefe die Internetverbindung und starte start.bat nochmal.
  pause
  exit /b 1
)

rem ---- 2. ffmpeg (schneiden und umwandeln) ----
if not exist "tools\ffmpeg\bin\ffmpeg.exe" (
  where ffmpeg >nul 2>nul
  if errorlevel 1 (
    echo   [2/4] Einmalig: ffmpeg wird geladen (ca. 100 MB, kann ein paar Minuten dauern^) ...
    if not exist tools mkdir tools
    curl.exe -L -# -o "tools\ffmpeg.zip" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    if errorlevel 1 (
      powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'tools\ffmpeg.zip'"
    )
    echo         Wird entpackt ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ProgressPreference='SilentlyContinue';" ^
      "Expand-Archive 'tools\ffmpeg.zip' -DestinationPath 'tools\ffmpeg_tmp' -Force;" ^
      "$inner = Get-ChildItem 'tools\ffmpeg_tmp' -Directory | Select-Object -First 1;" ^
      "Move-Item $inner.FullName 'tools\ffmpeg';" ^
      "Remove-Item 'tools\ffmpeg_tmp','tools\ffmpeg.zip' -Recurse -Force"
    if not exist "tools\ffmpeg\bin\ffmpeg.exe" (
      echo.
      echo   FEHLER: ffmpeg konnte nicht geladen werden. Bitte Internet pruefen und nochmal starten.
      pause
      exit /b 1
    )
  )
)

rem ---- 3. Python-Bausteine (mit Grafikkarten-Unterstuetzung, wenn Nvidia da ist) ----
echo   [3/4] Bausteine werden geprueft (beim ersten Mal dauert das einige Minuten) ...
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  uv sync --quiet
) else (
  echo         Nvidia-Grafikkarte gefunden: sie wird fuer die Spracherkennung genutzt.
  uv sync --quiet --extra gpu
  if errorlevel 1 (
    echo         Grafikkarten-Bausteine gingen nicht. Die App startet trotzdem, mit dem Prozessor.
    uv sync --quiet
  )
)
if errorlevel 1 (
  echo.
  echo   FEHLER: Die Bausteine konnten nicht installiert werden.
  echo   Bitte pruefe die Internetverbindung und starte start.bat nochmal.
  pause
  exit /b 1
)

rem ---- 4. Starten ----
echo   [4/4] Die App oeffnet sich gleich im Browser: http://127.0.0.1:8000
echo.
echo   Dieses Fenster bitte offen lassen, solange du mit der App arbeitest.
echo   Zum Beenden einfach das Fenster schliessen.
echo.
uv run backend\app.py
if errorlevel 1 (
  echo.
  echo   Die App wurde mit einem Fehler beendet. Bitte schick Claude ein Foto von diesem Fenster.
  pause
)
