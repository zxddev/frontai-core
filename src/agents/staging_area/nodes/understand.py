"""
灾情理解节点

职责：
1. 解析自然语言灾情描述
2. 提取关键约束条件
3. 校验LLM输出（遵循调用规范）
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.staging_area.state import (
    ParsedConstraint,
    ParsedDisasterInfo,
    StagingAreaAgentState,
)
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

logger = logging.getLogger(__name__)


def _fix_json_string(json_str: str) -> str:
    """修复常见的 JSON 格式问题"""
    # 移除注释（// 和 /* */）
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    # 移除尾部逗号（数组和对象中最后一个元素后的逗号）
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # 修复单引号为双引号
    json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
    
    # 修复中文冒号为英文冒号
    json_str = json_str.replace('：', ':')
    
    # 修复没有引号的键名（如 key: "value" -> "key": "value"）
    json_str = re.sub(r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):', r'\1"\2"\3:', json_str)
    
    # 修复多余的逗号（连续逗号）
    json_str = re.sub(r',\s*,', ',', json_str)
    
    # 修复字符串中的换行符（转义）
    # 注意：这只处理简单情况
    lines = json_str.split('\n')
    fixed_lines = []
    for line in lines:
        # 移除行尾的控制字符
        line = line.rstrip('\r')
        fixed_lines.append(line)
    json_str = '\n'.join(fixed_lines)
    
    return json_str.strip()


UNDERSTAND_PROMPT = """你是一个地震灾害分析专家。请分析以下灾情描述，提取关键信息。

## 灾情描述
{disaster_description}

## 任务
1. 识别灾害类型和基本参数（震级、震中位置等）
2. 提取可能影响救援队驻扎点选择的约束条件，包括：
   - 道路阻断
   - 区域淹没
   - 通信中断
   - 滑坡/泥石流风险区
   - 建筑倒塌区
3. 识别主要关切点

## 输出格式（JSON）
{{
    "disaster_type": "earthquake",
    "epicenter_description": "茂县叠溪镇",
    "magnitude": 7.0,
    "affected_area_description": "震中周边50公里范围",
    "key_concerns": ["道路损毁严重", "通信可能中断"],
    "extracted_constraints": [
        {{
            "constraint_type": "road_blocked",
            "description": "多处道路被滑坡阻断",
            "location_hint": "震中至茂县方向",
            "severity": "high",
            "confidence": 0.85
        }}
    ]
}}

请只输出JSON，不要其他内容。
"""


async def understand_disaster(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    灾情理解节点
    
    遵循调用规范：
    - 必须校验LLM输出（Pydantic）
    - 错误时返回错误信息而非抛出异常
    
    Args:
        state: Agent状态
        db: 数据库会话
        
    Returns:
        状态更新字典
    """
    start_time = time.perf_counter()
    
    # 检查是否跳过LLM分析
    if state.get("skip_llm_analysis", False):
        logger.info("[灾情理解] 跳过LLM分析（skip_llm_analysis=True）")
        return {
            "parsed_disaster": None,
            "processing_mode": "algorithm_only",
            "timing": {**state.get("timing", {}), "understand_ms": 0},
        }
    
    disaster_description = state.get("disaster_description", "")
    if not disaster_description:
        # 如果没有自然语言描述，使用结构化输入
        logger.info("[灾情理解] 无灾情描述，使用结构化输入")
        return {
            "parsed_disaster": None,
            "processing_mode": "structured_input",
            "timing": {**state.get("timing", {}), "understand_ms": 0},
        }
    
    try:
        # 调用LLM
        llm = _get_llm()
        prompt = UNDERSTAND_PROMPT.format(disaster_description=disaster_description)
        
        response = await llm.ainvoke(prompt)
        raw_output = response.content if hasattr(response, "content") else str(response)
        
        # 清理JSON（移除markdown代码块标记）
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_output.strip()
        
        # 尝试修复常见的 JSON 格式问题
        json_str = _fix_json_string(json_str)
        parsed_data = json.loads(json_str)
        
        # ⚠️ 必须：Pydantic校验LLM输出（遵循调用规范）
        try:
            parsed_disaster = ParsedDisasterInfo.model_validate(parsed_data)
            logger.info(
                f"[灾情理解] 成功解析: 类型={parsed_disaster.disaster_type}, "
                f"约束数={len(parsed_disaster.extracted_constraints)}"
            )
        except ValidationError as e:
            logger.warning(f"[灾情理解] LLM输出校验失败: {e}")
            return {
                "parsed_disaster": None,
                "errors": state.get("errors", []) + [f"灾情理解输出校验失败: {str(e)}"],
                "processing_mode": "fallback",
                "timing": {
                    **state.get("timing", {}),
                    "understand_ms": int((time.perf_counter() - start_time) * 1000),
                },
            }
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        return {
            "parsed_disaster": parsed_disaster,
            "processing_mode": "agent",
            "timing": {**state.get("timing", {}), "understand_ms": elapsed_ms},
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"[灾情理解] JSON解析失败: {e}")
        return {
            "parsed_disaster": None,
            "errors": state.get("errors", []) + [f"灾情理解JSON解析失败: {str(e)}"],
            "processing_mode": "fallback",
            "timing": {
                **state.get("timing", {}),
                "understand_ms": int((time.perf_counter() - start_time) * 1000),
            },
        }
        
    except Exception as e:
        logger.error(f"[灾情理解] 异常: {e}", exc_info=True)
        return {
            "parsed_disaster": None,
            "errors": state.get("errors", []) + [f"灾情理解异常: {str(e)}"],
            "processing_mode": "fallback",
            "timing": {
                **state.get("timing", {}),
                "understand_ms": int((time.perf_counter() - start_time) * 1000),
            },
        }
