@echo off
setlocal
title OpenStudy Dashboard

set ROOT=%~dp0
set FRONTEND=%ROOT%frontend

echo [1/3] Killing stale processes...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1

echo [2/3] Setting up MSVC build environment...
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

echo [3/3] Launching Tauri Dashboard...
cd /d %FRONTEND%
set OPEN_DASHBOARD=1
npm run dev

echo Dashboard closed. Cleaning up...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
