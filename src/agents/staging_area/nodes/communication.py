"""
通信分析节点

职责：
1. 评估候选点通信可行性
2. 分析网络覆盖质量
3. 提供通信冗余方案建议

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
    CommunicationAssessment,
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


COMMUNICATION_PROMPT = """你是地震救援通信保障专家。请根据以下候选驻扎点数据，评估通信可行性。

## 灾情背景
{disaster_context}

## 候选点数据
{candidates_json}

## 评估标准
- **网络类型** (primary_network_type): 5g/4g_lte/3g/satellite/shortwave/mesh/none
- **信号质量** (signal_quality): excellent/good/fair/poor
- **震后通信基础设施损毁风险**
- **卫星通信可用性**（山区可能有遮挡）

## 通信保障考虑
1. 主用通信：4G/5G移动网络
2. 备用通信：卫星电话、短波电台、应急通信车
3. 指挥通信：北斗卫星终端

## 输出格式（JSON数组）
[
    {{
        "site_id": "uuid",
        "site_name": "站点名称",
        "primary_network_quality": "excellent|good|fair|poor|none",
        "backup_options": ["卫星电话", "应急通信车"],
        "communication_risks": ["基站可能因余震损坏", "山谷地形影响信号"],
        "recommended_equipment": ["北斗卫星终端", "短波电台"],
        "confidence": 0.80
    }}
]

请只输出JSON数组，不要其他内容。
"""


async def analyze_communication(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    通信分析节点
    
    评估候选点通信可行性，提供通信冗余方案。
    
    Args:
        state: Agent状态
        db: 数据库会话
        
    Returns:
        状态更新字典
    """
    start_time = time.perf_counter()
    
    # 跳过条件检查
    if state.get("skip_llm_analysis", False):
        logger.info("[通信分析] 跳过（skip_llm_analysis=True）")
        return {
            "communication_assessments": None,
            "timing": {**state.get("timing", {}), "communication_ms": 0},
        }
    
    # 获取候选点数据
    candidate_sites = state.get("candidate_sites") or state.get("ranked_sites", [])
    if not candidate_sites:
        logger.warning("[通信分析] 无候选点数据")
        return {
            "communication_assessments": None,
            "errors": state.get("errors", []) + ["通信分析：无候选点数据"],
            "timing": {**state.get("timing", {}), "communication_ms": 0},
        }
    
    try:
        # 构建灾情上下文
        disaster_context = _build_disaster_context(state)
        
        # 提取通信相关数据
        comm_data = []
        for site in candidate_sites[:10]:
            comm_data.append({
                "site_id": site.get("site_id") or str(site.get("id", "")),
                "name": site.get("name", "未知"),
                "primary_network_type": site.get("network_type") or site.get("primary_network_type", "unknown"),
                "signal_quality": site.get("signal_quality", "unknown"),
                "site_type": site.get("site_type", "unknown"),
                "longitude": site.get("longitude"),
                "latitude": site.get("latitude"),
            })
        
        candidates_json = json.dumps(comm_data, ensure_ascii=False, indent=2)
        
        prompt = COMMUNICATION_PROMPT.format(
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
        communication_assessments: List[CommunicationAssessment] = []
        for item in parsed_data:
            try:
                item["site_id"] = UUID(item["site_id"])
                assessment = CommunicationAssessment.model_validate(item)
                communication_assessments.append(assessment)
            except (ValidationError, ValueError) as e:
                logger.warning(f"[通信分析] 单条评估校验失败: {e}")
                continue
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"[通信分析] 完成: {len(communication_assessments)} 个评估, 耗时 {elapsed_ms}ms")
        
        return {
            "communication_assessments": communication_assessments,
            "timing": {**state.get("timing", {}), "communication_ms": elapsed_ms},
        }
        
    except json.JSONDecodeError as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.warning(f"[通信分析] JSON解析失败: {e}")
        return {
            "communication_assessments": None,
            "errors": state.get("errors", []) + [f"通信分析JSON解析失败: {str(e)}"],
            "timing": {**state.get("timing", {}), "communication_ms": elapsed_ms},
        }
        
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"[通信分析] 异常: {e}", exc_info=True)
        return {
            "communication_assessments": None,
            "errors": state.get("errors", []) + [f"通信分析异常: {str(e)}"],
            "timing": {**state.get("timing", {}), "communication_ms": elapsed_ms},
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
        # 识别通信相关约束
        if hasattr(parsed, "extracted_constraints") and parsed.extracted_constraints:
            comm_constraints = [
                c.description for c in parsed.extracted_constraints 
                if hasattr(c, "constraint_type") and "communication" in c.constraint_type.lower()
            ]
            if comm_constraints:
                parts.append(f"通信约束: {', '.join(comm_constraints)}")
    
    return "\n".join(parts) if parts else "无详细灾情信息"
