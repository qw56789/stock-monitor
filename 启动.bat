@回车关闭
回声========================================
echo 徐老板盯盘 - 启动脚本
回声========================================
回声。

 REM 检查Python是否安装
python --version >nul 2>&1
如果 %errorlevel% 不等于 0 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    暂停
    退出 /b
)

echo [1/3] 检查依赖...
pip show streamlit >nul 2>&1
如果 %errorlevel% 不等于 0 (
    echo [安装] 正在安装依赖...
    使用pip安装 requirements.txt中的依赖项：pip install -r requirements.txt
)

echo [2/3] 启动应用...
回声。
回声========================================
应用启动中...
浏览器将自动打开 http://localhost:8501
echo   按 Ctrl+C 停止运行
回声========================================
回声。

streamlit run app.py

暂停
