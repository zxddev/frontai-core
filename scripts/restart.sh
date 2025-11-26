#!/bin/bash
# 重启frontai-core服务脚本

cd /home/dev/gitcode/frontai/frontai-core

echo "=== 停止现有服务 ==="
pkill -f "uvicorn src.main:app" 2>/dev/null
sleep 2

echo "=== 加载环境变量 ==="
set -a && source .env && set +a

echo "=== 启动服务 ==="
mkdir -p logs
nohup .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > logs/server.log 2>&1 &

sleep 3
echo "=== 服务已启动 ==="
echo "API地址: http://127.0.0.1:8000"
echo "文档地址: http://127.0.0.1:8000/docs"
echo ""
echo "查看日志: tail -f logs/server.log"
