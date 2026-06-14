@echo off
setlocal EnableDelayedExpansion
title OpenStudy — Setup & Launch

:: ─────────────────────────────────────────────────────────────────
::  OpenStudy — One-click Setup, Update & Launch
::  Run this once after cloning or to update dependencies.
:: ─────────────────────────────────────────────────────────────────

set ROOT=%~dp0
set FRONTEND=%ROOT%frontend
set LOG=%ROOT%setup.log

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║           OpenStudy — Setup ^& Launch                ║
echo  ║          github.com/mohgomaa-art/OpenStudy           ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ─── Kill any stale processes ────────────────────────────────────
echo [*] Cleaning stale processes on ports 8000 and 5173...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)

:: ─── Check Python ────────────────────────────────────────────────
echo [*] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] ERROR: Python not found!
    echo      Install Python 3.11+ from https://python.org
    echo      Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo     Found: %%v

:: ─── Check Node.js ───────────────────────────────────────────────
echo [*] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] ERROR: Node.js not found!
    echo      Install Node.js 20+ from https://nodejs.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo     Found: Node.js %%v

:: ─── Check .env file ─────────────────────────────────────────────
echo [*] Checking environment configuration...
if not exist "%ROOT%.env" (
    if exist "%ROOT%.env.example" (
        echo  [!] .env not found — copying from .env.example...
        copy "%ROOT%.env.example" "%ROOT%.env" >nul
        echo.
        echo  ╔══════════════════════════════════════════════════════╗
        echo  ║  ACTION REQUIRED: Open .env and add your API key:   ║
        echo  ║                                                      ║
        echo  ║   GEMINI_API_KEYS=your_key_here                      ║
        echo  ║                                                      ║
        echo  ║  Get a free key: https://aistudio.google.com/        ║
        echo  ╚══════════════════════════════════════════════════════╝
        echo.
        echo  Opening .env in Notepad...
        start notepad "%ROOT%.env"
        echo  Press any key after saving your API key to continue...
        pause >nul
    ) else (
        echo  [!] WARNING: No .env file found. App may not work correctly.
    )
) else (
    echo     .env found OK
)

:: ─── Install Python dependencies ─────────────────────────────────
echo.
echo [*] Installing Python dependencies (this may take a minute)...
pip install -r "%ROOT%requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  [!] WARNING: Some Python packages failed to install.
    echo      Try running manually: pip install -r requirements.txt
) else (
    echo     Python packages OK
)

:: ─── Install Node dependencies ────────────────────────────────────
echo.
echo [*] Installing Node.js dependencies...
cd /d "%FRONTEND%"
if not exist "node_modules" (
    echo     node_modules not found — running npm install...
    npm install --silent
    if errorlevel 1 (
        echo  [!] npm install failed. Check your internet connection.
        pause
        exit /b 1
    )
) else (
    echo     Updating packages...
    npm install --silent
)
echo     Node packages OK

:: ─── Start backend ───────────────────────────────────────────────
echo.
echo [*] Starting OpenStudy backend (Python)...
cd /d "%ROOT%"
start "OpenStudy-Backend" /min cmd /c "cd /d "%ROOT%" && python main.py > setup.log 2>&1"

:: ─── Wait for backend to be ready ────────────────────────────────
echo [*] Waiting for backend to be ready...
set /a ATTEMPTS=0
:wait_loop
set /a ATTEMPTS+=1
if !ATTEMPTS! GTR 30 (
    echo  [!] Backend is taking longer than expected...
    echo      Check setup.log for errors.
    goto :launch_frontend
)
ping -n 2 127.0.0.1 >nul
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/' -TimeoutSec 1 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto :wait_loop
echo     Backend ready!

:launch_frontend
:: ─── Launch frontend ─────────────────────────────────────────────
echo.
echo [*] Launching OpenStudy Dashboard in browser...
cd /d "%FRONTEND%"

:: Open browser after short delay
start "" cmd /c "ping -n 4 127.0.0.1 >nul && start http://localhost:5173"

:: Start Vite dev server (this stays open — close window to stop)
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   OpenStudy is running!                             ║
echo  ║   Opening: http://localhost:5173                    ║
echo  ║                                                     ║
echo  ║   Close this window to stop the app.               ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
npm run dev:vite

:: ─── Cleanup on exit ─────────────────────────────────────────────
echo.
echo [*] Shutting down...
taskkill /FI "WINDOWTITLE eq OpenStudy-Backend*" /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)
echo     Done. Goodbye!
timeout /t 2 >nul
