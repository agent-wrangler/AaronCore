@echo off
setlocal
cd /d "%~dp0\.."
python tools\runtime_quality_gate.py %*
endlocal
exit /b %errorlevel%
