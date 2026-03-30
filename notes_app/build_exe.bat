@echo off
chcp 65001 >nul
echo ========================================
echo   Nova笔记 打包工具
echo ========================================
echo.

REM 检查PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [1/3] 正在安装 PyInstaller...
    pip install pyinstaller -q
)

REM 清理旧文件
echo [2/3] 正在打包...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM 打包为单文件exe
pyinstaller --onefile --windowed --name "NovaNotes" --add-data "notes_data.json;." -- noconfirm notes_gui.py

REM 复制到桌面
echo [3/3] 移动到桌面...
if exist "dist\NovaNotes.exe" (
    copy "dist\NovaNotes.exe" "%USERPROFILE%\Desktop\NovaNotes.exe"
    echo.
    echo ✅ 打包完成！桌面已有 NovaNotes.exe
    echo.
    pause
) else (
    echo.
    echo ❌ 打包失败，请检查错误信息
    pause
)
