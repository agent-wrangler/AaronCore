@echo off
setlocal
cd /d "C:\Users\36459\NovaCore"
if exist "C:\Users\36459\NovaCore\desktop_runtime_35\dist\win-unpacked\NovaCore.exe" (
  start "" "C:\Users\36459\NovaCore\desktop_runtime_35\dist\win-unpacked\NovaCore.exe"
) else (
  start "" "C:\Users\36459\NovaCore\desktop_runtime_35\node_modules\electron\dist\electron.exe" "C:\Users\36459\NovaCore\desktop_runtime_35"
)
endlocal
exit /b 0
