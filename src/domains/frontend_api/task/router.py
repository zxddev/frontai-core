"""
前端任务API路由

接口路径: /tasks/*
对接前端任务相关操作
"""
from __future__ import annotations

import json
import logging
import uuid as uuid_lib
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db, AsyncSessionLocal
from src.core.dependencies import get_current_user
from src.core.stomp.broker import stomp_broker
from src.domains.tasks.service import TaskService
from src.domains.frontend_api.common import ApiResponse
from src.agents import get_frontline_rescue_agent
from src.infra.clients.amap.geocode import amap_regeo_async
from .schemas import (
    FrontendTask, TaskLogData, TaskLogCommitRequest,
    RescueTask, RescueDetailResponse, Location,
    RescuePoint, MultiRescueTaskDetail,
    UnitTask, EquipmentTask, TaskSendRequest,
    BatchRescueTaskRequest, BatchRescueTaskResponse, TaskCreateResult,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["前端-任务"])

# Redis配置（与 agents/router.py 保持一致）
EMERGENCY_RESULT_PREFIX = "emergency_ai_result:"


async def _get_ai_result_from_redis(event_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取AI分析结果"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        
        task_id = f"emergency-{event_id}"
        key = f"{EMERGENCY_RESULT_PREFIX}{task_id}"
        data = await redis_client.get(key)
        if data:
            logger.info(f"[multiRescueTask] 从Redis获取AI结果: event_id={event_id}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"[multiRescueTask] Redis读取失败: {e}")
        return None


async def _get_team_location_address(
    base_address: str,
    base_lng: float | None,
    base_lat: float | None,
) -> str:
    """
    获取队伍位置地址
    
    优先级：
    1. 数据库中的 base_address
    2. 调用高德逆地理编码
    3. 显示坐标 "坐标(lng, lat)"
    """
    # 1. 优先使用数据库中的地址
    if base_address and base_address.strip():
        return base_address.strip()
    
    # 2. 尝试逆地理编码
    if base_lng is not None and base_lat is not None:
        try:
            address = await amap_regeo_async(base_lng, base_lat)
            if address:
                return address
        except Exception as e:
            logger.warning(f"逆地理编码失败: ({base_lng}, {base_lat}), error={e}")
        
        # 3. 返回坐标
        return f"坐标({base_lng:.4f}, {base_lat:.4f})"
    
    return "位置未知"


def _extract_target_situation(ai_result: Dict[str, Any], event_description: str = "") -> str:
    """从AI结果提取目标情况"""
    parts = []
    parsed = ai_result.get("parsed_disaster", {})
    
    # 被困人数
    trapped = parsed.get("estimated_trapped", 0)
    if trapped > 0:
        parts.append(f"预估被困{trapped}人")
    
    # 现场情况
    if parsed.get("has_building_collapse"):
        parts.append("存在建筑倒塌")
    if parsed.get("has_trapped_persons") and trapped == 0:
        parts.append("有人员被困")
    
    # 如果没有从AI提取到，使用事件描述
    if not parts and event_description:
        return event_description[:100]  # 截取前100字符
    
    return "；".join(parts) if parts else ""


def _extract_risk_warnings(ai_result: Dict[str, Any]) -> List[str]:
    """从AI结果提取风险预警"""
    warnings = []
    parsed = ai_result.get("parsed_disaster", {})
    recommended = ai_result.get("recommended_scheme", {})
    
    # 次生灾害风险
    if parsed.get("has_secondary_fire"):
        warnings.append("存在次生火灾风险")
    if parsed.get("has_hazmat_leak"):
        warnings.append("存在危化品泄漏风险")
    if parsed.get("has_road_damage"):
        warnings.append("道路损毁，注意绕行")
    
    # 容量警告
    capacity_warning = recommended.get("capacity_warning")
    if capacity_warning:
        warnings.append(capacity_warning)
    
    # 多点分配警告
    multi_point = ai_result.get("multi_point_allocation", {})
    for w in multi_point.get("resource_warnings", []):
        warnings.append(w)
    
    return warnings


async def _extract_teams_from_ai_result(
    ai_result: Dict[str, Any],
    event_location: Location,
    event_address: str,
    event_description: str = "",
    team_contacts: Dict[str, Dict[str, str]] = None,
) -> tuple[List[UnitTask], str]:
    """
    从AI分析结果中提取队伍信息

    优先从 multi_point_allocation 获取，其次从 matching 或 recommended_scheme 获取

    Args:
        ai_result: AI分析结果
        event_location: 事件位置坐标
        event_address: 事件地址（用于前端显示）
        event_description: 事件描述（用于目标情况）
        team_contacts: 队伍联系人信息字典 {team_id: {contact_name, contact_phone}}

    Returns:
        (unit_tasks, source) - 队伍列表和来源标识
    """
    unit_tasks: List[UnitTask] = []
    team_contacts = team_contacts or {}
    
    # 提取目标情况和风险预警（所有队伍共享）
    target_situation = _extract_target_situation(ai_result, event_description)
    risk_warnings = _extract_risk_warnings(ai_result)
    
    # 1. 尝试从 multi_point_allocation 获取（多救援点模式）
    multi_point = ai_result.get("multi_point_allocation", {})
    if multi_point.get("enabled") and multi_point.get("rescue_points"):
        for point in multi_point.get("rescue_points", []):
            point_location = point.get("location", {})
            loc = Location(
                longitude=point_location.get("longitude", event_location.longitude),
                latitude=point_location.get("latitude", event_location.latitude),
            )
            # 多救援点模式下，使用救援点名称作为地址
            point_name = str(point.get("rescue_point_name", ""))
            point_address = point_name or event_address
            assigned_teams = point.get("assigned_teams", [])
            # 提取同组所有队伍名称（用于协作信息）
            all_team_names = [str(t.get("team_name", "")) for t in assigned_teams]
            
            for team in assigned_teams:
                current_team_name = str(team.get("team_name", ""))
                # 协作队伍 = 同组其他队伍
                collaborating = [n for n in all_team_names if n and n != current_team_name]
                
                # 获取队伍位置地址
                resource_state = team.get("resource_state", {})
                home_pos = resource_state.get("home_position", (None, None))
                base_lng = home_pos[0] if isinstance(home_pos, (list, tuple)) and len(home_pos) >= 2 else None
                base_lat = home_pos[1] if isinstance(home_pos, (list, tuple)) and len(home_pos) >= 2 else None
                team_loc = await _get_team_location_address(
                    str(team.get("base_address", "")), base_lng, base_lat
                )
                team_id = str(team.get("team_id", ""))
                contact_info = team_contacts.get(team_id, {})
                unit_tasks.append(UnitTask(
                    id=team_id,
                    name=current_team_name,
                    description=point_address,
                    team_location=team_loc,
                    location=loc,
                    equipments=[e.get("name", "") for e in team.get("equipments", []) if e.get("name")],
                    task_description=str(team.get("task_description", "")),
                    rescue_point_name=point_name,
                    target_situation=target_situation,
                    risk_warnings=risk_warnings,
                    commander_order="",
                    eta_minutes=float(team.get("eta_minutes", 0)),
                    collaborating_teams=collaborating,
                    contact_name=contact_info.get("contact_name", ""),
                    contact_phone=contact_info.get("contact_phone", ""),
                ))
        if unit_tasks:
            return unit_tasks, "ai_recommended"
    
    # 2. 尝试从 recommended_scheme 获取
    recommended = ai_result.get("recommended_scheme", {})
    allocations = recommended.get("allocations", [])
    if allocations:
        # 单点模式：所有队伍都是协作队伍
        all_team_names = [str(a.get("resource_name", a.get("team_name", ""))) for a in allocations]
        
        for alloc in allocations:
            current_team_name = str(alloc.get("resource_name", alloc.get("team_name", "")))
            collaborating = [n for n in all_team_names if n and n != current_team_name]
            
            # 获取队伍位置地址
            resource_state = alloc.get("resource_state", {})
            home_pos = resource_state.get("home_position", (None, None))
            base_lng = home_pos[0] if isinstance(home_pos, (list, tuple)) and len(home_pos) >= 2 else None
            base_lat = home_pos[1] if isinstance(home_pos, (list, tuple)) and len(home_pos) >= 2 else None
            team_loc = await _get_team_location_address(
                str(alloc.get("base_address", "")), base_lng, base_lat
            )
            team_id = str(alloc.get("resource_id", alloc.get("team_id", "")))
            contact_info = team_contacts.get(team_id, {})
            unit_tasks.append(UnitTask(
                id=team_id,
                name=current_team_name,
                description=event_address,
                team_location=team_loc,
                location=event_location,
                equipments=[e.get("name", "") for e in alloc.get("equipments", []) if e.get("name")],
                task_description=str(alloc.get("task_description", "")),
                rescue_point_name="",
                target_situation=target_situation,
                risk_warnings=risk_warnings,
                commander_order="",
                eta_minutes=float(alloc.get("eta_minutes", 0)),
                collaborating_teams=collaborating,
                contact_name=contact_info.get("contact_name", ""),
                contact_phone=contact_info.get("contact_phone", ""),
            ))
        if unit_tasks:
            return unit_tasks, "ai_recommended"
    
    # 3. 尝试从 matching.candidates_detail 获取
    matching = ai_result.get("matching", {})
    candidates_detail = matching.get("candidates_detail", [])
    if candidates_detail:
        all_team_names = [str(c.get("resource_name", "")) for c in candidates_detail]

        for candidate in candidates_detail:
            current_team_name = str(candidate.get("resource_name", ""))
            collaborating = [n for n in all_team_names if n and n != current_team_name]
            team_id = str(candidate.get("resource_id", ""))
            contact_info = team_contacts.get(team_id, {})

            unit_tasks.append(UnitTask(
                id=team_id,
                name=current_team_name,
                description=event_address,
                team_location="位置未知",
                location=event_location,
                equipments=[],
                task_description="",
                rescue_point_name="",
                target_situation=target_situation,
                risk_warnings=risk_warnings,
                commander_order="",
                eta_minutes=float(candidate.get("eta_minutes", 0)),
                collaborating_teams=collaborating,
                contact_name=contact_info.get("contact_name", ""),
                contact_phone=contact_info.get("contact_phone", ""),
            ))
        if unit_tasks:
            return unit_tasks, "ai_recommended"

    return [], ""


def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    """获取任务服务实例"""
    return TaskService(db)


STATUS_MAP_TO_FRONTEND = {
    "created": "PENDING",
    "assigned": "ASSIGNED",
    "accepted": "ASSIGNED",
    "in_progress": "IN_PROGRESS",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
}

STATUS_MAP_FROM_FRONTEND = {
    "PENDING": "created",
    "ASSIGNED": "assigned",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
}


@router.post("/send", response_model=ApiResponse)
async def tasks_send(
    request: TaskSendRequest,
    service: TaskService = Depends(get_task_service),
) -> ApiResponse:
    """
    侦察任务指令下发
    
    将生成的侦察任务下发给相应设备执行
    """
    logger.info(f"任务下发, schemeId={request.id}, eventId={request.eventId}")
    
    task_count = sum(len(t.taskList) for t in request.task)
    logger.info(f"下发任务数量: {task_count}")
    
    return ApiResponse.success({"taskCount": task_count}, "任务下发成功")


@router.post("/task-list-detail", response_model=ApiResponse[list[FrontendTask]])
async def task_list_detail(
    service: TaskService = Depends(get_task_service),
) -> ApiResponse[list[FrontendTask]]:
    """
    获取任务列表 - 对接v2真实数据
    
    返回所有已下发任务的列表
    """
    logger.info("获取任务列表")
    
    try:
        tasks = await service.list(page=1, page_size=100)
        
        result = []
        for task in tasks.items:
            frontend_status = STATUS_MAP_TO_FRONTEND.get(task.status, "PENDING")
            
            # 构建任务日志
            log_list = [
                TaskLogData(
                    timestamp=task.created_at.isoformat() if task.created_at else "",
                    origin="系统",
                    description=f"任务创建: {task.title}"
                )
            ]
            
            # 添加分配日志
            if task.assignments:
                for assignment in task.assignments:
                    if assignment.assigned_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.assigned_at.isoformat(),
                            origin="调度员",
                            description=f"任务分配给: {assignment.assignee_name or '执行者'}"
                        ))
                    if assignment.accepted_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.accepted_at.isoformat(),
                            origin=assignment.assignee_name or "执行者",
                            description="任务已接受"
                        ))
                    if assignment.started_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.started_at.isoformat(),
                            origin=assignment.assignee_name or "执行者",
                            description="开始执行任务"
                        ))
                    if assignment.completed_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.completed_at.isoformat(),
                            origin=assignment.assignee_name or "执行者",
                            description=assignment.completion_summary or "任务已完成"
                        ))
            
            # 按时间排序日志
            log_list.sort(key=lambda x: x.timestamp)
            
            result.append(FrontendTask(
                id=str(task.id),
                title=task.title,
                description=task.description or "",
                status=frontend_status,
                createdAt=task.created_at.isoformat() if task.created_at else "",
                deadline=task.planned_end_at.isoformat() if task.planned_end_at else None,
                taskLogDataList=log_list,
            ))
        
        logger.info(f"返回任务数量: {len(result)}")
        return ApiResponse.success(result)
        
    except Exception as e:
        logger.exception(f"获取任务列表失败: {e}")
        return ApiResponse.success([])


@router.post("/task-log-commit", response_model=ApiResponse)
async def task_log_commit(
    request: TaskLogCommitRequest,
    service: TaskService = Depends(get_task_service),
) -> ApiResponse:
    """
    任务日志提交/状态更新
    
    记录任务状态变更，支持结束任务等操作
    """
    logger.info(f"任务状态更新, taskId={request.taskId}, status={request.status}")
    
    try:
        task_uuid = UUID(request.taskId)
        
        if request.status == "COMPLETED":
            await service.complete_direct(task_uuid, completion_summary=request.description)
            logger.info(f"任务完成, taskId={request.taskId}")
        elif request.status == "CANCELLED":
            await service.cancel(task_uuid, reason=request.description)
            logger.info(f"任务取消, taskId={request.taskId}")
        
        return ApiResponse.success(None, "操作成功")
        
    except ValueError as e:
        logger.warning(f"无效的任务ID: {e}")
        return ApiResponse.error(400, f"无效的任务ID: {str(e)}")
    except Exception as e:
        logger.exception(f"任务状态更新失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


@router.post("/rescueTask", response_model=ApiResponse[BatchRescueTaskResponse])
async def rescue_task(
    request: BatchRescueTaskRequest,
) -> ApiResponse[BatchRescueTaskResponse]:
    """
    批量执行救援任务 - 真正的任务创建入口
    
    业务逻辑：
    1. 检查每个事件是否已有任务（防重复）
    2. 创建 tasks_v2 记录
    3. 创建 task_assignments_v2 记录
    4. 更新 rescue_teams_v2 状态为 deployed
    5. 更新 events_v2 状态为 executing
    
    Args:
        request: 批量执行请求，包含 scenario_id 和任务列表
        
    Returns:
        执行结果，包含成功/跳过/失败的任务信息
    """
    logger.info(f"[rescueTask] 批量执行救援任务, scenario_id={request.scenario_id}, tasks={len(request.tasks)}")
    
    results: List[TaskCreateResult] = []
    created_count = 0
    skipped_count = 0
    
    async with AsyncSessionLocal() as db:
        try:
            for task_item in request.tasks:
                event_id = task_item.event_id
                
                # ========== 1. 检查事件是否已有任务（防重复） ==========
                check_existing = text("""
                    SELECT COUNT(*) FROM operational_v2.tasks_v2
                    WHERE event_id = :event_id AND status NOT IN ('cancelled', 'failed')
                """)
                existing_result = await db.execute(check_existing, {"event_id": event_id})
                existing_count = existing_result.scalar()
                
                if existing_count and existing_count > 0:
                    logger.info(f"[rescueTask] 事件 {event_id} 已有任务，跳过")
                    results.append(TaskCreateResult(
                        event_id=event_id,
                        task_id="",
                        success=False,
                        skipped=True,
                        reason="该事件已有进行中的任务",
                    ))
                    skipped_count += 1
                    continue
                
                # ========== 2. 获取事件信息 ==========
                event_query = text("""
                    SELECT id, scenario_id, title, description, priority, address,
                           ST_X(location::geometry) as lng, ST_Y(location::geometry) as lat
                    FROM operational_v2.events_v2
                    WHERE id = :event_id
                """)
                event_result = await db.execute(event_query, {"event_id": event_id})
                event_row = event_result.fetchone()
                
                if not event_row:
                    logger.warning(f"[rescueTask] 事件 {event_id} 不存在")
                    results.append(TaskCreateResult(
                        event_id=event_id,
                        task_id="",
                        success=False,
                        skipped=False,
                        reason="事件不存在",
                    ))
                    continue
                
                scenario_id = str(event_row.scenario_id) if event_row.scenario_id else request.scenario_id
                event_title = event_row.title or "救援任务"
                event_description = event_row.description or ""
                event_priority = event_row.priority or "medium"
                event_lng = event_row.lng or 0
                event_lat = event_row.lat or 0
                
                # ========== 3. 获取下一个任务编号 ==========
                code_query = text("""
                    SELECT COALESCE(MAX(CAST(SUBSTRING(task_code FROM 5) AS INTEGER)), 0) + 1
                    FROM operational_v2.tasks_v2
                    WHERE scenario_id = :scenario_id
                """)
                code_result = await db.execute(code_query, {"scenario_id": scenario_id})
                next_code = code_result.scalar() or 1
                
                # ========== 4. 创建任务记录 ==========
                new_task_id = uuid_lib.uuid4()
                task_code = f"TSK-{next_code:04d}"
                task_title = task_item.title if task_item.title else f"{event_title} - 救援任务"

                # 构建任务描述：使用事件情况描述
                team_names = ", ".join([u.name for u in task_item.units if u.name])
                task_description = event_description or f"针对事件'{event_title}'的救援任务"
                
                insert_task = text("""
                    INSERT INTO operational_v2.tasks_v2 (
                        id, scenario_id, event_id, task_code, task_type,
                        title, description, status, priority,
                        target_location, created_at, updated_at
                    ) VALUES (
                        :id, :scenario_id, :event_id, :task_code, 'rescue',
                        :title, :description, 'assigned', :priority,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                        now(), now()
                    )
                """)
                await db.execute(insert_task, {
                    "id": str(new_task_id),
                    "scenario_id": scenario_id,
                    "event_id": event_id,
                    "task_code": task_code,
                    "title": task_title,
                    "description": task_description,
                    "priority": event_priority,
                    "lng": event_lng,
                    "lat": event_lat,
                })
                
                logger.info(f"[rescueTask] 创建任务 task_id={new_task_id}, task_code={task_code}")
                
                # ========== 5. 创建分配记录 ==========
                for unit in task_item.units:
                    if not unit.id:
                        continue

                    assignment_id = uuid_lib.uuid4()

                    # 构建mission_detail JSON
                    mission_detail_json = {}
                    if unit.mission_detail:
                        mission_detail_json = unit.mission_detail.model_dump()
                    elif unit.description or unit.commander_order:
                        # 兼容老版本：从description和commander_order构建
                        mission_detail_json = {
                            "task_description": unit.description,
                            "commander_order": unit.commander_order,
                        }

                    # 任务分配状态必须为 pending，service.py:105 的 accept 方法检查此状态
                    insert_assignment = text("""
                        INSERT INTO operational_v2.task_assignments_v2 (
                            id, task_id, assignee_type, assignee_id, assignee_name,
                            status, assignment_source, assignment_reason, mission_detail,
                            assigned_at, assigned_by
                        ) VALUES (
                            :id, :task_id, 'team', :assignee_id, :assignee_name,
                            'pending', 'command_dispatch', :reason, :mission_detail::jsonb,
                            now(), null
                        )
                    """)
                    await db.execute(insert_assignment, {
                        "id": str(assignment_id),
                        "task_id": str(new_task_id),
                        "assignee_id": unit.id,
                        "assignee_name": unit.name,
                        "reason": unit.commander_order or unit.description or "批量下发任务",
                        "mission_detail": json.dumps(mission_detail_json, ensure_ascii=False),
                    })
                    
                    # ========== 6. 更新队伍状态 ==========
                    update_team = text("""
                        UPDATE operational_v2.rescue_teams_v2
                        SET status = 'deployed', current_task_id = :task_id, updated_at = now()
                        WHERE id = :team_id
                    """)
                    await db.execute(update_team, {
                        "team_id": unit.id,
                        "task_id": str(new_task_id),
                    })
                    
                    logger.info(f"[rescueTask] 分配队伍 {unit.name} ({unit.id}) 到任务 {task_code}")

                    # ========== 6.1 STOMP推送任务给队伍关联用户 ==========
                    user_query = text("""
                        SELECT u.id as user_id
                        FROM operational_v2.users_v2 u
                        JOIN operational_v2.rescue_teams_v2 t
                            ON REGEXP_REPLACE(u.phone, '[\\s\\-+]', '', 'g') =
                               REGEXP_REPLACE(t.contact_phone, '[\\s\\-+]', '', 'g')
                        WHERE t.id = :team_id
                    """)
                    user_result = await db.execute(user_query, {"team_id": unit.id})
                    user_rows = user_result.fetchall()

                    if user_rows:
                        task_push_data = {
                            "task_id": str(new_task_id),
                            "event_id": event_id,
                            "task_code": task_code,
                            "title": task_title,
                            "priority": event_priority,
                            "target_location": {"longitude": event_lng, "latitude": event_lat},
                            "target_address": str(event_row.address or ""),
                            "units": [{"team_id": unit.id, "team_name": unit.name}],
                            "created_at": datetime.utcnow().isoformat(),
                            "scenario_id": scenario_id,
                        }
                        push_success = False
                        for user_row in user_rows:
                            try:
                                await stomp_broker.send_to_user(
                                    str(user_row.user_id),
                                    "/task/assigned",
                                    task_push_data
                                )
                                logger.info(f"[rescueTask] STOMP推送任务给用户 {user_row.user_id}")
                                push_success = True
                            except Exception as push_err:
                                logger.warning(f"[rescueTask] STOMP推送失败: {push_err}")

                        # 推送成功后更新 notified_at 字段，记录通知时间
                        if push_success:
                            update_notified = text("""
                                UPDATE operational_v2.task_assignments_v2
                                SET notified_at = now()
                                WHERE id = :assignment_id
                            """)
                            await db.execute(update_notified, {"assignment_id": str(assignment_id)})
                            logger.info(f"[rescueTask] 更新分配 {assignment_id} 的 notified_at")

                # ========== 7. 更新事件状态 ==========
                # 枚举值: pending, pre_confirmed, confirmed, planning, executing, resolved, escalated, cancelled
                update_event = text("""
                    UPDATE operational_v2.events_v2
                    SET status = 'executing', updated_at = now()
                    WHERE id = :event_id AND status NOT IN ('resolved', 'cancelled')
                """)
                await db.execute(update_event, {"event_id": event_id})
                
                results.append(TaskCreateResult(
                    event_id=event_id,
                    task_id=str(new_task_id),
                    success=True,
                    skipped=False,
                    reason="",
                ))
                created_count += 1
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            logger.exception(f"[rescueTask] 批量执行失败: {e}")
            return ApiResponse.error(500, f"批量执行失败: {str(e)}")
    
    response = BatchRescueTaskResponse(
        total=len(request.tasks),
        created=created_count,
        skipped=skipped_count,
        results=results,
    )
    
    logger.info(f"[rescueTask] 执行完成: 总数={len(request.tasks)}, 创建={created_count}, 跳过={skipped_count}")
    return ApiResponse.success(response, f"成功下发 {created_count} 个任务")


class EventIdRequest(BaseModel):
    """事件ID请求"""
    eventId: str


async def _get_user_type_and_team_id(
    db: AsyncSession,
    user_id: UUID,
) -> tuple[str | None, UUID | None]:
    """
    获取用户类型和关联的救援队伍ID

    通过 users_v2.phone = rescue_teams_v2.contact_phone 关联
    手机号规范化处理：去除空格、连字符、加号等字符

    Args:
        db: 数据库会话
        user_id: 用户ID

    Returns:
        (user_type, team_id): 用户类型和队伍ID，external_team用户才有team_id
    """
    sql = text("""
        SELECT u.user_type, t.id as team_id
        FROM operational_v2.users_v2 u
        LEFT JOIN operational_v2.rescue_teams_v2 t
            ON REGEXP_REPLACE(u.phone, '[\\s\\-+]', '', 'g') =
               REGEXP_REPLACE(t.contact_phone, '[\\s\\-+]', '', 'g')
        WHERE u.id = :user_id
    """)
    result = await db.execute(sql, {"user_id": str(user_id)})
    row = result.fetchone()
    if not row:
        logger.warning(f"[_get_user_type_and_team_id] 用户不存在: user_id={user_id}")
        return (None, None)

    team_id = UUID(str(row.team_id)) if row.team_id else None
    logger.info(
        f"[_get_user_type_and_team_id] user_id={user_id}, "
        f"user_type={row.user_type}, team_id={team_id}"
    )
    return (row.user_type, team_id)


async def _get_team_assigned_event_ids(
    db: AsyncSession,
    team_id: UUID,
) -> set[str]:
    """
    获取队伍被分配任务所关联的事件ID列表

    通过 task_assignments_v2 → tasks_v2 获取 event_id

    Args:
        db: 数据库会话
        team_id: 队伍ID

    Returns:
        事件ID集合
    """
    sql = text("""
        SELECT DISTINCT t.event_id::text
        FROM operational_v2.task_assignments_v2 ta
        JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
        WHERE ta.assignee_type = 'team'
          AND ta.assignee_id = :team_id
          AND t.event_id IS NOT NULL
    """)
    result = await db.execute(sql, {"team_id": str(team_id)})
    event_ids = {row.event_id for row in result.fetchall()}
    logger.info(
        f"[_get_team_assigned_event_ids] team_id={team_id}, "
        f"event_count={len(event_ids)}"
    )
    return event_ids


async def _get_team_assigned_events(
    db: AsyncSession,
    team_id: UUID,
) -> list[dict[str, Any]]:
    """
    获取队伍被分配任务所关联的事件详情列表

    直接查询已分配给队伍的事件，包含事件的完整信息
    用于 external_team 用户查看自己的任务

    Args:
        db: 数据库会话
        team_id: 队伍ID

    Returns:
        事件详情列表
    """
    sql = text("""
        SELECT DISTINCT
            e.id,
            e.scenario_id,
            e.event_code,
            e.event_type,
            e.source_type,
            e.title,
            e.description,
            e.address,
            e.status,
            e.priority,
            e.estimated_victims,
            e.reported_at,
            ST_X(e.location::geometry) AS longitude,
            ST_Y(e.location::geometry) AS latitude
        FROM operational_v2.task_assignments_v2 ta
        JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
        JOIN operational_v2.events_v2 e ON t.event_id = e.id
        WHERE ta.assignee_type = 'team'
          AND ta.assignee_id = :team_id
          AND t.event_id IS NOT NULL
          AND t.status NOT IN ('cancelled', 'failed', 'completed')
    """)
    result = await db.execute(sql, {"team_id": str(team_id)})
    rows = result.fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        events.append({
            "id": str(row.id),
            "scenario_id": str(row.scenario_id) if row.scenario_id else None,
            "event_code": row.event_code,
            "event_type": row.event_type,
            "source_type": row.source_type,
            "title": row.title,
            "description": row.description or "",
            "address": row.address,
            "status": row.status,
            "priority": row.priority,
            "estimated_victims": row.estimated_victims or 0,
            "reported_at": row.reported_at.isoformat() if row.reported_at else None,
            "longitude": float(row.longitude) if row.longitude else None,
            "latitude": float(row.latitude) if row.latitude else None,
        })

    # 按优先级排序: critical(1) > high(2) > medium(3) > low(4)，同优先级按上报时间倒序
    priority_order = {"critical": 1, "high": 2, "medium": 3, "low": 4}
    events.sort(
        key=lambda e: (
            priority_order.get(str(e.get("priority")), 5),
            "" if e.get("reported_at") is None else e.get("reported_at"),
        ),
        reverse=False,
    )
    # 同优先级内按时间倒序（上面的排序是升序，需要二次处理）
    # 使用稳定排序特性：先按时间倒序，再按优先级升序
    events.sort(key=lambda e: e.get("reported_at") or "", reverse=True)
    events.sort(key=lambda e: priority_order.get(str(e.get("priority")), 5))

    logger.info(
        f"[_get_team_assigned_events] team_id={team_id}, "
        f"event_count={len(events)}"
    )
    return events


# 优先级到level的映射
PRIORITY_LEVEL_MAP = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}

# 事件来源映射
SOURCE_TYPE_MAP = {
    "manual_report": "人工上报",
    "ai_detection": "AI识别",
    "sensor_alert": "传感器告警",
    "system_inference": "系统推演",
    "external_system": "外部系统",
}


@router.post("/multi-rescue-scheme", response_model=ApiResponse[list[RescuePoint]])
async def multi_rescue_scheme(
    scenarioId: str | None = Form(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[RescuePoint]]:
    """
    一线救援行动方案

    根据用户角色返回不同的事件列表：
    - internal 用户（指挥调度）：通过 FrontlineRescueAgent 获取待调度事件
    - external_team 用户（救援队伍）：直接查询已分配给自己队伍的事件

    业务逻辑：
    1. 获取用户类型和关联队伍
    2. external_team 用户直接查询已分配事件（绕过 Agent）
    3. internal 用户通过 Agent 获取待调度事件
    """
    user_id = UUID(current_user["sub"])
    logger.info(
        f"[multiRescueScheme] 请求: user_id={user_id}, scenario_id={scenarioId}"
    )

    # 获取用户类型和关联队伍
    user_type, team_id = await _get_user_type_and_team_id(db, user_id)
    logger.info(
        f"[multiRescueScheme] 用户角色: user_type={user_type}, team_id={team_id}"
    )

    # external_team 用户：直接查询已分配的事件（不经过 Agent）
    if user_type == "external_team" and team_id:
        assigned_events = await _get_team_assigned_events(db, team_id)
        if not assigned_events:
            logger.info(
                f"[multiRescueScheme] external_team 用户无分配事件，返回空列表"
            )
            return ApiResponse.success([])

        rescue_points: list[RescuePoint] = []
        for ev in assigned_events:
            lon = ev.get("longitude")
            lat = ev.get("latitude")
            if lon is None or lat is None:
                continue

            location = Location(longitude=float(lon), latitude=float(lat))
            priority = str(ev.get("priority") or "medium")
            level = PRIORITY_LEVEL_MAP.get(priority, 3)
            origin = SOURCE_TYPE_MAP.get(str(ev.get("source_type")), "系统")
            time_str = str(ev.get("reported_at") or datetime.now().isoformat())

            rescue_point = RescuePoint(
                level=level,
                title=str(ev.get("title", "")),
                origin=origin,
                time=time_str,
                locationName=str(ev.get("address") or f"坐标({lon:.4f}, {lat:.4f})"),
                location=location,
                image="",
                schema_="",
                description=str(ev.get("description", "")),
                id=str(ev.get("id", "")),
            )
            rescue_points.append(rescue_point)

        logger.info(
            f"[multiRescueScheme] external_team 返回已分配事件: {len(rescue_points)}"
        )
        return ApiResponse.success(rescue_points)

    # internal 用户：通过 Agent 获取待调度事件
    try:
        agent = get_frontline_rescue_agent()
        result = await agent.plan(scenarioId)
    except Exception as e:  # noqa: BLE001
        logger.exception("获取一线救援行动方案失败")
        return ApiResponse.error(500, f"获取方案失败: {e}")

    if result.get("status") == "failed":
        errors = ", ".join(result.get("errors") or [])
        logger.error("FrontlineRescueAgent failed: %s", errors)
        return ApiResponse.error(500, f"前线救援调度失败: {errors or '未知错误'}")

    events = result.get("prioritized_events") or []
    if not events:
        logger.info("未找到待处理事件")
        return ApiResponse.success([])

    rescue_points: list[RescuePoint] = []

    for ev in events:
        lon = ev.get("longitude")
        lat = ev.get("latitude")
        if lon is None or lat is None:
            continue

        location = Location(longitude=float(lon), latitude=float(lat))

        bucket = str(ev.get("priority_bucket") or ev.get("priority") or "medium")
        level = PRIORITY_LEVEL_MAP.get(
            bucket,
            PRIORITY_LEVEL_MAP.get(str(ev.get("priority", "medium")), 3),
        )

        origin = SOURCE_TYPE_MAP.get(str(ev.get("source_type")), "系统")
        time_str = str(ev.get("reported_at") or datetime.now().isoformat())

        # base_schema = _generate_default_scheme(
        #     event_type=str(ev.get("event_type", "other")),
        #     title=str(ev.get("title", "")),
        #     estimated_victims=int(ev.get("estimated_victims") or 0),
        # )
        # 不返回默认方案，由前端通过AI接口查询
        base_schema = ""

        score = float(ev.get("score", 0.0) or 0.0)
        reasons = ev.get("reasons") or []
        header_lines = [f"[priority={bucket}, score={score:.2f}]"]
        if reasons:
            header_lines.append("原因:")
            header_lines.extend([f"- {r}" for r in reasons])

        # 如果没有base_schema，schema_text也留空，让前端去轮询
        # schema_text = "\n".join(header_lines) + "\n\n" + base_schema
        schema_text = ""

        rescue_point = RescuePoint(
            level=level,
            title=str(ev.get("title", "")),
            origin=origin,
            time=time_str,
            locationName=str(ev.get("address") or f"坐标({lon:.4f}, {lat:.4f})"),
            location=location,
            image="",
            schema_=schema_text,
            description=str(ev.get("description", "")),
            id=str(ev.get("id", "")),
        )
        rescue_points.append(rescue_point)

    # internal 用户返回所有待调度事件
    total_count = len(rescue_points)
    logger.info(f"[multiRescueScheme] internal 用户返回待调度事件: {total_count}")
    return ApiResponse.success(rescue_points)


def _generate_default_scheme(event_type: str, title: str, estimated_victims: int) -> str:
    """根据事件类型生成默认救援方案描述"""
    schemes = {
        "trapped_person": f"立即调派搜救队携带生命探测仪进行搜救。预计被困{estimated_victims}人，需破拆工具和医疗支援。",
        "fire": "调派消防救援队进行灭火作业，同时组织人员疏散。注意防护装备和水源保障。",
        "flood": "调派水上救援队携带冲锋舟、救生设备进行救援。注意水流情况，确保救援人员安全。",
        "landslide": "调派搜救队和工程抢险队，使用生命探测仪搜索被埋人员。注意二次滑坡风险。",
        "building_collapse": f"调派消防救援队携带破拆工具、生命探测仪进行搜救。预计被困{estimated_victims}人。",
        "road_damage": "调派工程抢险队进行道路抢修，设置警示标志，引导车辆绕行。",
        "power_outage": "调派电力抢修队恢复供电，优先保障医院、指挥中心等重要设施。",
        "communication_lost": "调派通信保障队架设应急通信设备，恢复通信网络。",
        "hazmat_leak": "调派危化品处置队进行泄漏处置，划定警戒区域，组织群众疏散。",
        "epidemic": "调派医疗防疫队进行消杀处置，设置隔离区，做好人员防护。",
        "earthquake_secondary": f"调派综合救援力量处置次生灾害。预计受影响{estimated_victims}人。",
    }
    return schemes.get(event_type, f"针对{title}制定专项救援方案，调派相应救援力量。")


@router.post("/multi-rescue-task", response_model=ApiResponse[list[MultiRescueTaskDetail]])
async def multi_rescue_task(
    scenarioId: str = Form(None),
) -> ApiResponse[list[MultiRescueTaskDetail]]:
    """
    一线救援行动任务（草案生成）
    
    生成救援任务草案，供指挥员审核后通过 rescueTask 接口正式下发。
    
    业务逻辑：
    1. 获取待处理事件列表
    2. 对每个事件，优先读取 Redis 中的 AI 分析结果
    3. 无 AI 结果时，使用 frontline_rescue 快速分配作为建议
    4. 返回带有 event_id 的草案列表（不创建数据库记录）
    
    返回的 source 字段标识方案来源：
    - ai_recommended: 使用 EmergencyAI 分析结果
    - quick_recommended: 使用 frontline_rescue 快速分配
    """
    logger.info(f"[multiRescueTask] 生成救援任务草案, scenarioId={scenarioId}")

    # if not scenarioId:
    #     return ApiResponse.error(400, "scenarioId is required")

    try:
        agent = get_frontline_rescue_agent()
        result = await agent.plan(scenarioId)
    except Exception as e:  # noqa: BLE001
        logger.exception("[multiRescueTask] 获取事件列表失败")
        return ApiResponse.error(500, f"生成任务失败: {e}")

    if result.get("status") == "failed":
        errors = ", ".join(result.get("errors") or [])
        logger.error("[multiRescueTask] FrontlineRescueAgent failed: %s", errors)
        return ApiResponse.error(500, f"前线救援调度失败: {errors or '未知错误'}")

    events = result.get("prioritized_events") or []
    allocations = result.get("event_allocations") or []

    # 建立 event_id -> allocation 的索引（frontline 分配结果）
    alloc_by_event: dict[str, Any] = {a.get("event_id"): a for a in allocations}

    # ========== 批量查询队伍联系人信息 ==========
    # 收集所有涉及的team_id（从frontline分配结果）
    all_team_ids: set[str] = set()
    for alloc in allocations:
        for team in alloc.get("allocations") or []:
            tid = team.get("team_id")
            if tid:
                all_team_ids.add(str(tid))

    # 同时从AI结果中收集team_id，并缓存AI结果避免后续重复读取
    ai_results_cache: dict[str, dict[str, Any]] = {}
    for ev in events:
        ev_id = str(ev.get("id") or "")
        if not ev_id:
            continue
        ai_result = await _get_ai_result_from_redis(ev_id)
        if ai_result and ai_result.get("success"):
            ai_results_cache[ev_id] = ai_result
            # 从 multi_point_allocation 收集
            mp = ai_result.get("multi_point_allocation", {})
            if mp.get("enabled"):
                for point in mp.get("rescue_points", []):
                    for team in point.get("assigned_teams", []):
                        tid = team.get("team_id")
                        if tid:
                            all_team_ids.add(str(tid))
            # 从 recommended_scheme 收集
            rec = ai_result.get("recommended_scheme", {})
            for alloc_item in rec.get("allocations", []):
                tid = alloc_item.get("resource_id") or alloc_item.get("team_id")
                if tid:
                    all_team_ids.add(str(tid))
            # 从 matching.candidates_detail 收集
            matching = ai_result.get("matching", {})
            for candidate in matching.get("candidates_detail", []):
                tid = candidate.get("resource_id")
                if tid:
                    all_team_ids.add(str(tid))

    # 查询联系人信息
    team_contacts: dict[str, dict[str, str]] = {}
    if all_team_ids:
        try:
            async with AsyncSessionLocal() as db:
                contact_sql = text("""
                    SELECT id::text, contact_person, contact_phone
                    FROM operational_v2.rescue_teams_v2
                    WHERE id = ANY(:team_ids)
                """)
                contact_result = await db.execute(contact_sql, {"team_ids": list(all_team_ids)})
                for row in contact_result.fetchall():
                    team_contacts[row.id] = {
                        "contact_name": row.contact_person or "",
                        "contact_phone": row.contact_phone or "",
                    }
                logger.info(f"[multiRescueTask] 查询到 {len(team_contacts)} 个队伍联系人")
        except Exception as e:
            logger.warning(f"[multiRescueTask] 查询队伍联系人失败: {e}")

    details: list[MultiRescueTaskDetail] = []

    for ev in events:
        ev_id = str(ev.get("id") or "")
        if not ev_id:
            continue

        lon = ev.get("longitude")
        lat = ev.get("latitude")
        if lon is None or lat is None:
            continue

        location = Location(longitude=float(lon), latitude=float(lat))

        bucket = str(ev.get("priority_bucket") or ev.get("priority") or "medium")
        level = PRIORITY_LEVEL_MAP.get(
            bucket,
            PRIORITY_LEVEL_MAP.get(str(ev.get("priority", "medium")), 3),
        )

        # 事件地址（用于前端显示）
        event_address = str(ev.get("address") or f"坐标({lon:.4f}, {lat:.4f})")

        # ========== 优先使用缓存的 AI 分析结果 ==========
        ai_result = ai_results_cache.get(ev_id)

        unit_tasks: list[UnitTask] = []
        source = "quick_recommended"

        if ai_result:
            # 使用 AI 分析结果
            event_desc = str(ev.get("description", ""))
            unit_tasks, source = await _extract_teams_from_ai_result(
                ai_result, location, event_address, event_desc, team_contacts
            )
            if unit_tasks:
                logger.info(f"[multiRescueTask] 事件 {ev_id} 使用AI方案, 队伍数={len(unit_tasks)}")
        
        # ========== 无 AI 结果时使用 frontline 快速分配 ==========
        if not unit_tasks:
            alloc = alloc_by_event.get(ev_id) or {}
            teams = alloc.get("allocations") or []
            source = "quick_recommended"
            
            # 提取所有队伍名称（用于协作信息）
            all_team_names = [str(t.get("team_name", "")) for t in teams]
            event_desc = str(ev.get("description", ""))[:100]
            
            for team in teams:
                current_team_name = str(team.get("team_name", ""))
                collaborating = [n for n in all_team_names if n and n != current_team_name]

                # 获取队伍位置地址
                resource_state = team.get("resource_state", {})
                home_pos = resource_state.get("home_position", (None, None))
                base_lng = home_pos[0] if isinstance(home_pos, (list, tuple)) and len(home_pos) >= 2 else None
                base_lat = home_pos[1] if isinstance(home_pos, (list, tuple)) and len(home_pos) >= 2 else None
                team_loc = await _get_team_location_address(
                    str(team.get("base_address", "")), base_lng, base_lat
                )

                # 获取联系人信息
                team_id = str(team.get("team_id", ""))
                contact_info = team_contacts.get(team_id, {})

                unit_tasks.append(
                    UnitTask(
                        id=team_id,
                        name=current_team_name,
                        description=event_address,
                        team_location=team_loc,
                        location=location,
                        equipments=[],
                        task_description="",
                        rescue_point_name="",
                        target_situation=event_desc,
                        risk_warnings=[],
                        commander_order="",
                        eta_minutes=float(team.get("eta_minutes", 0)),
                        collaborating_teams=collaborating,
                        contact_name=contact_info.get("contact_name", ""),
                        contact_phone=contact_info.get("contact_phone", ""),
                    )
                )
            
            if unit_tasks:
                logger.info(f"[multiRescueTask] 事件 {ev_id} 使用快速分配, 队伍数={len(unit_tasks)}")

        if not unit_tasks:
            # 没有分配到队伍时返回占位，供前端提示资源缺口
            unit_tasks.append(
                UnitTask(
                    id="",
                    name="暂无可用队伍",
                    description=event_address,
                    team_location="无可用队伍",
                    location=location,
                    equipments=[],
                    task_description="",
                    rescue_point_name="",
                    target_situation="",
                    risk_warnings=[],
                    commander_order="",
                    eta_minutes=0,
                    collaborating_teams=[],
                    contact_name="",
                    contact_phone="",
                )
            )
            source = "no_resource"

        detail = MultiRescueTaskDetail(
            event_id=ev_id,  # 新增：关联事件ID
            source=source,   # 新增：方案来源
            level=level,
            title=str(ev.get("title", "")),
            rescueTask=[
                RescueTask(
                    units=unit_tasks,
                    equipmentList=[],
                )
            ],
        )
        details.append(detail)

    logger.info(f"[multiRescueTask] 生成草案完成, 共 {len(details)} 个事件")
    return ApiResponse.success(
        details,
        "救援任务草案已生成。请审核后点击【指令下发】正式执行。",
    )
