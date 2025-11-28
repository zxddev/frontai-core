"""
决策解释节点

职责：
1. 根据评分结果生成推荐理由
2. 生成风险警示
3. 提供备选方案建议

此节点使用LLM生成可解释的输出。
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
    AlternativeSuggestion,
    RiskWarning,
    SiteExplanation,
    StagingAreaAgentState,
)


def _fix_json_string(json_str: str) -> str:
    """修复常见的 JSON 格式问题"""
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
    return json_str.strip()


def _get_llm(max_tokens: int = 4096) -> ChatOpenAI:
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


EXPLAIN_PROMPT = """你是一个地震救援驻扎点选址专家。请根据以下评估结果，为指挥官生成决策解释。

## 灾情背景
{disaster_context}

## 候选点评分结果（按总分排序）
{ranked_sites_json}

## 任务
1. 为排名前{top_n}的站点生成推荐理由和注意事项
2. 识别潜在风险并生成警示
3. 提供备选方案建议

## 输出格式（JSON）
{{
    "site_explanations": [
        {{
            "site_id": "uuid",
            "site_name": "站点名称",
            "rank": 1,
            "recommendation_reason": "推荐理由...",
            "advantages": ["优势1", "优势2"],
            "concerns": ["注意事项1"],
            "confidence": 0.85
        }}
    ],
    "risk_warnings": [
        {{
            "warning_type": "secondary_hazard",
            "severity": "warning",
            "message": "警告消息...",
            "affected_sites": ["站点名"],
            "mitigation_advice": "缓解建议..."
        }}
    ],
    "alternatives": [
        {{
            "scenario": "如果道路进一步阻断",
            "suggested_site_id": "uuid",
            "suggested_site_name": "站点名",
            "reason": "该站点有直升机起降场..."
        }}
    ],
    "summary": "总体推荐摘要..."
}}

请只输出JSON，不要其他内容。
"""


async def explain_decision(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    决策解释节点
    
    使用LLM生成：
    1. 推荐理由
    2. 风险警示
    3. 备选方案
    
    遵循调用规范：必须校验LLM输出
    
    Args:
        state: Agent状态
        db: 数据库会话
        
    Returns:
        状态更新字典
    """
    start_time = time.perf_counter()
    
    ranked_sites = state.get("ranked_sites", [])
    if not ranked_sites:
        logger.warning("[决策解释] 无排序结果，跳过解释生成")
        return {
            "site_explanations": [],
            "risk_warnings": [],
            "alternatives": [],
            "summary": "未找到合适的驻扎点候选",
            "timing": {**state.get("timing", {}), "explain_ms": 0},
        }
    
    # 检查是否跳过LLM分析
    if state.get("skip_llm_analysis", False):
        # 生成基础解释（无LLM）
        explanations = _generate_basic_explanations(ranked_sites)
        return {
            "site_explanations": explanations,
            "risk_warnings": [],
            "alternatives": [],
            "summary": f"基于算法评分，推荐 {ranked_sites[0]['name']} 作为首选驻扎点（总分{ranked_sites[0]['total_score']:.2f}）",
            "timing": {**state.get("timing", {}), "explain_ms": 0},
        }
    
    try:
        # 构建灾情上下文
        disaster_context = _build_disaster_context(state)
        
        # 准备排序结果JSON
        ranked_sites_json = json.dumps(ranked_sites[:5], ensure_ascii=False, indent=2)
        
        top_n = state.get("top_n", 3)
        prompt = EXPLAIN_PROMPT.format(
            disaster_context=disaster_context,
            ranked_sites_json=ranked_sites_json,
            top_n=top_n,
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
        
        # 校验各部分输出
        site_explanations = []
        for exp_data in parsed_data.get("site_explanations", []):
            try:
                exp = SiteExplanation.model_validate(exp_data)
                site_explanations.append(exp)
            except ValidationError as e:
                logger.warning(f"[决策解释] 站点解释校验失败: {e}")
        
        risk_warnings = []
        for warn_data in parsed_data.get("risk_warnings", []):
            try:
                warn = RiskWarning.model_validate(warn_data)
                risk_warnings.append(warn)
            except ValidationError as e:
                logger.warning(f"[决策解释] 风险警示校验失败: {e}")
        
        alternatives = []
        for alt_data in parsed_data.get("alternatives", []):
            try:
                alt = AlternativeSuggestion.model_validate(alt_data)
                alternatives.append(alt)
            except ValidationError as e:
                logger.warning(f"[决策解释] 备选方案校验失败: {e}")
        
        summary = parsed_data.get("summary", "")
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            f"[决策解释] 完成: {len(site_explanations)} 个解释, "
            f"{len(risk_warnings)} 个警示, 耗时 {elapsed_ms}ms"
        )
        
        return {
            "site_explanations": site_explanations,
            "risk_warnings": risk_warnings,
            "alternatives": alternatives,
            "summary": summary,
            "timing": {**state.get("timing", {}), "explain_ms": elapsed_ms},
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"[决策解释] JSON解析失败: {e}")
        # 降级到基础解释
        explanations = _generate_basic_explanations(ranked_sites)
        return {
            "site_explanations": explanations,
            "risk_warnings": [],
            "alternatives": [],
            "summary": f"推荐 {ranked_sites[0]['name']} 作为首选驻扎点",
            "errors": state.get("errors", []) + ["决策解释JSON解析失败，使用基础解释"],
            "timing": {
                **state.get("timing", {}),
                "explain_ms": int((time.perf_counter() - start_time) * 1000),
            },
        }
        
    except Exception as e:
        logger.error(f"[决策解释] 异常: {e}", exc_info=True)
        explanations = _generate_basic_explanations(ranked_sites)
        return {
            "site_explanations": explanations,
            "risk_warnings": [],
            "alternatives": [],
            "summary": f"推荐 {ranked_sites[0]['name']} 作为首选驻扎点",
            "errors": state.get("errors", []) + [f"决策解释异常: {str(e)}"],
            "timing": {
                **state.get("timing", {}),
                "explain_ms": int((time.perf_counter() - start_time) * 1000),
            },
        }


def _build_disaster_context(state: StagingAreaAgentState) -> str:
    """构建灾情上下文描述"""
    parts = []
    
    if state.get("disaster_description"):
        parts.append(f"灾情描述: {state['disaster_description']}")
    
    if state.get("magnitude"):
        parts.append(f"震级: {state['magnitude']}")
    
    if state.get("epicenter_lon") and state.get("epicenter_lat"):
        parts.append(f"震中: ({state['epicenter_lon']:.4f}, {state['epicenter_lat']:.4f})")
    
    parsed = state.get("parsed_disaster")
    if parsed:
        if parsed.key_concerns:
            parts.append(f"主要关切: {', '.join(parsed.key_concerns)}")
        if parsed.extracted_constraints:
            constraints = [c.description for c in parsed.extracted_constraints]
            parts.append(f"约束条件: {', '.join(constraints)}")
    
    return "\n".join(parts) if parts else "无详细灾情信息"


def _generate_basic_explanations(ranked_sites: List[dict]) -> List[SiteExplanation]:
    """生成基础解释（不使用LLM）"""
    explanations = []
    
    for i, site in enumerate(ranked_sites[:3]):
        advantages = []
        concerns = []
        
        # 根据评分生成优势
        scores = site.get("scores", {})
        if scores.get("response_time", 0) > 0.7:
            advantages.append("响应时间短")
        if scores.get("safety", 0) > 0.7:
            advantages.append("安全性高")
        if scores.get("logistics", 0) > 0.7:
            advantages.append("后勤保障好")
        if site.get("has_water_supply"):
            advantages.append("有水源供应")
        if site.get("has_power_supply"):
            advantages.append("有电力供应")
        if site.get("can_helicopter_land"):
            advantages.append("可直升机起降")
        
        # 根据评分生成注意事项
        if scores.get("safety", 1) < 0.5:
            concerns.append("安全评分较低，需注意防护")
        if scores.get("communication", 1) < 0.5:
            concerns.append("通信条件一般，建议携带备用设备")
        
        reason = f"综合评分{site['total_score']:.2f}，" + (
            "在响应时间、安全性等方面表现均衡" if not advantages else f"优势包括{', '.join(advantages[:2])}"
        )
        
        explanations.append(SiteExplanation(
            site_id=UUID(site["site_id"]),
            site_name=site["name"],
            rank=i + 1,
            recommendation_reason=reason,
            advantages=advantages,
            concerns=concerns,
            confidence=0.7,
        ))
    
    return explanations
