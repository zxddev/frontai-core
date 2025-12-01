"""
语音指挥Agent工具集

工具分类:
- spatial_tools: 空间查询工具（只读）
- command_tools: 控制指令工具（写操作）
- task_tools: 任务查询工具
- resource_tools: 资源查询工具
"""

from .spatial_tools import (
    find_entity_location,
    find_nearest_unit,
    get_area_status,
)
from .command_tools import (
    prepare_dispatch_command,
    execute_confirmed_command,
)
from .task_tools import (
    query_task_summary,
    query_tasks_by_type,
    query_tasks_by_status,
)
from .resource_tools import (
    query_team_status,
    query_available_teams,
    query_team_summary,
)

__all__ = [
    # 空间查询
    "find_entity_location",
    "find_nearest_unit",
    "get_area_status",
    # 控制指令
    "prepare_dispatch_command",
    "execute_confirmed_command",
    # 任务查询
    "query_task_summary",
    "query_tasks_by_type",
    "query_tasks_by_status",
    # 资源查询
    "query_team_status",
    "query_available_teams",
    "query_team_summary",
]
