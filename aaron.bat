@echo off
setlocal
cd /d "%~dp0"
python "%~dp0aaron.py" %*
exit /b %ERRORLEVEL%
