@echo off
setlocal
cd /d "%~dp0"
set "AARONCORE_DEV_ROOT=%~dp0"
set "NOVACORE_DEV_ROOT=%~dp0"
set "AARON_DESKTOP=%USERPROFILE%\AaronCoreDesktop\win-unpacked"
set "LEGACY_NOVA_DESKTOP=%USERPROFILE%\NovaCoreDesktop\win-unpacked"
set "LOCAL_DIST=%~dp0desktop_runtime_35\dist\win-unpacked"

if exist "%AARON_DESKTOP%\AaronCore.exe" (
  start "" "%AARON_DESKTOP%\AaronCore.exe"
) else if exist "%LEGACY_NOVA_DESKTOP%\AaronCore.exe" (
  start "" "%LEGACY_NOVA_DESKTOP%\AaronCore.exe"
) else if exist "%LEGACY_NOVA_DESKTOP%\NovaCore.exe" (
  start "" "%LEGACY_NOVA_DESKTOP%\NovaCore.exe"
) else if exist "%LOCAL_DIST%\AaronCore.exe" (
  start "" "%LOCAL_DIST%\AaronCore.exe"
) else if exist "%LOCAL_DIST%\NovaCore.exe" (
  start "" "%LOCAL_DIST%\NovaCore.exe"
) else (
  start "" "%~dp0desktop_runtime_35\node_modules\electron\dist\electron.exe" "%~dp0desktop_runtime_35"
)
endlocal
exit /b 0