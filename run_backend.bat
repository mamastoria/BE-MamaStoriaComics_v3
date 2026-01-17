@echo off
REM Start Backend API for MamaStoria with stable config
cd /d "%~dp0"

REM Kill any existing Python processes on this port
taskkill /F /IM python.exe 2>nul

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Activate venv
call venv\Scripts\activate.bat

REM Run uvicorn without reload to avoid cascade crashes
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --workers 1

pause
