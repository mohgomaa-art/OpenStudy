@echo off
setlocal
title OpenStudy — Browser Mode

set ROOT=%~dp0
set FRONTEND=%ROOT%frontend

echo [1/3] Killing stale processes...
rem Nuke any orphan main.py backends, including multiprocessing children that don't appear in netstat
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*multiprocessing-fork*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1

echo [2/3] Starting backend...
start "Backend" /min cmd /c "cd /d %ROOT% && python main.py"

echo [3/3] Waiting for backend then launching Vite (browser)...
:wait_backend
ping -n 3 127.0.0.1 >nul
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto wait_backend
echo     Backend ready!

cd /d %FRONTEND%
start "" "http://localhost:5173"
npm run dev:vite

echo Done. Cleaning up...
taskkill /FI "WINDOWTITLE eq Backend*" /F >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*multiprocessing-fork*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
