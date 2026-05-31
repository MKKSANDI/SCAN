@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if /i "%~1"=="--elevated" shift

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting administrator privileges...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs"
  exit /b 0
)

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ and re-run.
  pause
  exit /b 1
)

%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)

%PYTHON% main.py %*
exit /b %errorlevel%
