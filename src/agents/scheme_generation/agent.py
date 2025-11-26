"""
方案生成Agent

封装LangGraph执行，提供同步和异步接口
支持数据库集成：预查询队伍、保存方案、资源锁定
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import BaseAgent
from ..db import TeamDataProvider, SchemePersister
from ..utils.resource_lock import ResourceLock
from .state import SchemeGenerationState
from .graph import build_scheme_generation_graph

logger = logging.getLogger(__name__)

# 默认约束条件
DEFAULT_CONSTRAINTS = {
    "max_response_time_min": 30,
    "max_teams": 10,
    "reserve_ratio": 0.2,
}

# 默认优化权重
DEFAULT_WEIGHTS = {
    "response_time": 0.35,
    "coverage_rate": 0.30,
    "cost": 0.15,
    "risk": 0.20,
}

# 默认生成选项
DEFAULT_OPTIONS = {
    "generate_alternatives": 3,
    "include_rationale": True,
    "include_pareto": True,
}


class SchemeGenerationAgent(BaseAgent[SchemeGenerationState]):
    """
    方案生成Agent
    
    基于军事版架构实现的应急救灾方案生成Agent，包含：
    1. 规则触发（TRRRuleEngine）
    2. 能力提取（CapabilityMappingProvider）
    3. 资源匹配（RescueTeamSelector + CSP）
    4. 多目标优化（NSGA-II）
    5. 硬规则过滤 + 软规则评分（TOPSIS）
    
    使用示例:
    ```python
    agent = SchemeGenerationAgent()
    result = agent.run(
        event_id="event-001",
        scenario_id="scenario-001",
        event_analysis={
            "disaster_type": "earthquake",
            "assessment": {"estimated_casualties": {"trapped": 20}},
        },
    )
    ```
    """
    
    def __init__(self) -> None:
        """初始化方案生成Agent"""
        super().__init__(name="SchemeGenerationAgent")
    
    def build_graph(self) -> CompiledStateGraph:
        """构建LangGraph"""
        return build_scheme_generation_graph()
    
    def prepare_input(self, **kwargs: Any) -> SchemeGenerationState:
        """
        准备输入状态
        
        Args:
            event_id: 事件ID
            scenario_id: 想定ID
            event_analysis: 事件分析结果（来自EventAnalysisAgent）
            constraints: 约束条件（可选）
            optimization_weights: 优化权重（可选）
            options: 生成选项（可选）
            available_teams: 预查询的队伍数据（可选）
            
        Returns:
            初始化的状态
        """
        # 处理ID
        event_id = kwargs.get("event_id", "")
        if isinstance(event_id, UUID):
            event_id = str(event_id)
        
        scenario_id = kwargs.get("scenario_id", "")
        if isinstance(scenario_id, UUID):
            scenario_id = str(scenario_id)
        
        # 合并约束条件
        constraints = {**DEFAULT_CONSTRAINTS, **kwargs.get("constraints", {})}
        
        # 合并优化权重
        optimization_weights = {**DEFAULT_WEIGHTS, **kwargs.get("optimization_weights", {})}
        
        # 合并生成选项
        options = {**DEFAULT_OPTIONS, **kwargs.get("options", {})}
        
        state: SchemeGenerationState = {
            # 输入
            "event_id": event_id,
            "scenario_id": scenario_id,
            "event_analysis": kwargs.get("event_analysis", {}),
            "constraints": constraints,
            "optimization_weights": optimization_weights,
            "options": options,
            
            # 预查询数据
            "available_teams": kwargs.get("available_teams", []),
            
            # 中间结果（初始化为空）
            "matched_rules": [],
            "capability_requirements": [],
            "resource_candidates": [],
            "resource_allocations": [],
            "scene_priorities": [],
            "conflict_resolutions": [],
            "pareto_solutions": [],
            "hard_rule_results": [],
            "feasible_schemes": [],
            "scheme_scores": [],
            "recommended_scheme": None,
            
            # 输出
            "schemes": [],
            
            # 追踪
            "trace": {"algorithms_used": [], "nodes_executed": []},
            "errors": [],
            
            # 时间戳
            "started_at": None,
            "completed_at": None,
        }
        
        return state
    
    async def run_with_db(
        self,
        db: AsyncSession,
        event_id: str,
        scenario_id: str,
        event_analysis: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
        optimization_weights: Optional[Dict[str, float]] = None,
        options: Optional[Dict[str, Any]] = None,
        save_to_db: bool = True,
    ) -> Dict[str, Any]:
        """
        带数据库集成的运行方法
        
        流程：
        1. 预查询可用队伍
        2. 执行方案生成（选择队伍）
        3. 锁定被选中的队伍（防止并发冲突）
        4. 保存方案 + 更新队伍状态
        5. 释放锁
        
        Args:
            db: 数据库session
            event_id: 事件ID
            scenario_id: 场景ID
            event_analysis: 事件分析结果
            constraints: 约束条件
            optimization_weights: 优化权重
            options: 生成选项
            save_to_db: 是否保存到数据库
            
        Returns:
            方案生成结果
        """
        logger.info(f"开始方案生成（数据库模式）: event={event_id}")
        
        resource_lock: Optional[ResourceLock] = None
        
        try:
            # 1. 预查询可用队伍
            available_teams = await self._fetch_available_teams(db, event_analysis)
            logger.info(f"预查询队伍完成: {len(available_teams)}支队伍")
            
            # 2. 执行LangGraph
            result = self.run(
                event_id=event_id,
                scenario_id=scenario_id,
                event_analysis=event_analysis,
                constraints=constraints or {},
                optimization_weights=optimization_weights or {},
                options=options or {},
                available_teams=available_teams,
            )
            
            # 3. 保存方案到数据库
            if save_to_db and result.get("success") and result.get("schemes"):
                # 3.1 提取被分配的队伍ID
                allocated_team_ids = self._extract_allocated_team_ids(result)
                
                # 3.2 锁定队伍（防止并发冲突）
                if allocated_team_ids:
                    resource_lock = ResourceLock(event_id=event_id)
                    await resource_lock.acquire_team_locks(allocated_team_ids, db=db)
                    logger.info(f"队伍锁定成功: {len(allocated_team_ids)}支队伍")
                    result["trace"]["resource_lock"] = {
                        "locked_teams": allocated_team_ids,
                        "lock_type": "redis" if resource_lock._use_redis else "database",
                    }
                
                # 3.3 保存方案
                persist_result = await self._save_schemes_to_db(
                    db=db,
                    event_id=event_id,
                    scenario_id=scenario_id,
                    event_analysis=event_analysis,
                    result=result,
                    allocated_team_ids=allocated_team_ids,
                )
                result["db_persist"] = persist_result
            
            return result
            
        finally:
            # 4. 释放锁（Redis锁，数据库锁在事务提交时自动释放）
            if resource_lock is not None:
                await resource_lock.release_locks()
    
    def _extract_allocated_team_ids(self, result: Dict[str, Any]) -> List[str]:
        """
        从方案结果中提取被分配的队伍ID
        """
        team_ids: List[str] = []
        
        # 从resource_allocations中提取
        allocations = result.get("resource_allocations", [])
        for alloc in allocations:
            resource_id = alloc.get("resource_id", "")
            if resource_id and resource_id not in team_ids:
                team_ids.append(resource_id)
        
        return team_ids
    
    async def _fetch_available_teams(
        self,
        db: AsyncSession,
        event_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """从数据库预查询可用队伍"""
        try:
            provider = TeamDataProvider(db)
            
            location = event_analysis.get("location", {})
            event_lat = location.get("latitude", 0)
            event_lng = location.get("longitude", 0)
            disaster_type = event_analysis.get("disaster_type", "")
            
            event_location = (event_lat, event_lng) if event_lat and event_lng else None
            
            teams = await provider.get_available_teams(
                event_location=event_location,
                disaster_type=disaster_type,
                max_distance_km=100.0,
            )
            return teams
        except Exception as e:
            logger.warning(f"预查询队伍失败: {e}，将使用模拟数据")
            return []
    
    async def _save_schemes_to_db(
        self,
        db: AsyncSession,
        event_id: str,
        scenario_id: str,
        event_analysis: Dict[str, Any],
        result: Dict[str, Any],
        allocated_team_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        保存方案到数据库
        
        同时更新被分配队伍的状态为deployed
        """
        try:
            persister = SchemePersister(db)
            
            schemes = result.get("schemes", [])
            if not schemes:
                return {"success": False, "error": "无方案可保存"}
            
            # 只保存推荐方案（第一个）
            scheme_output = schemes[0]
            
            # 从方案中获取资源分配
            resource_allocations = scheme_output.get("resource_allocations", [])
            
            # 保存方案并更新队伍状态
            return await persister.save_scheme(
                event_id=event_id,
                scenario_id=scenario_id,
                scheme_output=scheme_output,
                event_analysis=event_analysis,
                resource_allocations=resource_allocations,
                update_team_status=True,
                allocated_team_ids=allocated_team_ids,
            )
        except Exception as e:
            logger.error(f"保存方案到数据库失败: {e}")
            return {"success": False, "error": str(e)}
    
    def process_output(self, state: SchemeGenerationState) -> Dict[str, Any]:
        """
        处理输出结果
        
        Args:
            state: 最终状态
            
        Returns:
            格式化的API响应
        """
        schemes = state.get("schemes", [])
        pareto_solutions = state.get("pareto_solutions", [])
        scheme_scores = state.get("scheme_scores", [])
        
        # 构造响应
        result = {
            "success": True,
            "event_id": state.get("event_id", ""),
            "schemes": schemes,
            "pareto_solutions": [
                {
                    "id": s["solution_id"],
                    "objectives": s["objectives"],
                }
                for s in pareto_solutions
            ] if state.get("options", {}).get("include_pareto", True) else [],
            "scheme_count": len(schemes),
            "recommended_scheme_id": schemes[0]["scheme_id"] if schemes else None,
            "trace": state.get("trace", {}),
            "errors": state.get("errors", []),
            "started_at": state.get("started_at").isoformat() + "Z" if state.get("started_at") else None,
            "completed_at": state.get("completed_at").isoformat() + "Z" if state.get("completed_at") else None,
        }
        
        return result
