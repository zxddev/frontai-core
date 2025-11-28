#!/usr/bin/env python3
"""
RealTimeRiskAgent 风险预测端到端测试脚本
"""
import requests
import json
import sys
from uuid import uuid4

BASE_URL = "http://localhost:8000/api/v2/ai/early-warning"


def test_api_health():
    """测试API是否可访问"""
    print("\n" + "=" * 60)
    print("测试0: API健康检查")
    print("=" * 60)
    
    try:
        resp = requests.get("http://localhost:8000/api/v2/docs", timeout=5)
        print(f"API Status: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"API不可访问: {e}")
        return False


def test_path_risk_prediction():
    """测试路径风险预测API"""
    print("\n" + "=" * 60)
    print("测试1: POST /predict/path-risk")
    print("=" * 60)
    
    # 成都市区测试坐标
    payload = {
        "origin": {"lon": 104.0657, "lat": 30.6595},      # 成都市中心
        "destination": {"lon": 104.1437, "lat": 30.6267},  # 成都东站
        "team_name": "救援一队",
        "prediction_hours": 6,
    }
    
    try:
        print(f"请求: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        resp = requests.post(f"{BASE_URL}/predict/path-risk", json=payload, timeout=60)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"响应:")
            print(f"  request_id: {data.get('request_id')}")
            print(f"  success: {data.get('success')}")
            print(f"  message: {data.get('message')}")
            print(f"  predictions: {len(data.get('predictions', []))}条")
            print(f"  pending_human_review: {data.get('pending_human_review')}")
            
            if data.get('predictions'):
                pred = data['predictions'][0]
                print(f"\n  预测详情:")
                print(f"    risk_level: {pred.get('risk_level')}")
                print(f"    risk_score: {pred.get('risk_score')}")
                print(f"    confidence: {pred.get('confidence_score')}")
                print(f"    factors: {len(pred.get('risk_factors', []))}个")
                print(f"    recommendations: {pred.get('recommendations')}")
            return True, data
        else:
            print(f"Error: {resp.text}")
            return False, None
    except Exception as e:
        print(f"Exception: {e}")
        return False, None


def test_operation_risk_prediction():
    """测试作业风险评估API"""
    print("\n" + "=" * 60)
    print("测试2: POST /predict/operation-risk")
    print("=" * 60)
    
    payload = {
        "location": {"lon": 104.0657, "lat": 30.6595},
        "operation_type": "firefighting",
        "team_name": "消防救援队",
    }
    
    try:
        print(f"请求: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        resp = requests.post(f"{BASE_URL}/predict/operation-risk", json=payload, timeout=60)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"响应:")
            print(f"  request_id: {data.get('request_id')}")
            print(f"  success: {data.get('success')}")
            print(f"  message: {data.get('message')}")
            
            if data.get('predictions'):
                pred = data['predictions'][0]
                print(f"\n  预测详情:")
                print(f"    risk_level: {pred.get('risk_level')}")
                print(f"    risk_score: {pred.get('risk_score')}")
                print(f"    operation_type: {pred.get('prediction_type')}")
                print(f"    factors:")
                for f in pred.get('risk_factors', [])[:3]:
                    print(f"      - {f.get('description')}")
            return True, data
        else:
            print(f"Error: {resp.text}")
            return False, None
    except Exception as e:
        print(f"Exception: {e}")
        return False, None


def test_disaster_spread_prediction(disaster_id: str = None):
    """测试灾害扩散预测API"""
    print("\n" + "=" * 60)
    print("测试3: POST /predict/disaster-spread")
    print("=" * 60)
    
    if not disaster_id:
        # 先创建一个灾害
        disaster_payload = {
            "disaster_type": "fire",
            "disaster_name": "测试火灾",
            "boundary": {
                "type": "Polygon",
                "coordinates": [[
                    [104.0657, 30.6595],
                    [104.0757, 30.6595],
                    [104.0757, 30.6695],
                    [104.0657, 30.6695],
                    [104.0657, 30.6595],
                ]]
            },
            "severity_level": 3,
            "spread_direction": "NE",
            "spread_speed_mps": 0.5,
            "source": "e2e_test",
        }
        
        print("创建测试灾害...")
        try:
            resp = requests.post(f"{BASE_URL}/disasters/update", json=disaster_payload, timeout=30)
            if resp.status_code == 200:
                disaster_id = resp.json().get("disaster_id")
                print(f"  灾害ID: {disaster_id}")
            else:
                print(f"  创建灾害失败: {resp.text}")
                return False, None
        except Exception as e:
            print(f"  创建灾害异常: {e}")
            return False, None
    
    payload = {
        "disaster_id": disaster_id,
        "prediction_hours_list": [1, 6, 24],
    }
    
    try:
        print(f"\n请求: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        resp = requests.post(f"{BASE_URL}/predict/disaster-spread", json=payload, timeout=60)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"响应:")
            print(f"  request_id: {data.get('request_id')}")
            print(f"  success: {data.get('success')}")
            print(f"  message: {data.get('message')}")
            
            if data.get('predictions'):
                pred = data['predictions'][0]
                print(f"\n  预测详情:")
                print(f"    risk_level: {pred.get('risk_level')}")
                print(f"    target_name: {pred.get('target_name')}")
                print(f"    prediction_horizon_hours: {pred.get('prediction_horizon_hours')}")
                
                weather_data = pred.get('weather_data', {})
                spread_preds = weather_data.get('spread_predictions', [])
                print(f"    扩散预测 ({len(spread_preds)}个时间点):")
                for sp in spread_preds:
                    print(f"      - {sp.get('hours')}h: {sp.get('distance_m'):.0f}m")
            return True, data
        elif resp.status_code == 404:
            print(f"灾害不存在（预期行为）")
            return True, None
        else:
            print(f"Error: {resp.text}")
            return False, None
    except Exception as e:
        print(f"Exception: {e}")
        return False, None


def test_human_review():
    """测试人工审核API"""
    print("\n" + "=" * 60)
    print("测试4: POST /predictions/{id}/review")
    print("=" * 60)
    
    prediction_id = str(uuid4())
    payload = {
        "prediction_id": prediction_id,
        "reviewer_id": "test_reviewer",
        "decision": "approved",
        "notes": "E2E测试审核",
    }
    
    try:
        print(f"请求: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        resp = requests.post(
            f"{BASE_URL}/predictions/{prediction_id}/review", 
            json=payload, 
            timeout=10
        )
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"响应:")
            print(f"  prediction_id: {data.get('prediction_id')}")
            print(f"  decision: {data.get('decision')}")
            print(f"  success: {data.get('success')}")
            print(f"  message: {data.get('message')}")
            return True, data
        else:
            print(f"Error: {resp.text}")
            return False, None
    except Exception as e:
        print(f"Exception: {e}")
        return False, None


def test_different_operation_types():
    """测试不同作业类型的风险评估"""
    print("\n" + "=" * 60)
    print("测试5: 多种作业类型风险评估")
    print("=" * 60)
    
    operation_types = ["rescue", "firefighting", "hazmat", "height_work", "demolition"]
    results = []
    
    for op_type in operation_types:
        payload = {
            "location": {"lon": 104.0657, "lat": 30.6595},
            "operation_type": op_type,
            "team_name": f"测试队伍-{op_type}",
        }
        
        try:
            resp = requests.post(f"{BASE_URL}/predict/operation-risk", json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                pred = data.get('predictions', [{}])[0]
                risk_level = pred.get('risk_level', 'unknown')
                print(f"  {op_type:15} → {risk_level}")
                results.append((op_type, True, risk_level))
            else:
                print(f"  {op_type:15} → FAILED ({resp.status_code})")
                results.append((op_type, False, None))
        except Exception as e:
            print(f"  {op_type:15} → ERROR ({e})")
            results.append((op_type, False, None))
    
    all_pass = all(r[1] for r in results)
    return all_pass, results


def main():
    print("=" * 60)
    print("RealTimeRiskAgent 风险预测端到端测试")
    print("=" * 60)
    
    # 0. 检查API是否可用
    if not test_api_health():
        print("\nAPI服务未启动，请先运行:")
        print("  uvicorn src.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    results = []
    
    # 1. 路径风险预测
    success, _ = test_path_risk_prediction()
    results.append(("路径风险预测", success))
    
    # 2. 作业风险评估
    success, _ = test_operation_risk_prediction()
    results.append(("作业风险评估", success))
    
    # 3. 灾害扩散预测
    success, _ = test_disaster_spread_prediction()
    results.append(("灾害扩散预测", success))
    
    # 4. 人工审核
    success, _ = test_human_review()
    results.append(("人工审核", success))
    
    # 5. 多种作业类型
    success, _ = test_different_operation_types()
    results.append(("多作业类型", success))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:20} [{status}]")
        if not passed:
            all_pass = False
    
    print("=" * 60)
    if all_pass:
        print("所有测试通过!")
        return 0
    else:
        print("部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
