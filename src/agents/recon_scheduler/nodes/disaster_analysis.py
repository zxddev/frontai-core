"""
Phase 1: 灾情深度理解节点

分析灾情类型、严重程度、时间敏感性，识别优先目标。
支持CrewAI增强：当有自然语言输入时使用LLM理解灾情。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..state import (
    ReconSchedulerState,
    DisasterAnalysis,
    SecondaryRisk,
    PriorityTarget,
)
from ..config import get_disaster_scenarios

logger = logging.getLogger(__name__)

# CrewAI开关
USE_CREWAI = os.getenv("RECON_USE_CREWAI", "false").lower() == "true"


async def disaster_analysis_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    灾情深度理解节点
    
    输入:
        - recon_request: 侦察需求描述
        - target_area: 目标区域
        - disaster_context: 来自EmergencyAI的灾情上下文（可选）
    
    输出:
        - disaster_analysis: 灾情分析结果
    """
    logger.info("Phase 1: 灾情深度理解")
    
    recon_request = state.get("recon_request", "")
    target_area = state.get("target_area")
    disaster_context = state.get("disaster_context", {})
    
    # 加载灾情场景配置
    scenarios_config = get_disaster_scenarios()
    
    # CrewAI增强：当启用CrewAI且有自然语言输入时，强制使用LLM分析
    crewai_analysis = None
    if USE_CREWAI and recon_request and len(recon_request) > 10:
        from ..crewai import DisasterAnalysisCrew
        crew = DisasterAnalysisCrew()
        crewai_analysis = await crew.analyze(recon_request, target_area)
        logger.info(f"[CrewAI] 灾情分析完成: type={crewai_analysis.disaster_type}, severity={crewai_analysis.severity}")
        
        # 使用CrewAI分析结果更新上下文
        disaster_context = disaster_context.copy()
        disaster_context["disaster_type"] = crewai_analysis.disaster_type
        disaster_context["severity"] = crewai_analysis.severity
        disaster_context["crewai_analysis"] = crewai_analysis.analysis_summary
    
    # 从上下文或请求中识别灾情类型
    disaster_type = _identify_disaster_type(recon_request, disaster_context, scenarios_config)
    
    # 获取场景配置
    scenario_config = scenarios_config.get("scenarios", {}).get(disaster_type, {})
    characteristics = scenario_config.get("characteristics", {})
    
    # 评估严重程度
    severity_level = _assess_severity(disaster_context, characteristics)
    
    # 计算时间相关信息
    onset_time = disaster_context.get("onset_time")
    time_since_onset = _calculate_time_since_onset(onset_time)
    golden_hour_hours = characteristics.get("golden_hour_hours", 72)
    golden_hour_remaining = max(0, golden_hour_hours - time_since_onset)
    
    # 识别次生灾害风险
    secondary_risks = _identify_secondary_risks(
        disaster_type,
        disaster_context,
        characteristics.get("secondary_risks", [])
    )
    
    # 识别优先目标
    priority_targets = _identify_priority_targets(
        target_area,
        disaster_context,
        scenario_config.get("priority_rules", [])
    )
    
    # 估算影响人口
    estimated_affected = disaster_context.get("estimated_affected_population", 0)
    estimated_trapped = disaster_context.get("estimated_trapped", 0)
    
    # 构建分析结果
    disaster_analysis: DisasterAnalysis = {
        "disaster_type": disaster_type,
        "severity_level": severity_level,
        
        # 空间特征
        "affected_area": target_area or {},
        "epicenter": disaster_context.get("epicenter"),
        "spread_direction": disaster_context.get("spread_direction"),
        
        # 时间特征
        "onset_time": onset_time,
        "time_since_onset_hours": time_since_onset,
        "golden_hour_remaining": golden_hour_remaining,
        
        # 人员估计
        "estimated_affected_population": estimated_affected,
        "estimated_trapped": estimated_trapped,
        "high_risk_zones": disaster_context.get("high_risk_zones", []),
        
        # 次生灾害风险
        "secondary_risks": secondary_risks,
        
        # 侦察优先级
        "priority_targets": priority_targets,
        
        # 特征
        "characteristics": characteristics,
    }
    
    logger.info(f"灾情分析完成: 类型={disaster_type}, 严重程度={severity_level}, "
                f"黄金救援时间剩余={golden_hour_remaining:.1f}h")
    
    return {
        "disaster_analysis": disaster_analysis,
        "current_phase": "disaster_analysis",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "disaster_analysis",
            "timestamp": datetime.now().isoformat(),
            "disaster_type": disaster_type,
            "severity_level": severity_level,
        }],
    }


def _identify_disaster_type(
    recon_request: str,
    disaster_context: Dict[str, Any],
    scenarios_config: Dict[str, Any]
) -> str:
    """识别灾情类型"""
    # 优先从上下文获取
    if disaster_context.get("disaster_type"):
        return disaster_context["disaster_type"]
    
    # 从请求文本中识别
    request_lower = recon_request.lower()
    
    type_keywords = {
        "earthquake_collapse": ["地震", "倒塌", "earthquake", "collapse", "震"],
        "flood": ["洪涝", "洪水", "淹没", "flood", "水灾"],
        "fire": ["火灾", "火情", "fire", "着火"],
        "hazmat": ["危化", "泄漏", "化学", "hazmat", "chemical"],
        "landslide": ["滑坡", "泥石流", "landslide", "山体"],
    }
    
    for dtype, keywords in type_keywords.items():
        if any(kw in request_lower for kw in keywords):
            return dtype
    
    # 默认为地震倒塌（最常见）
    return "earthquake_collapse"


def _assess_severity(
    disaster_context: Dict[str, Any],
    characteristics: Dict[str, Any]
) -> str:
    """评估严重程度"""
    # 从上下文获取
    if disaster_context.get("severity_level"):
        return disaster_context["severity_level"]
    
    # 基于指标评估
    estimated_trapped = disaster_context.get("estimated_trapped", 0)
    estimated_affected = disaster_context.get("estimated_affected_population", 0)
    
    if estimated_trapped > 100 or estimated_affected > 10000:
        return "critical"
    elif estimated_trapped > 20 or estimated_affected > 1000:
        return "severe"
    elif estimated_trapped > 5 or estimated_affected > 100:
        return "moderate"
    else:
        return "minor"


def _calculate_time_since_onset(onset_time: Optional[str]) -> float:
    """计算灾情发生以来的时间（小时）"""
    if not onset_time:
        return 0.0
    
    try:
        onset_dt = datetime.fromisoformat(onset_time.replace("Z", "+00:00"))
        now = datetime.now(onset_dt.tzinfo) if onset_dt.tzinfo else datetime.now()
        delta = now - onset_dt
        return delta.total_seconds() / 3600
    except Exception as e:
        logger.warning(f"解析灾情发生时间失败: {e}")
        return 0.0


def _identify_secondary_risks(
    disaster_type: str,
    disaster_context: Dict[str, Any],
    default_risks: List[str]
) -> List[SecondaryRisk]:
    """识别次生灾害风险"""
    risks = []
    
    # 从上下文获取
    context_risks = disaster_context.get("secondary_risks", [])
    if context_risks:
        for risk in context_risks:
            if isinstance(risk, dict):
                risks.append(risk)
            else:
                risks.append({
                    "risk_type": risk,
                    "location": None,
                    "probability": "medium",
                    "description": f"潜在{risk}风险",
                })
        return risks
    
    # 使用默认风险
    for risk_type in default_risks:
        risks.append({
            "risk_type": risk_type,
            "location": None,
            "probability": "medium",
            "description": f"潜在{risk_type}风险，需侦察确认",
        })
    
    return risks


def _identify_priority_targets(
    target_area: Optional[Dict[str, Any]],
    disaster_context: Dict[str, Any],
    priority_rules: List[Dict[str, Any]]
) -> List[PriorityTarget]:
    """识别优先目标"""
    targets = []
    
    # 从上下文获取已知目标
    known_targets = disaster_context.get("priority_targets", [])
    if known_targets:
        for i, target in enumerate(known_targets):
            if isinstance(target, dict):
                targets.append({
                    "target_id": target.get("target_id", f"target_{i+1}"),
                    "target_type": target.get("target_type", "unknown"),
                    "location": target.get("location", {}),
                    "estimated_population": target.get("estimated_population", 0),
                    "priority_score": target.get("priority_score", 50),
                    "description": target.get("description", ""),
                })
    
    # 从上下文中的建筑物/区域信息生成目标
    buildings = disaster_context.get("affected_buildings", [])
    for i, building in enumerate(buildings):
        target_type = building.get("type", "residential")
        
        # 应用优先级规则
        priority_score = 50
        for rule in priority_rules:
            if rule.get("condition") == target_type:
                priority_score += rule.get("priority_boost", 0) * 10
            elif rule.get("condition") == "reported_trapped" and building.get("reported_trapped"):
                priority_score += rule.get("priority_boost", 0) * 10
        
        targets.append({
            "target_id": f"building_{i+1}",
            "target_type": target_type,
            "location": building.get("location", {}),
            "estimated_population": building.get("population", 0),
            "priority_score": min(100, priority_score),
            "description": building.get("name", f"建筑{i+1}"),
        })
    
    # 按优先级排序
    targets.sort(key=lambda x: x["priority_score"], reverse=True)
    
    return targets
