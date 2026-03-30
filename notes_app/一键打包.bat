@echo off
chcp 65001 > nul
echo ========================================
echo    Nova笔记 - 一键打包工具
echo ========================================
echo.

echo 正在安装依赖（首次运行）...
pip install pyinstaller -q

echo.
echo 正在打包，请稍等...
echo （首次打包需要1-3分钟）

pyinstaller --onefile --noconsole --name NovaNotes --destpath "%USERPROFILE%\Desktop" notes_gui.py

echo.
echo ========================================
echo    打包完成！�ying~
echo ========================================
echo.
echo 桌面上的 NovaNotes.exe 就是你的笔记应用！
echo 双击即可使用，无需Python环境～
pause
