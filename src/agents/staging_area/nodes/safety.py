"""
安全分析节点

职责：
1. 综合评估候选点安全风险
2. 分析次生灾害风险（滑坡、泥石流、堰塞湖）
3. 评估余震影响
4. 生成安全警示

遵循调用规范：LLM输出必须经过Pydantic校验
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List
from uuid import UUID

from langchain_openai import ChatOpenAI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.staging_area.state import (
    StagingAreaAgentState,
    SafetyAssessment,
)
logger = logging.getLogger(__name__)


def _fix_json_string(json_str: str) -> str:
    """修复常见的 JSON 格式问题"""
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
    json_str = json_str.replace('：', ':')
    json_str = re.sub(r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):', r'\1"\2"\3:', json_str)
    json_str = re.sub(r',\s*,', ',', json_str)
    return json_str.strip()


def _get_llm(max_tokens: int = 2048) -> ChatOpenAI:
    """获取LLM客户端"""
    import os
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


SAFETY_PROMPT = """你是地震救援安全评估专家。请根据以下候选驻扎点数据，综合评估安全风险。

## 灾情背景
{disaster_context}

## 候选点数据
{candidates_json}

## 安全评估标准
1. **次生灾害风险**：
   - 滑坡：山区、陡坡、降雨后
   - 泥石流：沟谷、暴雨诱发
   - 堰塞湖：河流上游堵塞形成，下游有溃坝风险
   - 建筑倒塌：危房、老旧建筑

2. **余震影响**：
   - 震中距离越近，余震影响越大
   - M7+地震后72小时内余震频繁

3. **撤离可行性**：
   - 是否有多条撤离路线
   - 路况是否受损

4. **距危险区距离** (distance_to_danger_m): 
   - >1000m 安全
   - 500-1000m 中等风险
   - <500m 高风险

## 输出格式（JSON数组）
[
    {{
        "site_id": "uuid",
        "site_name": "站点名称",
        "safety_level": "safe|moderate_risk|high_risk|dangerous",
        "secondary_hazard_risks": ["位于潜在堰塞湖下游", "周边有滑坡隐患点"],
        "aftershock_impact": "余震影响评估描述",
        "evacuation_feasibility": "撤离可行性评估描述",
        "safety_warnings": ["紧急警告内容"],
        "confidence": 0.85
    }}
]

请只输出JSON数组，不要其他内容。
"""


async def analyze_safety(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    安全分析节点
    
    综合评估候选点安全风险，生成安全警示。
    
    Args:
        state: Agent状态
        db: 数据库会话
        
    Returns:
        状态更新字典
    """
    start_time = time.perf_counter()
    
    # 跳过条件检查
    if state.get("skip_llm_analysis", False):
        logger.info("[安全分析] 跳过（skip_llm_analysis=True）")
        return {
            "safety_assessments": None,
            "timing": {**state.get("timing", {}), "safety_ms": 0},
        }
    
    # 获取候选点数据
    candidate_sites = state.get("candidate_sites") or state.get("ranked_sites", [])
    if not candidate_sites:
        logger.warning("[安全分析] 无候选点数据")
        return {
            "safety_assessments": None,
            "errors": state.get("errors", []) + ["安全分析：无候选点数据"],
            "timing": {**state.get("timing", {}), "safety_ms": 0},
        }
    
    try:
        # 构建灾情上下文
        disaster_context = _build_disaster_context(state)
        
        # 提取安全相关数据
        safety_data = []
        for site in candidate_sites[:10]:
            # 计算到震中的距离（用于余震影响评估）
            epicenter_dist = _calc_epicenter_distance(
                site.get("longitude"),
                site.get("latitude"),
                state.get("epicenter_lon"),
                state.get("epicenter_lat"),
            )
            
            safety_data.append({
                "site_id": site.get("site_id") or str(site.get("id", "")),
                "name": site.get("name", "未知"),
                "distance_to_danger_m": site.get("distance_to_danger_m"),
                "distance_to_epicenter_km": round(epicenter_dist / 1000, 1) if epicenter_dist else None,
                "site_type": site.get("site_type", "unknown"),
                "slope_degree": site.get("slope_degree"),
                "longitude": site.get("longitude"),
                "latitude": site.get("latitude"),
            })
        
        candidates_json = json.dumps(safety_data, ensure_ascii=False, indent=2)
        
        prompt = SAFETY_PROMPT.format(
            disaster_context=disaster_context,
            candidates_json=candidates_json,
        )
        
        # 调用LLM
        llm = _get_llm()
        response = await llm.ainvoke(prompt)
        raw_output = response.content if hasattr(response, "content") else str(response)
        
        # 解析JSON
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_output.strip()
        
        # 修复常见的 JSON 格式问题
        json_str = _fix_json_string(json_str)
        parsed_data = json.loads(json_str)
        
        # 校验每个评估结果
        safety_assessments: List[SafetyAssessment] = []
        for item in parsed_data:
            try:
                item["site_id"] = UUID(item["site_id"])
                assessment = SafetyAssessment.model_validate(item)
                safety_assessments.append(assessment)
            except (ValidationError, ValueError) as e:
                logger.warning(f"[安全分析] 单条评估校验失败: {e}")
                continue
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        # 统计高风险数量
        high_risk_count = sum(
            1 for sa in safety_assessments 
            if sa.safety_level in ("high_risk", "dangerous")
        )
        
        logger.info(
            f"[安全分析] 完成: {len(safety_assessments)} 个评估, "
            f"高风险 {high_risk_count} 个, 耗时 {elapsed_ms}ms"
        )
        
        return {
            "safety_assessments": safety_assessments,
            "timing": {**state.get("timing", {}), "safety_ms": elapsed_ms},
        }
        
    except json.JSONDecodeError as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.warning(f"[安全分析] JSON解析失败: {e}")
        return {
            "safety_assessments": None,
            "errors": state.get("errors", []) + [f"安全分析JSON解析失败: {str(e)}"],
            "timing": {**state.get("timing", {}), "safety_ms": elapsed_ms},
        }
        
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"[安全分析] 异常: {e}", exc_info=True)
        return {
            "safety_assessments": None,
            "errors": state.get("errors", []) + [f"安全分析异常: {str(e)}"],
            "timing": {**state.get("timing", {}), "safety_ms": elapsed_ms},
        }


def _build_disaster_context(state: StagingAreaAgentState) -> str:
    """构建灾情上下文"""
    parts = []
    
    if state.get("disaster_description"):
        parts.append(f"灾情描述: {state['disaster_description']}")
    
    magnitude = state.get("magnitude")
    if magnitude:
        parts.append(f"震级: {magnitude}")
        # 添加余震风险提示
        if magnitude >= 7.0:
            parts.append("⚠️ M7+地震，72小时内余震风险高")
        elif magnitude >= 6.0:
            parts.append("⚠️ M6+地震，48小时内余震风险较高")
    
    if state.get("epicenter_lon") and state.get("epicenter_lat"):
        parts.append(f"震中: ({state['epicenter_lon']:.4f}, {state['epicenter_lat']:.4f})")
    
    parsed = state.get("parsed_disaster")
    if parsed:
        if hasattr(parsed, "key_concerns") and parsed.key_concerns:
            parts.append(f"关切点: {', '.join(parsed.key_concerns)}")
        # 识别安全相关约束
        if hasattr(parsed, "extracted_constraints") and parsed.extracted_constraints:
            safety_keywords = ["landslide", "flood", "dam", "collapse", "fire", "blocked"]
            safety_constraints = [
                c.description for c in parsed.extracted_constraints 
                if hasattr(c, "constraint_type") and any(kw in c.constraint_type.lower() for kw in safety_keywords)
            ]
            if safety_constraints:
                parts.append(f"安全约束: {', '.join(safety_constraints)}")
    
    return "\n".join(parts) if parts else "无详细灾情信息"


def _calc_epicenter_distance(
    lon1: float | None,
    lat1: float | None,
    lon2: float | None,
    lat2: float | None,
) -> float | None:
    """计算到震中的距离（米）- Haversine公式"""
    import math
    
    if None in (lon1, lat1, lon2, lat2):
        return None
    
    EARTH_RADIUS_M = 6371000
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_M * c
