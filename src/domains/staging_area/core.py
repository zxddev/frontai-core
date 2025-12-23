"""
救援队驻扎点选址核心算法

遵循调用规范：Core层不持有db，通过Repository和RouteEngine依赖注入。
可作为Agent的底层Tool使用。
"""
from __future__ import annotations

import logging
import math
import time
import asyncio
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING, Protocol
from uuid import UUID

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
from src.core.file_config import get_int as get_file_int
from src.planning.algorithms.base import haversine_distance, Location
from src.planning.algorithms.routing.db_route_engine import (
    VehicleCapability,
    Point,
    InfeasiblePathError,
    RouteResult,
)

if TYPE_CHECKING:
    from src.domains.staging_area.repository import StagingAreaRepository

logger = logging.getLogger(__name__)


PRIORITY_WEIGHTS: Dict[TargetPriority, float] = {
    TargetPriority.CRITICAL: 4.0,
    TargetPriority.HIGH: 2.0,
    TargetPriority.MEDIUM: 1.0,
    TargetPriority.LOW: 0.5,
}

STAGING_ROUTE_MAX_CONCURRENCY = get_file_int("STAGING_ROUTE_MAX_CONCURRENCY", 8)


class RouteEngine(Protocol):
    async def plan_route(
        self,
        *,
        start: Point,
        end: Point,
        vehicle: VehicleCapability,
        scenario_id: Optional[UUID] = None,
        search_radius_km: float = 100.0,
    ) -> RouteResult: ...


class StagingAreaCore:
    """
    救援队驻扎点选址核心算法
    
    职责：
    1. 根据震中和灾害信息计算风险区域
    2. 搜索并过滤候选驻扎点
    3. 计算到救援目标的实际路径
    4. 多目标评估和排序
    
    遵循调用规范：
    - 不持有 db/session
    - 通过构造函数接收 Repository 和 RouteEngine
    - Service 层负责实例化依赖
    """
    
    def __init__(
        self,
        repository: "StagingAreaRepository",
        route_engine: RouteEngine,
    ) -> None:
        """
        初始化核心算法
        
        Args:
            repository: 驻扎点数据仓库（由Service层注入）
            route_engine: 路径规划引擎（由Service层注入）
        """
        self._repo = repository
        self._route_engine = route_engine
    
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

            # 2.1 地震烈度圈过滤/标注（不依赖 PostGIS）
            red_radius_km = self._estimate_intensity_radius(earthquake.magnitude, target_intensity=8)
            orange_radius_km = self._estimate_intensity_radius(earthquake.magnitude, target_intensity=6)
            yellow_radius_km = self._estimate_intensity_radius(earthquake.magnitude, target_intensity=4)

            candidates = self._annotate_and_filter_by_seismic_zones(
                candidates=candidates,
                epicenter_lon=earthquake.epicenter_lon,
                epicenter_lat=earthquake.epicenter_lat,
                red_radius_km=red_radius_km,
                orange_radius_km=orange_radius_km,
                yellow_radius_km=yellow_radius_km,
            )
            logger.info(f"[驻扎点选址] 烈度圈过滤后候选点: {len(candidates)} 个")
            
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
        db_zones = await self._repo.get_danger_zones(scenario_id)
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
        return await self._repo.search_candidates(
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
        if not candidates:
            return []

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

        semaphore = asyncio.Semaphore(max(1, STAGING_ROUTE_MAX_CONCURRENCY))
        # 单次推荐调用内的缓存：避免重复计算相同起终点
        route_cache: dict[tuple[float, float, float, float], RouteResult] = {}

        def _cache_key(a: Point, b: Point) -> tuple[float, float, float, float]:
            return (
                round(a.lon, 6),
                round(a.lat, 6),
                round(b.lon, 6),
                round(b.lat, 6),
            )

        def _is_same_place(a_lon: float, a_lat: float, b_lon: float, b_lat: float, threshold_m: float = 30.0) -> bool:
            return (
                haversine_distance(Location(a_lat, a_lon), Location(b_lat, b_lon)) * 1000.0
                <= threshold_m
            )

        async def _plan(start: Point, end: Point) -> RouteResult:
            key = _cache_key(start, end)
            cached = route_cache.get(key)
            if cached is not None:
                return cached
            async with semaphore:
                result = await self._route_engine.plan_route(
                    start=start,
                    end=end,
                    vehicle=vehicle,
                    scenario_id=scenario_id,
                )
                route_cache[key] = result
                return result

        async def _process_candidate(candidate: CandidateSite) -> Optional[CandidateWithRoutes]:
            candidate_point = Point(lon=candidate.longitude, lat=candidate.latitude)

            try:
                route_to_site = await _plan(team_point, candidate_point)
            except InfeasiblePathError:
                return None
            except Exception as e:
                logger.warning(f"[路径验证] 规划到 {candidate.name} 失败: {e}")
                return None

            async def _plan_to_target(target: RescueTarget) -> Optional[RouteToTarget]:
                target_point = Point(lon=target.longitude, lat=target.latitude)
                try:
                    # 常见场景：只有一个救援目标，且目标=队伍驻地/震中（回程对称），可直接复用 route_to_site
                    if _is_same_place(team.base_lon, team.base_lat, target.longitude, target.latitude):
                        return RouteToTarget(
                            target_id=target.id,
                            target_name=target.name,
                            distance_m=route_to_site.distance_m,
                            duration_seconds=route_to_site.duration_seconds,
                            priority=target.priority,
                        )
                    route = await _plan(candidate_point, target_point)
                    return RouteToTarget(
                        target_id=target.id,
                        target_name=target.name,
                        distance_m=route.distance_m,
                        duration_seconds=route.duration_seconds,
                        priority=target.priority,
                    )
                except Exception:
                    return None

            target_tasks = [asyncio.create_task(_plan_to_target(t)) for t in targets]
            target_results = await asyncio.gather(*target_tasks, return_exceptions=False)
            routes_to_targets = [r for r in target_results if r is not None]

            if not routes_to_targets:
                return None

            return CandidateWithRoutes(
                site=candidate,
                route_from_base_distance_m=route_to_site.distance_m,
                route_from_base_duration_s=route_to_site.duration_seconds,
                routes_to_targets=routes_to_targets,
                is_reachable=True,
            )

        tasks = [asyncio.create_task(_process_candidate(c)) for c in candidates]
        processed = await asyncio.gather(*tasks, return_exceptions=False)
        for item in processed:
            if item is not None:
                results.append(item)

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
        
        # 2. 安全性得分（距离危险区越远分数越高；叠加地震烈度圈惩罚）
        danger_dist = candidate.site.distance_to_danger_m
        if danger_dist is None:
            safety_score = 0.5
        else:
            safety_score = danger_dist / max_danger_dist if max_danger_dist > 0 else 0.5

        seismic_zone = (candidate.site.seismic_zone or "none").lower()
        if seismic_zone == "orange":
            safety_score *= 0.25
        elif seismic_zone == "yellow":
            safety_score *= 0.7
        
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

    @staticmethod
    def _annotate_and_filter_by_seismic_zones(
        *,
        candidates: List[CandidateSite],
        epicenter_lon: float,
        epicenter_lat: float,
        red_radius_km: float,
        orange_radius_km: float,
        yellow_radius_km: float,
    ) -> List[CandidateSite]:
        """
        给候选点打上距离震中/烈度圈标签，并进行过滤。

        规则：
        - 永远剔除红圈（烈度>=8）内点位
        - 尽量剔除橙圈（烈度>=6）内点位；如果剔除后候选点过少，则保留橙圈但在评分中强惩罚
        """
        annotated: List[CandidateSite] = []
        for c in candidates:
            dist_km = haversine_distance(
                Location(epicenter_lat, epicenter_lon),
                Location(c.latitude, c.longitude),
            )
            c.distance_to_epicenter_m = dist_km * 1000.0
            if dist_km <= red_radius_km:
                c.seismic_zone = "red"
            elif dist_km <= orange_radius_km:
                c.seismic_zone = "orange"
            elif dist_km <= yellow_radius_km:
                c.seismic_zone = "yellow"
            else:
                c.seismic_zone = "none"
            annotated.append(c)

        # always drop red
        no_red = [c for c in annotated if (c.seismic_zone or "") != "red"]
        # prefer drop orange if enough remain
        no_orange = [c for c in no_red if (c.seismic_zone or "") != "orange"]
        if len(no_orange) >= min(10, len(no_red)):
            return no_orange
        return no_red
    
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
