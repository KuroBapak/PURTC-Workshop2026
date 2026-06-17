@echo off
title Edge AI Smart Lock - Backend Server
color 0A
echo.
echo  ============================================
echo   Edge AI Smart Lock System - Workshop 2026
echo  ============================================
echo.

REM Navigate to project root (where start.bat lives)
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo.
    pause
    exit /b 1
)

echo  Detected:
python --version
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo  [1/3] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo        Done!
    echo.
) else (
    echo  [1/3] Virtual environment already exists. Skipping creation.
    echo.
)

REM Select GPU Type
echo  [2/3] Hardware Setup
echo  Please select your primary hardware:
echo  1. NVIDIA GPU (Default CUDA)
echo  2. AMD GPU / Ryzen AI iGPU (ROCm ^& DirectML)
set /p gpu_choice=" Enter 1 or 2: "

if "%gpu_choice%"=="2" (
    set REQ_FILE=backend\AMD-requirements.txt
    echo  Selected AMD requirements.
) else (
    set REQ_FILE=backend\requirements.txt
    echo  Selected Default NVIDIA requirements.
)
echo.

REM Activate the virtual environment
echo  [3/4] Activating virtual environment ^& installing dependencies...
call .venv\Scripts\activate.bat

REM Install dependencies into venv
pip install -r %REQ_FILE% --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to install dependencies.
    echo  Check your internet connection and try again.
    pause
    exit /b 1
)
echo        Done!
echo.

REM Launch the server
echo  [4/4] Starting FastAPI server...
echo.
echo  -----------------------------------------------
echo   Server:   http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo   Open frontend\index.html in your browser!
echo  -----------------------------------------------
echo.

REM Disable MIOpen SQLite caching to prevent "no such column: mode" crashes on Windows ROCm preview
set MIOPEN_DISABLE_CACHE=1
set MIOPEN_DEBUG_DISABLE_FIND_DB=1

python backend\main.py
echo.
echo  Server stopped.
pause
