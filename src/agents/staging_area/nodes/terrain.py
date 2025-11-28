"""
地形分析节点

职责：
1. 评估候选点地形适宜性
2. 分析坡度、稳定性、展开空间
3. 识别地形风险

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
    TerrainAssessment,
)
logger = logging.getLogger(__name__)


def _fix_json_string(json_str: str) -> str:
    """修复常见的 JSON 格式问题"""
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
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


TERRAIN_PROMPT = """你是地震救援地形分析专家。请根据以下候选驻扎点数据，评估地形适宜性。

## 灾情背景
{disaster_context}

## 候选点数据
{candidates_json}

## 评估标准
- **坡度** (slope_degree): 理想值<10°，>15°不适宜重型设备展开
- **面积** (area_m2): 最小2000m²才能容纳基础营地，5000m²以上为优秀
- **地质稳定性** (ground_stability): excellent/good/moderate/poor/unknown
- **考虑灾后地形变化风险**（滑坡、地陷）

## 输出格式（JSON数组）
[
    {{
        "site_id": "uuid",
        "site_name": "站点名称",
        "terrain_suitability": "excellent|good|fair|poor",
        "slope_assessment": "坡度评估描述",
        "stability_assessment": "稳定性评估描述",
        "expansion_space": "展开空间评估描述",
        "terrain_risks": ["风险1", "风险2"],
        "confidence": 0.85
    }}
]

请只输出JSON数组，不要其他内容。
"""


async def analyze_terrain(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    地形分析节点
    
    评估候选点地形适宜性，包括坡度、稳定性、展开空间。
    
    Args:
        state: Agent状态
        db: 数据库会话
        
    Returns:
        状态更新字典
    """
    start_time = time.perf_counter()
    
    # 跳过条件检查
    if state.get("skip_llm_analysis", False):
        logger.info("[地形分析] 跳过（skip_llm_analysis=True）")
        return {
            "terrain_assessments": None,
            "timing": {**state.get("timing", {}), "terrain_ms": 0},
        }
    
    # 获取候选点数据
    candidate_sites = state.get("candidate_sites") or state.get("ranked_sites", [])
    if not candidate_sites:
        logger.warning("[地形分析] 无候选点数据")
        return {
            "terrain_assessments": None,
            "errors": state.get("errors", []) + ["地形分析：无候选点数据"],
            "timing": {**state.get("timing", {}), "terrain_ms": 0},
        }
    
    try:
        # 构建灾情上下文
        disaster_context = _build_disaster_context(state)
        
        # 提取地形相关数据
        terrain_data = []
        for site in candidate_sites[:10]:  # 最多分析前10个
            terrain_data.append({
                "site_id": site.get("site_id") or str(site.get("id", "")),
                "name": site.get("name", "未知"),
                "slope_degree": site.get("slope_degree"),
                "area_m2": site.get("area_m2"),
                "ground_stability": site.get("ground_stability", "unknown"),
                "site_type": site.get("site_type", "unknown"),
            })
        
        candidates_json = json.dumps(terrain_data, ensure_ascii=False, indent=2)
        
        prompt = TERRAIN_PROMPT.format(
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
        
        json_str = _fix_json_string(json_str)
        parsed_data = json.loads(json_str)
        
        # 校验每个评估结果
        terrain_assessments: List[TerrainAssessment] = []
        for item in parsed_data:
            try:
                # 转换 site_id 为 UUID
                item["site_id"] = UUID(item["site_id"])
                assessment = TerrainAssessment.model_validate(item)
                terrain_assessments.append(assessment)
            except (ValidationError, ValueError) as e:
                logger.warning(f"[地形分析] 单条评估校验失败: {e}")
                continue
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"[地形分析] 完成: {len(terrain_assessments)} 个评估, 耗时 {elapsed_ms}ms")
        
        return {
            "terrain_assessments": terrain_assessments,
            "timing": {**state.get("timing", {}), "terrain_ms": elapsed_ms},
        }
        
    except json.JSONDecodeError as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.warning(f"[地形分析] JSON解析失败: {e}")
        return {
            "terrain_assessments": None,
            "errors": state.get("errors", []) + [f"地形分析JSON解析失败: {str(e)}"],
            "timing": {**state.get("timing", {}), "terrain_ms": elapsed_ms},
        }
        
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"[地形分析] 异常: {e}", exc_info=True)
        return {
            "terrain_assessments": None,
            "errors": state.get("errors", []) + [f"地形分析异常: {str(e)}"],
            "timing": {**state.get("timing", {}), "terrain_ms": elapsed_ms},
        }


def _build_disaster_context(state: StagingAreaAgentState) -> str:
    """构建灾情上下文"""
    parts = []
    
    if state.get("disaster_description"):
        parts.append(f"灾情描述: {state['disaster_description']}")
    
    if state.get("magnitude"):
        parts.append(f"震级: {state['magnitude']}")
    
    if state.get("epicenter_lon") and state.get("epicenter_lat"):
        parts.append(f"震中: ({state['epicenter_lon']:.4f}, {state['epicenter_lat']:.4f})")
    
    parsed = state.get("parsed_disaster")
    if parsed:
        if hasattr(parsed, "key_concerns") and parsed.key_concerns:
            parts.append(f"关切点: {', '.join(parsed.key_concerns)}")
        if hasattr(parsed, "extracted_constraints") and parsed.extracted_constraints:
            constraints = [c.description for c in parsed.extracted_constraints if hasattr(c, "description")]
            if constraints:
                parts.append(f"约束: {', '.join(constraints)}")
    
    return "\n".join(parts) if parts else "无详细灾情信息"
