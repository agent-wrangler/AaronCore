@echo off
setlocal
title AaronCore Installer

echo.
echo AaronCore CLI installer
echo =======================
echo.
echo This will install the `aaron` command for your Windows user account.
echo After it finishes, open a new terminal and type either:
echo.
echo   aaron
echo   aaroncore
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-aaron-cli.ps1"
set "INSTALL_CODE=%ERRORLEVEL%"

echo.
if "%INSTALL_CODE%"=="0" (
  echo Install finished.
  echo Open a new PowerShell window, then run: aaron
  echo Or run: aaroncore
) else (
  echo Install failed. Please check the message above.
)
echo.
pause
exit /b %INSTALL_CODE%
