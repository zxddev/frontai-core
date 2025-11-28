#!/usr/bin/env python3
"""
态势标绘端到端测试脚本

测试内容:
1. 直接调用API - 自动化场景
2. 对话式 - 自然语言指令标绘
"""
import requests
import json
import sys
from uuid import uuid4
import time

BASE_URL = "http://localhost:8000/api/v2/ai"

# 使用一个测试用的scenario_id
TEST_SCENARIO_ID = "00000000-0000-0000-0000-000000000001"


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(success: bool, response: dict):
    """打印结果"""
    status = "✅ 成功" if success else "❌ 失败"
    print(f"\n{status}")
    print(f"响应: {json.dumps(response, indent=2, ensure_ascii=False)}")


# ============================================================================
# 测试1: 直接调用API - 标绘点位
# ============================================================================

def test_plot_point():
    """测试标绘点位API"""
    print_section("测试1.1: POST /ai/plotting/point - 标绘事件点")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "plotting_type": "event_point",
        "name": "测试事件点",
        "longitude": 116.397128,
        "latitude": 39.916527,
        "description": "API自动化测试创建的事件点",
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/plotting/point", json=payload, timeout=30)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success, result.get("entity_id") if success else None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, None


def test_plot_rescue_target():
    """测试标绘救援目标（带波纹动画）"""
    print_section("测试1.2: POST /ai/plotting/point - 标绘救援目标(波纹动画)")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "plotting_type": "rescue_target",
        "name": "紧急救援点A",
        "longitude": 116.407526,
        "latitude": 39.904030,
        "description": "有人员被困，需紧急救援",
        "level": 4,
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/plotting/point", json=payload, timeout=30)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success, result.get("entity_id") if success else None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, None


# ============================================================================
# 测试2: 直接调用API - 标绘圆形区域
# ============================================================================

def test_plot_danger_area():
    """测试标绘危险区域"""
    print_section("测试2.1: POST /ai/plotting/circle - 标绘危险区(橙色)")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "plotting_type": "danger_area",
        "name": "危化品泄漏区",
        "center_longitude": 116.410,
        "center_latitude": 39.910,
        "radius_m": 500,
        "description": "需紧急疏散，500米范围内禁止进入",
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/plotting/circle", json=payload, timeout=30)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success, result.get("entity_id") if success else None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, None


def test_plot_safety_area():
    """测试标绘安全区域"""
    print_section("测试2.2: POST /ai/plotting/circle - 标绘安全区(绿色)")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "plotting_type": "safety_area",
        "name": "临时安置点",
        "center_longitude": 116.420,
        "center_latitude": 39.920,
        "radius_m": 300,
        "description": "已疏散人员临时安置区域",
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/plotting/circle", json=payload, timeout=30)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success, result.get("entity_id") if success else None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, None


# ============================================================================
# 测试3: 直接调用API - 标绘路线
# ============================================================================

def test_plot_route():
    """测试标绘规划路线"""
    print_section("测试3: POST /ai/plotting/route - 标绘救援路线")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "name": "救援路线1号",
        "coordinates": [
            [116.397, 39.916],
            [116.400, 39.914],
            [116.405, 39.912],
            [116.410, 39.910],
        ],
        "device_type": "car",
        "is_selected": True,
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/plotting/route", json=payload, timeout=30)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success, result.get("entity_id") if success else None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, None


# ============================================================================
# 测试4: 删除标绘
# ============================================================================

def test_delete_plot(entity_id: str):
    """测试删除标绘"""
    print_section(f"测试4: DELETE /ai/plotting/{entity_id}")
    
    try:
        resp = requests.delete(f"{BASE_URL}/plotting/{entity_id}", timeout=30)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


# ============================================================================
# 测试5: 对话式标绘
# ============================================================================

def test_dialog_plot_point():
    """测试对话式标绘 - 标点"""
    print_section("测试5.1: POST /ai/situation-plot - 对话标绘点位")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "message": "在经度116.405，纬度39.908的位置标一个救援目标，名称叫'被困人员位置B'",
    }
    
    try:
        print(f"用户指令: {payload['message']}")
        resp = requests.post(f"{BASE_URL}/situation-plot", json=payload, timeout=120)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def test_dialog_plot_circle():
    """测试对话式标绘 - 画圆"""
    print_section("测试5.2: POST /ai/situation-plot - 对话标绘圆形区域")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "message": "在116.415, 39.915画一个半径800米的危险区，名字叫'火灾蔓延区'",
    }
    
    try:
        print(f"用户指令: {payload['message']}")
        resp = requests.post(f"{BASE_URL}/situation-plot", json=payload, timeout=120)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def test_dialog_with_geocode():
    """测试对话式标绘 - 地址转坐标"""
    print_section("测试5.3: POST /ai/situation-plot - 地址转坐标后标绘")
    
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "message": "在北京市天安门广场标一个事件点，名称叫'演练集合点'",
    }
    
    try:
        print(f"用户指令: {payload['message']}")
        print("(此测试需要高德API Key，若未配置会失败)")
        resp = requests.post(f"{BASE_URL}/situation-plot", json=payload, timeout=120)
        result = resp.json()
        success = resp.status_code == 200 and result.get("success")
        print_result(success, result)
        return success
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("\n" + "=" * 60)
    print(" 态势标绘端到端测试")
    print("=" * 60)
    print(f"测试服务: {BASE_URL}")
    print(f"测试场景ID: {TEST_SCENARIO_ID}")
    
    results = []
    created_entities = []
    
    # ===== 场景1: 直接调用API =====
    print("\n\n" + "#" * 60)
    print("# 场景1: 直接调用API - 自动化标绘")
    print("#" * 60)
    
    # 测试1.1: 标绘事件点
    success, entity_id = test_plot_point()
    results.append(("标绘事件点", success))
    if entity_id:
        created_entities.append(entity_id)
    
    # 测试1.2: 标绘救援目标
    success, entity_id = test_plot_rescue_target()
    results.append(("标绘救援目标", success))
    if entity_id:
        created_entities.append(entity_id)
    
    # 测试2.1: 标绘危险区
    success, entity_id = test_plot_danger_area()
    results.append(("标绘危险区", success))
    if entity_id:
        created_entities.append(entity_id)
    
    # 测试2.2: 标绘安全区
    success, entity_id = test_plot_safety_area()
    results.append(("标绘安全区", success))
    if entity_id:
        created_entities.append(entity_id)
    
    # 测试3: 标绘路线
    success, entity_id = test_plot_route()
    results.append(("标绘路线", success))
    if entity_id:
        created_entities.append(entity_id)
    
    # 测试4: 删除标绘（删除第一个创建的实体）
    if created_entities:
        success = test_delete_plot(created_entities[0])
        results.append(("删除标绘", success))
        created_entities.pop(0)
    
    # ===== 场景2: 对话式标绘 =====
    print("\n\n" + "#" * 60)
    print("# 场景2: 对话式标绘 - 自然语言指令")
    print("#" * 60)
    
    # 测试5.1: 对话标点
    success = test_dialog_plot_point()
    results.append(("对话标绘点位", success))
    
    # 测试5.2: 对话画圆
    success = test_dialog_plot_circle()
    results.append(("对话标绘圆形", success))
    
    # 测试5.3: 地址转坐标
    success = test_dialog_with_geocode()
    results.append(("对话+地理编码", success))
    
    # ===== 测试结果汇总 =====
    print("\n\n" + "=" * 60)
    print(" 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    # 清理提示
    if created_entities:
        print(f"\n⚠️  剩余未删除的测试实体: {len(created_entities)} 个")
        print("   可手动删除或忽略（测试数据）")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
