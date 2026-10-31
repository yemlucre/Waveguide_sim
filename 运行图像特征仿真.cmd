@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0simulate-optics.ps1" -Scenario lamp -OpenReport
set "optics_exit=%errorlevel%"
pause
exit /b %optics_exit%
