"""
Agent抽象基类

定义Agent的生命周期和核心接口
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

# 状态类型变量
StateType = TypeVar("StateType", bound=Dict[str, Any])


class BaseAgent(ABC, Generic[StateType]):
    """
    Agent抽象基类
    
    所有Agent必须实现:
    1. build_graph() - 构建LangGraph
    2. prepare_input() - 准备输入状态
    3. process_output() - 处理输出结果
    """
    
    def __init__(self, name: str) -> None:
        """
        初始化Agent
        
        Args:
            name: Agent名称，用于日志和追踪
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._graph: Optional[CompiledStateGraph] = None
    
    @property
    def graph(self) -> CompiledStateGraph:
        """获取编译后的图，延迟初始化"""
        if self._graph is None:
            self.logger.info("构建LangGraph...")
            self._graph = self.build_graph()
            self.logger.info("LangGraph构建完成")
        return self._graph
    
    @abstractmethod
    def build_graph(self) -> CompiledStateGraph:
        """
        构建LangGraph状态图
        
        Returns:
            编译后的CompiledStateGraph
        """
        raise NotImplementedError
    
    @abstractmethod
    def prepare_input(self, **kwargs: Any) -> StateType:
        """
        准备输入状态
        
        Args:
            **kwargs: 原始输入参数
            
        Returns:
            初始化的状态字典
        """
        raise NotImplementedError
    
    @abstractmethod
    def process_output(self, state: StateType) -> Dict[str, Any]:
        """
        处理输出结果
        
        Args:
            state: 最终状态
            
        Returns:
            格式化的输出结果
        """
        raise NotImplementedError
    
    def run(self, **kwargs: Any) -> Dict[str, Any]:
        """
        同步执行Agent
        
        Args:
            **kwargs: 输入参数
            
        Returns:
            执行结果
        """
        start_time = time.time()
        task_id = kwargs.get("task_id", f"task-{self.name}-{int(time.time())}")
        
        self.logger.info(
            "Agent开始执行",
            extra={"task_id": task_id, "input_keys": list(kwargs.keys())},
        )
        
        try:
            # 准备输入
            input_state = self.prepare_input(**kwargs)
            input_state["task_id"] = task_id
            input_state["started_at"] = datetime.utcnow()
            input_state["trace"] = {"algorithms_used": [], "nodes_executed": []}
            input_state["errors"] = []
            
            # 执行图
            final_state = self.graph.invoke(input_state)
            
            # 记录完成时间
            final_state["completed_at"] = datetime.utcnow()
            
            # 处理输出
            result = self.process_output(final_state)
            
            execution_time_ms = (time.time() - start_time) * 1000
            result["execution_time_ms"] = round(execution_time_ms, 2)
            
            self.logger.info(
                "Agent执行完成",
                extra={
                    "task_id": task_id,
                    "execution_time_ms": execution_time_ms,
                    "has_errors": len(final_state.get("errors", [])) > 0,
                },
            )
            
            return result
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.logger.exception(
                "Agent执行失败",
                extra={"task_id": task_id, "error": str(e)},
            )
            raise
    
    async def arun(self, **kwargs: Any) -> Dict[str, Any]:
        """
        异步执行Agent
        
        Args:
            **kwargs: 输入参数
            
        Returns:
            执行结果
        """
        start_time = time.time()
        task_id = kwargs.get("task_id", f"task-{self.name}-{int(time.time())}")
        
        self.logger.info(
            "Agent开始异步执行",
            extra={"task_id": task_id, "input_keys": list(kwargs.keys())},
        )
        
        try:
            # 准备输入
            input_state = self.prepare_input(**kwargs)
            input_state["task_id"] = task_id
            input_state["started_at"] = datetime.utcnow()
            input_state["trace"] = {"algorithms_used": [], "nodes_executed": []}
            input_state["errors"] = []
            
            # 异步执行图
            final_state = await self.graph.ainvoke(input_state)
            
            # 记录完成时间
            final_state["completed_at"] = datetime.utcnow()
            
            # 处理输出
            result = self.process_output(final_state)
            
            execution_time_ms = (time.time() - start_time) * 1000
            result["execution_time_ms"] = round(execution_time_ms, 2)
            
            self.logger.info(
                "Agent异步执行完成",
                extra={
                    "task_id": task_id,
                    "execution_time_ms": execution_time_ms,
                    "has_errors": len(final_state.get("errors", [])) > 0,
                },
            )
            
            return result
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.logger.exception(
                "Agent异步执行失败",
                extra={"task_id": task_id, "error": str(e)},
            )
            raise
