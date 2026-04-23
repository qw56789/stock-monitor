@echo off
echo ========================================
echo   股票盯盘助手 - 启动脚本
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b
)

echo [1/3] 检查依赖...
pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo [安装] 正在安装依赖...
    pip install -r requirements.txt
)

echo [2/3] 启动应用...
echo.
echo ========================================
echo   应用启动中...
echo   浏览器将自动打开 http://localhost:8501
echo   按 Ctrl+C 停止运行
echo ========================================
echo.

streamlit run app.py

pause
