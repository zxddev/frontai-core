"""
预警监测API路由

提供预警相关的REST API接口。
"""
import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .agent import get_early_warning_agent
from .repository import DisasterRepository, WarningRepository
from .schemas import (
    DisasterUpdateRequest,
    DisasterUpdateResponse,
    WarningRecordResponse,
    WarningListResponse,
    WarningRespondRequest,
    DetourOptionsResponse,
    DetourOption,
    ConfirmDetourRequest,
    GeoPoint,
    GeoPolygon,
)

# 灾害类型到事件类型的映射
DISASTER_TO_EVENT_TYPE = {
    "fire": "fire",
    "flood": "flood",
    "chemical": "hazmat_leak",
    "landslide": "landslide",
    "earthquake": "earthquake_secondary",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/early-warning", tags=["预警监测"])


# ============ 灾害数据接口 ============

@router.post(
    "/disasters/update",
    response_model=DisasterUpdateResponse,
    summary="更新灾害数据",
    description="接收第三方灾情数据，触发预警检测流程",
)
async def update_disaster(request: DisasterUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    接收第三方灾情数据更新
    
    完整流程：
    1. 关联想定（指定或自动查找）
    2. 存储灾害态势到数据库
    3. 按需创建事件（needs_response=true且severity>=3）
    4. 创建地图实体（danger_zone）
    5. 查询影响范围内的队伍
    6. 生成预警记录并保存
    7. 通过WebSocket推送通知
    """
    logger.info(f"[API] Disaster update: type={request.disaster_type}, severity={request.severity_level}")
    
    from sqlalchemy import text
    
    scenario_id = request.scenario_id
    scenario_warning = None
    linked_event_id = None
    map_entity_id = None
    
    # ========== 1. 关联想定 ==========
    if not scenario_id:
        # 自动查找活动想定
        try:
            from src.domains.scenarios.repository import ScenarioRepository
            scenario_repo = ScenarioRepository(db)
            active_scenario = await scenario_repo.get_active()
            if active_scenario:
                scenario_id = active_scenario.id
                logger.info(f"[API] Auto-linked to active scenario: {scenario_id}")
            else:
                scenario_warning = "未找到活动想定，灾害未关联到想定"
                if request.severity_level >= 4:
                    scenario_warning += "；建议创建新想定以启动应急响应"
                logger.warning(f"[API] No active scenario found")
        except Exception as e:
            logger.warning(f"[API] Failed to find scenario: {e}")
            scenario_warning = f"想定查询失败: {str(e)}"
    
    # ========== 2. 保存灾害态势 ==========
    disaster_repo = DisasterRepository(db)
    disaster = await disaster_repo.create(
        disaster_type=request.disaster_type.value,
        boundary_geojson=request.boundary.model_dump(),
        scenario_id=scenario_id,
        disaster_name=request.disaster_name,
        buffer_distance_m=request.buffer_distance_m,
        spread_direction=request.spread_direction,
        spread_speed_mps=request.spread_speed_mps,
        severity_level=request.severity_level,
        source=request.source,
        properties=request.properties,
        needs_response=request.needs_response,
    )
    
    center_lon = _get_center_lon(request.boundary.coordinates)
    center_lat = _get_center_lat(request.boundary.coordinates)
    
    # ========== 3-5. 事件和地图实体创建（可选功能，暂时跳过） ==========
    # TODO: 当events_v2和layers_v2表可用时启用以下功能
    # - 按需创建事件 (needs_response && severity>=3)
    # - 创建danger_zone地图实体
    # - 更新关联字段
    # 当前版本这些功能会因表不存在而失败，暂时注释掉
    
    # ========== 6. 查询影响范围内的队伍 ==========
    buffer_m = request.buffer_distance_m
    result = await db.execute(text('''
        SELECT 
            t.id::text,
            t.name,
            t.contact_person,
            ST_X(t.base_location::geometry) as lon,
            ST_Y(t.base_location::geometry) as lat,
            ST_Distance(
                t.base_location::geography,
                ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography
            ) as distance_m
        FROM operational_v2.rescue_teams_v2 t
        WHERE t.base_location IS NOT NULL
        AND ST_DWithin(
            t.base_location::geography,
            ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography,
            :buffer_m
        )
        ORDER BY distance_m
    '''), {
        "center_lon": center_lon,
        "center_lat": center_lat,
        "buffer_m": buffer_m,
    })
    affected_teams = result.fetchall()
    
    # ========== 7. 为每个受影响队伍创建预警记录 ==========
    warning_repo = WarningRepository(db)
    warnings_created = 0
    
    for team in affected_teams:
        team_id, team_name, contact_person, lon, lat, distance_m = team
        
        # 确定预警级别
        if distance_m < 1000:
            level = "red"
        elif distance_m < 3000:
            level = "orange"
        elif distance_m < 5000:
            level = "yellow"
        else:
            level = "blue"
        
        # 计算预计接触时间（假设30km/h）
        estimated_minutes = int(distance_m / (30 * 1000 / 60)) if distance_m > 0 else 0
        
        await warning_repo.create(
            disaster_id=disaster.id,
            scenario_id=scenario_id,
            affected_type="team",
            affected_id=UUID(team_id),
            affected_name=team_name,
            notify_target_type="team_leader",
            notify_target_name=contact_person,
            warning_level=level,
            distance_m=distance_m,
            estimated_contact_minutes=estimated_minutes,
            warning_title=f"【路径预警-{_level_name(level)}】{team_name}",
            warning_message=f"距{request.disaster_name or request.disaster_type.value}区域{distance_m:.0f}米，预计{estimated_minutes}分钟后可能接触",
        )
        warnings_created += 1
    
    await db.commit()
    
    # ========== 8. WebSocket推送灾害通知 ==========
    try:
        from src.domains.frontend_api.websocket.router import ws_manager
        await ws_manager.broadcast_disaster({
            "disaster_id": str(disaster.id),
            "disaster_type": request.disaster_type.value,
            "disaster_name": request.disaster_name,
            "scenario_id": str(scenario_id) if scenario_id else None,
            "severity_level": request.severity_level,
            "center": {"lon": center_lon, "lat": center_lat},
            "warnings_count": warnings_created,
            "needs_response": request.needs_response,
            "linked_event_id": str(linked_event_id) if linked_event_id else None,
        })
        logger.info(f"[API] Broadcast disaster notification")
    except Exception as e:
        logger.warning(f"[API] Failed to broadcast: {e}")
    
    return DisasterUpdateResponse(
        disaster_id=disaster.id,
        scenario_id=scenario_id,
        linked_event_id=linked_event_id,
        map_entity_id=map_entity_id,
        warnings_generated=warnings_created,
        affected_vehicles=0,
        affected_teams=len(affected_teams),
        notifications_sent=warnings_created,
        message=f"已发送{warnings_created}条预警通知，涉及{len(affected_teams)}个受影响对象",
        scenario_warning=scenario_warning,
    )


def _get_center_lon(coordinates):
    """从多边形坐标获取中心经度"""
    if coordinates and coordinates[0]:
        return sum(p[0] for p in coordinates[0]) / len(coordinates[0])
    return 0


def _get_center_lat(coordinates):
    """从多边形坐标获取中心纬度"""
    if coordinates and coordinates[0]:
        return sum(p[1] for p in coordinates[0]) / len(coordinates[0])
    return 0


def _level_name(level: str) -> str:
    """获取预警级别中文名"""
    return {"red": "红色", "orange": "橙色", "yellow": "黄色", "blue": "蓝色"}.get(level, "黄色")


# ============ 预警记录接口 ============

@router.get(
    "/warnings",
    response_model=WarningListResponse,
    summary="查询预警列表",
    description="查询预警记录列表，支持分页和状态过滤",
)
async def list_warnings(
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    status: Optional[str] = Query(None, description="状态过滤: pending/acknowledged/responded/resolved"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """查询预警列表"""
    logger.info(f"[API] List warnings: scenario={scenario_id}, status={status}")
    
    repo = WarningRepository(db)
    items, total = await repo.list(
        page=page,
        page_size=page_size,
        scenario_id=scenario_id,
        status=status,
    )
    
    return WarningListResponse(
        items=[_warning_to_response(w) for w in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/warnings/{warning_id}",
    response_model=WarningRecordResponse,
    summary="查询预警详情",
    description="获取单条预警记录的详细信息",
)
async def get_warning(warning_id: UUID, db: AsyncSession = Depends(get_db)):
    """查询预警详情"""
    logger.info(f"[API] Get warning: {warning_id}")
    
    repo = WarningRepository(db)
    warning = await repo.get_by_id(warning_id)
    
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")
    
    return _warning_to_response(warning)


@router.post(
    "/warnings/{warning_id}/acknowledge",
    summary="确认收到预警",
    description="确认已收到预警消息",
)
async def acknowledge_warning(warning_id: UUID, db: AsyncSession = Depends(get_db)):
    """确认收到预警"""
    logger.info(f"[API] Acknowledge warning: {warning_id}")
    
    repo = WarningRepository(db)
    success = await repo.acknowledge(warning_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Warning not found or already acknowledged")
    
    await db.commit()
    return {"message": "Warning acknowledged", "warning_id": str(warning_id)}


@router.post(
    "/warnings/{warning_id}/respond",
    summary="响应预警",
    description="提交预警响应：continue(继续前进)/detour(申请绕行)/standby(原地待命)",
)
async def respond_to_warning(
    warning_id: UUID,
    request: WarningRespondRequest,
    db: AsyncSession = Depends(get_db),
):
    """响应预警"""
    logger.info(f"[API] Respond to warning: {warning_id}, action={request.action}")
    
    repo = WarningRepository(db)
    success = await repo.respond(
        warning_id=warning_id,
        action=request.action.value,
        reason=request.reason,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Warning not found")
    
    await db.commit()
    
    return {
        "message": f"Response recorded: {request.action.value}",
        "warning_id": str(warning_id),
        "action": request.action.value,
    }


# ============ 绕行接口 ============

# 临时存储绕行选项（实际应存Redis）
_detour_options_cache: dict = {}


@router.get(
    "/warnings/{warning_id}/detour-options",
    response_model=DetourOptionsResponse,
    summary="获取绕行选项",
    description="调用路径规划智能体获取避开灾害区域的绕行路线",
)
async def get_detour_options(warning_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    获取绕行选项
    
    调用RoutePlanningAgent，传入灾害范围作为avoid_areas，
    返回多条备选绕行路线供用户选择。
    """
    logger.info(f"[API] Get detour options for warning: {warning_id}")
    
    # 1. 查询预警记录
    warning_repo = WarningRepository(db)
    warning = await warning_repo.get_by_id(warning_id)
    
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")
    
    # 2. 查询灾害范围
    disaster_repo = DisasterRepository(db)
    disaster = await disaster_repo.get_by_id(warning.disaster_id) if warning.disaster_id else None
    
    if not disaster:
        raise HTTPException(status_code=404, detail="Disaster not found")
    
    # 获取灾害边界GeoJSON
    boundary_geojson = await disaster_repo.get_boundary_geojson(disaster.id)
    
    if not boundary_geojson:
        raise HTTPException(status_code=400, detail="Disaster boundary not available")
    
    # 3. 生成绕行选项（使用模拟数据，实际应调用RoutePlanningAgent）
    # TODO: 集成RoutePlanningAgent，传入avoid_areas参数
    options = _generate_mock_detour_options()
    
    # 缓存选项供确认时使用
    _detour_options_cache[str(warning_id)] = {
        "options": options,
        "boundary": boundary_geojson,
    }
    
    return DetourOptionsResponse(
        warning_id=warning_id,
        original_route_distance_m=5000,
        original_route_duration_seconds=600,
        avoid_area=GeoPolygon(**boundary_geojson),
        options=options,
    )


@router.post(
    "/warnings/{warning_id}/confirm-detour",
    summary="确认绕行路线",
    description="确认选择的绕行路线并执行",
)
async def confirm_detour(
    warning_id: UUID,
    request: ConfirmDetourRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    确认绕行路线
    
    用户选择绕行路线后：
    1. 验证route_id有效
    2. 更新预警状态为resolved
    3. 记录绕行决策
    """
    logger.info(f"[API] Confirm detour for warning: {warning_id}, route={request.route_id}")
    
    # 1. 验证route_id在缓存中
    cached = _detour_options_cache.get(str(warning_id))
    if cached:
        valid_routes = [opt.route_id for opt in cached.get("options", [])]
        if request.route_id not in valid_routes:
            raise HTTPException(status_code=400, detail="Invalid route_id")
    
    # 2. 更新预警状态
    repo = WarningRepository(db)
    success = await repo.confirm_detour(warning_id, request.route_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Warning not found")
    
    await db.commit()
    
    # 3. 清理缓存
    _detour_options_cache.pop(str(warning_id), None)
    
    # TODO: 4. 更新任务/车辆的规划路径
    # TODO: 5. 通过WebSocket通知相关方路径已变更
    
    return {
        "message": "Detour confirmed and route updated",
        "warning_id": str(warning_id),
        "route_id": request.route_id,
    }


def _generate_mock_detour_options() -> list[DetourOption]:
    """生成模拟的绕行选项"""
    return [
        DetourOption(
            route_id=str(uuid4()),
            path_points=[
                GeoPoint(lon=116.397, lat=39.908),
                GeoPoint(lon=116.405, lat=39.915),
                GeoPoint(lon=116.420, lat=39.918),
                GeoPoint(lon=116.450, lat=39.920),
            ],
            total_distance_m=6200,
            total_duration_seconds=744,
            additional_distance_m=1200,
            additional_time_seconds=144,
            risk_level="low",
            description="推荐路线：向北绕行，避开灾害区域",
        ),
        DetourOption(
            route_id=str(uuid4()),
            path_points=[
                GeoPoint(lon=116.397, lat=39.908),
                GeoPoint(lon=116.390, lat=39.900),
                GeoPoint(lon=116.430, lat=39.895),
                GeoPoint(lon=116.450, lat=39.920),
            ],
            total_distance_m=7500,
            total_duration_seconds=900,
            additional_distance_m=2500,
            additional_time_seconds=300,
            risk_level="medium",
            description="备选路线：向南绕行，路程较长但道路通畅",
        ),
    ]


def _warning_to_response(warning) -> WarningRecordResponse:
    """将数据库模型转换为响应模型"""
    return WarningRecordResponse(
        id=warning.id,
        disaster_id=warning.disaster_id,
        scenario_id=warning.scenario_id,
        affected_type=warning.affected_type,
        affected_id=warning.affected_id,
        affected_name=warning.affected_name,
        notify_target_type=warning.notify_target_type,
        notify_target_id=warning.notify_target_id,
        notify_target_name=warning.notify_target_name,
        warning_level=warning.warning_level,
        distance_m=float(warning.distance_m) if warning.distance_m else None,
        estimated_contact_minutes=warning.estimated_contact_minutes,
        route_affected=warning.route_affected or False,
        warning_title=warning.warning_title,
        warning_message=warning.warning_message,
        status=warning.status,
        response_action=warning.response_action,
        response_reason=warning.response_reason,
        created_at=warning.created_at,
        acknowledged_at=warning.acknowledged_at,
        responded_at=warning.responded_at,
        resolved_at=warning.resolved_at,
    )
