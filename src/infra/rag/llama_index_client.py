"""RAG 封装：使用 OpenAIEmbeddings + QdrantClient.query_points，兼容本地自定义 embedding。
- 不依赖 qdrant_client.search 方法，适配新版客户端。
- 检索为空或异常时直接抛错，不做降级。
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from src.infra.settings import Settings

logger = logging.getLogger(__name__)


class LlamaIndexRag:
    """RAG 检索封装（类名保持兼容）。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        logger.info(
            "初始化 RAG",
            extra={
                "embed_base": settings.embedding_base_url,
                "embed_model": settings.embedding_model,
                "qdrant_url": settings.qdrant_url,
                "collection": settings.qdrant_collection,
            },
        )
        self._embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
        )
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            prefer_grpc=False,
        )
        self._collection = settings.qdrant_collection
        self._top_k = settings.rag_top_k

    def similarity_search(self, query: str) -> List[Tuple[str, float, dict]]:
        """执行向量检索，返回文本、分数与元数据。"""
        logger.info(
            "执行 RAG 检索",
            extra={"collection": self._collection, "top_k": self._top_k},
        )
        vector = self._embeddings.embed_query(query)
        res = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=self._top_k,
            with_payload=True,
        )
        points = res.points
        if not points:
            raise RuntimeError("向量检索为空，拒绝继续")
        results: List[Tuple[str, float, dict]] = []
        for pt in points:
            payload = dict(pt.payload or {})
            text = payload.get("text", "")
            results.append((text, float(pt.score or 0.0), payload))
        return results
