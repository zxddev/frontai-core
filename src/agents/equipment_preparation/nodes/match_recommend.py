"""
匹配推荐节点

根据需求规格和仓库库存，匹配设备并生成推荐清单。
核心功能：
1. 使用 SupplyDemandCalculator 计算物资需求量
2. 为每个推荐项生成AI选择理由
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.database import AsyncSessionLocal
from src.domains.resource_scheduling.sphere_demand_calculator import SphereDemandCalculator
from src.infra.config.algorithm_config_service import AlgorithmConfigService
from src.domains.disaster import (
    ResponsePhase, 
    ClimateType, 
    CasualtyEstimator,
    DisasterType,
)
from src.domains.disaster.casualty_estimator import CasualtyEstimate
from ..state import (
    EquipmentPreparationState, 
    DeviceRecommendation, 
    SupplyRecommendation,
)

logger = logging.getLogger(__name__)


def _get_llm(max_tokens: int = 2048) -> ChatOpenAI:
    """获取LLM客户端实例"""
    llm_model = os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    openai_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    request_timeout = int(os.environ.get('REQUEST_TIMEOUT', '120'))
    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        timeout=request_timeout,
        max_tokens=max_tokens,
        max_retries=0,
    )


# 设备选择理由生成Prompt
DEVICE_REASON_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an emergency rescue equipment expert. Generate a concise reason (in Chinese) 
explaining why this device is recommended for the disaster scenario.

Consider:
1. Device capabilities vs disaster requirements
2. Environmental suitability
3. Operational advantages

Keep the reason under 50 Chinese characters."""),
    ("human", """Disaster: {disaster_type}, severity: {severity}
Disaster features: {disaster_features}
Device: {device_name} ({device_type})
Device capabilities: {device_capabilities}

Generate the selection reason in Chinese:"""),
])

# 物资选择理由生成Prompt
SUPPLY_REASON_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an emergency rescue supply expert. Generate a concise reason (in Chinese) 
explaining why this supply is recommended and the quantity calculation basis.

Keep the reason under 50 Chinese characters."""),
    ("human", """Disaster: {disaster_type}
Estimated trapped: {estimated_trapped}
Estimated personnel: {estimated_personnel}
Supply: {supply_name} ({category})
Quantity: {quantity} {unit}

Generate the selection reason in Chinese:"""),
])


async def match_and_recommend(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    匹配推荐节点
    
    1. 匹配设备与灾情需求
    2. 配置设备模块
    3. 计算物资数量
    4. 生成每项的选择理由
    """
    logger.info("执行匹配推荐节点", extra={"event_id": state.get("event_id")})
    
    requirement_spec = state.get("requirement_spec")
    warehouse_inventory = state.get("warehouse_inventory")
    parsed_disaster = state.get("parsed_disaster", {})
    
    if not requirement_spec or not warehouse_inventory:
        logger.warning("缺少需求规格或仓库库存")
        return {
            "recommended_devices": [],
            "recommended_supplies": [],
        }
    
    # 匹配设备
    recommended_devices = await _match_devices(
        devices=warehouse_inventory.get("devices", []),
        modules=warehouse_inventory.get("modules", []),
        requirement_spec=requirement_spec,
        parsed_disaster=parsed_disaster,
    )
    
    # 匹配物资
    recommended_supplies = await _match_supplies(
        supplies=warehouse_inventory.get("supplies", []),
        requirement_spec=requirement_spec,
        parsed_disaster=parsed_disaster,
    )
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_and_recommend"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + len(recommended_devices) + len(recommended_supplies)
    
    logger.info(
        "匹配推荐完成",
        extra={
            "devices_recommended": len(recommended_devices),
            "supplies_recommended": len(recommended_supplies),
        }
    )
    
    return {
        "recommended_devices": recommended_devices,
        "recommended_supplies": recommended_supplies,
        "current_phase": "match_recommend",
        "trace": trace,
    }


async def _match_devices(
    devices: List[Dict[str, Any]],
    modules: List[Dict[str, Any]],
    requirement_spec: Dict[str, Any],
    parsed_disaster: Dict[str, Any],
) -> List[DeviceRecommendation]:
    """匹配设备并生成推荐"""
    required_capabilities = requirement_spec.get("required_capabilities", [])
    required_device_types = requirement_spec.get("required_device_types", [])
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    
    recommendations: List[DeviceRecommendation] = []
    
    for device in devices:
        device_type = device.get("device_type")
        
        # 检查设备类型是否匹配
        if required_device_types and device_type not in required_device_types:
            continue
        
        # 检查灾害适用性
        applicable = device.get("applicable_disasters", [])
        if applicable and disaster_type not in applicable:
            continue
        
        # 匹配模块
        matched_modules = _match_modules_for_device(
            device=device,
            modules=modules,
            required_capabilities=required_capabilities,
        )
        
        # 确定优先级
        priority = _determine_device_priority(device, parsed_disaster)
        
        # 生成选择理由
        reason = await _generate_device_reason(
            device=device,
            matched_modules=matched_modules,
            parsed_disaster=parsed_disaster,
        )
        
        recommendation: DeviceRecommendation = {
            "device_id": device["id"],
            "device_name": device["name"],
            "device_type": device_type,
            "modules": matched_modules,
            "reason": reason,
            "priority": priority,
        }
        recommendations.append(recommendation)
    
    # 按优先级排序
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))
    
    return recommendations


def _match_modules_for_device(
    device: Dict[str, Any],
    modules: List[Dict[str, Any]],
    required_capabilities: List[str],
) -> List[Dict[str, Any]]:
    """为设备匹配模块"""
    device_type = device.get("device_type")
    module_slots = device.get("module_slots", 0)
    base_capabilities = device.get("base_capabilities", [])
    
    # 找出设备缺少但需要的能力
    missing_capabilities = [
        cap for cap in required_capabilities 
        if cap not in base_capabilities
    ]
    
    matched_modules = []
    slots_used = 0
    
    for module in modules:
        if slots_used >= module_slots:
            break
        
        # 检查模块是否兼容该设备
        compatible_devices = module.get("compatible_devices", [])
        if device_type not in compatible_devices:
            continue
        
        # 检查模块是否提供所需能力
        module_capabilities = module.get("capabilities", [])
        provides_needed = any(
            cap in missing_capabilities 
            for cap in module_capabilities
        )
        
        if provides_needed:
            matched_modules.append({
                "module_id": module["id"],
                "module_name": module["name"],
                "reason": f"提供{', '.join(module_capabilities)}能力",
            })
            slots_used += 1
            # 更新缺少的能力
            for cap in module_capabilities:
                if cap in missing_capabilities:
                    missing_capabilities.remove(cap)
    
    return matched_modules


def _determine_device_priority(
    device: Dict[str, Any],
    parsed_disaster: Dict[str, Any],
) -> str:
    """确定设备优先级"""
    device_type = device.get("device_type")
    severity = parsed_disaster.get("severity", "medium")
    has_trapped = parsed_disaster.get("has_trapped_persons", False)
    has_collapse = parsed_disaster.get("has_building_collapse", False)
    
    # 严重灾情 + 被困人员 = 关键优先
    if severity in ["critical", "high"] and has_trapped:
        if device_type in ["drone", "dog"]:  # 搜救设备
            return "critical"
    
    # 建筑倒塌 + 机器狗 = 高优先（狭小空间搜索）
    if has_collapse and device_type == "dog":
        return "high"
    
    # 无人机通常是高优先（快速侦察）
    if device_type == "drone":
        return "high"
    
    return "medium"


async def _generate_device_reason(
    device: Dict[str, Any],
    matched_modules: List[Dict[str, Any]],
    parsed_disaster: Dict[str, Any],
) -> str:
    """生成设备选择理由"""
    try:
        llm = _get_llm()
        
        # 构建灾情特征描述
        disaster_features = []
        if parsed_disaster.get("has_building_collapse"):
            disaster_features.append("建筑倒塌")
        if parsed_disaster.get("has_trapped_persons"):
            disaster_features.append(f"被困人员约{parsed_disaster.get('estimated_trapped', 0)}人")
        if parsed_disaster.get("has_secondary_fire"):
            disaster_features.append("次生火灾")
        if parsed_disaster.get("has_hazmat_leak"):
            disaster_features.append("危化品泄漏")
        
        chain = DEVICE_REASON_PROMPT | llm
        response = await chain.ainvoke({
            "disaster_type": parsed_disaster.get("disaster_type", "unknown"),
            "severity": parsed_disaster.get("severity", "medium"),
            "disaster_features": "、".join(disaster_features) if disaster_features else "无特殊情况",
            "device_name": device.get("name"),
            "device_type": device.get("device_type"),
            "device_capabilities": ", ".join(device.get("base_capabilities", [])),
        })
        
        return response.content.strip()
    except Exception as e:
        logger.warning(f"生成设备理由失败: {e}")
        # 返回默认理由
        return f"{device.get('name')}适用于{parsed_disaster.get('disaster_type', '此类')}灾害救援"


def _map_severity_to_score(severity: str) -> float:
    """将severity字符串映射为0-1的评分"""
    mapping = {
        "critical": 0.9,
        "high": 0.7,
        "medium": 0.5,
        "low": 0.3,
    }
    return mapping.get(severity, 0.5)


async def _match_supplies(
    supplies: List[Dict[str, Any]],
    requirement_spec: Dict[str, Any],
    parsed_disaster: Dict[str, Any],
) -> List[SupplyRecommendation]:
    """
    匹配物资并生成推荐
    
    使用 SphereDemandCalculator + CasualtyEstimator 计算需求量。
    """
    estimated_personnel = requirement_spec.get("estimated_personnel", 1)
    estimated_trapped = parsed_disaster.get("estimated_trapped", 0)
    affected_population = parsed_disaster.get("affected_population", 0)
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    severity = parsed_disaster.get("severity", "medium")
    
    # 如果没有受影响人口数据，基于被困人数估算
    if affected_population == 0 and estimated_trapped > 0:
        affected_population = estimated_trapped * 5
    
    # 使用 SphereDemandCalculator 计算需求量
    demand_requirements: Dict[str, Dict[str, Any]] = {}
    
    if affected_population > 0:
        try:
            # 构造伤亡估算（使用通用模型）
            estimator = CasualtyEstimator()
            try:
                dt = DisasterType(disaster_type)
            except ValueError:
                dt = DisasterType.EARTHQUAKE
            
            casualty = estimator.estimate_generic(
                disaster_type=dt,
                severity=_map_severity_to_score(severity),
                population=affected_population,
            )
            # 如果有明确的被困人数，覆盖估算值
            if estimated_trapped > 0:
                casualty = CasualtyEstimate(
                    fatalities=casualty.fatalities,
                    severe_injuries=casualty.severe_injuries,
                    minor_injuries=casualty.minor_injuries,
                    trapped=estimated_trapped,
                    displaced=casualty.displaced,
                    affected=affected_population,
                    confidence=casualty.confidence,
                    methodology=casualty.methodology,
                )
            
            async with AsyncSessionLocal() as session:
                config_service = AlgorithmConfigService(session)
                calculator = SphereDemandCalculator(session, config_service)
                demand_result = await calculator.calculate(
                    phase=ResponsePhase.IMMEDIATE,
                    casualty_estimate=casualty,
                    duration_days=3,
                    climate=ClimateType.TEMPERATE,
                )
                
                for req in demand_result.requirements:
                    demand_requirements[req.supply_code] = {
                        "quantity": int(req.quantity),
                        "unit": req.unit,
                        "priority": req.priority,
                    }
                
                logger.info(
                    f"[物资推荐] SphereDemandCalculator计算完成: "
                    f"{len(demand_requirements)}种物资需求"
                )
        except Exception as e:
            logger.warning(f"[物资推荐] 需求计算失败，使用备用逻辑: {e}")
    
    recommendations: List[SupplyRecommendation] = []
    
    for supply in supplies:
        supply_code = supply.get("code", "")
        category = supply.get("category")
        
        # 优先使用计算器的需求量
        if supply_code in demand_requirements:
            demand = demand_requirements[supply_code]
            quantity = demand["quantity"]
            priority = demand["priority"]
        else:
            # 备用计算逻辑
            quantity = _calculate_supply_quantity_fallback(
                supply=supply,
                estimated_trapped=estimated_trapped,
                estimated_personnel=estimated_personnel,
            )
            # 确定优先级
            required_for = supply.get("required_for_disasters", [])
            if disaster_type in required_for:
                priority = "critical"
            elif category == "medical":
                priority = "high"
            else:
                priority = "medium"
        
        if quantity <= 0:
            continue
        
        # 检查库存是否足够
        stock_quantity = supply.get("stock_quantity", 0)
        actual_quantity = min(quantity, stock_quantity) if stock_quantity > 0 else quantity
        
        # 生成选择理由
        reason = await _generate_supply_reason(
            supply=supply,
            quantity=actual_quantity,
            parsed_disaster=parsed_disaster,
            estimated_personnel=estimated_personnel,
        )
        
        recommendation: SupplyRecommendation = {
            "supply_id": supply["id"],
            "supply_code": supply_code,
            "supply_name": supply["name"],
            "quantity": actual_quantity,
            "required_quantity": quantity,
            "unit": supply.get("unit", "piece"),
            "reason": reason,
            "priority": priority,
            "stock_available": stock_quantity,
            "is_shortage": stock_quantity < quantity if stock_quantity > 0 else False,
        }
        recommendations.append(recommendation)
    
    # 按优先级排序
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))
    
    return recommendations


def _calculate_supply_quantity_fallback(
    supply: Dict[str, Any],
    estimated_trapped: int,
    estimated_personnel: int,
) -> int:
    """
    计算物资推荐数量（备用逻辑）
    
    当 SupplyDemandCalculator 不可用时使用。
    """
    category = supply.get("category", "")
    per_person_per_day = supply.get("per_person_per_day", 1.0)
    
    # 优先使用物资自带的 per_person_per_day 参数
    if per_person_per_day and per_person_per_day > 0:
        base_people = max(estimated_trapped, estimated_personnel * 5)
        return int(base_people * per_person_per_day * 3)  # 3天
    
    # 根据类别和人数计算
    if category == "medical":
        return max(estimated_trapped, estimated_personnel * 5)
    elif category == "protection":
        return estimated_personnel * 2
    elif category == "rescue":
        return max(1, estimated_personnel // 3)
    elif category == "life":
        return max(estimated_trapped, 10)
    else:
        return max(1, estimated_personnel)


async def _generate_supply_reason(
    supply: Dict[str, Any],
    quantity: int,
    parsed_disaster: Dict[str, Any],
    estimated_personnel: int,
) -> str:
    """生成物资选择理由"""
    try:
        llm = _get_llm()
        
        chain = SUPPLY_REASON_PROMPT | llm
        response = await chain.ainvoke({
            "disaster_type": parsed_disaster.get("disaster_type", "unknown"),
            "estimated_trapped": parsed_disaster.get("estimated_trapped", 0),
            "estimated_personnel": estimated_personnel,
            "supply_name": supply.get("name"),
            "category": supply.get("category"),
            "quantity": quantity,
            "unit": supply.get("unit", "piece"),
        })
        
        return response.content.strip()
    except Exception as e:
        logger.warning(f"生成物资理由失败: {e}")
        return f"根据灾情需求配置{quantity}{supply.get('unit', '件')}"
