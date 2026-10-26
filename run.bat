@echo off
echo ============================================================
echo   Intelligent Traffic Management System - Launcher
echo ============================================================

REM Check standard python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python app.py
    goto end
)

REM Check py launcher
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py app.py
    goto end
)

REM Check Anaconda Python path
if exist "C:\ProgramData\anaconda3\python.exe" (
    "C:\ProgramData\anaconda3\python.exe" app.py
    goto end
)

echo ERROR: Python was not found in PATH or at C:\ProgramData\anaconda3\python.exe.
echo Please install Python 3.9+ or run with your local Python interpreter.
pause

:end
