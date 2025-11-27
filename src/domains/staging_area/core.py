"""
救援队驻扎点选址核心算法

参考 ResourceSchedulingCore 设计模式，提供纯算法实现。
不使用 LangGraph，因为核心是空间优化问题，不需要LLM参与决策。
"""
from __future__ import annotations

import logging
import math
import time
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.staging_area.repository import StagingAreaRepository
from src.domains.staging_area.schemas import (
    CandidateSite,
    CandidateWithRoutes,
    DimensionScores,
    EarthquakeParams,
    EvaluationWeights,
    NetworkType,
    RankedStagingSite,
    RescueTarget,
    RiskZone,
    RiskZoneType,
    RouteToTarget,
    StagingConstraints,
    StagingRecommendation,
    TargetPriority,
    TeamInfo,
)
from src.planning.algorithms.routing.db_route_engine import (
    DatabaseRouteEngine,
    VehicleCapability,
    Point,
    InfeasiblePathError,
)

logger = logging.getLogger(__name__)


PRIORITY_WEIGHTS: Dict[TargetPriority, float] = {
    TargetPriority.CRITICAL: 4.0,
    TargetPriority.HIGH: 2.0,
    TargetPriority.MEDIUM: 1.0,
    TargetPriority.LOW: 0.5,
}


class StagingAreaCore:
    """
    救援队驻扎点选址核心算法
    
    职责：
    1. 根据震中和灾害信息计算风险区域
    2. 搜索并过滤候选驻扎点
    3. 计算到救援目标的实际路径
    4. 多目标评估和排序
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repository = StagingAreaRepository(db)
        self._route_engine = DatabaseRouteEngine(db)
    
    async def recommend(
        self,
        scenario_id: UUID,
        earthquake: EarthquakeParams,
        rescue_targets: List[RescueTarget],
        team: TeamInfo,
        constraints: StagingConstraints,
        weights: Optional[EvaluationWeights] = None,
    ) -> StagingRecommendation:
        """
        执行驻扎点推荐
        
        Args:
            scenario_id: 想定ID
            earthquake: 地震参数
            rescue_targets: 救援目标列表
            team: 救援队伍信息
            constraints: 约束条件
            weights: 评估权重（可选）
            
        Returns:
            StagingRecommendation: 推荐结果
        """
        start_time = time.perf_counter()
        weights = weights or EvaluationWeights()
        
        logger.info(
            f"[驻扎点选址] 开始: scenario={scenario_id}, "
            f"震中=({earthquake.epicenter_lon:.4f}, {earthquake.epicenter_lat:.4f}), "
            f"震级={earthquake.magnitude}, 目标数={len(rescue_targets)}"
        )
        
        try:
            # 1. 计算风险区域
            risk_zones = await self._calculate_risk_zones(scenario_id, earthquake)
            logger.info(f"[驻扎点选址] 风险区域计算完成: {len(risk_zones)} 个区域")
            
            # 2. 搜索候选点
            candidates = await self._search_candidates(
                scenario_id=scenario_id,
                earthquake=earthquake,
                constraints=constraints,
            )
            
            if not candidates:
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                logger.warning("[驻扎点选址] 无可用候选点")
                return StagingRecommendation(
                    success=False,
                    error="无可用候选驻扎点，请检查数据或放宽约束条件",
                    risk_zones_count=len(risk_zones),
                    elapsed_ms=elapsed_ms,
                )
            
            logger.info(f"[驻扎点选址] 候选点搜索完成: {len(candidates)} 个")
            
            # 3. 批量验证路径可行性
            candidates_with_routes = await self._validate_routes_batch(
                candidates=candidates,
                targets=rescue_targets,
                team=team,
                scenario_id=scenario_id,
            )
            
            reachable = [c for c in candidates_with_routes if c.is_reachable]
            logger.info(f"[驻扎点选址] 路径验证完成: {len(reachable)}/{len(candidates)} 可达")
            
            if not reachable:
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                return StagingRecommendation(
                    success=False,
                    error="所有候选点均不可达，请检查路网数据或调整搜索范围",
                    risk_zones_count=len(risk_zones),
                    candidates_total=len(candidates),
                    elapsed_ms=elapsed_ms,
                )
            
            # 4. 多目标评估排序
            ranked_sites = self._evaluate_and_rank(
                candidates=reachable,
                targets=rescue_targets,
                constraints=constraints,
                weights=weights,
            )
            
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(
                f"[驻扎点选址] 完成: 推荐 {min(len(ranked_sites), constraints.top_n)} 个, "
                f"耗时 {elapsed_ms}ms"
            )
            
            return StagingRecommendation(
                success=True,
                risk_zones_count=len(risk_zones),
                candidates_total=len(candidates),
                candidates_reachable=len(reachable),
                recommended_sites=ranked_sites[:constraints.top_n],
                elapsed_ms=elapsed_ms,
            )
            
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"[驻扎点选址] 异常: {e}", exc_info=True)
            return StagingRecommendation(
                success=False,
                error=f"选址过程异常: {str(e)}",
                elapsed_ms=elapsed_ms,
            )
    
    async def _calculate_risk_zones(
        self,
        scenario_id: UUID,
        earthquake: EarthquakeParams,
    ) -> List[RiskZone]:
        """
        计算综合风险区域
        
        来源:
        1. 烈度衰减模型计算的影响区
        2. 数据库中已标记的危险区域
        """
        zones: List[RiskZone] = []
        
        # 1. 基于烈度衰减模型计算（简化公式）
        # 烈度 I = M - k*log10(R) - c*R, 其中M为震级，R为距离(km)
        # 反推：R = f(M, I_target)
        red_radius_km = self._estimate_intensity_radius(earthquake.magnitude, target_intensity=8)
        orange_radius_km = self._estimate_intensity_radius(earthquake.magnitude, target_intensity=6)
        
        zones.append(RiskZone(
            zone_type=RiskZoneType.SEISMIC_RED,
            geometry_wkt=f"POINT({earthquake.epicenter_lon} {earthquake.epicenter_lat})",
            risk_level=10,
            passable=False,
            source=f"seismic_model_radius_{red_radius_km:.1f}km",
        ))
        
        zones.append(RiskZone(
            zone_type=RiskZoneType.SEISMIC_ORANGE,
            geometry_wkt=f"POINT({earthquake.epicenter_lon} {earthquake.epicenter_lat})",
            risk_level=7,
            passable=False,
            source=f"seismic_model_radius_{orange_radius_km:.1f}km",
        ))
        
        # 2. 查询数据库中的危险区域
        db_zones = await self._repository.get_danger_zones(scenario_id)
        for z in db_zones:
            zone_type = self._map_area_type_to_risk_zone(z["area_type"])
            zones.append(RiskZone(
                zone_type=zone_type,
                geometry_wkt=z["geometry_wkt"],
                risk_level=z["risk_level"],
                passable=z["passable"],
                source="database",
            ))
        
        return zones
    
    @staticmethod
    def _estimate_intensity_radius(magnitude: float, target_intensity: float) -> float:
        """
        估算指定烈度对应的影响半径（km）
        
        使用简化的烈度衰减公式：I = 1.5*M - 3.5*log10(R) - 0.0087*R + 2
        反推R较复杂，这里使用经验公式近似
        """
        if magnitude <= 0:
            return 0.0
        
        # 简化经验公式
        base_radius = 10 ** ((magnitude - target_intensity + 2) / 3.5)
        # 限制范围
        return min(max(base_radius, 1.0), 200.0)
    
    @staticmethod
    def _map_area_type_to_risk_zone(area_type: str) -> RiskZoneType:
        mapping = {
            "danger_zone": RiskZoneType.DANGER_ZONE,
            "blocked": RiskZoneType.BLOCKED,
            "flooded": RiskZoneType.FLOODED,
            "fire": RiskZoneType.FIRE,
            "landslide": RiskZoneType.LANDSLIDE,
        }
        return mapping.get(area_type, RiskZoneType.DANGER_ZONE)
    
    async def _search_candidates(
        self,
        scenario_id: UUID,
        earthquake: EarthquakeParams,
        constraints: StagingConstraints,
    ) -> List[CandidateSite]:
        """
        搜索候选驻扎点
        
        使用PostGIS空间查询，排除危险区域内的点位。
        """
        return await self._repository.search_candidates(
            scenario_id=scenario_id,
            center_lon=earthquake.epicenter_lon,
            center_lat=earthquake.epicenter_lat,
            max_distance_m=constraints.max_search_radius_m,
            min_buffer_from_danger_m=constraints.min_buffer_m,
            max_slope_deg=constraints.max_slope_deg,
            require_water=constraints.require_water_supply,
            require_power=constraints.require_power_supply,
            require_helicopter=constraints.require_helicopter_landing,
            max_results=constraints.max_candidates,
        )
    
    async def _validate_routes_batch(
        self,
        candidates: List[CandidateSite],
        targets: List[RescueTarget],
        team: TeamInfo,
        scenario_id: UUID,
    ) -> List[CandidateWithRoutes]:
        """
        批量验证路径可行性
        
        复用 DatabaseRouteEngine：
        - 队伍驻地 → 候选点
        - 候选点 → 各救援目标
        """
        results: List[CandidateWithRoutes] = []
        
        # 构建车辆能力参数
        vehicle = VehicleCapability(
            vehicle_id=team.vehicle_id or team.team_id,
            vehicle_code=team.team_name,
            max_speed_kmh=int(team.max_speed_kmh),
            is_all_terrain=False,
            terrain_capabilities=[],
            terrain_speed_factors={},
            max_gradient_percent=None,
            max_wading_depth_m=None,
            width_m=None,
            height_m=None,
            total_weight_kg=None,
        )
        
        team_point = Point(lon=team.base_lon, lat=team.base_lat)
        
        for candidate in candidates:
            candidate_point = Point(lon=candidate.longitude, lat=candidate.latitude)
            
            # 1. 规划：驻地 → 候选点
            try:
                route_to_site = await self._route_engine.plan_route(
                    start=team_point,
                    end=candidate_point,
                    vehicle=vehicle,
                    scenario_id=scenario_id,
                )
            except InfeasiblePathError:
                logger.debug(f"[路径验证] 候选点 {candidate.name} 从驻地不可达")
                continue
            except Exception as e:
                logger.warning(f"[路径验证] 规划到 {candidate.name} 失败: {e}")
                continue
            
            # 2. 规划：候选点 → 各目标
            routes_to_targets: List[RouteToTarget] = []
            for target in targets:
                target_point = Point(lon=target.longitude, lat=target.latitude)
                try:
                    route = await self._route_engine.plan_route(
                        start=candidate_point,
                        end=target_point,
                        vehicle=vehicle,
                        scenario_id=scenario_id,
                    )
                    routes_to_targets.append(RouteToTarget(
                        target_id=target.id,
                        target_name=target.name,
                        distance_m=route.distance_m,
                        duration_seconds=route.duration_seconds,
                        priority=target.priority,
                    ))
                except (InfeasiblePathError, Exception):
                    pass
            
            # 至少能到达一个目标
            if routes_to_targets:
                results.append(CandidateWithRoutes(
                    site=candidate,
                    route_from_base_distance_m=route_to_site.distance_m,
                    route_from_base_duration_s=route_to_site.duration_seconds,
                    routes_to_targets=routes_to_targets,
                    is_reachable=True,
                ))
        
        return results
    
    def _evaluate_and_rank(
        self,
        candidates: List[CandidateWithRoutes],
        targets: List[RescueTarget],
        constraints: StagingConstraints,
        weights: EvaluationWeights,
    ) -> List[RankedStagingSite]:
        """
        多目标加权评估排序
        """
        ranked: List[RankedStagingSite] = []
        
        # 计算归一化参数
        max_response_time = max(
            max((r.duration_seconds for r in c.routes_to_targets), default=0)
            for c in candidates
        ) or 1
        max_danger_dist = max(
            c.site.distance_to_danger_m or 0 for c in candidates
        ) or 1
        max_logistics_dist = max(
            (c.site.nearest_supply_depot_m or 0) + (c.site.nearest_medical_point_m or 0)
            for c in candidates
        ) or 1
        
        for c in candidates:
            scores = self._calculate_dimension_scores(
                candidate=c,
                targets=targets,
                max_response_time=max_response_time,
                max_danger_dist=max_danger_dist,
                max_logistics_dist=max_logistics_dist,
            )
            
            total = (
                weights.response_time * scores.response_time +
                weights.safety * scores.safety +
                weights.logistics * scores.logistics +
                weights.facility * scores.facility +
                weights.communication * scores.communication
            )
            
            avg_response_s = self._calc_weighted_avg_response(c.routes_to_targets)
            
            ranked.append(RankedStagingSite(
                site_id=c.site.id,
                site_code=c.site.site_code,
                name=c.site.name,
                site_type=c.site.site_type.value,
                longitude=c.site.longitude,
                latitude=c.site.latitude,
                area_m2=c.site.area_m2,
                slope_degree=c.site.slope_degree,
                has_water_supply=c.site.has_water_supply,
                has_power_supply=c.site.has_power_supply,
                can_helicopter_land=c.site.can_helicopter_land,
                network_type=c.site.primary_network_type.value,
                distance_to_danger_m=c.site.distance_to_danger_m,
                route_from_base_distance_m=c.route_from_base_distance_m,
                route_from_base_duration_s=c.route_from_base_duration_s,
                avg_response_time_to_targets_s=avg_response_s,
                reachable_target_count=len(c.routes_to_targets),
                scores={
                    "response_time": round(scores.response_time, 3),
                    "safety": round(scores.safety, 3),
                    "logistics": round(scores.logistics, 3),
                    "facility": round(scores.facility, 3),
                    "communication": round(scores.communication, 3),
                },
                total_score=round(total, 3),
            ))
        
        ranked.sort(key=lambda x: x.total_score, reverse=True)
        return ranked
    
    def _calculate_dimension_scores(
        self,
        candidate: CandidateWithRoutes,
        targets: List[RescueTarget],
        max_response_time: float,
        max_danger_dist: float,
        max_logistics_dist: float,
    ) -> DimensionScores:
        """计算五维评分（0-1归一化）"""
        
        # 1. 响应时间得分（时间越短分数越高）
        avg_response = self._calc_weighted_avg_response(candidate.routes_to_targets)
        response_score = 1.0 - (avg_response / max_response_time) if max_response_time > 0 else 0
        
        # 2. 安全性得分（距离危险区越远分数越高）
        danger_dist = candidate.site.distance_to_danger_m or 0
        safety_score = danger_dist / max_danger_dist if max_danger_dist > 0 else 0
        
        # 3. 后勤保障得分（到补给/医疗点越近分数越高）
        supply_dist = candidate.site.nearest_supply_depot_m or 0
        medical_dist = candidate.site.nearest_medical_point_m or 0
        total_logistics_dist = supply_dist + medical_dist
        logistics_score = 1.0 - (total_logistics_dist / max_logistics_dist) if max_logistics_dist > 0 else 0.5
        
        # 4. 设施条件得分
        facility_score = self._calc_facility_score(candidate.site)
        
        # 5. 通信质量得分
        comm_score = self._calc_communication_score(candidate.site)
        
        return DimensionScores(
            response_time=max(0, min(1, response_score)),
            safety=max(0, min(1, safety_score)),
            logistics=max(0, min(1, logistics_score)),
            facility=max(0, min(1, facility_score)),
            communication=max(0, min(1, comm_score)),
        )
    
    def _calc_weighted_avg_response(self, routes: List[RouteToTarget]) -> float:
        """计算加权平均响应时间"""
        if not routes:
            return float("inf")
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for r in routes:
            w = PRIORITY_WEIGHTS.get(r.priority, 1.0)
            weighted_sum += r.duration_seconds * w
            total_weight += w
        
        return weighted_sum / total_weight if total_weight > 0 else 0
    
    @staticmethod
    def _calc_facility_score(site: CandidateSite) -> float:
        """计算设施条件得分"""
        score = 0.0
        if site.has_water_supply:
            score += 0.3
        if site.has_power_supply:
            score += 0.3
        if site.can_helicopter_land:
            score += 0.2
        if site.area_m2 and site.area_m2 >= 5000:
            score += 0.2
        elif site.area_m2 and site.area_m2 >= 2000:
            score += 0.1
        return min(1.0, score)
    
    @staticmethod
    def _calc_communication_score(site: CandidateSite) -> float:
        """计算通信质量得分"""
        network_scores: Dict[NetworkType, float] = {
            NetworkType.FIVE_G: 1.0,
            NetworkType.FOUR_G_LTE: 0.85,
            NetworkType.SATELLITE: 0.7,
            NetworkType.THREE_G: 0.5,
            NetworkType.MESH: 0.6,
            NetworkType.SHORTWAVE: 0.4,
            NetworkType.NONE: 0.0,
        }
        base_score = network_scores.get(site.primary_network_type, 0.3)
        
        # 信号质量修正
        quality_factor = {
            "excellent": 1.0,
            "good": 0.9,
            "fair": 0.7,
            "poor": 0.4,
        }.get(site.signal_quality or "", 0.7)
        
        return base_score * quality_factor
