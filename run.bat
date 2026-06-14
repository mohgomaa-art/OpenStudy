@echo off
setlocal
title OpenStudy

set ROOT=%~dp0
set FRONTEND=%ROOT%frontend

echo [1/4] Killing stale processes...
rem Nuke any orphan main.py backends, including multiprocessing children that don't appear in netstat
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*multiprocessing-fork*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1

echo [2/4] Setting up MSVC build environment...
set VCVARS_FOUND=0

if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    set VCVARS_FOUND=1
)
if %VCVARS_FOUND%==0 if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    set VCVARS_FOUND=1
)
if %VCVARS_FOUND%==0 if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    set VCVARS_FOUND=1
)
if %VCVARS_FOUND%==0 if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    set VCVARS_FOUND=1
)
if %VCVARS_FOUND%==0 (
    echo [WARN] Visual Studio 2022 not found. Tauri build may fail.
    echo        Install "Desktop development with C++" workload in VS installer.
    echo        Or open this project in a VS Developer Command Prompt.
)

echo [3/4] Launching Tauri (backend will start silently)...
cd /d %FRONTEND%
npm run dev

echo Application closed. Cleaning up...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*multiprocessing-fork*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
