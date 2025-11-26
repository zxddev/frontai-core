"""LLM 客户端：使用 ChatOpenAI 直连本地 vLLM，禁止降级。"""
from __future__ import annotations

import logging  # 日志记录
from langchain_openai import ChatOpenAI  # 引入 ChatOpenAI

from infra.settings import Settings  # 引入配置

logger = logging.getLogger(__name__)  # 初始化日志器


def build_chat_model(settings: Settings) -> ChatOpenAI:
    """构建 ChatOpenAI 模型实例，使用 vLLM 网关。"""
    logger.info(
        "初始化LLM",  # 日志：初始化
        extra={
            "base_url": settings.openai_base_url,  # 记录 base_url
            "model": settings.llm_model,  # 记录模型
            "timeout": settings.request_timeout,  # 记录超时
            "concurrency": settings.max_concurrency,  # 记录并发
        },
    )
    return ChatOpenAI(
        model=settings.llm_model,  # 指定模型
        base_url=settings.openai_base_url,  # 指定 vLLM 网关
        api_key=settings.openai_api_key,  # 指定密钥
        timeout=settings.request_timeout,  # 设置超时
        max_retries=0,  # 禁止内部重试
    )
