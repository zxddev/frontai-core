#!/bin/bash
# 重启frontai-core服务脚本

cd /home/dev/gitcode/frontai/frontai-core

echo "=== 停止现有服务 ==="
# 使用 SIGKILL 强制杀死进程
pkill -9 -f "uvicorn src.main:app" 2>/dev/null || true
pkill -9 -f "frontai-core/.venv/bin/python" 2>/dev/null || true
sleep 1

# 等待端口释放
echo "=== 等待端口释放 ==="
for i in {1..10}; do
    if ! lsof -i :8000 >/dev/null 2>&1; then
        echo "端口 8000 已释放"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "警告: 端口 8000 仍被占用，尝试强制释放..."
        fuser -k 8000/tcp 2>/dev/null || true
        sleep 1
    fi
    sleep 1
done

echo "=== 加载环境变量 ==="
set -a && source .env && set +a

echo "=== 启动服务 ==="
mkdir -p logs
nohup .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > logs/server.log 2>&1 &

# 等待服务启动并验证
echo "=== 验证服务状态 ==="
for i in {1..15}; do
    if curl -s http://127.0.0.1:8000/ >/dev/null 2>&1; then
        echo "服务启动成功！"
        echo ""
        echo "API地址: http://127.0.0.1:8000"
        echo "文档地址: http://127.0.0.1:8000/api/v2/docs"
        echo ""
        echo "查看日志: tail -f logs/server.log"
        exit 0
    fi
    sleep 1
done

echo "警告: 服务可能启动失败，请检查日志"
tail -20 logs/server.log
exit 1
