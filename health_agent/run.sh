#!/bin/bash

# Health Agent 启动脚本

# 激活虚拟环境
source ../venv/bin/activate

echo "================================"
echo "Health Agent 启动选项"
echo "================================"
echo "1. 运行命令行版本"
echo "2. 运行 Web 版本"
echo "3. 退出"
echo "================================"
read -p "请选择 (1-3): " choice

case $choice in
    1)
        echo "启动命令行版本..."
        python3 main.py
        ;;
    2)
        echo "启动 Web 版本..."
        streamlit run app.py
        ;;
    3)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
