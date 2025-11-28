"""
驻扎点选址智能体入口

提供Agent调用接口，支持：
1. Agent模式：LLM分析 + 算法计算 + 解释生成
2. 降级模式：纯算法计算
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.staging_area.graph import staging_area_graph
from src.agents.staging_area.state import StagingAreaAgentState

logger = logging.getLogger(__name__)


class StagingAreaAgent:
    """
    驻扎点选址智能体
    
    提供统一的Agent调用接口，内部使用LangGraph编排流程。
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        初始化Agent
        
        Args:
            db: 数据库会话
        """
        self._db = db
    
    async def recommend(
        self,
        scenario_id: UUID,
        epicenter_lon: float,
        epicenter_lat: float,
        magnitude: float,
        team_id: UUID,
        team_base_lon: float,
        team_base_lat: float,
        rescue_targets: List[Dict[str, Any]],
        disaster_description: Optional[str] = None,
        team_name: str = "救援队",
        top_n: int = 5,
        skip_llm_analysis: bool = False,
    ) -> Dict[str, Any]:
        """
        执行驻扎点推荐
        
        Args:
            scenario_id: 想定ID
            epicenter_lon: 震中经度
            epicenter_lat: 震中纬度
            magnitude: 震级
            team_id: 队伍ID
            team_base_lon: 队伍驻地经度
            team_base_lat: 队伍驻地纬度
            rescue_targets: 救援目标列表 [{id, lon, lat, name, priority}]
            disaster_description: 自然语言灾情描述（可选）
            team_name: 队伍名称
            top_n: 返回前N个推荐
            skip_llm_analysis: 是否跳过LLM分析（降级为纯算法）
            
        Returns:
            推荐结果字典
        """
        start_time = time.perf_counter()
        
        # 构建初始状态
        initial_state: StagingAreaAgentState = {
            # 输入
            "disaster_description": disaster_description or "",
            "scenario_id": scenario_id,
            "epicenter_lon": epicenter_lon,
            "epicenter_lat": epicenter_lat,
            "magnitude": magnitude,
            "team_id": team_id,
            "team_base_lon": team_base_lon,
            "team_base_lat": team_base_lat,
            "team_name": team_name,
            "rescue_targets": rescue_targets,
            "skip_llm_analysis": skip_llm_analysis,
            "top_n": top_n,
            # 初始化
            "errors": [],
            "timing": {},
            "processing_mode": "agent" if not skip_llm_analysis else "algorithm_only",
            "overall_confidence": 0.0,
        }
        
        try:
            # 运行Graph
            # 注意：LangGraph需要通过config传递db
            config = {"configurable": {"db": self._db}}
            
            # 由于LangGraph节点签名问题，我们手动执行流程
            final_state = await self._run_graph(initial_state)
            
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            final_state["timing"]["total_ms"] = elapsed_ms
            
            # 构建响应
            return self._build_response(final_state)
            
        except Exception as e:
            logger.error(f"[StagingAreaAgent] 执行异常: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Agent执行异常: {str(e)}",
                "processing_mode": "error",
                "elapsed_ms": int((time.perf_counter() - start_time) * 1000),
            }
    
    async def _run_graph(self, state: StagingAreaAgentState) -> StagingAreaAgentState:
        """
        手动执行Graph流程（6节点完整版）
        
        由于LangGraph节点需要db参数，这里手动编排执行。
        
        流程（修正版）：
        understand → search_candidates → [terrain | communication | safety] → evaluate → explain
                                         ↑__________ 并行执行 __________↑
        """
        import asyncio
        from src.agents.staging_area.nodes import (
            understand_disaster,
            analyze_terrain,
            analyze_communication,
            analyze_safety,
            evaluate_candidates,
            explain_decision,
        )
        
        # 1. 灾情理解
        logger.info("[StagingAreaAgent] 执行灾情理解节点")
        understand_result = await understand_disaster(state, self._db)
        state = {**state, **understand_result}
        
        # 检查是否继续
        errors = state.get("errors", [])
        critical_errors = [e for e in errors if "缺少" in e and ("scenario" in e or "震中" in e)]
        if critical_errors:
            logger.warning(f"[StagingAreaAgent] 关键参数缺失，终止流程: {critical_errors}")
            return state
        
        # 2. 先搜索候选点（为分析节点提供数据）
        logger.info("[StagingAreaAgent] 搜索候选点")
        candidate_sites = await self._search_candidate_sites(state)
        if candidate_sites:
            state["candidate_sites"] = candidate_sites
            logger.info(f"[StagingAreaAgent] 找到 {len(candidate_sites)} 个候选点")
        else:
            logger.warning("[StagingAreaAgent] 未找到候选点，跳过分析节点")
        
        # 3. 并行执行分析节点（如果未跳过LLM分析且有候选点）
        if not state.get("skip_llm_analysis", False) and candidate_sites:
            logger.info("[StagingAreaAgent] 并行执行分析节点: terrain, communication, safety")
            
            # 并行执行三个分析任务
            terrain_task = asyncio.create_task(analyze_terrain(state, self._db))
            communication_task = asyncio.create_task(analyze_communication(state, self._db))
            safety_task = asyncio.create_task(analyze_safety(state, self._db))
            
            # 等待所有任务完成
            terrain_result, communication_result, safety_result = await asyncio.gather(
                terrain_task,
                communication_task,
                safety_task,
                return_exceptions=True,
            )
            
            # 合并结果（处理异常情况）
            if isinstance(terrain_result, dict):
                state = {**state, **terrain_result}
            else:
                logger.error(f"[StagingAreaAgent] 地形分析异常: {terrain_result}")
                state["errors"] = state.get("errors", []) + [f"地形分析异常: {str(terrain_result)}"]
            
            if isinstance(communication_result, dict):
                state = {**state, **communication_result}
            else:
                logger.error(f"[StagingAreaAgent] 通信分析异常: {communication_result}")
                state["errors"] = state.get("errors", []) + [f"通信分析异常: {str(communication_result)}"]
            
            if isinstance(safety_result, dict):
                state = {**state, **safety_result}
            else:
                logger.error(f"[StagingAreaAgent] 安全分析异常: {safety_result}")
                state["errors"] = state.get("errors", []) + [f"安全分析异常: {str(safety_result)}"]
        else:
            if state.get("skip_llm_analysis", False):
                logger.info("[StagingAreaAgent] skip_llm_analysis=True，跳过分析节点")
            else:
                logger.info("[StagingAreaAgent] 无候选点，跳过分析节点")
        
        # 4. 评估排序
        logger.info("[StagingAreaAgent] 执行评估排序节点")
        evaluate_result = await evaluate_candidates(state, self._db)
        state = {**state, **evaluate_result}
        
        # 检查是否继续
        if not state.get("ranked_sites"):
            logger.warning("[StagingAreaAgent] 无候选点，终止流程")
            return state
        
        # 5. 决策解释
        logger.info("[StagingAreaAgent] 执行决策解释节点")
        explain_result = await explain_decision(state, self._db)
        state = {**state, **explain_result}
        
        return state
    
    async def _search_candidate_sites(self, state: StagingAreaAgentState) -> List[Dict[str, Any]]:
        """
        搜索候选驻扎点（不含路径验证）
        
        仅通过 PostGIS 空间查询获取候选点，用于后续 LLM 分析。
        路径验证在 evaluate_candidates 节点中执行。
        """
        from src.domains.staging_area.repository import StagingAreaRepository
        
        try:
            repo = StagingAreaRepository(self._db)
            
            # 获取参数
            scenario_id = state.get("scenario_id")
            epicenter_lon = state.get("epicenter_lon")
            epicenter_lat = state.get("epicenter_lat")
            magnitude = state.get("magnitude", 6.0)
            
            if not all([scenario_id, epicenter_lon, epicenter_lat]):
                return []
            
            # 计算搜索半径（基于震级）
            search_radius_m = (30 + (magnitude - 5) * 10) * 1000  # 5级30km，7级50km
            
            # 查询候选点
            candidates = await repo.search_candidates(
                scenario_id=scenario_id,
                center_lon=epicenter_lon,
                center_lat=epicenter_lat,
                max_distance_m=search_radius_m,
                max_results=20,
            )
            
            # 转换为dict列表
            result = []
            for c in candidates:
                # 处理枚举类型
                site_type = c.site_type.value if hasattr(c.site_type, 'value') else str(c.site_type)
                ground_stability = c.ground_stability.value if hasattr(c.ground_stability, 'value') else str(c.ground_stability)
                network_type = c.primary_network_type.value if hasattr(c.primary_network_type, 'value') else str(c.primary_network_type)
                
                result.append({
                    "site_id": str(c.id),
                    "site_code": c.site_code,
                    "name": c.name,
                    "site_type": site_type,
                    "longitude": c.longitude,
                    "latitude": c.latitude,
                    "area_m2": c.area_m2,
                    "slope_degree": c.slope_degree,
                    "ground_stability": ground_stability,
                    "has_water_supply": c.has_water_supply,
                    "has_power_supply": c.has_power_supply,
                    "can_helicopter_land": c.can_helicopter_land,
                    "primary_network_type": network_type,
                    "signal_quality": c.signal_quality,
                    "distance_to_danger_m": c.distance_to_danger_m,
                })
            
            return result
            
        except Exception as e:
            logger.error(f"[StagingAreaAgent] 候选点搜索失败: {e}", exc_info=True)
            return []
    
    def _build_response(self, state: StagingAreaAgentState) -> Dict[str, Any]:
        """构建响应"""
        ranked_sites = state.get("ranked_sites", [])
        errors = state.get("errors", [])
        
        # 转换SiteExplanation为dict
        site_explanations = []
        for exp in (state.get("site_explanations") or []):
            if hasattr(exp, "model_dump"):
                site_explanations.append(exp.model_dump())
            elif isinstance(exp, dict):
                site_explanations.append(exp)
        
        # 转换RiskWarning为dict
        risk_warnings = []
        for warn in (state.get("risk_warnings") or []):
            if hasattr(warn, "model_dump"):
                risk_warnings.append(warn.model_dump())
            elif isinstance(warn, dict):
                risk_warnings.append(warn)
        
        # 转换AlternativeSuggestion为dict
        alternatives = []
        for alt in (state.get("alternatives") or []):
            if hasattr(alt, "model_dump"):
                alternatives.append(alt.model_dump())
            elif isinstance(alt, dict):
                alternatives.append(alt)
        
        return {
            "success": len(ranked_sites) > 0,
            "processing_mode": state.get("processing_mode", "unknown"),
            "recommended_sites": ranked_sites,
            "site_explanations": site_explanations,
            "risk_warnings": risk_warnings,
            "alternatives": alternatives,
            "summary": state.get("summary", ""),
            "errors": errors,
            "timing": state.get("timing", {}),
        }
    
    async def recommend_with_description(
        self,
        disaster_description: str,
        scenario_id: UUID,
        team_id: UUID,
        team_base_lon: float,
        team_base_lat: float,
        rescue_targets: List[Dict[str, Any]],
        epicenter_lon: Optional[float] = None,
        epicenter_lat: Optional[float] = None,
        magnitude: Optional[float] = None,
        team_name: str = "救援队",
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        使用自然语言灾情描述进行推荐
        
        此方法会使用LLM解析灾情描述，提取震中和震级信息。
        如果提供了epicenter_lon/lat/magnitude，则使用提供的值。
        
        Args:
            disaster_description: 自然语言灾情描述
            scenario_id: 想定ID
            team_id: 队伍ID
            team_base_lon: 队伍驻地经度
            team_base_lat: 队伍驻地纬度
            rescue_targets: 救援目标列表
            epicenter_lon: 震中经度（可选）
            epicenter_lat: 震中纬度（可选）
            magnitude: 震级（可选）
            team_name: 队伍名称
            top_n: 返回前N个推荐
            
        Returns:
            推荐结果字典
        """
        # 如果未提供震中坐标，需要从描述中提取或使用默认值
        if epicenter_lon is None or epicenter_lat is None:
            # TODO: 实现从描述中提取坐标的逻辑
            # 暂时返回错误
            return {
                "success": False,
                "error": "使用自然语言描述时，必须提供震中坐标（epicenter_lon, epicenter_lat）",
                "processing_mode": "error",
            }
        
        return await self.recommend(
            scenario_id=scenario_id,
            epicenter_lon=epicenter_lon,
            epicenter_lat=epicenter_lat,
            magnitude=magnitude or 6.0,
            team_id=team_id,
            team_base_lon=team_base_lon,
            team_base_lat=team_base_lat,
            rescue_targets=rescue_targets,
            disaster_description=disaster_description,
            team_name=team_name,
            top_n=top_n,
            skip_llm_analysis=False,
        )
