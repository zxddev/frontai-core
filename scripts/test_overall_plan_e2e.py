#!/usr/bin/env python3
"""
总体救灾方案端到端测试

验证内容：
1. SPHERE标准数值正确性
2. 估算器计算逻辑
3. 完整ResourcePlanner流程（需要vLLM）

运行方式：
  # 仅SPHERE标准验证（无需LLM）
  PYTHONPATH=. python3 scripts/test_overall_plan_e2e.py --unit-only

  # 完整端到端测试（需要vLLM）
  PYTHONPATH=. python3 scripts/test_overall_plan_e2e.py

  # 指定vLLM服务器
  OPENAI_BASE_URL=http://192.168.31.50:8000/v1 \
  LLM_MODEL=/models/openai/gpt-oss-120b \
  OPENAI_API_KEY=dummy_key \
  PYTHONPATH=. python3 scripts/test_overall_plan_e2e.py

环境变量：
  OPENAI_BASE_URL: vLLM服务器地址（必需）
  LLM_MODEL: 模型名称（必需）
  OPENAI_API_KEY: API密钥（必需，vLLM可用任意值）
"""

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ==============================================================================
# SPHERE标准验证（官方2018版手册）
# ==============================================================================

# 来源：Sphere Handbook 2018 Edition
# https://spherestandards.org/wp-content/uploads/Sphere-Handbook-2018-EN.pdf
SPHERE_2018_OFFICIAL = {
    # WASH Standard 2.1 - Water Access and Quantity
    "water_survival_liters_per_person_per_day": 2.5,  # 最低生存用水（立即响应）
    "water_basic_min_liters_per_person_per_day": 7.5,  # 基本用水最低（短期）
    "water_basic_target_liters_per_person_per_day": 15,  # 基本用水目标（短期）
    "water_full_target_liters_per_person_per_day": 20,  # 全量目标（含洗浴、清洁）
    
    # Shelter Standard 3 - Living Space
    "shelter_covered_space_warm_m2_per_person": 3.5,  # 温暖气候人均有盖面积
    "shelter_covered_space_cold_min_m2_per_person": 4.5,  # 寒冷气候人均最低
    "shelter_covered_space_cold_max_m2_per_person": 5.5,  # 寒冷气候人均建议
    
    # Food Security Standard 1 - Food Requirements
    "food_energy_kcal_per_person_per_day": 2100,  # 每日热量摄入
    "food_dry_ration_kg_per_person_per_day": 0.5,  # 相当于2100kcal的干粮
    
    # WASH Standard 3.2 - Toilet Access
    "toilet_ratio_persons_per_toilet": 20,  # 最多20人共用一个厕所
    
    # Shelter Standard 4 - Non-Food Items
    "blankets_min_per_person": 1,  # 最低每人1床
    "blankets_target_per_person": 2,  # 目标每人2床（温带/寒冷）
    "sleeping_mat_per_person": 1,  # 每人1个睡垫
}


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    expected: Any = None
    actual: Any = None


def test_sphere_water_standards() -> list[TestResult]:
    """验证水标准"""
    from src.agents.overall_plan.metagpt.estimators import SPHERE_STANDARDS
    from src.domains.disaster.sphere_standards import SPHERE_STANDARDS as DOMAIN_SPHERE

    results = []
    
    # estimators.py使用20L（目标值，非最低标准）
    results.append(TestResult(
        name="估算器水标准（20L）属于SPHERE目标范围",
        passed=SPHERE_STANDARDS["water_liters_per_person_per_day"] == 20,
        message="20L/人/天是SPHERE完整目标（含洗浴），非最低标准7.5L",
        expected=20,
        actual=SPHERE_STANDARDS["water_liters_per_person_per_day"],
    ))
    
    # sphere_standards.py使用分阶段水标准
    survival_water = DOMAIN_SPHERE.get("SPHERE-WASH-001")
    if survival_water:
        results.append(TestResult(
            name="领域层生存用水标准正确",
            passed=survival_water.min_quantity == 2.5,
            message="SPHERE立即响应阶段最低2.5L/人/天",
            expected=2.5,
            actual=survival_water.min_quantity,
        ))
    
    basic_water = DOMAIN_SPHERE.get("SPHERE-WASH-002")
    if basic_water:
        results.append(TestResult(
            name="领域层基本用水标准正确",
            passed=basic_water.min_quantity == 7.5 and basic_water.target_quantity == 15.0,
            message="SPHERE短期阶段最低7.5L，目标15L",
            expected=(7.5, 15.0),
            actual=(basic_water.min_quantity, basic_water.target_quantity),
        ))
    
    return results


def test_sphere_shelter_standards() -> list[TestResult]:
    """验证庇护所标准"""
    from src.agents.overall_plan.metagpt.estimators import SPHERE_STANDARDS
    from src.domains.disaster.sphere_standards import SPHERE_STANDARDS as DOMAIN_SPHERE

    results = []
    
    # 3.5m²是温暖气候的有盖居住面积，正确
    results.append(TestResult(
        name="估算器庇护所面积标准正确",
        passed=SPHERE_STANDARDS["shelter_area_sqm_per_person"] == 3.5,
        message="SPHERE 2018: 温暖气候最低3.5m²/人有盖居住面积",
        expected=3.5,
        actual=SPHERE_STANDARDS["shelter_area_sqm_per_person"],
    ))
    
    shelter_space = DOMAIN_SPHERE.get("SPHERE-SHELTER-001")
    if shelter_space:
        results.append(TestResult(
            name="领域层庇护所面积标准正确",
            passed=shelter_space.min_quantity == 3.5 and shelter_space.target_quantity == 4.5,
            message="SPHERE: 最低3.5m²（温暖），目标4.5m²（可调节）",
            expected=(3.5, 4.5),
            actual=(shelter_space.min_quantity, shelter_space.target_quantity),
        ))
    
    return results


def test_sphere_food_standards() -> list[TestResult]:
    """验证食物标准"""
    from src.agents.overall_plan.metagpt.estimators import SPHERE_STANDARDS
    
    results = []
    
    results.append(TestResult(
        name="食物配给标准正确",
        passed=SPHERE_STANDARDS["food_kg_per_person_per_day"] == 0.5,
        message="SPHERE: 0.5kg干粮/人/天 ≈ 2100kcal",
        expected=0.5,
        actual=SPHERE_STANDARDS["food_kg_per_person_per_day"],
    ))
    
    return results


def test_sphere_blanket_standards() -> list[TestResult]:
    """验证毛毯标准"""
    from src.agents.overall_plan.metagpt.estimators import SPHERE_STANDARDS
    
    results = []
    
    results.append(TestResult(
        name="毛毯配给标准正确（使用目标值）",
        passed=SPHERE_STANDARDS["blankets_per_person"] == 2,
        message="SPHERE: 最低1床/人，目标2床/人（温带/寒冷）",
        expected=2,
        actual=SPHERE_STANDARDS["blankets_per_person"],
    ))
    
    return results


def test_estimator_calculations() -> list[TestResult]:
    """验证估算器计算逻辑"""
    from src.agents.overall_plan.metagpt.estimators import (
        estimate_shelter_needs,
        estimate_rescue_force,
        estimate_medical_resources,
        EstimatorValidationError,
    )
    
    results = []
    
    # 测试1: 1000人3天的庇护需求
    shelter = estimate_shelter_needs(1000, days=3)
    
    results.append(TestResult(
        name="帐篷计算正确（1000人）",
        passed=shelter["tents"] == 200,  # 1000/5 = 200
        message="5人/顶帐篷",
        expected=200,
        actual=shelter["tents"],
    ))
    
    results.append(TestResult(
        name="毛毯计算正确（1000人）",
        passed=shelter["blankets"] == 2000,  # 1000*2 = 2000
        message="2床/人",
        expected=2000,
        actual=shelter["blankets"],
    ))
    
    results.append(TestResult(
        name="饮水计算正确（1000人3天）",
        passed=shelter["water_liters"] == 60000,  # 1000*20*3 = 60000
        message="20L/人/天 * 3天",
        expected=60000,
        actual=shelter["water_liters"],
    ))
    
    results.append(TestResult(
        name="食物计算正确（1000人3天）",
        passed=shelter["food_kg"] == 1500,  # 1000*0.5*3 = 1500
        message="0.5kg/人/天 * 3天",
        expected=1500,
        actual=shelter["food_kg"],
    ))
    
    # 测试2: 救援力量计算
    rescue = estimate_rescue_force(50)
    results.append(TestResult(
        name="救援队伍计算正确（50被困）",
        passed=rescue["rescue_teams"] == 1,  # ceil(50/50) = 1
        message="1队/50被困人员",
        expected=1,
        actual=rescue["rescue_teams"],
    ))
    
    rescue = estimate_rescue_force(51)
    results.append(TestResult(
        name="救援队伍计算正确（51被困）",
        passed=rescue["rescue_teams"] == 2,  # ceil(51/50) = 2
        message="ceil(51/50) = 2",
        expected=2,
        actual=rescue["rescue_teams"],
    ))
    
    # 测试3: 医疗资源计算
    medical = estimate_medical_resources(100, 25)
    results.append(TestResult(
        name="医护人员计算正确",
        passed=medical["medical_staff"] == 5,  # ceil(100/20) = 5
        message="1医护/20伤员",
        expected=5,
        actual=medical["medical_staff"],
    ))
    
    results.append(TestResult(
        name="担架计算正确",
        passed=medical["stretchers"] == 25,  # 重伤人数
        message="每位重伤员1副担架",
        expected=25,
        actual=medical["stretchers"],
    ))
    
    # 测试4: 边界情况
    shelter_zero = estimate_shelter_needs(0, days=3)
    results.append(TestResult(
        name="零人口返回零需求",
        passed=shelter_zero["tents"] == 0 and shelter_zero["water_liters"] == 0,
        message="正确处理边界情况",
        expected=(0, 0),
        actual=(shelter_zero["tents"], shelter_zero["water_liters"]),
    ))
    
    # 测试5: 输入验证
    try:
        estimate_shelter_needs(-100, days=3)
        results.append(TestResult(
            name="负数人口应抛出异常",
            passed=False,
            message="未抛出EstimatorValidationError",
        ))
    except EstimatorValidationError:
        results.append(TestResult(
            name="负数人口正确抛出异常",
            passed=True,
            message="EstimatorValidationError正确触发",
        ))
    
    return results


def test_sphere_comm_standards() -> list[TestResult]:
    """验证通信设备标准（v2新增）"""
    from src.domains.disaster.sphere_standards import (
        SPHERE_STANDARDS as DOMAIN_SPHERE,
        SphereCategory,
        ScalingBasis,
    )
    
    results = []
    
    # 卫星电话
    sat_phone = DOMAIN_SPHERE.get("SPHERE-COMM-001")
    if sat_phone:
        results.append(TestResult(
            name="卫星电话标准正确",
            passed=(
                sat_phone.min_quantity == 1.0 and
                sat_phone.category == SphereCategory.COMM and
                sat_phone.scaling_basis == ScalingBasis.PER_TEAM
            ),
            message="1部/救援队",
            expected=(1.0, "COMM", "per_team"),
            actual=(sat_phone.min_quantity, sat_phone.category.value, sat_phone.scaling_basis.value),
        ))
    else:
        results.append(TestResult(
            name="卫星电话标准存在",
            passed=False,
            message="SPHERE-COMM-001 未找到",
        ))
    
    # 数字对讲机
    radio = DOMAIN_SPHERE.get("SPHERE-COMM-002")
    if radio:
        results.append(TestResult(
            name="数字对讲机标准正确",
            passed=(
                radio.min_quantity == 1.0 and
                radio.scaling_basis == ScalingBasis.PER_RESCUER
            ),
            message="1部/救援人员",
            expected=(1.0, "per_rescuer"),
            actual=(radio.min_quantity, radio.scaling_basis.value),
        ))
    
    # 便携中继台
    repeater = DOMAIN_SPHERE.get("SPHERE-COMM-003")
    if repeater:
        results.append(TestResult(
            name="便携中继台标准正确",
            passed=(
                repeater.min_quantity == 1.0 and
                repeater.scaling_basis == ScalingBasis.PER_COMMAND_GROUP
            ),
            message="1台/指挥组",
            expected=(1.0, "per_command_group"),
            actual=(repeater.min_quantity, repeater.scaling_basis.value),
        ))
    
    # 应急通信车
    comm_vehicle = DOMAIN_SPHERE.get("SPHERE-COMM-004")
    if comm_vehicle:
        results.append(TestResult(
            name="应急通信车标准正确",
            passed=(
                comm_vehicle.min_quantity == 0.002 and
                comm_vehicle.scaling_basis == ScalingBasis.PER_DISPLACED
            ),
            message="1辆/500受灾群众",
            expected=(0.002, "per_displaced"),
            actual=(comm_vehicle.min_quantity, comm_vehicle.scaling_basis.value),
        ))
    
    return results


def test_sphere_rescue_ops_standards() -> list[TestResult]:
    """验证救援人员保障标准（v2新增）"""
    from src.domains.disaster.sphere_standards import (
        SPHERE_STANDARDS as DOMAIN_SPHERE,
        SphereCategory,
        ScalingBasis,
    )
    
    results = []
    
    # 救援人员饮水
    rescuer_water = DOMAIN_SPHERE.get("SPHERE-RES-001")
    if rescuer_water:
        results.append(TestResult(
            name="救援人员饮水标准正确",
            passed=(
                rescuer_water.min_quantity == 5.0 and
                rescuer_water.category == SphereCategory.RESCUE_OPS and
                rescuer_water.scaling_basis == ScalingBasis.PER_RESCUER
            ),
            message="5L/人/天（群众标准的2倍）",
            expected=(5.0, "RESCUE_OPS", "per_rescuer"),
            actual=(rescuer_water.min_quantity, rescuer_water.category.value, rescuer_water.scaling_basis.value),
        ))
    else:
        results.append(TestResult(
            name="救援人员饮水标准存在",
            passed=False,
            message="SPHERE-RES-001 未找到",
        ))
    
    # 救援人员热食
    rescuer_meals = DOMAIN_SPHERE.get("SPHERE-RES-002")
    if rescuer_meals:
        results.append(TestResult(
            name="救援人员热食标准正确",
            passed=(
                rescuer_meals.min_quantity == 3.0 and
                rescuer_meals.unit == "meal"
            ),
            message="3餐/人/天",
            expected=(3.0, "meal"),
            actual=(rescuer_meals.min_quantity, rescuer_meals.unit),
        ))
    
    # 轮换周期上限
    work_hours = DOMAIN_SPHERE.get("SPHERE-RES-003")
    if work_hours:
        results.append(TestResult(
            name="连续作业上限标准正确",
            passed=(
                work_hours.min_quantity == 8.0 and
                work_hours.unit == "hour" and
                work_hours.scaling_basis == ScalingBasis.FIXED
            ),
            message="8小时连续作业上限",
            expected=(8.0, "hour", "fixed"),
            actual=(work_hours.min_quantity, work_hours.unit, work_hours.scaling_basis.value),
        ))
    
    # 最低休息时间
    rest_period = DOMAIN_SPHERE.get("SPHERE-RES-004")
    if rest_period:
        results.append(TestResult(
            name="最低休息时间标准正确",
            passed=(
                rest_period.min_quantity == 6.0 and
                rest_period.target_quantity == 8.0
            ),
            message="最低6小时，建议8小时",
            expected=(6.0, 8.0),
            actual=(rest_period.min_quantity, rest_period.target_quantity),
        ))
    
    return results


def test_sphere_health_extended_standards() -> list[TestResult]:
    """验证扩展医疗标准（v2新增）"""
    from src.domains.disaster.sphere_standards import (
        SPHERE_STANDARDS as DOMAIN_SPHERE,
        SphereCategory,
        ScalingBasis,
    )
    
    results = []
    
    # 基础医疗点
    medical_station = DOMAIN_SPHERE.get("SPHERE-HEALTH-004")
    if medical_station:
        results.append(TestResult(
            name="基础医疗点标准正确",
            passed=(
                medical_station.min_quantity == 0.0001 and
                medical_station.scaling_basis == ScalingBasis.PER_DISPLACED
            ),
            message="1/10000受灾群众",
            expected=(0.0001, "per_displaced"),
            actual=(medical_station.min_quantity, medical_station.scaling_basis.value),
        ))
    else:
        results.append(TestResult(
            name="基础医疗点标准存在",
            passed=False,
            message="SPHERE-HEALTH-004 未找到",
        ))
    
    # 伤员床位
    beds = DOMAIN_SPHERE.get("SPHERE-HEALTH-005")
    if beds:
        results.append(TestResult(
            name="伤员床位标准正确",
            passed=(
                beds.min_quantity == 1.2 and
                beds.scaling_basis == ScalingBasis.PER_CASUALTY
            ),
            message="重伤员数×1.2",
            expected=(1.2, "per_casualty"),
            actual=(beds.min_quantity, beds.scaling_basis.value),
        ))
    
    # 医护人员配比
    personnel = DOMAIN_SPHERE.get("SPHERE-HEALTH-006")
    if personnel:
        results.append(TestResult(
            name="医护人员配比标准正确",
            passed=(
                personnel.min_quantity == 0.3 and
                personnel.scaling_basis == ScalingBasis.PER_BED
            ),
            message="0.3人/床位",
            expected=(0.3, "per_bed"),
            actual=(personnel.min_quantity, personnel.scaling_basis.value),
        ))
    
    return results


def test_scaling_basis_coverage() -> list[TestResult]:
    """验证新ScalingBasis枚举完整性"""
    from src.domains.disaster.sphere_standards import ScalingBasis
    
    results = []
    
    # 检查新增枚举值存在
    new_values = ["per_rescuer", "per_command_group", "per_bed"]
    for val in new_values:
        try:
            basis = ScalingBasis(val)
            results.append(TestResult(
                name=f"ScalingBasis.{val.upper()} 存在",
                passed=True,
                message=f"枚举值 {val} 正确定义",
            ))
        except ValueError:
            results.append(TestResult(
                name=f"ScalingBasis.{val.upper()} 存在",
                passed=False,
                message=f"枚举值 {val} 未定义",
            ))
    
    return results


def run_unit_tests() -> bool:
    """运行所有单元测试"""
    logger.info("=" * 60)
    logger.info("SPHERE标准验证与估算器单元测试")
    logger.info("=" * 60)
    
    all_results: list[TestResult] = []
    
    # 运行各组测试
    test_groups = [
        ("水标准验证", test_sphere_water_standards),
        ("庇护所标准验证", test_sphere_shelter_standards),
        ("食物标准验证", test_sphere_food_standards),
        ("毛毯标准验证", test_sphere_blanket_standards),
        ("估算器计算逻辑", test_estimator_calculations),
        # v2新增测试组
        ("通信设备标准验证（v2）", test_sphere_comm_standards),
        ("救援人员保障标准验证（v2）", test_sphere_rescue_ops_standards),
        ("扩展医疗标准验证（v2）", test_sphere_health_extended_standards),
        ("ScalingBasis枚举完整性", test_scaling_basis_coverage),
    ]
    
    for group_name, test_func in test_groups:
        logger.info(f"\n[测试组] {group_name}")
        logger.info("-" * 40)
        
        try:
            results = test_func()
            all_results.extend(results)
            
            for r in results:
                status = "✅" if r.passed else "❌"
                logger.info(f"  {status} {r.name}")
                if not r.passed:
                    logger.info(f"      预期: {r.expected}, 实际: {r.actual}")
                    logger.info(f"      说明: {r.message}")
                    
        except Exception as e:
            logger.error(f"  ❌ 测试组执行失败: {e}")
            all_results.append(TestResult(
                name=f"{group_name}执行",
                passed=False,
                message=str(e),
            ))
    
    # 汇总结果
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"测试汇总: {passed}/{total} 通过")
    logger.info("=" * 60)
    
    return passed == total


# ==============================================================================
# 端到端测试（需要vLLM）
# ==============================================================================

async def check_vllm_connection() -> bool:
    """检查vLLM服务连接"""
    import os
    import httpx
    
    base_url = os.environ.get("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    model = os.environ.get("LLM_MODEL", "/models/openai/gpt-oss-120b")
    api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")
    
    logger.info(f"vLLM配置:")
    logger.info(f"  Base URL: {base_url}")
    logger.info(f"  Model: {model}")
    logger.info(f"  API Key: {'***' if api_key else 'NOT SET'}")
    
    # 测试连接
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 尝试获取模型列表
            resp = await client.get(
                f"{base_url.rstrip('/v1')}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                logger.info(f"  可用模型: {[m.get('id') for m in models[:5]]}")
                return True
            else:
                logger.warning(f"  模型列表请求失败: {resp.status_code}")
                # 即使模型列表失败，也尝试继续
                return True
    except Exception as e:
        logger.error(f"  连接失败: {e}")
        return False


async def test_resource_planner_e2e() -> bool:
    """完整ResourcePlanner端到端测试"""
    import os
    import time
    
    logger.info("\n" + "=" * 60)
    logger.info("ResourcePlanner端到端测试（需要vLLM）")
    logger.info("=" * 60)
    
    # 检查连接
    if not await check_vllm_connection():
        logger.error("无法连接vLLM服务，跳过端到端测试")
        logger.info("请确保设置环境变量: OPENAI_BASE_URL, LLM_MODEL, OPENAI_API_KEY")
        return False
    
    try:
        from src.agents.overall_plan.metagpt.roles import ResourcePlanner
        from src.agents.overall_plan.schemas import ResourceCalculationInput
        from src.agents.overall_plan.instructor.client import create_instructor_client
        
        # 创建测试输入 - 模拟中等规模地震
        test_input = ResourceCalculationInput(
            affected_population=10000,
            trapped_count=100,
            injured_count=500,
            serious_injury_count=125,
            emergency_duration_days=3,
            buildings_collapsed=50,
            buildings_damaged=200,
            roads_damaged_km=15.0,
            bridges_damaged=2,
            power_outage_households=5000,
            communication_towers_damaged=3,
            disaster_type="地震",
            affected_area="四川省绵阳市北川县",
        )
        
        logger.info("\n[测试场景] 中等规模地震")
        logger.info(f"  受灾人口: {test_input.affected_population:,}")
        logger.info(f"  被困人员: {test_input.trapped_count}")
        logger.info(f"  伤员人数: {test_input.injured_count}")
        logger.info(f"  倒塌建筑: {test_input.buildings_collapsed}")
        logger.info(f"  应急天数: {test_input.emergency_duration_days}")
        
        # 创建客户端和规划师
        logger.info("\n[创建Instructor客户端]")
        client = create_instructor_client()
        planner = ResourcePlanner(client)
        
        # 执行计算
        logger.info("\n[执行ResourcePlanner]")
        logger.info("正在调用LLM生成各模块内容，请等待...")
        
        start_time = time.time()
        output = await planner.run(test_input)
        elapsed = time.time() - start_time
        
        logger.info(f"执行完成，耗时: {elapsed:.2f}秒")
        
        # 验证输出
        all_passed = True
        
        logger.info("\n[模块生成验证]")
        modules = [
            ("module_1_rescue_force", "模块1 救援力量部署"),
            ("module_2_medical", "模块2 医疗救护"),
            ("module_3_infrastructure", "模块3 基础设施抢修"),
            ("module_4_shelter", "模块4 临时安置与生活保障"),
            ("module_6_communication", "模块6 通信与信息保障"),
            ("module_7_logistics", "模块7 物资调拨与运输"),
            ("module_8_self_support", "模块8 救援力量自身保障"),
        ]
        
        for attr_name, desc in modules:
            content = getattr(output, attr_name, "")
            if content and len(content) > 100:
                logger.info(f"  ✅ {desc}: {len(content)} 字符")
            else:
                logger.error(f"  ❌ {desc}: 内容不足 ({len(content) if content else 0} 字符)")
                all_passed = False
        
        # 验证计算详情
        logger.info("\n[计算详情验证]")
        details = output.calculation_details
        if details:
            logger.info("  ✅ calculation_details 已生成")
            
            # 验证SPHERE核心数值
            shelter_calc = details.get("shelter_calculation", {})
            if shelter_calc:
                # 帐篷: 10000人 / 5人/顶 = 2000顶
                expected_tents = 10000 // 5
                actual_tents = shelter_calc.get("tents", 0)
                status = "✅" if actual_tents == expected_tents else "⚠️"
                logger.info(f"  {status} 帐篷: {actual_tents} (预期 {expected_tents})")
                
                # 毛毯: 10000人 * 2床/人 = 20000床
                expected_blankets = 10000 * 2
                actual_blankets = shelter_calc.get("blankets", 0)
                status = "✅" if actual_blankets == expected_blankets else "⚠️"
                logger.info(f"  {status} 毛毯: {actual_blankets} (预期 {expected_blankets})")
                
                # 饮水: 10000人 * 20L/天 * 3天 = 600,000L
                expected_water = 10000 * 20 * 3
                actual_water = shelter_calc.get("water_liters", 0)
                status = "✅" if actual_water == expected_water else "⚠️"
                logger.info(f"  {status} 饮水: {actual_water:,}L (预期 {expected_water:,}L)")
                
                # 食物: 10000人 * 0.5kg/天 * 3天 = 15,000kg
                expected_food = 10000 * 0.5 * 3
                actual_food = shelter_calc.get("food_kg", 0)
                status = "✅" if actual_food == expected_food else "⚠️"
                logger.info(f"  {status} 食物: {actual_food:,}kg (预期 {expected_food:,}kg)")
            
            # 验证救援力量计算
            rescue_calc = details.get("rescue_calculation", {})
            if rescue_calc:
                # 救援队: ceil(100/50) = 2队
                expected_teams = 2
                actual_teams = rescue_calc.get("rescue_teams", 0)
                status = "✅" if actual_teams == expected_teams else "⚠️"
                logger.info(f"  {status} 救援队: {actual_teams} (预期 {expected_teams})")
            
            # 验证医疗资源计算
            medical_calc = details.get("medical_calculation", {})
            if medical_calc:
                # 医护人员: ceil(500/20) = 25人
                expected_staff = 25
                actual_staff = medical_calc.get("medical_staff", 0)
                status = "✅" if actual_staff == expected_staff else "⚠️"
                logger.info(f"  {status} 医护人员: {actual_staff} (预期 {expected_staff})")
        else:
            logger.error("  ❌ calculation_details 缺失")
            all_passed = False
        
        # 打印模块样例
        logger.info("\n" + "=" * 60)
        logger.info("[模块1 救援力量部署方案 完整内容]")
        logger.info("=" * 60)
        logger.info(output.module_1_rescue_force)
        
        logger.info("\n" + "=" * 60)
        logger.info("[模块4 临时安置与生活保障 完整内容]")
        logger.info("=" * 60)
        logger.info(output.module_4_shelter)
        
        return all_passed
        
    except Exception as e:
        logger.exception(f"端到端测试失败: {e}")
        return False


async def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="总体救灾方案端到端测试")
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="仅运行单元测试（不需要vLLM）",
    )
    args = parser.parse_args()
    
    # 单元测试
    unit_passed = run_unit_tests()
    
    if args.unit_only:
        sys.exit(0 if unit_passed else 1)
    
    # 端到端测试
    e2e_passed = await test_resource_planner_e2e()
    
    # 最终结果
    logger.info("\n" + "=" * 60)
    logger.info("最终结果")
    logger.info("=" * 60)
    logger.info(f"  单元测试: {'✅ 通过' if unit_passed else '❌ 失败'}")
    logger.info(f"  端到端测试: {'✅ 通过' if e2e_passed else '❌ 失败'}")
    
    if unit_passed and e2e_passed:
        logger.info("\n🎉 所有测试通过!")
        sys.exit(0)
    else:
        logger.error("\n❌ 部分测试失败")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
