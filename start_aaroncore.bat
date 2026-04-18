@echo off
setlocal
cd /d "%~dp0"
set "AARONCORE_ROOT=%~dp0"
set "NOVACORE_ROOT=%~dp0"
set "AARONCORE_DATA_DIR=%~dp0"
set "NOVACORE_DATA_DIR=%~dp0"
if not defined AARONCORE_USER_DATA_DIR set "AARONCORE_USER_DATA_DIR=%APPDATA%\AaronCore-dev-shell"
if not defined NOVACORE_USER_DATA_DIR set "NOVACORE_USER_DATA_DIR=%APPDATA%\AaronCore-dev-shell"
set "AARONCORE_DEV_ROOT=%~dp0"
set "NOVACORE_DEV_ROOT=%~dp0"
set "AARON_DESKTOP=%USERPROFILE%\AaronCoreDesktop\win-unpacked"
set "LEGACY_NOVA_DESKTOP=%USERPROFILE%\NovaCoreDesktop\win-unpacked"
set "LOCAL_DIST=%~dp0desktop_runtime_35\dist\win-unpacked"
set "LOCAL_ELECTRON=%~dp0desktop_runtime_35\node_modules\electron\dist\electron.exe"

if exist "%LOCAL_DIST%\AaronCore.exe" (
  start "" "%LOCAL_DIST%\AaronCore.exe"
) else if exist "%LOCAL_DIST%\NovaCore.exe" (
  start "" "%LOCAL_DIST%\NovaCore.exe"
) else if exist "%LOCAL_ELECTRON%" (
  start "" "%LOCAL_ELECTRON%" "%~dp0desktop_runtime_35"
) else if exist "%AARON_DESKTOP%\AaronCore.exe" (
  start "" "%AARON_DESKTOP%\AaronCore.exe"
) else if exist "%LEGACY_NOVA_DESKTOP%\AaronCore.exe" (
  start "" "%LEGACY_NOVA_DESKTOP%\AaronCore.exe"
) else if exist "%LEGACY_NOVA_DESKTOP%\NovaCore.exe" (
  start "" "%LEGACY_NOVA_DESKTOP%\NovaCore.exe"
) else (
  echo AaronCore dev shell not found. Please run npm install in desktop_runtime_35 first.
)
endlocal
exit /b 0
