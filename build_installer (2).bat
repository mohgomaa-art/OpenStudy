@echo off
setlocal EnableDelayedExpansion
title OpenStudy — Build Installer

set ROOT=%~dp0
set FRONTEND=%ROOT%frontend

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       OpenStudy — Global Installer Compiler          ║
echo  ║          github.com/mohgomaa-art/OpenStudy           ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: 1. Terminate stale processes
echo [*] Terminating any running instances of OpenStudy or Python backend...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*multiprocessing-fork*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
taskkill /F /IM OpenStudy.exe >nul 2>&1
taskkill /F /IM OpenStudyBackend.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /PID %%p /F >nul 2>&1

:: 2. Check for PyInstaller
echo [*] Checking for PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
)

:: 3. Compile Python FastAPI Backend
echo [*] Compiling Python backend using PyInstaller...
call pyinstaller --clean --onefile --noconsole --name OpenStudyBackend ^
    --add-data "docs;docs" ^
    --add-data "services;services" ^
    --add-data "magic_engine;magic_engine" ^
    --hidden-import uvicorn.protocols.http.h11_impl ^
    --hidden-import uvicorn.protocols.http.auto ^
    --hidden-import uvicorn.protocols.websockets.auto ^
    --hidden-import uvicorn.loops.auto ^
    --hidden-import uvicorn.loops.asyncio ^
    --hidden-import uvicorn.lifespan.on ^
    --hidden-import uvicorn.lifespan.off ^
    --hidden-import sqlite3 ^
    --hidden-import google.genai ^
    --hidden-import google.genai.types ^
    --hidden-import google.auth ^
    --hidden-import google.auth.transport.requests ^
    --hidden-import httpx ^
    --hidden-import openai ^
    --hidden-import anthropic ^
    --hidden-import groq ^
    --hidden-import fitz ^
    --hidden-import docx ^
    --hidden-import pptx ^
    --hidden-import multipart ^
    --hidden-import starlette.middleware.cors ^
    --hidden-import starlette.responses ^
    --hidden-import email_validator ^
    main.py

if errorlevel 1 (
    echo.
    echo [!] ERROR: PyInstaller compilation failed!
    pause
    exit /b 1
)

echo [*] Copying compiled backend to Tauri resource directory...
if not exist "%FRONTEND%\src-tauri" mkdir "%FRONTEND%\src-tauri"
copy /Y "%ROOT%dist\OpenStudyBackend.exe" "%FRONTEND%\src-tauri\OpenStudyBackend.exe"

if errorlevel 1 (
    echo [!] ERROR: Failed to copy OpenStudyBackend.exe to src-tauri!
    pause
    exit /b 1
)

:: 4. Set up MSVC build environment for Tauri
echo [*] Setting up MSVC build environment...
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
    echo [WARN] Visual Studio 2022 vcvars64.bat not found. Tauri build may fail.
)

:: 5. Compile Front-End and Build Installer
echo [*] Compiling frontend and packaging Tauri installer...
cd /d "%FRONTEND%"
call npm run build

if errorlevel 1 (
    echo.
    echo [!] ERROR: Tauri build failed!
    cd /d "%ROOT%"
    pause
    exit /b 1
)

:: 6. Read product name + version from tauri.conf.json
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-Content -Raw '%FRONTEND%\src-tauri\tauri.conf.json' | ConvertFrom-Json).productName"') do set "PRODUCT_NAME=%%i"
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-Content -Raw '%FRONTEND%\src-tauri\tauri.conf.json' | ConvertFrom-Json).version"') do set "APP_VERSION=%%i"
if "%PRODUCT_NAME%"=="" set "PRODUCT_NAME=OpenStudy"
if "%APP_VERSION%"=="" set "APP_VERSION=0.0.0"

set "RELEASE_DIR=%FRONTEND%\src-tauri\target\release"
set "BUNDLE_DIR=%RELEASE_DIR%\bundle"

:: 7. Package portable build (raw exe + backend sidecar, zipped)
echo [*] Packaging portable build...
set "PORTABLE_DIR=%ROOT%dist-portable\%PRODUCT_NAME%-Portable"
if exist "%PORTABLE_DIR%" rmdir /S /Q "%PORTABLE_DIR%"
mkdir "%PORTABLE_DIR%" >nul 2>&1

if exist "%RELEASE_DIR%\%PRODUCT_NAME%.exe" (
    copy /Y "%RELEASE_DIR%\%PRODUCT_NAME%.exe" "%PORTABLE_DIR%\" >nul
) else (
    echo [WARN] Could not find %PRODUCT_NAME%.exe in %RELEASE_DIR%
)

:: Include the compiled backend (copied into src-tauri earlier in this script)
if exist "%FRONTEND%\src-tauri\OpenStudyBackend.exe" (
    copy /Y "%FRONTEND%\src-tauri\OpenStudyBackend.exe" "%PORTABLE_DIR%\" >nul
) else (
    echo [WARN] OpenStudyBackend.exe not found in %FRONTEND%\src-tauri
)

set "PORTABLE_ZIP=%ROOT%dist-portable\%PRODUCT_NAME%-%APP_VERSION%-Portable.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%PORTABLE_DIR%\*' -DestinationPath '%PORTABLE_ZIP%' -Force"

:: 8. Collect installer package(s) produced by Tauri
echo [*] Collecting installer package(s)...
set "INSTALLER_DIR=%ROOT%dist-installer"
if not exist "%INSTALLER_DIR%" mkdir "%INSTALLER_DIR%" >nul 2>&1
if exist "%BUNDLE_DIR%\nsis" copy /Y "%BUNDLE_DIR%\nsis\*.exe" "%INSTALLER_DIR%\" >nul 2>&1
if exist "%BUNDLE_DIR%\msi"  copy /Y "%BUNDLE_DIR%\msi\*.msi"  "%INSTALLER_DIR%\" >nul 2>&1

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║             BUILD COMPLETED SUCCESSFULLY!            ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo Portable build (no installation required):
echo   %PORTABLE_ZIP%
echo   (unzipped copy also at %PORTABLE_DIR%)
echo.
echo Installer package(s):
echo   %INSTALLER_DIR%\
echo.
cd /d "%ROOT%"
pause
