@echo off
chcp 65001 >nul
echo ==========================================
echo    🧠 脑力训练外挂 - 启动中...
echo ==========================================
echo.
cd /d "%~dp0"
python brain_training_hub.py
pause
