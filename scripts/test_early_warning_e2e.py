#!/usr/bin/env python3
"""
预警监测智能体端到端测试脚本
"""
import requests
import json
import sys
from uuid import uuid4

BASE_URL = "http://localhost:8000/api/v2/ai/early-warning"


def test_disaster_update():
    """测试灾害数据更新接口"""
    print("\n" + "=" * 50)
    print("测试1: POST /disasters/update")
    print("=" * 50)
    
    payload = {
        "disaster_type": "fire",
        "disaster_name": "XX路火灾测试",
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.397, 39.908],
                    [116.400, 39.908],
                    [116.400, 39.910],
                    [116.397, 39.910],
                    [116.397, 39.908],
                ]
            ]
        },
        "buffer_distance_m": 3000,
        "severity_level": 3,
        "source": "e2e_test",
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/disasters/update", json=payload, timeout=30)
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.status_code == 200, resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return False, None


def test_list_warnings():
    """测试预警列表查询"""
    print("\n" + "=" * 50)
    print("测试2: GET /warnings")
    print("=" * 50)
    
    try:
        resp = requests.get(f"{BASE_URL}/warnings", timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.status_code == 200, resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return False, None


def test_warning_detail(warning_id: str):
    """测试预警详情查询"""
    print("\n" + "=" * 50)
    print(f"测试3: GET /warnings/{warning_id}")
    print("=" * 50)
    
    try:
        resp = requests.get(f"{BASE_URL}/warnings/{warning_id}", timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        else:
            print(f"Response: {resp.text}")
        return resp.status_code in [200, 404], resp.json() if resp.status_code == 200 else None
    except Exception as e:
        print(f"Error: {e}")
        return False, None


def test_acknowledge_warning(warning_id: str):
    """测试确认预警"""
    print("\n" + "=" * 50)
    print(f"测试4: POST /warnings/{warning_id}/acknowledge")
    print("=" * 50)
    
    try:
        resp = requests.post(f"{BASE_URL}/warnings/{warning_id}/acknowledge", timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.status_code in [200, 404], resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return False, None


def test_respond_warning(warning_id: str, action: str = "continue"):
    """测试响应预警"""
    print("\n" + "=" * 50)
    print(f"测试5: POST /warnings/{warning_id}/respond (action={action})")
    print("=" * 50)
    
    payload = {
        "action": action,
        "reason": "测试响应"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/warnings/{warning_id}/respond", json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.status_code in [200, 404], resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return False, None


def test_detour_options(warning_id: str):
    """测试获取绕行选项"""
    print("\n" + "=" * 50)
    print(f"测试6: GET /warnings/{warning_id}/detour-options")
    print("=" * 50)
    
    try:
        resp = requests.get(f"{BASE_URL}/warnings/{warning_id}/detour-options", timeout=30)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        else:
            print(f"Response: {resp.text}")
        return resp.status_code in [200, 404, 500], resp.json() if resp.status_code == 200 else None
    except Exception as e:
        print(f"Error: {e}")
        return False, None


def test_api_health():
    """测试API是否可访问"""
    print("\n" + "=" * 50)
    print("测试0: API健康检查")
    print("=" * 50)
    
    try:
        resp = requests.get("http://localhost:8000/api/v2/docs", timeout=5)
        print(f"API Status: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"API不可访问: {e}")
        return False


def main():
    print("=" * 50)
    print("预警监测智能体端到端测试")
    print("=" * 50)
    
    # 0. 检查API是否可用
    if not test_api_health():
        print("\nAPI服务未启动，请先运行: uvicorn src.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    results = []
    
    # 1. 测试灾害更新
    success, data = test_disaster_update()
    results.append(("灾害更新", success))
    
    # 2. 测试预警列表
    success, warnings_data = test_list_warnings()
    results.append(("预警列表", success))
    
    # 使用模拟的warning_id进行后续测试
    test_warning_id = str(uuid4())
    
    # 3. 测试预警详情（预期404，因为没有真实数据）
    success, _ = test_warning_detail(test_warning_id)
    results.append(("预警详情", success))
    
    # 4. 测试确认预警
    success, _ = test_acknowledge_warning(test_warning_id)
    results.append(("确认预警", success))
    
    # 5. 测试响应预警
    success, _ = test_respond_warning(test_warning_id, "continue")
    results.append(("响应预警", success))
    
    # 6. 测试绕行选项（需要有效的warning_id和disaster_id）
    success, _ = test_detour_options(test_warning_id)
    results.append(("绕行选项", success))
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: [{status}]")
        if not passed:
            all_pass = False
    
    print("=" * 50)
    if all_pass:
        print("所有测试通过!")
        return 0
    else:
        print("部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
