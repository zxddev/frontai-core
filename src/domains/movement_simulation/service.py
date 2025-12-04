"""
移动仿真核心服务

MovementSimulationManager - 管理所有移动会话的生命周期
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Callable, Awaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .schemas import (
    MovementSession, MovementState, EntityType, Point, Waypoint,
    MovementStartRequest, MovementStartResponse, MovementStatusResponse,
    MovementEventPayload, LocationUpdatePayload,
)
from .interpolator import RouteInterpolator
from .speed_resolver import SpeedResolver
from .persistence import MovementPersistence, get_persistence

logger = logging.getLogger(__name__)


def _get_stomp_broker():
    """延迟导入避免循环依赖"""
    from src.core.stomp.broker import stomp_broker
    return stomp_broker


class MovementSimulationManager:
    """
    移动仿真管理器
    
    核心功能：
    1. 启动/暂停/恢复/取消移动会话
    2. 后台任务循环更新位置
    3. 实时推送位置到WebSocket
    4. 任务停靠点处理
    
    使用示例:
    ```python
    manager = MovementSimulationManager(db)
    await manager.start()
    
    session_id = await manager.start_movement(request)
    status = await manager.get_status(session_id)
    await manager.pause_movement(session_id)
    await manager.resume_movement(session_id)
    await manager.cancel_movement(session_id)
    
    await manager.stop()
    ```
    """
    
    # 位置更新间隔（秒）
    UPDATE_INTERVAL = 1.0
    
    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self._db = db
        self._persistence: Optional[MovementPersistence] = None
        self._speed_resolver: Optional[SpeedResolver] = None
        
        # 运行中的任务: session_id -> asyncio.Task
        self._tasks: Dict[str, asyncio.Task] = {}
        
        # 暂停控制事件: session_id -> asyncio.Event
        self._pause_events: Dict[str, asyncio.Event] = {}
        
        # 插值器缓存: session_id -> RouteInterpolator
        self._interpolators: Dict[str, RouteInterpolator] = {}
        
        # 运行状态
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """启动管理器"""
        if self._running:
            return
        
        logger.info("启动移动仿真管理器")
        self._running = True
        self._persistence = await get_persistence()
        
        # 恢复之前活跃的会话
        await self._recover_sessions()
        
        # 启动定期清理任务
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self) -> None:
        """停止管理器"""
        if not self._running:
            return
        
        logger.info("停止移动仿真管理器")
        self._running = False
        
        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 暂停所有移动任务（保存状态）
        for session_id in list(self._tasks.keys()):
            await self._stop_task(session_id, save_state=True)
        
        logger.info("移动仿真管理器已停止")
    
    async def _recover_sessions(self) -> None:
        """恢复之前活跃的会话"""
        if not self._persistence:
            return
        
        sessions = await self._persistence.get_active_sessions()
        recovered = 0
        
        for session in sessions:
            if session.state == MovementState.MOVING:
                # 恢复移动中的会话
                self._create_interpolator(session)
                self._start_movement_task(session)
                recovered += 1
            elif session.state == MovementState.PAUSED:
                # 暂停的会话保持暂停状态
                self._create_interpolator(session)
                recovered += 1
        
        if recovered > 0:
            logger.info(f"恢复了 {recovered} 个移动会话")
    
    # =========================================================================
    # 公开API
    # =========================================================================
    
    async def start_movement(
        self,
        request: MovementStartRequest,
        db: Optional[AsyncSession] = None,
    ) -> MovementStartResponse:
        """
        启动移动
        
        Args:
            request: 启动请求
            db: 数据库会话（用于获取速度）
            
        Returns:
            启动响应
            
        Raises:
            ConflictError: 实体已有活跃移动
            ValidationError: 路径无效
        """
        # 检查实体是否已有活跃移动
        existing = await self._persistence.get_session_by_entity(request.entity_id)
        if existing and existing.state in (
            MovementState.PENDING, MovementState.MOVING, 
            MovementState.PAUSED, MovementState.EXECUTING_TASK
        ):
            raise ConflictError(
                error_code="MV4001",
                message=f"实体 {request.entity_id} 已有活跃移动会话: {existing.session_id}"
            )
        
        # 解析路径
        route = [Point(lon=p[0], lat=p[1]) for p in request.route]
        if len(route) < 2:
            raise ValidationError(
                error_code="MV4002",
                message="路径至少需要2个点"
            )
        
        # 创建插值器计算距离
        interpolator = RouteInterpolator(route)
        
        # 获取速度
        if request.speed_mps:
            speed_mps = request.speed_mps
        else:
            use_db = db or self._db
            if use_db and request.resource_id:
                resolver = SpeedResolver(use_db)
                speed_mps = await resolver.resolve_speed_mps(
                    request.entity_type, request.resource_id
                )
            else:
                # 使用默认速度
                from .speed_resolver import DEFAULT_SPEEDS_KMH
                speed_mps = DEFAULT_SPEEDS_KMH.get(request.entity_type, 10) / 3.6
        
        # 创建会话
        session_id = str(uuid.uuid4())
        session = MovementSession(
            session_id=session_id,
            entity_id=request.entity_id,
            entity_type=request.entity_type,
            resource_id=request.resource_id,
            route=route,
            total_distance_m=interpolator.total_distance_m,
            segment_distances=interpolator.segment_distances,
            speed_mps=speed_mps,
            waypoints=request.waypoints,
            state=MovementState.MOVING,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
        )
        
        # 保存会话
        await self._persistence.save_session(session)
        
        # 缓存插值器
        self._interpolators[session_id] = interpolator
        
        # 启动移动任务
        self._start_movement_task(session)
        
        # 广播开始事件
        await self._broadcast_event(session, "started")
        
        logger.info(
            f"启动移动: session={session_id}, entity={request.entity_id}, "
            f"distance={interpolator.total_distance_m:.0f}m, speed={speed_mps:.1f}m/s"
        )
        
        return MovementStartResponse(
            session_id=session_id,
            entity_id=request.entity_id,
            state=MovementState.MOVING,
            total_distance_m=interpolator.total_distance_m,
            estimated_duration_s=interpolator.total_distance_m / speed_mps,
            speed_mps=speed_mps,
        )
    
    async def pause_movement(self, session_id: str) -> MovementStatusResponse:
        """暂停移动"""
        session = await self._get_session_or_raise(session_id)
        
        if session.state != MovementState.MOVING:
            raise ConflictError(
                error_code="MV4003",
                message=f"只能暂停移动中的会话，当前状态: {session.state.value}"
            )
        
        # 设置暂停事件
        if session_id in self._pause_events:
            self._pause_events[session_id].clear()
        
        # 更新状态
        session.state = MovementState.PAUSED
        session.paused_at = datetime.utcnow()
        await self._persistence.save_session(session)
        
        # 广播暂停事件
        await self._broadcast_event(session, "paused")
        
        logger.info(f"暂停移动: session={session_id}")
        
        return await self._build_status_response(session)
    
    async def resume_movement(self, session_id: str) -> MovementStatusResponse:
        """恢复移动"""
        session = await self._get_session_or_raise(session_id)
        
        if session.state != MovementState.PAUSED:
            raise ConflictError(
                error_code="MV4004",
                message=f"只能恢复暂停的会话，当前状态: {session.state.value}"
            )
        
        # 计算暂停时长
        if session.paused_at:
            pause_duration = (datetime.utcnow() - session.paused_at).total_seconds()
            session.total_pause_duration_s += pause_duration
        
        # 更新状态
        session.state = MovementState.MOVING
        session.paused_at = None
        await self._persistence.save_session(session)
        
        # 设置恢复事件
        if session_id in self._pause_events:
            self._pause_events[session_id].set()
        else:
            # 重新启动任务
            self._start_movement_task(session)
        
        # 广播恢复事件
        await self._broadcast_event(session, "resumed")
        
        logger.info(f"恢复移动: session={session_id}")
        
        return await self._build_status_response(session)
    
    async def cancel_movement(self, session_id: str) -> MovementStatusResponse:
        """取消移动"""
        session = await self._get_session_or_raise(session_id)
        
        if session.state in (MovementState.COMPLETED, MovementState.CANCELLED):
            raise ConflictError(
                error_code="MV4005",
                message=f"会话已结束，状态: {session.state.value}"
            )
        
        # 停止任务
        await self._stop_task(session_id, save_state=False)
        
        # 更新状态
        session.state = MovementState.CANCELLED
        session.completed_at = datetime.utcnow()
        await self._persistence.save_session(session)
        
        # 广播取消事件
        await self._broadcast_event(session, "cancelled")
        
        logger.info(f"取消移动: session={session_id}")
        
        return await self._build_status_response(session)
    
    async def get_status(self, session_id: str) -> MovementStatusResponse:
        """获取移动状态"""
        session = await self._get_session_or_raise(session_id)
        return await self._build_status_response(session)
    
    async def get_active_sessions(self) -> list[MovementStatusResponse]:
        """获取所有活跃会话"""
        sessions = await self._persistence.get_active_sessions()
        return [await self._build_status_response(s) for s in sessions]
    
    # =========================================================================
    # 内部方法
    # =========================================================================
    
    async def _get_session_or_raise(self, session_id: str) -> MovementSession:
        """获取会话，不存在则抛出异常"""
        session = await self._persistence.get_session(session_id)
        if not session:
            raise NotFoundError("MovementSession", session_id)
        return session
    
    def _create_interpolator(self, session: MovementSession) -> RouteInterpolator:
        """创建或获取插值器"""
        if session.session_id not in self._interpolators:
            self._interpolators[session.session_id] = RouteInterpolator(session.route)
        return self._interpolators[session.session_id]
    
    def _start_movement_task(self, session: MovementSession) -> None:
        """启动移动后台任务"""
        if session.session_id in self._tasks:
            return
        
        # 创建暂停控制事件
        pause_event = asyncio.Event()
        pause_event.set()  # 初始为非暂停状态
        self._pause_events[session.session_id] = pause_event
        
        # 创建后台任务
        task = asyncio.create_task(
            self._movement_loop(session.session_id),
            name=f"movement-{session.session_id[:8]}"
        )
        self._tasks[session.session_id] = task
    
    async def _stop_task(self, session_id: str, save_state: bool = True) -> None:
        """停止移动任务"""
        # 取消任务
        task = self._tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 清理事件
        self._pause_events.pop(session_id, None)
        
        # 清理插值器
        if not save_state:
            self._interpolators.pop(session_id, None)
    
    async def _movement_loop(self, session_id: str) -> None:
        """
        移动主循环
        
        每 UPDATE_INTERVAL 秒更新一次位置
        """
        try:
            while self._running:
                # 检查暂停
                pause_event = self._pause_events.get(session_id)
                if pause_event:
                    await pause_event.wait()
                
                # 获取会话
                session = await self._persistence.get_session(session_id)
                if not session or session.state not in (MovementState.MOVING, MovementState.EXECUTING_TASK):
                    break
                
                # 处理任务执行状态
                if session.state == MovementState.EXECUTING_TASK:
                    await asyncio.sleep(self.UPDATE_INTERVAL)
                    continue
                
                # 计算新位置
                updated_session = await self._update_position(session)
                
                # 检查是否完成
                if updated_session.state == MovementState.COMPLETED:
                    break
                
                # 等待下次更新
                await asyncio.sleep(self.UPDATE_INTERVAL)
        
        except asyncio.CancelledError:
            logger.debug(f"移动任务被取消: {session_id}")
        except Exception as e:
            logger.error(f"移动任务异常: {session_id}, error={e}", exc_info=True)
        finally:
            # 清理
            self._tasks.pop(session_id, None)
            self._pause_events.pop(session_id, None)
    
    async def _update_position(self, session: MovementSession) -> MovementSession:
        """更新位置"""
        interpolator = self._create_interpolator(session)
        
        # 计算有效行驶时间
        if session.started_at:
            elapsed = (datetime.utcnow() - session.started_at).total_seconds()
            effective_elapsed = elapsed - session.total_pause_duration_s
        else:
            effective_elapsed = 0
        
        # 插值计算位置
        result = interpolator.interpolate_by_time(effective_elapsed, session.speed_mps)
        
        # 更新会话状态
        session.current_segment_index = result.segment_index
        session.segment_progress = result.segment_progress
        session.traveled_distance_m = result.traveled_distance_m
        session.current_heading = result.heading
        session.last_update_at = datetime.utcnow()
        
        # 检查是否到达任务停靠点
        await self._check_waypoints(session, result)
        
        # 检查是否完成
        if result.traveled_distance_m >= session.total_distance_m - 0.1:
            session.state = MovementState.COMPLETED
            session.completed_at = datetime.utcnow()
            await self._persistence.save_session(session)
            await self._broadcast_event(session, "completed")
            logger.info(f"移动完成: session={session.session_id}")
            return session
        
        # 保存状态
        await self._persistence.save_session(session)
        
        # 广播位置更新
        await self._broadcast_location(session, result.position)
        
        return session
    
    async def _check_waypoints(self, session: MovementSession, result) -> None:
        """检查是否到达任务停靠点"""
        for i, waypoint in enumerate(session.waypoints):
            if waypoint.executed:
                continue
            
            # 检查是否到达
            interpolator = self._interpolators.get(session.session_id)
            if interpolator and interpolator.check_waypoint_reached(
                waypoint.point_index, result.segment_index, result.segment_progress
            ):
                # 标记为执行中
                session.state = MovementState.EXECUTING_TASK
                session.current_waypoint_index = i
                await self._persistence.save_session(session)
                
                # 广播到达事件
                await self._broadcast_event(session, "waypoint_reached", waypoint=waypoint)
                
                logger.info(
                    f"到达任务点: session={session.session_id}, "
                    f"waypoint={i}, task_type={waypoint.task_type}"
                )
                
                # 等待任务执行时间
                await asyncio.sleep(waypoint.task_duration_s)
                
                # 标记任务完成
                waypoint.executed = True
                waypoint.executed_at = datetime.utcnow()
                session.state = MovementState.MOVING
                await self._persistence.save_session(session)
                
                break
    
    async def _broadcast_location(self, session: MovementSession, position: Point) -> None:
        """广播位置更新（适配前端 handleEntityItem 期望的格式）"""
        try:
            broker = _get_stomp_broker()
            
            # 映射 entity_type 到前端期望的 type
            type_map = {
                "team": "realTime_command_vhicle",  # 队伍用指挥车模型
                "vehicle": "realTime_command_vhicle",
                "uav": "realTime_uav",
                "robotic_dog": "realTime_robotic_dog",
                "usv": "realTime_usv",
            }
            frontend_type = type_map.get(session.entity_type.value, "realTime_command_vhicle")
            
            await broker.broadcast_location({
                "id": str(session.entity_id),
                "type": frontend_type,
                "layerCode": "layer.realTimeEquipment",
                "geometry": {
                    "coordinates": [position.lon, position.lat]
                },
                "properties": {
                    "state": "moving",
                    "name": "救援队伍",
                    "heading": int(session.current_heading),
                    "speed": f"{session.speed_mps * 3.6:.0f}km/h",
                },
                "styleOverrides": {}
            })
            
            # 同步更新数据库中的队伍位置，供风险检测使用
            if session.entity_type.value == "team":
                await self._update_team_location_in_db(session.entity_id, position)
                
        except Exception as e:
            logger.warning(f"广播位置失败: {e}")
    
    async def _update_team_location_in_db(self, team_id: UUID, position: Point) -> None:
        """更新数据库中的队伍当前位置（用于风险检测）"""
        try:
            from src.core.database import AsyncSessionLocal
            from sqlalchemy import text
            
            async with AsyncSessionLocal() as db:
                sql = text("""
                    UPDATE operational_v2.rescue_teams_v2 
                    SET current_location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                    WHERE id = :team_id
                """)
                await db.execute(sql, {
                    "lon": position.lon,
                    "lat": position.lat,
                    "team_id": str(team_id),
                })
                await db.commit()
        except Exception as e:
            logger.debug(f"更新队伍数据库位置失败（不阻塞）: {e}")
    
    async def _broadcast_event(
        self, 
        session: MovementSession, 
        event_type: str,
        waypoint: Optional[Waypoint] = None,
    ) -> None:
        """广播移动事件"""
        try:
            broker = _get_stomp_broker()
            
            # 获取当前位置
            interpolator = self._interpolators.get(session.session_id)
            position = None
            if interpolator:
                result = interpolator.interpolate_by_distance(session.traveled_distance_m)
                position = result.position
            
            payload = {
                "session_id": session.session_id,
                "entity_id": str(session.entity_id),
                "entity_type": session.entity_type.value,
                "event_type": event_type,
                "position": {"lon": position.lon, "lat": position.lat} if position else None,
                "heading": session.current_heading,
                "progress_percent": (session.traveled_distance_m / session.total_distance_m * 100) if session.total_distance_m > 0 else 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if waypoint:
                payload["waypoint"] = waypoint.model_dump()
            
            await broker.broadcast(f"/topic/movement.{event_type}", {"payload": payload})
        except Exception as e:
            logger.warning(f"广播事件失败: {e}")
    
    async def _build_status_response(self, session: MovementSession) -> MovementStatusResponse:
        """构建状态响应"""
        interpolator = self._create_interpolator(session)
        result = interpolator.interpolate_by_distance(session.traveled_distance_m)
        
        # 计算时间
        elapsed = 0.0
        if session.started_at:
            elapsed = (datetime.utcnow() - session.started_at).total_seconds()
            elapsed -= session.total_pause_duration_s
        
        remaining = interpolator.get_estimated_remaining_time(
            session.traveled_distance_m, session.speed_mps
        )
        
        # 下一个未执行的停靠点
        next_waypoint = None
        completed_waypoints = 0
        for wp in session.waypoints:
            if wp.executed:
                completed_waypoints += 1
            elif next_waypoint is None:
                next_waypoint = wp
        
        return MovementStatusResponse(
            session_id=session.session_id,
            entity_id=session.entity_id,
            state=session.state,
            current_position=result.position,
            current_heading=result.heading,
            progress_percent=round(session.traveled_distance_m / session.total_distance_m * 100, 2) if session.total_distance_m > 0 else 0,
            traveled_distance_m=session.traveled_distance_m,
            remaining_distance_m=interpolator.get_remaining_distance(session.traveled_distance_m),
            elapsed_time_s=elapsed,
            estimated_remaining_s=remaining,
            next_waypoint=next_waypoint,
            completed_waypoints=completed_waypoints,
        )
    
    async def _periodic_cleanup(self) -> None:
        """定期清理已完成的会话"""
        while self._running:
            try:
                await asyncio.sleep(3600)  # 每小时清理一次
                await self._persistence.cleanup_completed()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务异常: {e}")


# 全局单例
_manager: Optional[MovementSimulationManager] = None


async def get_movement_manager() -> MovementSimulationManager:
    """获取移动仿真管理器单例"""
    global _manager
    if _manager is None:
        _manager = MovementSimulationManager()
        await _manager.start()
    return _manager


async def shutdown_movement_manager() -> None:
    """关闭移动仿真管理器"""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
