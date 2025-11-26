"""
RAG工具封装

使用Qdrant向量数据库实现历史案例检索。
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)


# ============================================================================
# Qdrant客户端获取
# ============================================================================

def _get_qdrant_client() -> QdrantClient:
    """获取Qdrant客户端实例"""
    qdrant_url = os.environ.get('QDRANT_URL', 'http://192.168.31.50:6333')
    qdrant_api_key = os.environ.get('QDRANT_API_KEY', '')
    return QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key if qdrant_api_key else None,
    )


def _get_embeddings() -> OpenAIEmbeddings:
    """获取向量化模型"""
    embedding_base_url = os.environ.get('EMBEDDING_BASE_URL', 'http://192.168.31.50:8001/v1')
    embedding_model = os.environ.get('EMBEDDING_MODEL', 'embedding-3')
    embedding_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    return OpenAIEmbeddings(
        model=embedding_model,
        base_url=embedding_base_url,
        api_key=embedding_api_key,
    )


# ============================================================================
# 案例集合配置
# ============================================================================

# 应急救灾案例集合名称
EMERGENCY_CASES_COLLECTION = "emergency_cases"


# ============================================================================
# 工具函数定义
# ============================================================================

@tool
def search_similar_cases(
    query: str,
    disaster_type: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    检索相似历史案例。
    
    从向量数据库中检索与当前灾情相似的历史案例，
    用于借鉴经验教训和最佳实践。
    
    Args:
        query: 检索查询（灾情描述）
        disaster_type: 灾害类型过滤（可选）
        top_k: 返回最相似的K个案例
        
    Returns:
        相似案例列表，每个案例包含：
        - case_id: 案例ID
        - title: 案例标题
        - disaster_type: 灾害类型
        - description: 案例描述
        - lessons_learned: 经验教训
        - best_practices: 最佳实践
        - similarity_score: 相似度分数
    """
    logger.info(
        "调用RAG检索相似案例",
        extra={"query_length": len(query), "disaster_type": disaster_type, "top_k": top_k}
    )
    
    client = _get_qdrant_client()
    embeddings = _get_embeddings()
    
    # 检查集合是否存在
    try:
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        # 优先使用emergency_cases，如果不存在则使用rag_案例
        if EMERGENCY_CASES_COLLECTION in collection_names:
            collection_name = EMERGENCY_CASES_COLLECTION
        elif "rag_案例" in collection_names:
            collection_name = "rag_案例"
            logger.info("使用已有集合rag_案例进行检索")
        else:
            logger.warning("案例集合不存在，返回空结果")
            return []
    except Exception as e:
        logger.error("检查Qdrant集合失败", extra={"error": str(e)})
        return []
    
    # 向量化查询
    try:
        query_vector = embeddings.embed_query(query)
    except Exception as e:
        logger.error("向量化查询失败", extra={"error": str(e)})
        raise RuntimeError(f"向量化失败: {e}") from e
    
    # 构建过滤条件
    search_filter = None
    if disaster_type:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="disaster_type",
                    match=MatchValue(value=disaster_type),
                )
            ]
        )
    
    # 执行检索
    try:
        from qdrant_client.models import QueryRequest
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.error("Qdrant检索失败", extra={"error": str(e)})
        raise RuntimeError(f"向量检索失败: {e}") from e
    
    # 格式化结果
    cases: List[Dict[str, Any]] = []
    for hit in results.points:
        payload = hit.payload or {}
        case = {
            "case_id": payload.get("case_id", str(hit.id)),
            "title": payload.get("title", "未知案例"),
            "disaster_type": payload.get("disaster_type", "unknown"),
            "description": payload.get("description", payload.get("content", "")),
            "lessons_learned": payload.get("lessons_learned", []),
            "best_practices": payload.get("best_practices", []),
            "similarity_score": float(hit.score) if hit.score else 0.0,
        }
        cases.append(case)
    
    logger.info("RAG检索完成", extra={"results_count": len(cases)})
    return cases


# ============================================================================
# 非工具版本（供节点直接调用）
# ============================================================================

async def search_similar_cases_async(
    query: str,
    disaster_type: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    异步版本的相似案例检索
    
    由于qdrant_client同步API，这里使用同步调用包装
    """
    # Qdrant Python客户端的search是同步的，直接调用
    return search_similar_cases.invoke({
        "query": query,
        "disaster_type": disaster_type,
        "top_k": top_k,
    })


# ============================================================================
# 案例导入工具
# ============================================================================

def import_emergency_cases(cases: List[Dict[str, Any]]) -> int:
    """
    导入应急救灾案例到Qdrant
    
    Args:
        cases: 案例列表，每个案例包含：
            - case_id: 案例ID
            - title: 标题
            - disaster_type: 灾害类型
            - description: 描述
            - lessons_learned: 经验教训列表
            - best_practices: 最佳实践列表
            
    Returns:
        导入成功的案例数量
    """
    logger.info("开始导入应急案例", extra={"total": len(cases)})
    
    client = _get_qdrant_client()
    embeddings = _get_embeddings()
    
    # 检查并创建集合
    try:
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if EMERGENCY_CASES_COLLECTION not in collection_names:
            # 获取向量维度
            test_vector = embeddings.embed_query("test")
            vector_size = len(test_vector)
            
            from qdrant_client.models import VectorParams, Distance
            client.create_collection(
                collection_name=EMERGENCY_CASES_COLLECTION,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("创建案例集合", extra={"collection": EMERGENCY_CASES_COLLECTION})
    except Exception as e:
        logger.error("创建集合失败", extra={"error": str(e)})
        raise
    
    # 导入案例
    success_count = 0
    from qdrant_client.models import PointStruct
    
    for case in cases:
        try:
            # 构建检索文本
            search_text = f"{case['title']} {case['description']}"
            vector = embeddings.embed_query(search_text)
            
            point = PointStruct(
                id=hash(case["case_id"]) % (2**63),
                vector=vector,
                payload={
                    "case_id": case["case_id"],
                    "title": case["title"],
                    "disaster_type": case["disaster_type"],
                    "description": case["description"],
                    "lessons_learned": case.get("lessons_learned", []),
                    "best_practices": case.get("best_practices", []),
                },
            )
            
            client.upsert(
                collection_name=EMERGENCY_CASES_COLLECTION,
                points=[point],
            )
            success_count += 1
        except Exception as e:
            logger.error("导入案例失败", extra={"case_id": case.get("case_id"), "error": str(e)})
    
    logger.info("案例导入完成", extra={"success": success_count, "total": len(cases)})
    return success_count
