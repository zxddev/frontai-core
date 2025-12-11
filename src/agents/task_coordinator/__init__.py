"""
Task Coordinator Agent

任务级协调智能体，负责将 emergency_ai 的任务分配
细化为步骤级的多队伍协作指令。

核心功能：
1. 匹配 SOP 模板（从 Neo4j 知识图谱）
2. 分解执行步骤
3. 分配队伍角色（主攻/配合/保障）
4. 匹配设备资源
5. 生成步骤级指令
"""

from .agent import create_task_coordinator_graph, run_task_coordinator

__all__ = [
    "create_task_coordinator_graph",
    "run_task_coordinator",
]
