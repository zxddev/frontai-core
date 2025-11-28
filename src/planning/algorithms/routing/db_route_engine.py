"""
基于数据库路网的A*路径规划引擎

从PostgreSQL road_edges_v2/road_nodes_v2表加载路网数据，
结合车辆能力和灾害区域进行避障路径规划。

核心功能：
1. 从数据库加载指定范围的路网
2. 根据车辆能力过滤不可通行的路段
3. 根据灾害区域排除或惩罚路段
4. 使用A*算法搜索最优路径
5. 计算真实的行驶时间（考虑地形速度系数）

依赖：
- networkx: A*搜索算法
- PostGIS: 空间查询
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set
from uuid import UUID

import networkx as nx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .types import (
    Audit,
    PathCandidate,
    PathSearchMetrics,
    Point,
    InfeasiblePathError,
)

logger = logging.getLogger(__name__)


# 道路类型默认速度 (km/h)
ROAD_TYPE_DEFAULT_SPEEDS: Dict[str, int] = {
    "motorway": 120,
    "motorway_link": 60,
    "trunk": 100,
    "trunk_link": 50,
    "primary": 80,
    "primary_link": 40,
    "secondary": 60,
    "secondary_link": 30,
    "tertiary": 40,
    "tertiary_link": 25,
    "residential": 30,
    "living_street": 20,
    "service": 20,
    "unclassified": 30,
    "track": 20,
    "path": 10,
    "footway": 5,
}

# 地形类型默认速度系数
TERRAIN_DEFAULT_FACTORS: Dict[str, float] = {
    "urban": 1.0,
    "suburban": 0.9,
    "rural": 0.85,
    "mountain": 0.6,
    "forest": 0.5,
    "grassland": 0.7,
    "water_adjacent": 0.4,
    "desert": 0.7,
    "wetland": 0.3,
    "unknown": 0.8,
}


@dataclass
class VehicleCapability:
    """车辆能力参数"""
    vehicle_id: UUID
    vehicle_code: str
    max_speed_kmh: int
    is_all_terrain: bool
    terrain_capabilities: List[str]
    terrain_speed_factors: Dict[str, float]
    max_gradient_percent: Optional[int]
    max_wading_depth_m: Optional[float]
    width_m: Optional[float]
    height_m: Optional[float]
    total_weight_kg: Optional[float]  # 自重 + 最大载重


@dataclass
class RouteEdge:
    """路网边数据"""
    edge_id: UUID
    from_node_id: UUID
    to_node_id: UUID
    from_lon: float
    from_lat: float
    to_lon: float
    to_lat: float
    length_m: float
    max_speed_kmh: Optional[int]
    road_type: Optional[str]
    avg_gradient_percent: Optional[float]
    max_gradient_percent: Optional[float]
    terrain_type: Optional[str]
    is_accessible: bool
    width_m: Optional[float]
    bridge: bool
    bridge_max_weight_ton: Optional[float]
    tunnel: bool
    tunnel_height_m: Optional[float]


class PassageStatus:
    """通行状态枚举"""
    CONFIRMED_BLOCKED = "confirmed_blocked"        # 已确认不可通行
    NEEDS_RECONNAISSANCE = "needs_reconnaissance"  # 需侦察确认
    PASSABLE_WITH_CAUTION = "passable_with_caution"  # 可通行但需谨慎
    CLEAR = "clear"                                # 已确认安全
    UNKNOWN = "unknown"                            # 未知状态


@dataclass
class DisasterArea:
    """灾害影响区域"""
    area_id: UUID
    area_type: str
    passable: bool
    passable_vehicle_types: List[str]
    speed_reduction_percent: int
    risk_level: int
    passage_status: str = PassageStatus.UNKNOWN  # 新增：通行状态
    reconnaissance_required: bool = False         # 新增：是否需侦察


@dataclass
class RouteResult:
    """路径规划结果"""
    path_points: List[Point]
    distance_m: float
    duration_seconds: float
    path_edges: List[UUID]
    blocked_by_disaster: bool = False
    warnings: List[str] = field(default_factory=list)


class DatabaseRouteEngine:
    """
    基于数据库的路径规划引擎
    
    使用PostgreSQL + PostGIS存储路网数据，
    networkx进行A*搜索。
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        初始化引擎
        
        Args:
            db: SQLAlchemy异步数据库会话
        """
        self._db = db
        self._graph: Optional[nx.DiGraph] = None
        self._node_coords: Dict[UUID, Tuple[float, float]] = {}
        self._edge_data: Dict[Tuple[UUID, UUID], RouteEdge] = {}
    
    async def plan_route(
        self,
        start: Point,
        end: Point,
        vehicle: VehicleCapability,
        scenario_id: Optional[UUID] = None,
        search_radius_km: float = 100.0,
    ) -> RouteResult:
        """
        规划从起点到终点的最优路径
        
        Args:
            start: 起点坐标
            end: 终点坐标
            vehicle: 车辆能力参数
            scenario_id: 想定ID（用于查询灾害区域）
            search_radius_km: 搜索半径（公里）
            
        Returns:
            RouteResult 包含路径、距离、时间等
            
        Raises:
            InfeasiblePathError: 无法找到可行路径
        """
        logger.info(
            f"[路径规划] 开始 vehicle={vehicle.vehicle_code} "
            f"start=({start.lon:.4f},{start.lat:.4f}) end=({end.lon:.4f},{end.lat:.4f})"
        )
        start_time = time.perf_counter()
        
        # 计算搜索范围（起终点外扩）
        center_lon = (start.lon + end.lon) / 2
        center_lat = (start.lat + end.lat) / 2
        
        # 加载路网
        edges = await self._load_road_network(
            center_lon=center_lon,
            center_lat=center_lat,
            radius_m=search_radius_km * 1000,
        )
        logger.info(f"[路径规划] 加载路网: {len(edges)}条边")
        
        if not edges:
            raise InfeasiblePathError(f"搜索范围{search_radius_km}km内无路网数据")
        
        # 加载灾害区域
        disaster_areas: List[DisasterArea] = []
        blocked_edge_ids: Set[UUID] = set()
        if scenario_id:
            disaster_areas = await self._load_disaster_areas(scenario_id)
            if disaster_areas:
                blocked_edge_ids = await self._get_blocked_edges(
                    scenario_id=scenario_id,
                    vehicle_type=vehicle.vehicle_code,
                )
                logger.info(
                    f"[路径规划] 灾害区域: {len(disaster_areas)}个, "
                    f"封锁边: {len(blocked_edge_ids)}条"
                )
        
        # 构建图并过滤
        graph, node_coords = self._build_graph(
            edges=edges,
            vehicle=vehicle,
            blocked_edge_ids=blocked_edge_ids,
        )
        
        if graph.number_of_edges() == 0:
            raise InfeasiblePathError("所有路段均不可通行（车辆能力不足或灾害封锁）")
        
        # 找到最近的起终点节点
        start_node = self._find_nearest_node(node_coords, start)
        end_node = self._find_nearest_node(node_coords, end)
        
        if start_node is None:
            raise InfeasiblePathError(f"起点({start.lon:.4f},{start.lat:.4f})附近无可达路网节点")
        if end_node is None:
            raise InfeasiblePathError(f"终点({end.lon:.4f},{end.lat:.4f})附近无可达路网节点")
        
        logger.info(
            f"[路径规划] 图构建完成: {graph.number_of_nodes()}节点, "
            f"{graph.number_of_edges()}边, 起点节点={start_node}, 终点节点={end_node}"
        )
        
        # A*搜索
        search_start = time.perf_counter()
        try:
            path_nodes = nx.astar_path(
                graph,
                start_node,
                end_node,
                heuristic=lambda n1, n2: self._haversine_distance(
                    node_coords[n1][0], node_coords[n1][1],
                    node_coords[n2][0], node_coords[n2][1],
                ),
                weight="weight",
            )
        except nx.NetworkXNoPath:
            raise InfeasiblePathError("无法找到从起点到终点的可行路径")
        
        search_time = time.perf_counter() - search_start
        logger.info(f"[路径规划] A*搜索完成: {len(path_nodes)}个节点, 耗时{search_time*1000:.1f}ms")
        
        # 构建结果
        result = self._build_result(
            path_nodes=path_nodes,
            node_coords=node_coords,
            graph=graph,
            start=start,
            end=end,
        )
        
        total_time = time.perf_counter() - start_time
        logger.info(
            f"[路径规划] 完成: 距离{result.distance_m/1000:.2f}km, "
            f"时间{result.duration_seconds/60:.1f}分钟, 总耗时{total_time*1000:.1f}ms"
        )
        
        return result
    
    async def _load_road_network(
        self,
        center_lon: float,
        center_lat: float,
        radius_m: float,
    ) -> List[RouteEdge]:
        """
        从数据库加载指定范围的路网
        
        使用PostGIS ST_DWithin进行空间查询
        """
        sql = text("""
            SELECT 
                e.id, e.from_node_id, e.to_node_id,
                e.length_m, e.max_speed_kmh, e.road_type::text,
                e.avg_gradient_percent, e.max_gradient_percent,
                e.terrain_type::text, e.is_accessible,
                e.width_m, e.bridge, e.bridge_max_weight_ton,
                e.tunnel, e.tunnel_height_m,
                n1.lon as from_lon, n1.lat as from_lat,
                n2.lon as to_lon, n2.lat as to_lat
            FROM operational_v2.road_edges_v2 e
            JOIN operational_v2.road_nodes_v2 n1 ON e.from_node_id = n1.id
            JOIN operational_v2.road_nodes_v2 n2 ON e.to_node_id = n2.id
            WHERE ST_DWithin(
                e.geometry,
                ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography,
                :radius_m
            )
            AND e.is_accessible = true
        """)
        
        result = await self._db.execute(sql, {
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius_m": radius_m,
        })
        
        edges: List[RouteEdge] = []
        for row in result.fetchall():
            edge = RouteEdge(
                edge_id=row[0],
                from_node_id=row[1],
                to_node_id=row[2],
                length_m=row[3],
                max_speed_kmh=row[4],
                road_type=row[5],
                avg_gradient_percent=row[6],
                max_gradient_percent=row[7],
                terrain_type=row[8],
                is_accessible=row[9],
                width_m=row[10],
                bridge=row[11] or False,
                bridge_max_weight_ton=row[12],
                tunnel=row[13] or False,
                tunnel_height_m=row[14],
                from_lon=row[15],
                from_lat=row[16],
                to_lon=row[17],
                to_lat=row[18],
            )
            edges.append(edge)
        
        return edges
    
    async def _load_disaster_areas(self, scenario_id: UUID) -> List[DisasterArea]:
        """加载想定关联的灾害影响区域"""
        sql = text("""
            SELECT id, area_type, passable, passable_vehicle_types,
                   speed_reduction_percent, risk_level,
                   COALESCE(passage_status, 'unknown') as passage_status,
                   COALESCE(reconnaissance_required, false) as reconnaissance_required
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = :scenario_id
            AND (estimated_end_at IS NULL OR estimated_end_at > now())
        """)
        
        result = await self._db.execute(sql, {"scenario_id": scenario_id})
        
        areas: List[DisasterArea] = []
        for row in result.fetchall():
            area = DisasterArea(
                area_id=row[0],
                area_type=row[1],
                passable=row[2] or False,
                passable_vehicle_types=row[3] or [],
                speed_reduction_percent=row[4] or 100,
                risk_level=row[5] or 5,
                passage_status=row[6] or PassageStatus.UNKNOWN,
                reconnaissance_required=row[7] or False,
            )
            areas.append(area)
        
        return areas
    
    async def _get_blocked_edges(
        self,
        scenario_id: UUID,
        vehicle_type: str,
        allow_unverified_areas: bool = False,
    ) -> Set[UUID]:
        """
        获取被灾害区域封锁的边ID
        
        使用PostGIS ST_Intersects检查边与灾害区域是否相交
        
        通行状态决策逻辑：
        - confirmed_blocked: 绝对绕行
        - needs_reconnaissance: 默认绕行，除非 allow_unverified_areas=True
        - passable_with_caution: 允许通行（通过速度惩罚处理）
        - clear/unknown: 允许通行
        
        Args:
            scenario_id: 想定ID
            vehicle_type: 车辆类型代码
            allow_unverified_areas: 是否允许进入未验证区域（侦察任务时为True）
        """
        sql = text("""
            SELECT DISTINCT e.id
            FROM operational_v2.road_edges_v2 e
            JOIN operational_v2.disaster_affected_areas_v2 d 
                ON ST_Intersects(e.geometry::geometry, d.geometry::geometry)
            WHERE d.scenario_id = :scenario_id
            AND (d.estimated_end_at IS NULL OR d.estimated_end_at > now())
            AND (
                -- 已确认不可通行：绝对绕行
                COALESCE(d.passage_status, 'unknown') = 'confirmed_blocked'
                OR (
                    -- 需侦察区域：根据参数决定是否绕行
                    COALESCE(d.passage_status, 'unknown') = 'needs_reconnaissance'
                    AND :allow_unverified = false
                )
                OR (
                    -- 兼容旧数据：passable=false 且 passage_status 未设置
                    d.passable = false 
                    AND COALESCE(d.passage_status, 'unknown') = 'unknown'
                )
            )
            AND NOT (:vehicle_type = ANY(COALESCE(d.passable_vehicle_types, ARRAY[]::text[])))
        """)
        
        result = await self._db.execute(sql, {
            "scenario_id": scenario_id,
            "vehicle_type": vehicle_type,
            "allow_unverified": allow_unverified_areas,
        })
        
        return {row[0] for row in result.fetchall()}
    
    def _build_graph(
        self,
        edges: List[RouteEdge],
        vehicle: VehicleCapability,
        blocked_edge_ids: Set[UUID],
        snap_tolerance_m: float = 15.0,
    ) -> Tuple[nx.DiGraph, Dict[str, Tuple[float, float]]]:
        """
        构建networkx有向图
        
        使用空间网格合并近邻节点（容差内的点合并到同一网格单元）。
        
        Args:
            edges: 路网边列表
            vehicle: 车辆能力
            blocked_edge_ids: 被封锁的边ID集合
            snap_tolerance_m: 节点合并容差（米），默认15米
        """
        graph = nx.DiGraph()
        node_coords: Dict[str, Tuple[float, float]] = {}
        
        filtered_count = 0
        blocked_count = 0
        
        # 计算网格大小（经纬度度数）
        # 在中国四川地区（约31°N），1度纬度≈111km，1度经度≈95km
        # 15米容差 ≈ 0.00013度纬度, 0.00016度经度
        # 使用统一的0.00015度作为网格大小
        grid_size = snap_tolerance_m / 111000.0  # 约0.000135度
        
        def coord_to_grid_id(lon: float, lat: float) -> str:
            """将坐标映射到网格ID（合并近邻节点）"""
            grid_lon = round(lon / grid_size) * grid_size
            grid_lat = round(lat / grid_size) * grid_size
            return f"{grid_lon:.6f},{grid_lat:.6f}"
        
        for edge in edges:
            # 灾害封锁检查
            if edge.edge_id in blocked_edge_ids:
                blocked_count += 1
                continue
            
            # 车辆通行性检查
            can_pass, reason = self._check_vehicle_passability(edge, vehicle)
            if not can_pass:
                filtered_count += 1
                continue
            
            # 使用网格ID作为节点ID（自动合并近邻节点）
            from_node = coord_to_grid_id(edge.from_lon, edge.from_lat)
            to_node = coord_to_grid_id(edge.to_lon, edge.to_lat)
            
            # 跳过自环（合并后可能产生）
            if from_node == to_node:
                continue
            
            # 添加节点坐标（保存实际坐标用于距离计算）
            # 如果节点已存在，不覆盖（保持第一次出现的坐标）
            if from_node not in node_coords:
                node_coords[from_node] = (edge.from_lon, edge.from_lat)
            if to_node not in node_coords:
                node_coords[to_node] = (edge.to_lon, edge.to_lat)
            
            # 计算边权重（行驶时间，秒）
            weight = self._calculate_edge_weight(edge, vehicle)
            
            # 添加边（双向）
            # 如果边已存在，保留权重较小的
            if graph.has_edge(from_node, to_node):
                existing_weight = graph[from_node][to_node]["weight"]
                if weight < existing_weight:
                    graph[from_node][to_node]["weight"] = weight
                    graph[from_node][to_node]["length_m"] = edge.length_m
                    graph[from_node][to_node]["edge_id"] = edge.edge_id
            else:
                graph.add_edge(
                    from_node,
                    to_node,
                    weight=weight,
                    length_m=edge.length_m,
                    edge_id=edge.edge_id,
                )
            
            # 反向边
            if graph.has_edge(to_node, from_node):
                existing_weight = graph[to_node][from_node]["weight"]
                if weight < existing_weight:
                    graph[to_node][from_node]["weight"] = weight
                    graph[to_node][from_node]["length_m"] = edge.length_m
                    graph[to_node][from_node]["edge_id"] = edge.edge_id
            else:
                graph.add_edge(
                    to_node,
                    from_node,
                    weight=weight,
                    length_m=edge.length_m,
                    edge_id=edge.edge_id,
                )
        
        if filtered_count > 0 or blocked_count > 0:
            logger.info(
                f"[路径规划] 边过滤: 车辆不可通行{filtered_count}条, 灾害封锁{blocked_count}条"
            )
        
        return graph, node_coords
    
    def _check_vehicle_passability(
        self,
        edge: RouteEdge,
        vehicle: VehicleCapability,
    ) -> Tuple[bool, str]:
        """
        检查车辆能否通过该路段
        
        检查项：坡度、地形、宽度、桥梁限重、隧道限高
        """
        # 坡度检查
        if edge.max_gradient_percent and vehicle.max_gradient_percent:
            if edge.max_gradient_percent > vehicle.max_gradient_percent:
                return False, f"坡度{edge.max_gradient_percent:.0f}%超过车辆能力{vehicle.max_gradient_percent}%"
        
        # 地形检查（非全地形车辆）
        if not vehicle.is_all_terrain and edge.terrain_type:
            terrain = edge.terrain_type.lower()
            if terrain not in ["urban", "suburban", "unknown"]:
                # 检查车辆是否支持该地形
                if terrain not in [t.lower() for t in vehicle.terrain_capabilities]:
                    return False, f"车辆不支持{terrain}地形"
        
        # 宽度检查
        if edge.width_m and vehicle.width_m:
            if vehicle.width_m > edge.width_m:
                return False, f"车宽{vehicle.width_m:.1f}m超过路宽{edge.width_m:.1f}m"
        
        # 桥梁限重检查
        if edge.bridge and edge.bridge_max_weight_ton and vehicle.total_weight_kg:
            vehicle_weight_ton = vehicle.total_weight_kg / 1000
            if vehicle_weight_ton > edge.bridge_max_weight_ton:
                return False, f"车重{vehicle_weight_ton:.1f}t超过桥梁限重{edge.bridge_max_weight_ton:.1f}t"
        
        # 隧道限高检查
        if edge.tunnel and edge.tunnel_height_m and vehicle.height_m:
            if vehicle.height_m > edge.tunnel_height_m:
                return False, f"车高{vehicle.height_m:.1f}m超过隧道限高{edge.tunnel_height_m:.1f}m"
        
        return True, "可通行"
    
    def _calculate_edge_weight(
        self,
        edge: RouteEdge,
        vehicle: VehicleCapability,
    ) -> float:
        """
        计算边的权重（行驶时间，秒）
        
        考虑：道路限速、车辆最大速度、地形速度系数、坡度惩罚
        """
        # 基础速度（道路限速或类型默认速度）
        road_speed = edge.max_speed_kmh
        if road_speed is None or road_speed <= 0:
            road_type = edge.road_type or "unclassified"
            road_speed = ROAD_TYPE_DEFAULT_SPEEDS.get(road_type, 30)
        
        # 车辆最大速度限制
        base_speed = min(road_speed, vehicle.max_speed_kmh)
        
        # 地形速度系数
        terrain = (edge.terrain_type or "unknown").lower()
        terrain_factor = vehicle.terrain_speed_factors.get(
            terrain,
            TERRAIN_DEFAULT_FACTORS.get(terrain, 0.8)
        )
        
        # 坡度惩罚（上坡减速）
        gradient_factor = 1.0
        if edge.avg_gradient_percent:
            gradient = abs(edge.avg_gradient_percent)
            if gradient > 15:
                gradient_factor = 0.5  # 极陡坡
            elif gradient > 10:
                gradient_factor = 0.65
            elif gradient > 5:
                gradient_factor = 0.8
        
        # 最终速度 (km/h)
        actual_speed = base_speed * terrain_factor * gradient_factor
        actual_speed = max(actual_speed, 5.0)  # 最低5km/h
        
        # 时间 = 距离 / 速度 (秒)
        time_seconds = (edge.length_m / 1000) / actual_speed * 3600
        
        return time_seconds
    
    def _find_nearest_node(
        self,
        node_coords: Dict[str, Tuple[float, float]],
        point: Point,
        max_distance_m: float = 5000.0,
    ) -> Optional[str]:
        """找到距离指定点最近的节点"""
        nearest_node: Optional[str] = None
        nearest_distance = float("inf")
        
        for node_id, (lon, lat) in node_coords.items():
            dist = self._haversine_distance(point.lon, point.lat, lon, lat)
            if dist < nearest_distance:
                nearest_distance = dist
                nearest_node = node_id
        
        if nearest_distance > max_distance_m:
            return None
        
        return nearest_node
    
    def _haversine_distance(
        self,
        lon1: float,
        lat1: float,
        lon2: float,
        lat2: float,
    ) -> float:
        """
        计算两点间的球面距离（米）
        
        Haversine公式
        """
        R = 6371000  # 地球半径（米）
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def _build_result(
        self,
        path_nodes: List[str],
        node_coords: Dict[str, Tuple[float, float]],
        graph: nx.DiGraph,
        start: Point,
        end: Point,
    ) -> RouteResult:
        """构建路径规划结果"""
        path_points: List[Point] = []
        path_edges: List[UUID] = []
        total_distance = 0.0
        total_time = 0.0
        
        # 添加起点
        path_points.append(start)
        
        # 遍历路径节点
        for i, node_id in enumerate(path_nodes):
            lon, lat = node_coords[node_id]
            path_points.append(Point(lon=lon, lat=lat))
            
            # 累加边的距离和时间
            if i > 0:
                prev_node = path_nodes[i - 1]
                edge_data = graph.get_edge_data(prev_node, node_id)
                if edge_data:
                    total_distance += edge_data.get("length_m", 0)
                    total_time += edge_data.get("weight", 0)
                    edge_id = edge_data.get("edge_id")
                    if edge_id:
                        path_edges.append(edge_id)
        
        # 添加终点
        path_points.append(end)
        
        return RouteResult(
            path_points=path_points,
            distance_m=total_distance,
            duration_seconds=total_time,
            path_edges=path_edges,
        )


async def load_vehicle_capability(
    db: AsyncSession,
    vehicle_id: UUID,
) -> Optional[VehicleCapability]:
    """
    从数据库加载车辆能力参数
    
    Args:
        db: 数据库会话
        vehicle_id: 车辆ID
        
    Returns:
        VehicleCapability或None
    """
    sql = text("""
        SELECT id, code, max_speed_kmh, is_all_terrain,
               terrain_capabilities, terrain_speed_factors,
               max_gradient_percent, max_wading_depth_m,
               width_m, height_m, self_weight_kg, max_weight_kg
        FROM operational_v2.vehicles_v2
        WHERE id = :vehicle_id
    """)
    
    result = await db.execute(sql, {"vehicle_id": vehicle_id})
    row = result.fetchone()
    
    if not row:
        return None
    
    total_weight = None
    if row[10] is not None and row[11] is not None:
        total_weight = float(row[10]) + float(row[11])
    
    return VehicleCapability(
        vehicle_id=row[0],
        vehicle_code=row[1],
        max_speed_kmh=row[2] or 60,
        is_all_terrain=row[3] or False,
        terrain_capabilities=row[4] or [],
        terrain_speed_factors=row[5] or {},
        max_gradient_percent=row[6],
        max_wading_depth_m=float(row[7]) if row[7] else None,
        width_m=float(row[8]) if row[8] else None,
        height_m=float(row[9]) if row[9] else None,
        total_weight_kg=total_weight,
    )


async def get_team_primary_vehicle(
    db: AsyncSession,
    team_id: UUID,
) -> Optional[UUID]:
    """
    获取队伍的主力车辆ID
    
    Args:
        db: 数据库会话
        team_id: 队伍ID
        
    Returns:
        车辆ID或None
    """
    sql = text("""
        SELECT vehicle_id
        FROM operational_v2.team_vehicles_v2
        WHERE team_id = :team_id
        AND status = 'available'
        ORDER BY is_primary DESC, assigned_at ASC
        LIMIT 1
    """)
    
    result = await db.execute(sql, {"team_id": team_id})
    row = result.fetchone()
    
    return row[0] if row else None
