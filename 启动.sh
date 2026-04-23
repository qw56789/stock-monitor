#!/bin/bash

echo "========================================"
echo "  股票盯盘助手 - 启动脚本"
echo "========================================"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python，请先安装Python 3.8+"
    exit 1
fi

echo "[1/3] 检查依赖..."
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "[安装] 正在安装依赖..."
    pip3 install -r requirements.txt
fi

echo "[2/3] 启动应用..."
echo ""
echo "========================================"
echo "  应用启动中..."
echo "  浏览器将自动打开 http://localhost:8501"
echo "  按 Ctrl+C 停止运行"
echo "========================================"
echo ""

streamlit run app.py
