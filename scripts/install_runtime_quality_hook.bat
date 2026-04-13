@echo off
setlocal
cd /d "%~dp0\.."

git config core.hooksPath .githooks
if errorlevel 1 exit /b %errorlevel%

for /f "usebackq delims=" %%i in (`git config --get core.hooksPath`) do set "HOOKS_PATH=%%i"
echo [AaronCore] installed git hook path: %HOOKS_PATH%
echo [AaronCore] pre-commit will run tools\runtime_quality_gate.py --strict

endlocal
exit /b 0
