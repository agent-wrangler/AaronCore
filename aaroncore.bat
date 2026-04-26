@echo off
setlocal
set "AARONCORE_ROOT=%~dp0"
cd /d "%AARONCORE_ROOT%"

set "AARONCORE_PYTHON=python"
if exist "%AARONCORE_ROOT%.venv\Scripts\python.exe" set "AARONCORE_PYTHON=%AARONCORE_ROOT%.venv\Scripts\python.exe"
if exist "%AARONCORE_ROOT%.aaroncore-installed" (
  if exist "%AARONCORE_ROOT%..\.venv\Scripts\python.exe" set "AARONCORE_PYTHON=%AARONCORE_ROOT%..\.venv\Scripts\python.exe"
  if not defined AARONCORE_DATA_DIR set "AARONCORE_DATA_DIR=%AARONCORE_ROOT%..\data"
)

"%AARONCORE_PYTHON%" "%AARONCORE_ROOT%aaron.py" %*
exit /b %ERRORLEVEL%
