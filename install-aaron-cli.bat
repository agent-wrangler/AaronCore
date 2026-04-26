@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-aaron-cli.ps1"
exit /b %ERRORLEVEL%
