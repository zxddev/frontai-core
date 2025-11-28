"""
批量移动服务

支持多实体协同移动（编队）
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .schemas import (
    MovementSession, MovementState, BatchMovementSession, FormationType,
    Point, MovementStartRequest, MovementStartResponse,
    BatchMovementStartRequest, BatchMovementStartResponse, MovementStatusResponse,
)
from .service import MovementSimulationManager, get_movement_manager
from .persistence import get_persistence

logger = logging.getLogger(__name__)


class BatchMovementService:
    """
    批量移动服务
    
    支持三种编队模式：
    - CONVOY: 纵队，依次出发，间隔 interval_s 秒
    - PARALLEL: 并行，同时出发
    - STAGGERED: 交错，奇偶分组出发
    """
    
    def __init__(self, manager: MovementSimulationManager) -> None:
        self._manager = manager
    
    async def start_batch(
        self,
        request: BatchMovementStartRequest,
        db: Optional[AsyncSession] = None,
    ) -> BatchMovementStartResponse:
        """
        启动批量移动
        
        Args:
            request: 批量启动请求
            db: 数据库会话
            
        Returns:
            批量启动响应
        """
        if len(request.movements) < 1:
            raise ValidationError(
                error_code="MV4010",
                message="批量移动至少需要1个实体"
            )
        
        batch_id = str(uuid.uuid4())
        session_responses: List[MovementStartResponse] = []
        session_ids: List[str] = []
        
        persistence = await get_persistence()
        
        # 根据编队类型处理
        if request.formation == FormationType.PARALLEL:
            # 并行：同时启动所有
            tasks = []
            for movement in request.movements:
                # 如果有共享路径，覆盖各自路径
                if request.shared_route:
                    movement.route = request.shared_route
                tasks.append(self._manager.start_movement(movement, db))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"启动单个移动失败: {result}")
                else:
                    session_responses.append(result)
                    session_ids.append(result.session_id)
        
        elif request.formation == FormationType.CONVOY:
            # 纵队：依次启动，间隔时间
            for i, movement in enumerate(request.movements):
                if request.shared_route:
                    movement.route = request.shared_route
                
                try:
                    response = await self._manager.start_movement(movement, db)
                    session_responses.append(response)
                    session_ids.append(response.session_id)
                    
                    # 等待间隔（最后一个不等待）
                    if i < len(request.movements) - 1 and request.interval_s > 0:
                        await asyncio.sleep(request.interval_s)
                except Exception as e:
                    logger.warning(f"启动第{i+1}个移动失败: {e}")
        
        elif request.formation == FormationType.STAGGERED:
            # 交错：分两批启动
            odd_movements = request.movements[::2]   # 奇数位置
            even_movements = request.movements[1::2]  # 偶数位置
            
            # 第一批（奇数）
            for movement in odd_movements:
                if request.shared_route:
                    movement.route = request.shared_route
                try:
                    response = await self._manager.start_movement(movement, db)
                    session_responses.append(response)
                    session_ids.append(response.session_id)
                except Exception as e:
                    logger.warning(f"启动移动失败: {e}")
            
            # 等待间隔
            if request.interval_s > 0 and even_movements:
                await asyncio.sleep(request.interval_s)
            
            # 第二批（偶数）
            for movement in even_movements:
                if request.shared_route:
                    movement.route = request.shared_route
                try:
                    response = await self._manager.start_movement(movement, db)
                    session_responses.append(response)
                    session_ids.append(response.session_id)
                except Exception as e:
                    logger.warning(f"启动移动失败: {e}")
        
        # 创建批量会话记录
        batch_session = BatchMovementSession(
            batch_id=batch_id,
            sessions=session_ids,
            formation=request.formation,
            interval_s=request.interval_s,
            state=MovementState.MOVING,
            created_at=datetime.utcnow(),
        )
        await persistence.save_batch_session(batch_session)
        
        logger.info(
            f"批量移动启动: batch_id={batch_id}, "
            f"formation={request.formation.value}, "
            f"count={len(session_ids)}"
        )
        
        return BatchMovementStartResponse(
            batch_id=batch_id,
            sessions=session_responses,
            formation=request.formation,
            total_entities=len(session_ids),
        )
    
    async def pause_batch(self, batch_id: str) -> List[MovementStatusResponse]:
        """暂停批量移动"""
        batch = await self._get_batch_or_raise(batch_id)
        
        results = []
        for session_id in batch.sessions:
            try:
                status = await self._manager.pause_movement(session_id)
                results.append(status)
            except Exception as e:
                logger.warning(f"暂停会话失败: {session_id}, error={e}")
        
        # 更新批量状态
        batch.state = MovementState.PAUSED
        persistence = await get_persistence()
        await persistence.save_batch_session(batch)
        
        logger.info(f"批量暂停: batch_id={batch_id}, paused={len(results)}")
        return results
    
    async def resume_batch(self, batch_id: str) -> List[MovementStatusResponse]:
        """恢复批量移动"""
        batch = await self._get_batch_or_raise(batch_id)
        
        results = []
        for session_id in batch.sessions:
            try:
                status = await self._manager.resume_movement(session_id)
                results.append(status)
            except Exception as e:
                logger.warning(f"恢复会话失败: {session_id}, error={e}")
        
        # 更新批量状态
        batch.state = MovementState.MOVING
        persistence = await get_persistence()
        await persistence.save_batch_session(batch)
        
        logger.info(f"批量恢复: batch_id={batch_id}, resumed={len(results)}")
        return results
    
    async def cancel_batch(self, batch_id: str) -> List[MovementStatusResponse]:
        """取消批量移动"""
        batch = await self._get_batch_or_raise(batch_id)
        
        results = []
        for session_id in batch.sessions:
            try:
                status = await self._manager.cancel_movement(session_id)
                results.append(status)
            except Exception as e:
                logger.warning(f"取消会话失败: {session_id}, error={e}")
        
        # 更新批量状态
        batch.state = MovementState.CANCELLED
        persistence = await get_persistence()
        await persistence.save_batch_session(batch)
        
        logger.info(f"批量取消: batch_id={batch_id}, cancelled={len(results)}")
        return results
    
    async def get_batch_status(self, batch_id: str) -> dict:
        """获取批量移动状态"""
        batch = await self._get_batch_or_raise(batch_id)
        
        session_statuses = []
        moving_count = 0
        completed_count = 0
        
        for session_id in batch.sessions:
            try:
                status = await self._manager.get_status(session_id)
                session_statuses.append(status)
                
                if status.state == MovementState.MOVING:
                    moving_count += 1
                elif status.state == MovementState.COMPLETED:
                    completed_count += 1
            except Exception as e:
                logger.warning(f"获取会话状态失败: {session_id}, error={e}")
        
        # 判断整体状态
        if completed_count == len(batch.sessions):
            overall_state = MovementState.COMPLETED
        elif moving_count > 0:
            overall_state = MovementState.MOVING
        else:
            overall_state = batch.state
        
        return {
            "batch_id": batch_id,
            "formation": batch.formation.value,
            "state": overall_state.value,
            "total": len(batch.sessions),
            "moving": moving_count,
            "completed": completed_count,
            "sessions": session_statuses,
        }
    
    async def _get_batch_or_raise(self, batch_id: str) -> BatchMovementSession:
        """获取批量会话"""
        persistence = await get_persistence()
        batch = await persistence.get_batch_session(batch_id)
        if not batch:
            raise NotFoundError("BatchMovementSession", batch_id)
        return batch


# 工厂函数
async def get_batch_service() -> BatchMovementService:
    """获取批量移动服务"""
    manager = await get_movement_manager()
    return BatchMovementService(manager)
