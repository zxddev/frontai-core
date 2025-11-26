"""
知识库检索客户端封装

调用LlamaIndexRag进行操作手册检索，转换结果为ManualRecommendation格式。
检索为空时直接抛出异常，不做降级。
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID, uuid4

from src.infra.settings import load_settings, Settings
from src.infra.rag.llama_index_client import LlamaIndexRag
from .schemas import ManualRecommendation

logger = logging.getLogger(__name__)

# RAG客户端单例
_rag_client: Optional[LlamaIndexRag] = None
_settings: Optional[Settings] = None


def get_rag_client() -> LlamaIndexRag:
    """
    获取RAG客户端单例
    
    首次调用时初始化，后续复用同一实例。
    初始化失败直接抛出异常。
    """
    global _rag_client, _settings
    
    if _rag_client is None:
        logger.info("初始化RAG客户端")
        _settings = load_settings()
        _rag_client = LlamaIndexRag(_settings)
        logger.info(
            "RAG客户端初始化完成",
            extra={
                "qdrant_url": _settings.qdrant_url,
                "collection": _settings.qdrant_collection,
            }
        )
    
    return _rag_client


def search_manuals_by_query(
    query: str,
    limit: int = 10,
    disaster_type: Optional[str] = None,
) -> List[ManualRecommendation]:
    """
    根据查询检索操作手册
    
    Args:
        query: 搜索查询文本
        limit: 返回结果数量上限
        disaster_type: 灾害类型过滤（当前未实现过滤，仅用于构造查询）
        
    Returns:
        ManualRecommendation列表，按相关性排序
        
    Raises:
        RuntimeError: 检索结果为空时抛出
    """
    # 构造增强查询（如果指定了灾害类型）
    enhanced_query = query
    if disaster_type:
        enhanced_query = f"{disaster_type} {query}"
    
    logger.info(
        "执行手册检索",
        extra={"query": enhanced_query, "limit": limit}
    )
    
    client = get_rag_client()
    
    # 调用RAG检索，检索为空会抛出RuntimeError
    results = client.similarity_search(enhanced_query)
    
    # 转换结果为ManualRecommendation
    recommendations: List[ManualRecommendation] = []
    
    for text, score, metadata in results[:limit]:
        # 从metadata提取字段，提供默认值
        manual_id_str = metadata.get("manual_id", "")
        try:
            manual_id = UUID(manual_id_str) if manual_id_str else uuid4()
        except ValueError:
            manual_id = uuid4()
        
        title = metadata.get("title", "未知手册")
        keywords = metadata.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        
        # 截取前500字符作为摘要
        summary = text[:500] if len(text) > 500 else text
        
        rec = ManualRecommendation(
            manual_id=manual_id,
            title=title,
            relevance_score=round(score, 4),
            matched_keywords=keywords,
            summary=summary,
        )
        recommendations.append(rec)
    
    logger.info(
        "手册检索完成",
        extra={"result_count": len(recommendations)}
    )
    
    return recommendations


def search_manuals_by_event(
    event_id: UUID,
    disaster_type: str,
    description: str,
    limit: int = 5,
) -> List[ManualRecommendation]:
    """
    根据事件信息检索相关操作手册
    
    Args:
        event_id: 事件ID（用于日志）
        disaster_type: 灾害类型
        description: 事件描述
        limit: 返回结果数量上限
        
    Returns:
        ManualRecommendation列表
    """
    # 构造查询：灾害类型 + 描述关键部分
    query_parts = [disaster_type]
    
    # 提取描述的关键部分（前100字符）
    if description:
        query_parts.append(description[:100])
    
    query = " ".join(query_parts)
    
    logger.info(
        "根据事件检索手册",
        extra={"event_id": str(event_id), "query": query}
    )
    
    return search_manuals_by_query(query=query, limit=limit)
