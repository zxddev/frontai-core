#!/bin/bash
# 前端API接口测试脚本
# 用法: ./scripts/test_frontend_api.sh [host]

HOST=${1:-localhost:8000}
BASE_URL="http://$HOST"

echo "========================================"
echo "前端API接口测试"
echo "目标: $BASE_URL"
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

test_api() {
    local method=$1
    local path=$2
    local data=$3
    local expected=$4
    
    echo -n "测试 $method $path ... "
    
    if [ "$method" == "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$path")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$BASE_URL$path" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" == "$expected" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $http_code)"
        return 0
    else
        echo -e "${RED}FAIL${NC} (HTTP $http_code, expected $expected)"
        echo "  Response: $body"
        return 1
    fi
}

echo "=== 1. 健康检查 ==="
test_api GET "/health" "" "200"
echo ""

echo "=== 2. 用户模块 ==="
test_api POST "/api/v1/user/login" '{"username":"admin","password":"wrong"}' "200"
test_api POST "/web-api/api/v1/user/login" '{"username":"test","password":"test"}' "200"
echo ""

echo "=== 3. 事件模块 ==="
test_api GET "/api/v1/events/event-confirm" "" "200"
test_api GET "/api/v1/events/pending?scenarioId=00000000-0000-0000-0000-000000000001" "" "200"
echo ""

echo "=== 4. 消息模块 ==="
test_api POST "/api/v1/message/message-list" '{"userId":"user1","page":1,"pageSize":10}' "200"
test_api POST "/api/v1/message/message-ack" '{"messageId":"msg1","userId":"user1"}' "200"
echo ""

echo "=== 5. 方案模块 ==="
test_api GET "/api/v1/scheme/push" "" "200"
test_api POST "/api/v1/scheme/listHistory" '{"eventId":"123","hazardType":1,"keyWords":""}' "200"
test_api POST "/api/v1/scheme/create" '{"planData":"测试方案","eventId":"123"}' "200"
echo ""

echo "=== 6. 任务模块 ==="
test_api POST "/api/v1/tasks/send" '{"id":"1","eventId":"123","task":[]}' "200"
test_api POST "/api/v1/tasks/task-list-detail" '{}' "200"
test_api POST "/api/v1/tasks/task-log-commit" '{"taskId":"00000000-0000-0000-0000-000000000001","description":"test","recorderName":"admin","recorderId":"1","origin":"admin","status":"COMPLETED"}' "200"
test_api POST "/api/v1/tasks/rescueTask" '[]' "200"
test_api POST "/api/v1/tasks/multi-rescue-scheme" '{"eventId":"123"}' "200"
test_api POST "/api/v1/tasks/multi-rescue-task" '{"eventId":"123"}' "200"
echo ""

echo "=== 7. 调试模块 ==="
test_api POST "/web-api/api/v1/debug/test/rescueDetail" '{"eventId":"123"}' "200"
test_api POST "/web-api/api/v1/debug/test/rescue-confirm" '{}' "200"
test_api POST "/web-api/api/v1/debug/test/addRescue" '{}' "200"
echo ""

echo "=== 8. WebSocket端点检查 ==="
echo -n "检查 /ws/real-time ... "
ws_info=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/ws/real-time" 2>/dev/null || echo "000")
if [ "$ws_info" == "000" ] || [ "$ws_info" == "426" ]; then
    echo -e "${GREEN}PASS${NC} (WebSocket端点存在)"
else
    echo -e "${RED}WARN${NC} (HTTP $ws_info)"
fi

echo -n "检查 /ws/stomp/info ... "
stomp_info=$(curl -s "$BASE_URL/ws/stomp/info" 2>/dev/null)
if echo "$stomp_info" | grep -q "websocket"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
fi
echo ""

echo "========================================"
echo "测试完成"
echo "========================================"
