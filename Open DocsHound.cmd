@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1" -Port 8001
if errorlevel 1 pause
