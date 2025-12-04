"""
Phase 8: 风险评估节点

识别风险、制定应急预案、生成检查清单。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..state import (
    ReconSchedulerState,
    RiskAssessment,
    Risk,
    ContingencyPlan,
)
from ..config import get_contingency_plans

logger = logging.getLogger(__name__)


async def risk_assessment_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    风险评估节点
    
    输入:
        - disaster_analysis: 灾情分析
        - environment_assessment: 环境评估
        - flight_plans: 航线计划
        - timeline_scheduling: 时间线编排
    
    输出:
        - risk_assessment: 风险评估结果
        - contingency_plans: 应急预案
        - overall_risk_level: 总体风险等级
    """
    logger.info("Phase 8: 风险评估")
    
    disaster_analysis = state.get("disaster_analysis", {})
    environment = state.get("environment_assessment", {})
    flight_plans = state.get("flight_plans", [])
    timeline = state.get("timeline_scheduling", {})
    
    weather = environment.get("weather", {})
    flight_condition = state.get("flight_condition", "green")
    
    # 加载应急预案配置
    contingency_config = get_contingency_plans()
    
    # 识别风险
    identified_risks = []
    
    # 1. 天气风险
    weather_risk = _assess_weather_risk(weather, flight_condition)
    if weather_risk:
        identified_risks.append(weather_risk)
    
    # 2. 设备风险
    equipment_risks = _assess_equipment_risks(flight_plans)
    identified_risks.extend(equipment_risks)
    
    # 3. 次生灾害风险
    secondary_risks = disaster_analysis.get("secondary_risks", [])
    for sr in secondary_risks:
        identified_risks.append({
            "risk_id": f"risk_secondary_{sr.get('risk_type', 'unknown')}",
            "risk_type": "secondary_disaster",
            "description": sr.get("description", f"次生灾害风险: {sr.get('risk_type')}"),
            "probability": sr.get("probability", "medium"),
            "impact": "high",
            "risk_score": _calculate_risk_score(sr.get("probability", "medium"), "high"),
            "mitigation": "持续监测，发现异常立即上报",
            "monitoring_indicators": [f"{sr.get('risk_type')}迹象", "异常气体", "温度变化"],
        })
    
    # 4. 通信风险
    signal_coverage = environment.get("signal_coverage", {})
    if signal_coverage.get("coverage_percent", 100) < 80:
        identified_risks.append({
            "risk_id": "risk_communication",
            "risk_type": "communication",
            "description": f"部分区域信号覆盖不足（{signal_coverage.get('coverage_percent', 0)}%）",
            "probability": "high",
            "impact": "medium",
            "risk_score": _calculate_risk_score("high", "medium"),
            "mitigation": "使用通信中继设备，规划信号覆盖路径",
            "monitoring_indicators": ["信号强度", "图传质量", "遥控响应"],
        })
    
    # 5. 时间风险
    total_duration = timeline.get("total_duration_min", 0)
    golden_hour = disaster_analysis.get("golden_hour_remaining", 72)
    if total_duration > golden_hour * 60:
        identified_risks.append({
            "risk_id": "risk_time",
            "risk_type": "time",
            "description": f"任务时长({total_duration}min)可能超过黄金救援时间",
            "probability": "medium",
            "impact": "high",
            "risk_score": _calculate_risk_score("medium", "high"),
            "mitigation": "优先执行关键任务，并行执行以缩短时间",
            "monitoring_indicators": ["任务进度", "剩余时间"],
        })
    
    # 计算总体风险等级
    overall_risk_level = _calculate_overall_risk(identified_risks)
    
    # 生成应急预案
    contingency_plans = _generate_contingency_plans(
        identified_risks, contingency_config
    )
    
    # 生成检查清单
    pre_flight_checklist = _generate_checklist(flight_plans, weather)
    
    # 构建结果
    risk_assessment: RiskAssessment = {
        "identified_risks": identified_risks,
        "overall_risk_level": overall_risk_level,
        "contingency_plans": contingency_plans,
        "pre_flight_checklist": pre_flight_checklist,
    }
    
    logger.info(f"风险评估完成: 识别{len(identified_risks)}个风险, "
                f"总体风险={overall_risk_level}, 预案数={len(contingency_plans)}")
    
    return {
        "risk_assessment": risk_assessment,
        "contingency_plans": contingency_plans,
        "overall_risk_level": overall_risk_level,
        "current_phase": "risk_assessment",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "risk_assessment",
            "timestamp": datetime.now().isoformat(),
            "risks_count": len(identified_risks),
            "overall_risk": overall_risk_level,
        }],
    }


def _assess_weather_risk(weather: Dict[str, Any], flight_condition: str) -> Optional[Risk]:
    """评估天气风险"""
    if flight_condition == "green":
        return None
    
    risk_map = {
        "yellow": ("medium", "medium", "天气条件谨慎，部分设备受限"),
        "red": ("high", "high", "天气条件危险，大部分设备禁飞"),
        "black": ("critical", "critical", "天气条件禁飞"),
    }
    
    if flight_condition in risk_map:
        prob, impact, desc = risk_map[flight_condition]
        return {
            "risk_id": "risk_weather",
            "risk_type": "weather",
            "description": desc,
            "probability": prob,
            "impact": impact,
            "risk_score": _calculate_risk_score(prob, impact),
            "mitigation": "持续监测天气变化，准备随时召回设备",
            "monitoring_indicators": ["风速", "能见度", "降雨量"],
        }
    
    return None


def _assess_equipment_risks(flight_plans: List[Dict]) -> List[Risk]:
    """评估设备风险"""
    risks = []
    
    # 检查电池消耗
    high_consumption_devices = []
    for fp in flight_plans:
        stats = fp.get("statistics", {})
        battery = stats.get("battery_consumption_percent", 0)
        if battery > 70:
            high_consumption_devices.append(fp.get("device_name", "未知设备"))
    
    if high_consumption_devices:
        risks.append({
            "risk_id": "risk_battery",
            "risk_type": "equipment",
            "description": f"设备电池消耗较高: {', '.join(high_consumption_devices)}",
            "probability": "medium",
            "impact": "medium",
            "risk_score": _calculate_risk_score("medium", "medium"),
            "mitigation": "准备备用电池，监控电量，设置返航阈值",
            "monitoring_indicators": ["电池电量", "电压", "温度"],
        })
    
    # 检查航线长度
    long_flights = []
    for fp in flight_plans:
        stats = fp.get("statistics", {})
        duration = stats.get("total_duration_min", 0)
        if duration > 40:
            long_flights.append(fp.get("device_name", "未知设备"))
    
    if long_flights:
        risks.append({
            "risk_id": "risk_long_flight",
            "risk_type": "equipment",
            "description": f"任务时间较长可能导致设备疲劳: {', '.join(long_flights)}",
            "probability": "low",
            "impact": "medium",
            "risk_score": _calculate_risk_score("low", "medium"),
            "mitigation": "分段执行任务，中途检查设备状态",
            "monitoring_indicators": ["电机温度", "GPS精度", "图传稳定性"],
        })
    
    return risks


def _calculate_risk_score(probability: str, impact: str) -> int:
    """计算风险分数"""
    prob_scores = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    impact_scores = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    
    return prob_scores.get(probability, 2) * impact_scores.get(impact, 2)


def _calculate_overall_risk(risks: List[Risk]) -> str:
    """计算总体风险等级"""
    if not risks:
        return "low"
    
    max_score = max(r.get("risk_score", 0) for r in risks)
    
    if max_score >= 12:
        return "critical"
    elif max_score >= 6:
        return "high"
    elif max_score >= 3:
        return "medium"
    else:
        return "low"


def _generate_contingency_plans(
    risks: List[Risk],
    config: Dict[str, Any]
) -> List[ContingencyPlan]:
    """生成应急预案"""
    plans = []
    plan_configs = config.get("plans", {})
    
    # 总是包含基本预案
    essential_plans = ["device_failure", "weather_deteriorate", "victim_found", "communication_loss", "low_battery"]
    
    for plan_id in essential_plans:
        plan_config = plan_configs.get(plan_id, {})
        if plan_config:
            plans.append({
                "plan_id": plan_id,
                "trigger_condition": plan_config.get("trigger_conditions", ["未知触发条件"])[0] if plan_config.get("trigger_conditions") else "未知",
                "immediate_actions": plan_config.get("immediate_actions", []),
                "follow_up_actions": plan_config.get("follow_up_actions", []),
                "resource_reallocation": plan_config.get("resource_reallocation"),
                "notification_chain": plan_config.get("notification_chain", []),
            })
    
    # 根据识别的风险添加特定预案
    for risk in risks:
        risk_type = risk.get("risk_type", "")
        
        if risk_type == "secondary_disaster":
            plan_config = plan_configs.get("secondary_hazard", {})
            if plan_config and "secondary_hazard" not in [p["plan_id"] for p in plans]:
                plans.append({
                    "plan_id": "secondary_hazard",
                    "trigger_condition": risk.get("description", "发现次生灾害"),
                    "immediate_actions": plan_config.get("immediate_actions", []),
                    "follow_up_actions": plan_config.get("follow_up_actions", []),
                    "resource_reallocation": None,
                    "notification_chain": plan_config.get("notification_chain", []),
                })
    
    return plans


def _generate_checklist(
    flight_plans: List[Dict],
    weather: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """生成飞行前检查清单"""
    checklist = []
    
    # 通用检查项
    general_checks = [
        ("check_weather", "设备", "确认天气条件适合飞行", True),
        ("check_airspace", "空域", "确认空域无冲突", True),
        ("check_battery", "设备", "检查所有电池电量充足", True),
        ("check_communication", "通信", "测试通信链路正常", True),
        ("check_gps", "设备", "确认GPS信号良好", True),
        ("check_sensors", "设备", "检查相机/传感器正常", True),
        ("check_propellers", "设备", "检查桨叶无损伤", True),
        ("check_firmware", "设备", "确认固件版本正确", False),
    ]
    
    for check_id, category, desc, is_critical in general_checks:
        checklist.append({
            "item_id": check_id,
            "category": category,
            "description": desc,
            "is_critical": is_critical,
            "checked": False,
        })
    
    # 根据天气添加特定检查项
    rain_level = weather.get("rain_level", "none")
    if rain_level != "none":
        checklist.append({
            "item_id": "check_waterproof",
            "category": "设备",
            "description": "确认设备防水等级满足要求",
            "is_critical": True,
            "checked": False,
        })
    
    wind_speed = weather.get("wind_speed_ms", 0)
    if wind_speed > 8:
        checklist.append({
            "item_id": "check_wind_resistance",
            "category": "设备",
            "description": "确认设备抗风能力满足要求",
            "is_critical": True,
            "checked": False,
        })
    
    return checklist


from typing import Optional
