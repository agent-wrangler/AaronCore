@echo off
setlocal
cd /d "%~dp0\.."

git config --unset core.hooksPath 2>nul
if errorlevel 1 (
  echo [AaronCore] no local core.hooksPath was set.
  endlocal
  exit /b 0
)

echo [AaronCore] removed local git hook path configuration.

endlocal
exit /b 0
