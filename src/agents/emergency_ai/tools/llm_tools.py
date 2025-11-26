"""
LLM工具封装

使用LangChain工具装饰器封装LLM调用，实现灾情解析、推理、解释功能。
"""
from __future__ import annotations

import os
import json
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic模型定义（用于结构化输出）
# ============================================================================

class DisasterParseResult(BaseModel):
    """灾情解析结果"""
    disaster_type: str = Field(description="灾害类型: earthquake/fire/flood/hazmat/landslide")
    severity: str = Field(description="严重程度: critical/high/medium/low")
    has_building_collapse: bool = Field(description="是否有建筑倒塌")
    has_trapped_persons: bool = Field(description="是否有被困人员")
    estimated_trapped: int = Field(description="预估被困人数")
    has_secondary_fire: bool = Field(description="是否有次生火灾")
    has_hazmat_leak: bool = Field(description="是否有危化品泄漏")
    has_road_damage: bool = Field(description="是否有道路损毁")
    affected_population: int = Field(description="受影响人口估算")
    building_damage_level: str = Field(description="建筑损坏等级: severe/moderate/minor/none")
    key_entities: List[str] = Field(description="关键实体列表")
    urgency_factors: List[str] = Field(description="紧急因素列表")


class RescuePriorityResult(BaseModel):
    """救援优先级推理结果"""
    priority_order: List[str] = Field(description="任务优先级排序")
    critical_tasks: List[str] = Field(description="关键任务列表")
    reasoning: str = Field(description="推理说明")
    time_constraints: Dict[str, int] = Field(description="时间约束(小时)")


class SchemeExplanation(BaseModel):
    """方案解释"""
    summary: str = Field(description="方案摘要")
    selection_reason: str = Field(description="选择该方案的原因")
    key_advantages: List[str] = Field(description="关键优势")
    potential_risks: List[str] = Field(description="潜在风险")
    mitigation_measures: List[str] = Field(description="风险缓解措施")
    execution_suggestions: List[str] = Field(description="执行建议")


# ============================================================================
# LLM客户端获取
# ============================================================================

def _get_llm() -> ChatOpenAI:
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
        max_retries=0,  # 禁止内部重试，失败直接抛错
    )


# ============================================================================
# 工具函数定义
# ============================================================================

@tool
def parse_disaster_description(
    description: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    解析灾情描述文本，提取结构化信息。
    
    使用LLM分析自然语言灾情描述，识别灾害类型、严重程度、
    被困人员、次生灾害等关键信息。
    
    Args:
        description: 灾情描述文本（自然语言）
        context: 可选上下文信息（位置、时间等）
        
    Returns:
        结构化的灾情信息字典
    """
    logger.info("调用LLM解析灾情描述", extra={"description_length": len(description)})
    
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=DisasterParseResult)
    
    # 构建提示词
    system_prompt = """你是应急救灾AI助手，负责分析灾情信息。
请仔细分析用户提供的灾情描述，提取关键信息并返回JSON格式结果。

注意：
1. 如果描述中没有明确提到某项信息，请根据灾害类型和描述内容合理推断
2. 被困人数如果不确定，给出保守估计
3. 严重程度根据灾害规模、伤亡情况、影响范围综合判断

{format_instructions}"""

    human_prompt = """请分析以下灾情描述：

{description}

{context_info}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    # 构建上下文信息
    context_info = ""
    if context:
        context_info = f"补充信息：{json.dumps(context, ensure_ascii=False)}"
    
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({
            "description": description,
            "context_info": context_info,
            "format_instructions": parser.get_format_instructions(),
        })
        logger.info("LLM灾情解析完成", extra={"disaster_type": result.get("disaster_type")})
        return result
    except Exception as e:
        logger.error("LLM灾情解析失败", extra={"error": str(e)})
        raise RuntimeError(f"LLM解析失败: {e}") from e


@tool
def reason_rescue_priority(
    disaster_info: Dict[str, Any],
    available_resources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    推理救援任务优先级。
    
    根据灾情信息和可用资源，使用LLM推理确定救援任务的优先级顺序。
    
    Args:
        disaster_info: 灾情信息（parse_disaster_description的输出）
        available_resources: 可用资源列表
        
    Returns:
        优先级推理结果
    """
    logger.info("调用LLM推理救援优先级")
    
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=RescuePriorityResult)
    
    system_prompt = """你是应急救灾指挥专家，负责确定救援任务优先级。

请根据灾情信息和可用资源，确定救援任务的优先级顺序。

优先级判断原则：
1. 生命优先：被困人员救援优先级最高
2. 时间敏感：考虑黄金救援时间（72小时）
3. 次生灾害：火灾、危化品泄漏等需要优先控制
4. 资源匹配：确保有对应能力的资源执行任务

{format_instructions}"""

    human_prompt = """灾情信息：
{disaster_info}

可用资源：
{resources}

请确定救援任务优先级。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({
            "disaster_info": json.dumps(disaster_info, ensure_ascii=False, indent=2),
            "resources": json.dumps(available_resources, ensure_ascii=False, indent=2),
            "format_instructions": parser.get_format_instructions(),
        })
        logger.info("LLM优先级推理完成")
        return result
    except Exception as e:
        logger.error("LLM优先级推理失败", extra={"error": str(e)})
        raise RuntimeError(f"LLM推理失败: {e}") from e


@tool
def explain_scheme(
    scheme: Dict[str, Any],
    disaster_info: Dict[str, Any],
    alternatives: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    为推荐方案生成自然语言解释。
    
    使用LLM分析方案内容，生成易于理解的方案说明和执行建议。
    
    Args:
        scheme: 推荐方案详情
        disaster_info: 灾情信息
        alternatives: 备选方案列表（用于对比说明）
        
    Returns:
        方案解释结果
    """
    logger.info("调用LLM生成方案解释")
    
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=SchemeExplanation)
    
    system_prompt = """你是应急救灾方案专家，负责解释救援方案。

请根据方案内容和灾情信息，生成清晰的方案说明，包括：
1. 方案摘要
2. 选择该方案的原因
3. 关键优势
4. 潜在风险及缓解措施
5. 执行建议

{format_instructions}"""

    human_prompt = """灾情信息：
{disaster_info}

推荐方案：
{scheme}

{alternatives_info}

请生成方案解释。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    # 备选方案信息
    alternatives_info = ""
    if alternatives:
        alternatives_info = f"备选方案：\n{json.dumps(alternatives[:3], ensure_ascii=False, indent=2)}"
    
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({
            "disaster_info": json.dumps(disaster_info, ensure_ascii=False, indent=2),
            "scheme": json.dumps(scheme, ensure_ascii=False, indent=2),
            "alternatives_info": alternatives_info,
            "format_instructions": parser.get_format_instructions(),
        })
        logger.info("LLM方案解释生成完成")
        return result
    except Exception as e:
        logger.error("LLM方案解释生成失败", extra={"error": str(e)})
        raise RuntimeError(f"LLM解释生成失败: {e}") from e


# ============================================================================
# 非工具版本（供节点直接调用）
# ============================================================================

async def parse_disaster_description_async(
    description: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """异步版本的灾情解析"""
    logger.info("异步调用LLM解析灾情描述", extra={"description_length": len(description)})
    
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=DisasterParseResult)
    
    system_prompt = """你是应急救灾AI助手，负责分析灾情信息。
请仔细分析用户提供的灾情描述，提取关键信息并返回JSON格式结果。

注意：
1. 如果描述中没有明确提到某项信息，请根据灾害类型和描述内容合理推断
2. 被困人数如果不确定，给出保守估计
3. 严重程度根据灾害规模、伤亡情况、影响范围综合判断

{format_instructions}"""

    human_prompt = """请分析以下灾情描述：

{description}

{context_info}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    context_info = ""
    if context:
        context_info = f"补充信息：{json.dumps(context, ensure_ascii=False)}"
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "description": description,
            "context_info": context_info,
            "format_instructions": parser.get_format_instructions(),
        })
        logger.info("异步LLM灾情解析完成", extra={"disaster_type": result.get("disaster_type")})
        return result
    except Exception as e:
        logger.error("异步LLM灾情解析失败", extra={"error": str(e)})
        raise RuntimeError(f"LLM解析失败: {e}") from e


async def explain_scheme_async(
    scheme: Dict[str, Any],
    disaster_info: Dict[str, Any],
    alternatives: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """异步版本的方案解释"""
    logger.info("异步调用LLM生成方案解释")
    
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=SchemeExplanation)
    
    system_prompt = """你是应急救灾方案专家，负责解释救援方案。

请根据方案内容和灾情信息，生成清晰的方案说明，包括：
1. 方案摘要
2. 选择该方案的原因
3. 关键优势
4. 潜在风险及缓解措施
5. 执行建议

{format_instructions}"""

    human_prompt = """灾情信息：
{disaster_info}

推荐方案：
{scheme}

{alternatives_info}

请生成方案解释。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    alternatives_info = ""
    if alternatives:
        alternatives_info = f"备选方案：\n{json.dumps(alternatives[:3], ensure_ascii=False, indent=2)}"
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "disaster_info": json.dumps(disaster_info, ensure_ascii=False, indent=2),
            "scheme": json.dumps(scheme, ensure_ascii=False, indent=2),
            "alternatives_info": alternatives_info,
            "format_instructions": parser.get_format_instructions(),
        })
        logger.info("异步LLM方案解释生成完成")
        return result
    except Exception as e:
        logger.error("异步LLM方案解释生成失败", extra={"error": str(e)})
        raise RuntimeError(f"LLM解释生成失败: {e}") from e
