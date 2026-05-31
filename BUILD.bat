@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "APP_NAME=SCAN"
set "ENTRY=main.py"
set "ICON=icon.ico"

echo ============================================
echo SCAN Build Script
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not available in PATH.
  exit /b 1
)

python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install requirements.
  exit /b 1
)
python -m pip install pyinstaller
if errorlevel 1 (
  echo Failed to install PyInstaller.
  exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del "%APP_NAME%.spec"

set "ICON_ARG="
if exist "%ICON%" set "ICON_ARG=--icon %ICON%"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name "%APP_NAME%" ^
  --noupx ^
  --hidden-import rich.console ^
  --hidden-import rich.panel ^
  --hidden-import rich.table ^
  --hidden-import rich.live ^
  --hidden-import rich.progress ^
  --hidden-import rich.text ^
  --hidden-import pystyle ^
  --collect-all rich ^
  --collect-all pystyle ^
  %ICON_ARG% ^
  "%ENTRY%"

if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

if not exist "dist\%APP_NAME%.exe" (
  echo Build completed but dist\%APP_NAME%.exe was not found.
  exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%i"
set "RELEASE_DIR=releases\scan-%STAMP%"
set "RELEASE_ZIP=releases\scan-%STAMP%.zip"
if not exist releases mkdir releases
mkdir "%RELEASE_DIR%"

copy /y "dist\%APP_NAME%.exe" "%RELEASE_DIR%\%APP_NAME%.exe" >nul
copy /y "README.md" "%RELEASE_DIR%\" >nul
copy /y "RUN.bat" "%RELEASE_DIR%\" >nul
copy /y "requirements.txt" "%RELEASE_DIR%\" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\\*' -DestinationPath '%RELEASE_ZIP%' -Force" >nul
if errorlevel 1 (
  echo Release packaging failed.
  exit /b 1
)

echo.
echo Build complete.
echo EXE: dist\%APP_NAME%.exe
echo Release folder: %RELEASE_DIR%
echo Release zip: %RELEASE_ZIP%
exit /b 0
