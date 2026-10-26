# Intelligent Traffic Management System - PowerShell Launcher
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Intelligent Traffic Management System - Launcher" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$pythonCmd = $null

if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Test-Path "C:\ProgramData\anaconda3\python.exe") {
    $pythonCmd = "C:\ProgramData\anaconda3\python.exe"
}

if ($pythonCmd) {
    Write-Host "Using Python: $pythonCmd" -ForegroundColor Green
    & $pythonCmd app.py
} else {
    Write-Host "ERROR: Python was not found. Please install Python 3.9+ or run with your local interpreter." -ForegroundColor Red
}
