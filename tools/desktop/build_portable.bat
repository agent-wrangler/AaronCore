@echo off
cd /d "%~dp0..\..\desktop_runtime_35"
call npm run dist:portable
