@echo off
setlocal
cd /d "%~dp0"
if exist "C:\Users\36459\NovaCoreDesktop\win-unpacked\AaronCore.exe" (
  start "" "C:\Users\36459\NovaCoreDesktop\win-unpacked\AaronCore.exe"
) else if exist "C:\Users\36459\NovaCoreDesktop\win-unpacked\NovaCore.exe" (
  start "" "C:\Users\36459\NovaCoreDesktop\win-unpacked\NovaCore.exe"
) else if exist "C:\Users\36459\NovaCore\desktop_runtime_35\dist\win-unpacked\AaronCore.exe" (
  start "" "C:\Users\36459\NovaCore\desktop_runtime_35\dist\win-unpacked\AaronCore.exe"
) else if exist "C:\Users\36459\NovaCore\desktop_runtime_35\dist\win-unpacked\NovaCore.exe" (
  start "" "C:\Users\36459\NovaCore\desktop_runtime_35\dist\win-unpacked\NovaCore.exe"
) else (
  start "" "%~dp0desktop_runtime_35\node_modules\electron\dist\electron.exe" "%~dp0desktop_runtime_35"
)
endlocal
exit /b 0
