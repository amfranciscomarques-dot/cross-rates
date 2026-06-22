@echo off
rem Launches the cross-rates web UI (FastAPI) from its virtualenv.
if not exist "%~dp0.venv\Scripts\cross-rates-web.exe" (
    echo cross-rates-web.exe not found in .venv. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e .[web]
    pause
    exit /b 1
)
echo Serving on http://127.0.0.1:8000  (Ctrl+C to stop)
start "" http://127.0.0.1:8000
"%~dp0.venv\Scripts\cross-rates-web.exe"
pause
