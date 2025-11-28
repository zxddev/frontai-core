#!/usr/bin/env python3
"""
茂县态势标绘完整测试脚本

测试所有标绘类型，坐标使用茂县范围内的真实位置。
茂县中心: 103.853, 31.682
"""
import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000/api/v2/ai"
TEST_SCENARIO_ID = "00000000-0000-0000-0000-000000000001"

# 茂县关键位置坐标
MAOXIAN_LOCATIONS = {
    "county_center": (103.853, 31.682),      # 茂县县城中心
    "fengyi_town": (103.856, 31.685),        # 凤仪镇
    "nanxin_town": (103.823, 31.603),        # 南新镇
    "goukou_village": (103.879, 31.712),     # 沟口乡
    "disaster_site": (103.862, 31.675),      # 模拟灾害点
    "command_post": (103.848, 31.688),       # 指挥部
    "shelter_1": (103.841, 31.695),          # 安置点1
    "shelter_2": (103.867, 31.671),          # 安置点2
    "rescue_point_1": (103.858, 31.679),     # 救援点1
    "rescue_point_2": (103.871, 31.669),     # 救援点2
    "resource_depot": (103.845, 31.691),     # 物资仓库
}

# 救援路线（县城到灾害点）
RESCUE_ROUTE_1 = [
    [103.853, 31.682],  # 起点：县城
    [103.855, 31.680],
    [103.858, 31.678],
    [103.860, 31.676],
    [103.862, 31.675],  # 终点：灾害点
]

# 疏散路线（灾害点到安置点）
EVACUATION_ROUTE = [
    [103.862, 31.675],  # 起点：灾害点
    [103.858, 31.680],
    [103.852, 31.685],
    [103.848, 31.690],
    [103.841, 31.695],  # 终点：安置点1
]


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def plot_point(plotting_type: str, name: str, lon: float, lat: float, 
               description: str = None, level: int = None) -> dict:
    """标绘点位"""
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "plotting_type": plotting_type,
        "name": name,
        "longitude": lon,
        "latitude": lat,
    }
    if description:
        payload["description"] = description
    if level:
        payload["level"] = level
    
    resp = requests.post(f"{BASE_URL}/plotting/point", json=payload, timeout=30)
    return resp.json()


def plot_circle(plotting_type: str, name: str, lon: float, lat: float, 
                radius_m: float, description: str = None) -> dict:
    """标绘圆形区域"""
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "plotting_type": plotting_type,
        "name": name,
        "center_longitude": lon,
        "center_latitude": lat,
        "radius_m": radius_m,
    }
    if description:
        payload["description"] = description
    
    resp = requests.post(f"{BASE_URL}/plotting/circle", json=payload, timeout=30)
    return resp.json()


def plot_route(name: str, coordinates: list, device_type: str = "car", 
               is_selected: bool = True) -> dict:
    """标绘路线"""
    payload = {
        "scenario_id": TEST_SCENARIO_ID,
        "name": name,
        "coordinates": coordinates,
        "device_type": device_type,
        "is_selected": is_selected,
    }
    
    resp = requests.post(f"{BASE_URL}/plotting/route", json=payload, timeout=30)
    return resp.json()


def main():
    print("\n" + "#" * 60)
    print("# 茂县态势标绘完整测试")
    print("# 所有标绘将通过STOMP推送到前端")
    print("#" * 60)
    print(f"\n测试场景ID: {TEST_SCENARIO_ID}")
    print(f"茂县中心坐标: {MAOXIAN_LOCATIONS['county_center']}")
    
    results = []
    entity_ids = []
    
    # =========================================================================
    # 1. 事件图层 (layer.event)
    # =========================================================================
    print_section("1. 事件图层 (layer.event)")
    
    # 1.1 事件点 - event_point
    print("\n[1.1] 标绘事件点 (event_point)")
    loc = MAOXIAN_LOCATIONS["disaster_site"]
    result = plot_point(
        "event_point", 
        "茂县山体滑坡事件",
        loc[0], loc[1],
        description="2024年暴雨引发山体滑坡，道路中断"
    )
    print(f"  结果: {result}")
    results.append(("event_point", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # 1.2 态势描述点 - situation_point
    print("\n[1.2] 标绘态势描述点 (situation_point)")
    loc = MAOXIAN_LOCATIONS["county_center"]
    result = plot_point(
        "situation_point",
        "当前态势",
        loc[0], loc[1],
        description="已疏散1200人，道路抢通中"
    )
    print(f"  结果: {result}")
    results.append(("situation_point", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    time.sleep(0.5)  # 避免请求过快
    
    # =========================================================================
    # 2. 救援图层 (layer.rescue)
    # =========================================================================
    print_section("2. 救援图层 (layer.rescue)")
    
    # 2.1 救援目标 - rescue_target (带波纹动画)
    print("\n[2.1] 标绘救援目标 (rescue_target) - 波纹动画")
    loc = MAOXIAN_LOCATIONS["rescue_point_1"]
    result = plot_point(
        "rescue_target",
        "被困人员位置A",
        loc[0], loc[1],
        description="5人被困，需紧急救援",
        level=4
    )
    print(f"  结果: {result}")
    results.append(("rescue_target_1", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # 第二个救援点
    print("\n[2.2] 标绘救援目标2 (rescue_target)")
    loc = MAOXIAN_LOCATIONS["rescue_point_2"]
    result = plot_point(
        "rescue_target",
        "被困人员位置B",
        loc[0], loc[1],
        description="3人被困，伤情较轻",
        level=3
    )
    print(f"  结果: {result}")
    results.append(("rescue_target_2", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    time.sleep(0.5)
    
    # =========================================================================
    # 3. 区域图层 (layer.area)
    # =========================================================================
    print_section("3. 区域图层 (layer.area)")
    
    # 3.1 危险区 - danger_area (橙色)
    print("\n[3.1] 标绘危险区 (danger_area) - 橙色圆形")
    loc = MAOXIAN_LOCATIONS["disaster_site"]
    result = plot_circle(
        "danger_area",
        "滑坡危险区",
        loc[0], loc[1],
        radius_m=500,
        description="滑坡核心区域，禁止进入"
    )
    print(f"  结果: {result}")
    results.append(("danger_area", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # 3.2 安全区 - safety_area (绿色)
    print("\n[3.2] 标绘安全区 (safety_area) - 绿色圆形")
    loc = MAOXIAN_LOCATIONS["shelter_1"]
    result = plot_circle(
        "safety_area",
        "临时安置区A",
        loc[0], loc[1],
        radius_m=300,
        description="已安置群众800人"
    )
    print(f"  结果: {result}")
    results.append(("safety_area_1", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # 第二个安全区
    print("\n[3.3] 标绘安全区2 (safety_area)")
    loc = MAOXIAN_LOCATIONS["shelter_2"]
    result = plot_circle(
        "safety_area",
        "临时安置区B",
        loc[0], loc[1],
        radius_m=200,
        description="已安置群众400人"
    )
    print(f"  结果: {result}")
    results.append(("safety_area_2", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    time.sleep(0.5)
    
    # =========================================================================
    # 4. 资源图层 (layer.resource)
    # =========================================================================
    print_section("4. 资源图层 (layer.resource)")
    
    # 4.1 资源点 - resource_point
    print("\n[4.1] 标绘资源点 (resource_point)")
    loc = MAOXIAN_LOCATIONS["resource_depot"]
    result = plot_point(
        "resource_point",
        "应急物资仓库",
        loc[0], loc[1],
        description="帐篷500顶、棉被2000床、食品若干"
    )
    print(f"  结果: {result}")
    results.append(("resource_point", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # 4.2 指挥部候选点 - command_post_candidate (蓝色)
    print("\n[4.2] 标绘指挥部 (command_post_candidate) - 蓝色圆形")
    loc = MAOXIAN_LOCATIONS["command_post"]
    result = plot_circle(
        "command_post_candidate",
        "现场指挥部",
        loc[0], loc[1],
        radius_m=100,
        description="前线指挥协调中心"
    )
    print(f"  结果: {result}")
    results.append(("command_post", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    time.sleep(0.5)
    
    # =========================================================================
    # 5. 安置图层 (layer.shelter)
    # =========================================================================
    print_section("5. 安置图层 (layer.shelter)")
    
    # 5.1 安置点 - resettle_point
    print("\n[5.1] 标绘安置点 (resettle_point)")
    loc = MAOXIAN_LOCATIONS["fengyi_town"]
    result = plot_point(
        "resettle_point",
        "凤仪镇安置点",
        loc[0], loc[1],
        description="可容纳2000人的长期安置点"
    )
    print(f"  结果: {result}")
    results.append(("resettle_point", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    time.sleep(0.5)
    
    # =========================================================================
    # 6. 路线图层 (layer.route)
    # =========================================================================
    print_section("6. 路线图层 (layer.route)")
    
    # 6.1 救援路线
    print("\n[6.1] 标绘救援路线 (planned_route)")
    result = plot_route(
        "救援1号路线",
        RESCUE_ROUTE_1,
        device_type="car",
        is_selected=True
    )
    print(f"  结果: {result}")
    results.append(("rescue_route", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # 6.2 疏散路线
    print("\n[6.2] 标绘疏散路线 (planned_route)")
    result = plot_route(
        "疏散路线",
        EVACUATION_ROUTE,
        device_type="car",
        is_selected=False
    )
    print(f"  结果: {result}")
    results.append(("evacuation_route", result.get("success", False)))
    if result.get("entity_id"):
        entity_ids.append(result["entity_id"])
    
    # =========================================================================
    # 测试结果汇总
    # =========================================================================
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
    print(f"已创建 {len(entity_ids)} 个实体")
    
    print("\n" + "-" * 60)
    print("前端应通过STOMP收到以下主题的消息:")
    print("  - /topic/map.entity.create (实体创建)")
    print("  - 收到消息后调用 getEntityList API 获取完整数据")
    print("  - handleEntityListType 根据type渲染对应动画")
    print("-" * 60)
    
    print("\n图层渲染效果说明:")
    print("  - rescue_target: 波纹动画 (isShowWave: true)")
    print("  - danger_area: 橙色圆形 (#FFC000)")
    print("  - safety_area: 绿色圆形 (#1AAB65)")
    print("  - command_post_candidate: 蓝色圆形 (#1EB0FC)")
    print("  - planned_route: 导航动画路线")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
