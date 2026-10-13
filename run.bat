@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found. Install Python 3.10+ and try again.
  pause
  exit /b 1
)
if not exist venv\Scripts\python.exe (
  echo [1/3] Creating virtual environment...
  python -m venv venv
  if errorlevel 1 (
    echo ERROR: Could not create the virtual environment.
    pause
    exit /b 1
  )
)
echo [2/3] Installing required packages...
venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: pip could not reach PyPI. Check your internet connection.
  pause
  exit /b 1
)
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed.
  pause
  exit /b 1
)
echo [3/3] Starting HoneyChain...
venv\Scripts\python.exe app.py
pause
