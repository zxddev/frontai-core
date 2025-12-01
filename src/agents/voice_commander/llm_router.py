"""
LLM意图路由器

使用本地LLM进行意图分类，准确率高于embedding相似度匹配。
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


# 路由名称到目标Agent的映射
ROUTE_TARGETS = {
    "spatial_query": "spatial_agent",
    "task_status": "task_agent",
    "resource_status": "resource_agent",
    "robot_command": "commander_agent",
    "chitchat": "basic_llm",
}

# 意图分类提示词
INTENT_CLASSIFICATION_PROMPT = """你是应急救援指挥系统的意图分类器。分析用户语音指令，返回最匹配的类别。

## 类别和示例

task_status（任务查询）:
- 任务进度怎么样、任务列表、汇报任务情况、紧急任务有几个、二号队在执行什么任务

spatial_query（位置/区域查询）:
- 消防大队在哪里、医疗队在哪里、最近的消防站在哪、A区域现在什么情况、B区状态怎么样

resource_status（资源/队伍查询）:
- 消防队在干什么、可调度的队伍有哪些、资源统计、消防车可以调动吗

robot_command（控制指令）:
- 派无人机去东门、返航、停止

chitchat（仅限纯问候）:
- 你好、谢谢、收到

## 关键词判断
- 含"任务"/"执行什么" → task_status
- 含"在哪"/"最近"/"区域"/"区状态" → spatial_query
- 含"队伍"/"资源"/"调动"/"可调度" → resource_status
- 含"派"/"返航" → robot_command
- 仅"你好/谢谢/收到" → chitchat

返回类别名称："""


def _get_llm() -> ChatOpenAI:
    """获取LLM客户端"""
    from src.infra.settings import load_settings
    settings = load_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        max_tokens=50,  # 足够返回类别名称
        temperature=0,
        request_timeout=15,
    )


class LLMIntentRouter:
    """
    基于LLM的意图路由器
    
    直接使用本地LLM进行意图分类，准确率高。
    """
    
    def __init__(self) -> None:
        self._llm: Optional[ChatOpenAI] = None
        logger.info("LLM意图路由器初始化")
    
    def _ensure_llm(self) -> ChatOpenAI:
        """懒加载LLM"""
        if self._llm is None:
            self._llm = _get_llm()
        return self._llm
    
    async def classify(self, text: str) -> Tuple[str, float]:
        """
        分类用户意图
        
        Args:
            text: 用户输入
            
        Returns:
            (route_name, latency_seconds)
        """
        llm = self._ensure_llm()
        start_ts = time.time()
        
        try:
            messages = [
                SystemMessage(content=INTENT_CLASSIFICATION_PROMPT),
                HumanMessage(content=text),
            ]
            
            response = await llm.ainvoke(messages)
            result = response.content.strip().lower()
            
            # 规范化结果（按优先级匹配）
            if "spatial" in result:
                route = "spatial_query"
            elif "task" in result:
                route = "task_status"
            elif "resource" in result:
                route = "resource_status"
            elif "robot" in result or "command" in result:
                route = "robot_command"
            else:
                route = "chitchat"
            
            latency = time.time() - start_ts
            logger.info(f"LLM路由: '{text[:30]}...' -> {route} ({latency*1000:.0f}ms)")
            
            return route, latency
            
        except Exception as e:
            logger.exception(f"LLM路由失败: {e}")
            return "chitchat", time.time() - start_ts


# 全局实例
_router: Optional[LLMIntentRouter] = None


def get_llm_router() -> LLMIntentRouter:
    """获取LLM路由器单例"""
    global _router
    if _router is None:
        _router = LLMIntentRouter()
    return _router
