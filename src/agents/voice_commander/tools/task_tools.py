"""
任务查询工具

提供任务状态查询、统计和列表功能。
调用 TaskService 获取任务数据。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.tools import tool

from src.core.database import AsyncSessionLocal
from src.domains.tasks.service import TaskService
from src.domains.tasks.schemas import TaskStatus, TaskType

logger = logging.getLogger(__name__)


# 任务状态中文映射
TASK_STATUS_CN: Dict[str, str] = {
    "created": "待分配",
    "assigned": "已分配",
    "accepted": "已接受",
    "in_progress": "执行中",
    "paused": "已暂停",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}

# 任务类型中文映射
TASK_TYPE_CN: Dict[str, str] = {
    "search": "搜索",
    "rescue": "救援",
    "evacuation": "疏散转移",
    "transport": "运输",
    "medical": "医疗救治",
    "supply": "物资配送",
    "reconnaissance": "侦察",
    "communication": "通信保障",
    "other": "其他",
}


@tool
async def query_task_summary() -> Dict[str, Any]:
    """
    查询任务统计摘要
    
    返回当前所有任务的状态分布和总体进度。
    用于回答"任务进度怎么样"、"有多少任务"等问题。
    
    Returns:
        任务统计信息:
        - total: 任务总数
        - by_status: 按状态分组的数量
        - in_progress_tasks: 进行中任务列表（名称）
        - completion_rate: 完成率百分比
    """
    logger.info("查询任务统计摘要")
    
    async with AsyncSessionLocal() as db:
        service = TaskService(db)
        
        # 获取所有任务
        task_list = await service.list(page=1, page_size=200)
        tasks = task_list.items
        
        # 按状态统计
        by_status: Dict[str, int] = {}
        in_progress_tasks: List[str] = []
        completed_count = 0
        
        for task in tasks:
            status = task.status
            by_status[status] = by_status.get(status, 0) + 1
            
            if status == "in_progress":
                in_progress_tasks.append(task.title)
            elif status == "completed":
                completed_count += 1
        
        # 计算完成率
        total = len(tasks)
        completion_rate = (completed_count / total * 100) if total > 0 else 0
        
        # 转换状态为中文
        by_status_cn = {
            TASK_STATUS_CN.get(k, k): v
            for k, v in by_status.items()
        }
        
        result = {
            "success": True,
            "total": total,
            "by_status": by_status_cn,
            "in_progress_count": len(in_progress_tasks),
            "in_progress_tasks": in_progress_tasks[:5],  # 最多显示5个
            "completed_count": completed_count,
            "completion_rate": round(completion_rate, 1),
        }
        
        logger.info(f"任务统计: total={total}, in_progress={len(in_progress_tasks)}, completion={completion_rate:.1f}%")
        return result


@tool
async def query_tasks_by_type(task_type: str) -> Dict[str, Any]:
    """
    按类型查询任务
    
    查询指定类型任务的数量和状态。
    用于回答"搜救任务有多少"、"侦察任务完成了吗"等问题。
    
    Args:
        task_type: 任务类型，可选值:
            - search: 搜索
            - rescue: 救援
            - evacuation: 疏散转移
            - transport: 运输
            - medical: 医疗救治
            - reconnaissance: 侦察
            
    Returns:
        该类型任务的统计和列表
    """
    logger.info(f"按类型查询任务: type={task_type}")
    
    # 标准化类型名
    type_mapping = {
        "搜救": "rescue",
        "搜索": "search",
        "救援": "rescue",
        "侦察": "reconnaissance",
        "转运": "transport",
        "运输": "transport",
        "医疗": "medical",
        "疏散": "evacuation",
    }
    normalized_type = type_mapping.get(task_type, task_type)
    
    async with AsyncSessionLocal() as db:
        service = TaskService(db)
        
        # 获取所有任务并筛选
        task_list = await service.list(page=1, page_size=200)
        
        # 按类型筛选
        filtered = [t for t in task_list.items if t.task_type == normalized_type]
        
        # 统计状态
        by_status: Dict[str, int] = {}
        task_names: List[str] = []
        
        for task in filtered:
            status = task.status
            by_status[status] = by_status.get(status, 0) + 1
            task_names.append(task.title)
        
        # 转换为中文
        by_status_cn = {
            TASK_STATUS_CN.get(k, k): v
            for k, v in by_status.items()
        }
        type_cn = TASK_TYPE_CN.get(normalized_type, normalized_type)
        
        result = {
            "success": True,
            "task_type": type_cn,
            "total": len(filtered),
            "by_status": by_status_cn,
            "task_names": task_names[:5],
        }
        
        logger.info(f"{type_cn}任务统计: total={len(filtered)}")
        return result


@tool
async def query_tasks_by_status(status: str) -> Dict[str, Any]:
    """
    按状态查询任务
    
    查询指定状态的任务列表。
    用于回答"有哪些任务在执行"、"完成了哪些任务"等问题。
    
    Args:
        status: 任务状态，可选值:
            - in_progress / 执行中
            - completed / 已完成
            - assigned / 已分配
            - created / 待分配
            
    Returns:
        该状态任务的列表
    """
    logger.info(f"按状态查询任务: status={status}")
    
    # 标准化状态名
    status_mapping = {
        "执行中": "in_progress",
        "进行中": "in_progress",
        "已完成": "completed",
        "完成": "completed",
        "已分配": "assigned",
        "待分配": "created",
        "待执行": "assigned",
    }
    normalized_status = status_mapping.get(status, status)
    
    async with AsyncSessionLocal() as db:
        service = TaskService(db)
        task_list = await service.list(page=1, page_size=200, status=normalized_status)
        
        tasks_info = []
        for task in task_list.items:
            # 获取执行者信息
            assignee_name = None
            if task.assignments:
                assignee_name = task.assignments[0].assignee_name
            
            tasks_info.append({
                "id": str(task.id),
                "title": task.title,
                "type": TASK_TYPE_CN.get(task.task_type, task.task_type),
                "assignee": assignee_name,
                "progress": task.progress_percent,
            })
        
        status_cn = TASK_STATUS_CN.get(normalized_status, normalized_status)
        
        result = {
            "success": True,
            "status": status_cn,
            "total": len(tasks_info),
            "tasks": tasks_info[:10],  # 最多返回10个
        }
        
        logger.info(f"{status_cn}任务: count={len(tasks_info)}")
        return result


@tool
async def get_task_detail(task_id: str) -> Dict[str, Any]:
    """
    获取任务详情
    
    查询指定任务的详细信息。
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务详细信息
    """
    logger.info(f"获取任务详情: task_id={task_id}")
    
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return {"success": False, "error": f"无效的任务ID: {task_id}"}
    
    async with AsyncSessionLocal() as db:
        service = TaskService(db)
        
        try:
            task = await service.get_by_id(task_uuid)
        except Exception as e:
            logger.warning(f"任务不存在: {task_id}")
            return {"success": False, "error": f"任务不存在: {task_id}"}
        
        # 获取执行者信息
        assignees = []
        for assignment in (task.assignments or []):
            assignees.append({
                "name": assignment.assignee_name,
                "type": assignment.assignee_type,
                "status": assignment.status,
            })
        
        result = {
            "success": True,
            "task": {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "type": TASK_TYPE_CN.get(task.task_type, task.task_type),
                "status": TASK_STATUS_CN.get(task.status, task.status),
                "priority": task.priority,
                "progress": task.progress_percent,
                "assignees": assignees,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            },
        }
        
        return result
