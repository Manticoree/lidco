@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ─────────────────────────────────────────────────────────────────────────────
:: LIDCO Installer — Windows
:: ─────────────────────────────────────────────────────────────────────────────
::
:: Usage:
::   install.bat
::
:: What it does:
::   1. Creates Python virtual environment
::   2. Installs all dependencies
::   3. Copies .env.example → .env (if not exists)
::   4. Creates global 'lidco' command in %USERPROFILE%\.local\bin
::   5. Adds to PATH if needed
::   6. Ready to use from any directory
:: ─────────────────────────────────────────────────────────────────────────────

set "LIDCO_DIR=%~dp0"
set "LIDCO_DIR=%LIDCO_DIR:~0,-1%"
set "VENV_DIR=%LIDCO_DIR%\.venv"
set "BIN_DIR=%USERPROFILE%\.local\bin"

echo.
echo   LIDCO Installer
echo   LLM-Integrated Development COmpanion
echo.
echo   Project: %LIDCO_DIR%
echo.

:: ── Check Python ─────────────────────────────────────────────────────────────

set "PYTHON="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
        if %%a geq 3 if %%b geq 12 set "PYTHON=python"
    )
)

if not defined PYTHON (
    echo [ERROR] Python 3.12+ is required.
    echo         Download from https://python.org
    exit /b 1
)

for /f "delims=" %%v in ('python --version 2^>^&1') do echo [OK] %%v found

:: ── Create venv ──────────────────────────────────────────────────────────────

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] Virtual environment already exists
) else (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    echo [OK] Virtual environment created
)

:: Activate
call "%VENV_DIR%\Scripts\activate.bat"
echo [OK] Virtual environment activated

:: ── Install dependencies ─────────────────────────────────────────────────────

echo [INFO] Installing dependencies (this may take a minute)...
pip install --upgrade pip -q >nul 2>&1
pip install -e ".[dev]" -q
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    exit /b 1
)
echo [OK] Dependencies installed

:: ── Setup .env ───────────────────────────────────────────────────────────────

if not exist "%LIDCO_DIR%\.env" (
    copy "%LIDCO_DIR%\.env.example" "%LIDCO_DIR%\.env" >nul
    echo [WARN] .env created from .env.example — add your API keys there
) else (
    echo [INFO] .env already exists, skipping
)

:: ── Create global launcher ───────────────────────────────────────────────────

if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

:: lidco.cmd
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo set PYTHONIOENCODING=utf-8
echo.
echo if "%%VIRTUAL_ENV%%"=="" ^(
echo     call "%VENV_DIR%\Scripts\activate.bat" ^>nul 2^>^&1
echo ^)
echo.
echo python -m lidco %%*
) > "%BIN_DIR%\lidco.cmd"

:: lidco-serve.cmd
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo set PYTHONIOENCODING=utf-8
echo.
echo if "%%VIRTUAL_ENV%%"=="" ^(
echo     call "%VENV_DIR%\Scripts\activate.bat" ^>nul 2^>^&1
echo ^)
echo.
echo python -m lidco serve %%*
) > "%BIN_DIR%\lidco-serve.cmd"

echo [OK] Launcher created: %BIN_DIR%\lidco.cmd

:: ── Check PATH ───────────────────────────────────────────────────────────────

echo %PATH% | findstr /i /c:"%BIN_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Adding %BIN_DIR% to user PATH...
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
    if defined USER_PATH (
        setx PATH "!USER_PATH!;%BIN_DIR%" >nul 2>&1
    ) else (
        setx PATH "%BIN_DIR%" >nul 2>&1
    )
    echo [OK] PATH updated. Restart your terminal to apply.
) else (
    echo [OK] %BIN_DIR% is already in PATH
)

:: ── Done ─────────────────────────────────────────────────────────────────────

echo.
echo   Installation complete!
echo.
echo   Usage:
echo     lidco              — interactive CLI
echo     lidco serve        — HTTP server (port 8321)
echo     lidco-serve        — shortcut for server
echo.
echo   First time? Edit .env and add your API key:
echo     notepad "%LIDCO_DIR%\.env"
echo.
echo   If 'lidco' is not found, restart your terminal.
echo.

endlocal
