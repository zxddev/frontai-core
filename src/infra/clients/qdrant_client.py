"""Qdrant 向量检索封装，必须成功连接后才能继续流程。"""
from __future__ import annotations

import logging  # 日志
from typing import List, Tuple  # 类型提示

from langchain_openai import OpenAIEmbeddings  # 向量模型
from langchain_community.vectorstores import Qdrant  # Qdrant 向量库封装
from qdrant_client import QdrantClient  # 低层客户端

from infra.settings import Settings  # 配置

logger = logging.getLogger(__name__)  # 日志器


class RagClient:
    """封装向量检索，禁止降级。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings  # 保存配置
        logger.info(
            "初始化Qdrant",
            extra={
                "url": settings.qdrant_url,
                "collection": settings.qdrant_collection,
                "top_k": settings.rag_top_k,
            },
        )
        self._client = QdrantClient(
            url=settings.qdrant_url,  # Qdrant 地址
            api_key=settings.qdrant_api_key,  # Qdrant 密钥
        )
        # 构建向量存储，若集合不存在会抛错，确保无降级
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,  # 向量模型
            base_url=settings.openai_base_url,  # 使用同一网关
            api_key=settings.embedding_api_key,  # 向量密钥
        )
        self._store = Qdrant(
            client=self._client,  # 传入底层客户端
            collection_name=settings.qdrant_collection,  # 集合名称
            embeddings=embeddings,  # 向量模型
        )

    def similarity_search(self, query: str) -> List[Tuple[str, float, dict]]:
        """执行相似度检索，返回文本、分数与元数据。"""
        logger.info(
            "执行向量检索",
            extra={"collection": self._settings.qdrant_collection, "top_k": self._settings.rag_top_k},
        )
        docs = self._store.similarity_search(query, k=self._settings.rag_top_k)  # 执行检索
        if not docs:
            raise RuntimeError("向量检索为空，拒绝继续")  # 空结果直接报错
        results: List[Tuple[str, float, dict]] = []  # 初始化结果
        for doc in docs:
            meta = dict(doc.metadata or {})  # 复制元数据
            results.append((doc.page_content, float(meta.get("score", 0.0)), meta))  # 追加结果
        return results  # 返回检索结果
