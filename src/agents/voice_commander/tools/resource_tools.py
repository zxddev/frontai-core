"""
资源查询工具

提供队伍状态查询、空闲资源查询等功能。
调用 TeamService 和 TaskService 获取数据。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import text

from src.core.database import AsyncSessionLocal
from src.domains.resources.teams.service import TeamService
from src.domains.tasks.service import TaskService

logger = logging.getLogger(__name__)


# 队伍状态中文映射
TEAM_STATUS_CN: Dict[str, str] = {
    "standby": "待命",
    "deployed": "执行中",
    "resting": "休整中",
    "unavailable": "不可用",
}

# 队伍类型中文映射
TEAM_TYPE_CN: Dict[str, str] = {
    "fire": "消防",
    "medical": "医疗",
    "rescue": "救援",
    "police": "公安",
    "militia": "民兵",
    "volunteer": "志愿者",
}


@tool
async def query_team_status(team_name: str) -> Dict[str, Any]:
    """
    查询队伍状态
    
    查询指定队伍的当前状态和正在执行的任务。
    用于回答"消防队在干什么"、"一号车队状态"等问题。
    
    Args:
        team_name: 队伍名称或关键词（支持模糊匹配）
        
    Returns:
        队伍状态信息:
        - team: 队伍基本信息
        - current_tasks: 当前执行的任务
        - location: 位置信息
    """
    logger.info(f"查询队伍状态: name={team_name}")
    
    async with AsyncSessionLocal() as db:
        # 模糊查询队伍
        search_pattern = f"%{team_name}%"
        query = text("""
            SELECT 
                id, code, name, team_type, status,
                available_personnel, contact_person, contact_phone,
                ST_X(base_location::geometry) as lng,
                ST_Y(base_location::geometry) as lat,
                base_address
            FROM operational_v2.rescue_teams_v2
            WHERE name ILIKE :pattern OR code ILIKE :pattern
            LIMIT 5
        """)
        
        result = await db.execute(query, {"pattern": search_pattern})
        teams = result.fetchall()
        
        if not teams:
            return {
                "success": True,
                "found": False,
                "message": f"未找到名为'{team_name}'的队伍",
            }
        
        team = teams[0]
        team_id = team.id
        
        # 查询该队伍当前的任务
        task_service = TaskService(db)
        my_tasks = await task_service.get_my_tasks(
            assignee_type="team",
            assignee_id=team_id,
            status="in_progress",
        )
        
        current_tasks = []
        for task in my_tasks.items:
            current_tasks.append({
                "id": str(task.id),
                "title": task.title,
                "type": task.task_type,
                "progress": task.progress_percent,
            })
        
        team_info = {
            "id": str(team.id),
            "code": team.code,
            "name": team.name,
            "type": TEAM_TYPE_CN.get(team.team_type, team.team_type),
            "status": TEAM_STATUS_CN.get(team.status, team.status),
            "personnel": team.available_personnel,
            "location": {
                "lng": team.lng,
                "lat": team.lat,
                "address": team.base_address,
            } if team.lng and team.lat else None,
        }
        
        return {
            "success": True,
            "found": True,
            "team": team_info,
            "current_tasks": current_tasks,
            "task_count": len(current_tasks),
        }


@tool
async def query_available_teams(team_type: Optional[str] = None) -> Dict[str, Any]:
    """
    查询可用/空闲队伍
    
    查询当前处于待命状态的队伍列表。
    用于回答"还有哪些队伍可用"、"哪些队伍空闲"等问题。
    
    Args:
        team_type: 可选，队伍类型过滤（fire/medical/rescue等）
        
    Returns:
        可用队伍列表:
        - teams: 队伍列表（包含ID用于地图高亮）
        - total: 总数
    """
    logger.info(f"查询可用队伍: type={team_type}")
    
    # 标准化类型
    type_mapping = {
        "消防": "fire",
        "医疗": "medical",
        "救援": "rescue",
        "公安": "police",
    }
    normalized_type = type_mapping.get(team_type, team_type) if team_type else None
    
    async with AsyncSessionLocal() as db:
        team_service = TeamService(db)
        
        # 查询待命队伍
        available = await team_service.list_available(team_type=normalized_type)
        
        teams_info = []
        entity_ids = []
        
        for team in available:
            teams_info.append({
                "id": str(team.id),
                "name": team.name,
                "type": TEAM_TYPE_CN.get(team.team_type, team.team_type),
                "personnel": team.available_personnel,
            })
            # 地图实体ID格式：team-{uuid}
            entity_ids.append(f"team-{team.id}")
        
        type_cn = TEAM_TYPE_CN.get(normalized_type, "所有") if normalized_type else "所有"
        
        return {
            "success": True,
            "total": len(teams_info),
            "type_filter": type_cn,
            "teams": teams_info[:10],  # 最多返回10个
            "entity_ids": entity_ids[:10],  # 用于地图高亮
        }


@tool
async def query_team_summary() -> Dict[str, Any]:
    """
    查询队伍资源统计
    
    统计所有队伍的状态分布。
    用于回答"有多少队伍"、"资源情况怎么样"等问题。
    
    Returns:
        队伍统计信息:
        - total: 队伍总数
        - by_status: 按状态分组
        - by_type: 按类型分组
    """
    logger.info("查询队伍资源统计")
    
    async with AsyncSessionLocal() as db:
        # 统计查询
        query = text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'standby') as standby_count,
                COUNT(*) FILTER (WHERE status = 'deployed') as deployed_count,
                COUNT(*) FILTER (WHERE status = 'resting') as resting_count,
                SUM(available_personnel) as total_personnel
            FROM operational_v2.rescue_teams_v2
        """)
        
        result = await db.execute(query)
        stats = result.fetchone()
        
        # 按类型统计
        type_query = text("""
            SELECT team_type, COUNT(*) as count
            FROM operational_v2.rescue_teams_v2
            GROUP BY team_type
        """)
        
        type_result = await db.execute(type_query)
        type_stats = {
            TEAM_TYPE_CN.get(row.team_type, row.team_type): row.count
            for row in type_result.fetchall()
        }
        
        return {
            "success": True,
            "total": stats.total or 0,
            "by_status": {
                "待命": stats.standby_count or 0,
                "执行中": stats.deployed_count or 0,
                "休整中": stats.resting_count or 0,
            },
            "by_type": type_stats,
            "total_personnel": stats.total_personnel or 0,
            "available_count": stats.standby_count or 0,
        }
