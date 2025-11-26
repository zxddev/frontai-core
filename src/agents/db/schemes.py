"""
方案持久化模块

将AI生成的方案保存到数据库
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.schemes.service import SchemeService
from src.domains.schemes.schemas import (
    SchemeCreate,
    SchemeType,
    SchemeSource,
    ResourceAllocationCreate,
)

logger = logging.getLogger(__name__)


class SchemePersister:
    """
    方案持久化器
    
    将SchemeGenerationAgent生成的方案保存到数据库
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        Args:
            db: SQLAlchemy异步数据库session
        """
        self._db = db
        self._service = SchemeService(db)
    
    async def save_scheme(
        self,
        event_id: str,
        scenario_id: str,
        scheme_output: Dict[str, Any],
        event_analysis: Dict[str, Any],
        resource_allocations: List[Dict[str, Any]],
        update_team_status: bool = False,
        allocated_team_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        保存AI生成的方案
        
        Args:
            event_id: 事件ID
            scenario_id: 场景ID
            scheme_output: SchemeOutputState格式的方案数据
            event_analysis: 事件分析结果
            resource_allocations: 资源分配列表
            update_team_status: 是否更新队伍状态
            allocated_team_ids: 被分配的队伍ID列表
            
        Returns:
            保存结果，包含scheme_id和allocation_ids
        """
        logger.info(f"保存AI方案: event={event_id}, scenario={scenario_id}")
        
        try:
            # 1. 创建方案
            scheme_response = await self._create_scheme(
                event_id=event_id,
                scenario_id=scenario_id,
                scheme_output=scheme_output,
                event_analysis=event_analysis,
            )
            scheme_id = scheme_response.id
            logger.info(f"方案创建成功: {scheme_id}")
            
            # 2. 创建资源分配
            allocation_ids = []
            for allocation in resource_allocations:
                alloc_response = await self._create_allocation(scheme_id, allocation)
                allocation_ids.append(str(alloc_response.id))
            
            logger.info(f"资源分配保存成功: {len(allocation_ids)}条")
            
            # 3. 更新队伍状态
            team_status_updated = False
            if update_team_status and allocated_team_ids:
                await self._update_team_status(
                    team_ids=allocated_team_ids,
                    status="deployed",
                    task_id=event_id,
                )
                team_status_updated = True
                logger.info(f"队伍状态已更新: {len(allocated_team_ids)}支队伍设为deployed")
            
            return {
                "success": True,
                "scheme_id": str(scheme_id),
                "allocation_ids": allocation_ids,
                "team_status_updated": team_status_updated,
            }
            
        except Exception as e:
            logger.error(f"保存方案失败: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _update_team_status(
        self,
        team_ids: List[str],
        status: str,
        task_id: Optional[str] = None,
    ) -> None:
        """
        批量更新队伍状态
        
        Args:
            team_ids: 队伍ID列表
            status: 新状态（standby/deployed/resting/unavailable）
            task_id: 当前任务ID（事件ID）
        """
        from sqlalchemy import text
        
        if not team_ids:
            return
        
        # 使用原生SQL批量更新
        sql = text("""
            UPDATE operational_v2.rescue_teams_v2
            SET status = :status,
                current_task_id = :task_id,
                updated_at = NOW()
            WHERE id = ANY(:team_ids::uuid[])
        """)
        
        await self._db.execute(
            sql,
            {
                "status": status,
                "task_id": task_id,
                "team_ids": team_ids,
            }
        )
        await self._db.flush()
    
    async def _create_scheme(
        self,
        event_id: str,
        scenario_id: str,
        scheme_output: Dict[str, Any],
        event_analysis: Dict[str, Any],
    ) -> Any:
        """创建方案记录"""
        disaster_type = event_analysis.get("disaster_type", "unknown")
        
        # 根据灾害类型映射方案类型
        scheme_type = self._map_disaster_to_scheme_type(disaster_type)
        
        # 构造标题
        title = scheme_output.get("title") or f"AI生成方案 - {disaster_type}"
        
        # 构造目标
        objective = scheme_output.get("objective") or self._generate_objective(event_analysis)
        
        # 构造描述
        description = scheme_output.get("description") or scheme_output.get("rationale", "")
        
        # 约束条件
        constraints = scheme_output.get("constraints") or {}
        
        # 风险评估
        risk_assessment = scheme_output.get("risk_assessment") or {
            "confidence_score": scheme_output.get("confidence_score", 0.8),
            "estimated_metrics": scheme_output.get("estimated_metrics", {}),
        }
        
        # 预估时长
        estimated_duration = scheme_output.get("estimated_duration_minutes") or 60
        
        # AI特有字段（在创建后通过原生SQL更新，因为SchemeCreate不包含这些字段）
        ai_confidence_score = scheme_output.get("confidence_score", 0.8)
        ai_reasoning = scheme_output.get("rationale", "")
        
        scheme_data = SchemeCreate(
            event_id=UUID(event_id),
            scenario_id=UUID(scenario_id),
            scheme_type=scheme_type,
            source=SchemeSource.ai_generated,
            title=title[:500],  # 截断以符合数据库限制
            objective=objective,
            description=description,
            constraints=constraints,
            risk_assessment=risk_assessment,
            estimated_duration_minutes=estimated_duration,
        )
        
        scheme_response = await self._service.create(scheme_data)
        
        # 更新AI字段（SchemeCreate不包含ai_confidence_score和ai_reasoning）
        await self._update_ai_fields(scheme_response.id, ai_confidence_score, ai_reasoning)
        
        return scheme_response
    
    async def _update_ai_fields(
        self,
        scheme_id: UUID,
        ai_confidence_score: float,
        ai_reasoning: str,
    ) -> None:
        """更新AI特有字段"""
        from sqlalchemy import text
        
        sql = """
            UPDATE operational_v2.schemes_v2
            SET ai_confidence_score = :score, ai_reasoning = :reasoning
            WHERE id = :scheme_id
        """
        await self._db.execute(
            text(sql),
            {"scheme_id": str(scheme_id), "score": ai_confidence_score, "reasoning": ai_reasoning}
        )
        await self._db.commit()
    
    async def _create_allocation(
        self,
        scheme_id: UUID,
        allocation: Dict[str, Any],
    ) -> Any:
        """创建资源分配记录"""
        # 从AI输出中提取资源ID（可能是字符串或UUID）
        resource_id_str = allocation.get("resource_id", "")
        try:
            resource_id = UUID(resource_id_str) if resource_id_str else None
        except ValueError:
            # 如果不是有效UUID，生成一个新的（用于模拟数据）
            from uuid import uuid4
            resource_id = uuid4()
            logger.warning(f"资源ID不是有效UUID，生成新ID: {resource_id}")
        
        allocation_data = ResourceAllocationCreate(
            resource_type=allocation.get("resource_type", "rescue_team"),
            resource_id=resource_id,
            resource_name=allocation.get("resource_name", "未知资源"),
            assigned_role=", ".join(allocation.get("assigned_task_types", [])),
            match_score=allocation.get("match_score"),
            full_recommendation_reason=allocation.get("recommendation_reason", ""),
            alternative_resources=allocation.get("alternatives", []),
        )
        
        return await self._service.add_allocation(scheme_id, allocation_data)
    
    def _map_disaster_to_scheme_type(self, disaster_type: str) -> SchemeType:
        """灾害类型映射到方案类型"""
        mapping = {
            "earthquake": SchemeType.emergency_rescue,
            "fire": SchemeType.fire_fighting,
            "flood": SchemeType.flood_rescue,
            "hazmat": SchemeType.hazmat_response,
            "landslide": SchemeType.emergency_rescue,
            "typhoon": SchemeType.comprehensive,
            "explosion": SchemeType.emergency_rescue,
            "traffic_accident": SchemeType.traffic_control,
        }
        return mapping.get(disaster_type, SchemeType.comprehensive)
    
    def _generate_objective(self, event_analysis: Dict[str, Any]) -> str:
        """根据事件分析生成方案目标"""
        disaster_type = event_analysis.get("disaster_type", "未知灾害")
        assessment = event_analysis.get("assessment", {})
        level = assessment.get("disaster_level", "III")
        
        casualties = assessment.get("estimated_casualties", {})
        trapped = casualties.get("trapped", 0)
        injured = casualties.get("injured", 0)
        
        objective_parts = [f"应对{disaster_type}（{level}级）"]
        
        if trapped > 0:
            objective_parts.append(f"搜救被困人员约{trapped}人")
        if injured > 0:
            objective_parts.append(f"救治伤员约{injured}人")
        
        objective_parts.append("保障人民群众生命财产安全")
        
        return "，".join(objective_parts)
