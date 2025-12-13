#!/bin/bash
# 测试 /tasks/send API

curl -s "http://localhost:8000/web-api/api/v1/tasks/send" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-scheme-001",
    "eventId": "411196cf-f923-48c2-b19c-00ab770553a6",
    "task": [
      {
        "type": "drone",
        "taskList": [
          {
            "deviceId": "dcdddc8c-5c09-4fbb-a45c-ef1a14f57bab",
            "deviceName": "翼龙-2H应急救援型无人机",
            "deviceType": "drone",
            "carryingModule": "高清摄像头",
            "timeConsuming": "30分钟",
            "searchRoute": "沿边界飞行"
          }
        ]
      }
    ]
  }' | python3 -m json.tool
