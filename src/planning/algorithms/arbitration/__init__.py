"""
冲突仲裁模块

功能:
1. 资源冲突消解 - 多任务竞争同一资源时的优先级仲裁
2. 场景优先级仲裁 - 多场景并发时的资源分配决策
"""

from .conflict_resolver import ConflictResolver
from .scene_arbitrator import SceneArbitrator

__all__ = ["ConflictResolver", "SceneArbitrator"]
