@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0simulate-optics.ps1" -Scenario python -OpenReport
if errorlevel 1 pause

