"""
元任务库加载器

从Neo4j知识图谱加载元任务(MetaTask)配置。
"""
from __future__ import annotations

import logging
from typing import Dict, List, TypedDict, Any

logger = logging.getLogger(__name__)


# ============================================================================
# 类型定义
# ============================================================================

class TaskChainConfig(TypedDict):
    """任务链配置"""
    name: str                                  # 任务链名称
    description: str                           # 任务链描述
    tasks: List[str]                           # 任务ID列表
    dependencies: Dict[str, List[str]]         # 任务依赖关系 {task_id: [depends_on]}
    parallel_groups: List[List[str]]           # 可并行执行的任务组


class SceneDefinition(TypedDict):
    """场景定义"""
    name: str                                  # 场景名称
    description: str                           # 场景描述
    triggers: List[str]                        # 触发条件
    typical_tasks: List[str]                   # 典型任务列表
    priority_objectives: List[str]             # 优先目标


class MetaTaskDict(TypedDict, total=False):
    """元任务数据结构"""
    id: str
    name: str
    category: str
    phase: str
    effect: str
    precondition: str
    required_capabilities: List[str]
    outputs: List[str]
    typical_scenes: List[str]
    duration_min: int
    duration_max: int
    risk_level: str


# ============================================================================
# Neo4j元任务查询
# ============================================================================

def get_meta_task(task_id: str) -> MetaTaskDict:
    """
    从Neo4j获取元任务详情
    
    Args:
        task_id: 任务ID，如"EM06"
        
    Returns:
        元任务配置字典
        
    Raises:
        RuntimeError: Neo4j连接失败或任务不存在
    """
    from src.agents.emergency_ai.tools.kg_tools import _get_neo4j_driver
    
    driver = _get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run(
            'MATCH (m:MetaTask {id: $task_id}) RETURN m',
            {'task_id': task_id}
        )
        record = result.single()
        
        if not record:
            raise RuntimeError(f"Neo4j中元任务不存在: {task_id}")
        
        node_data: MetaTaskDict = dict(record['m'])
        logger.debug(f"从Neo4j获取元任务: {task_id} -> {node_data.get('name')}")
        return node_data
