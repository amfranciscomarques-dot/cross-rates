@echo off
rem Launches the cross-rates TUI calculator from its virtualenv.
if not exist "%~dp0.venv\Scripts\cross-rates.exe" (
    echo cross-rates.exe not found in .venv. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e .
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\cross-rates.exe"
pause
