"""越野 A* 引擎：用于路网不可达时的地面越野规划。

TODO: [refactor-architecture-conventions] 待改造项：
1. 异步化 - 当前是同步实现，需要改为 async/await
2. 与 DatabaseRouteEngine 集成 - 作为路网不通时的 fallback
3. 初始化代码 - 需要添加加载 DEM (data/四川省.tif) 和水域数据的代码
4. 性能优化 - 80米网格在大范围搜索时性能较差
"""

from __future__ import annotations

import heapq
import logging
import math
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import rasterio
from shapely.geometry import Polygon, LineString
from shapely.prepared import prep

from .types import (
    Audit,
    CapabilityMetrics,
    InfeasiblePathError,
    Obstacle,
    PathCandidate,
    PathSearchMetrics,
    Point,
    dedupe,
    slope_deg_to_percent,
)

logger = logging.getLogger(__name__)


@dataclass(order=True)
class _Node:
    f: float
    g: float
    h: float
    lon: float
    lat: float
    parent: Optional["_Node"] = None


@dataclass(slots=True)
class OffroadConfig:
    resolution_m: float = 80.0
    max_iterations: int = 200000


class OffroadEngine:
    """DEM+水域+障碍的越野 A*。"""

    def __init__(self, *, dem: rasterio.io.DatasetReader, water_polygons: Sequence[Polygon], config: OffroadConfig) -> None:
        self._dem = dem
        self._water_prepared = [prep(poly) for poly in water_polygons]
        self._cfg = config

    def plan(self, start: Point, end: Point, obstacles: Sequence[Obstacle], hard_req: set[str], soft_req: set[str], capability: CapabilityMetrics) -> PathCandidate:
        start_ts = time.perf_counter()
        step_lon, step_lat = self._deg_step((start.lat + end.lat) / 2.0, self._cfg.resolution_m)
        open_list: List[_Node] = []
        closed: set[Tuple[float, float]] = set()
        start_node = _Node(f=0.0, g=0.0, h=self._heuristic(start.lon, start.lat, end.lon, end.lat), lon=start.lon, lat=start.lat, parent=None)
        start_node.f = start_node.h
        heapq.heappush(open_list, start_node)

        iterations = 0

        while open_list and iterations < self._cfg.max_iterations:
            iterations += 1
            current = heapq.heappop(open_list)
            closed.add((current.lon, current.lat))

            if self._distance_m(current.lon, current.lat, end.lon, end.lat) <= self._cfg.resolution_m:
                points = self._reconstruct(current)
                dist = self._path_length(points)
                audit_hard: List[str] = []
                audit_soft: List[str] = []
                audit_violated: List[str] = []
                for p1, p2 in zip(points[:-1], points[1:]):
                    seg = ((p1.lon, p1.lat), (p2.lon, p2.lat))
                    h_hits, s_hits, v_hits = self._check_obstacles(seg, obstacles, hard_req, soft_req)
                    if h_hits:
                        logger.info(f"offroad_path_hard_hit hits={h_hits}")
                        raise InfeasiblePathError("offroad_hard_obstacle")
                    audit_soft.extend(s_hits)
                    audit_violated.extend(v_hits)
                dur = self._estimate_duration(dist, capability)
                elapsed = (time.perf_counter() - start_ts) * 1000.0
                metrics = PathSearchMetrics(iterations=iterations, nodes_expanded=len(closed), elapsed_ms=elapsed, path_points=len(points))
                audit = Audit(hard_hits=dedupe(audit_hard), soft_hits=dedupe(audit_soft), violated_soft=dedupe(audit_violated), waivers=[])
                cost = dist + len(audit.soft_hits) * 50.0 + len(audit.violated_soft) * 200.0
                return PathCandidate(id="offroad", points=points, distance_m=dist, duration_s=dur, cost=cost, audit=audit, metadata={"mode": "offroad"}, metrics=metrics)

            for dlon, dlat in self._neighbors(step_lon, step_lat):
                nlon = current.lon + dlon
                nlat = current.lat + dlat
                if (nlon, nlat) in closed:
                    continue
                seg = ((current.lon, current.lat), (nlon, nlat))
                if self._segment_hits_water(seg):
                    continue
                h_hits, _, _ = self._check_obstacles(seg, obstacles, hard_req, soft_req)
                if h_hits:
                    continue
                try:
                    slope_deg = self._slope_at(nlon, nlat)  # DEM计算返回角度
                    slope_percent = slope_deg_to_percent(slope_deg)  # 转换为百分比
                except Exception:
                    continue
                # 使用百分比比较，与数据库字段 max_gradient_percent 保持一致
                if capability.slope_percent and slope_percent > capability.slope_percent:
                    continue

                g_cost = current.g + self._distance_m(current.lon, current.lat, nlon, nlat)
                h_cost = self._heuristic(nlon, nlat, end.lon, end.lat)
                node = _Node(f=g_cost + h_cost, g=g_cost, h=h_cost, lon=nlon, lat=nlat, parent=current)
                heapq.heappush(open_list, node)

        raise InfeasiblePathError("offroad_no_path")

    def _segment_hits_water(self, seg: Tuple[Tuple[float, float], Tuple[float, float]]) -> bool:
        line = LineString(seg)
        for poly in self._water_prepared:
            if poly.intersects(line):
                return True
        return False

    def _neighbors(self, step_lon: float, step_lat: float) -> Iterable[Tuple[float, float]]:
        for dlon in (-step_lon, 0.0, step_lon):
            for dlat in (-step_lat, 0.0, step_lat):
                if dlon == 0.0 and dlat == 0.0:
                    continue
                yield dlon, dlat

    def _heuristic(self, lon: float, lat: float, goal_lon: float, goal_lat: float) -> float:
        return self._distance_m(lon, lat, goal_lon, goal_lat)

    def _distance_m(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        dx = (lon2 - lon1) * 111000.0 * math.cos(math.radians((lat1 + lat2) / 2.0))
        dy = (lat2 - lat1) * 111000.0
        return math.hypot(dx, dy)

    def _reconstruct(self, node: _Node) -> List[Point]:
        path: List[Point] = []
        cur: Optional[_Node] = node
        while cur is not None:
            path.append(Point(lon=cur.lon, lat=cur.lat))
            cur = cur.parent
        path.reverse()
        return path

    def _path_length(self, pts: List[Point]) -> float:
        total = 0.0
        for p1, p2 in zip(pts[:-1], pts[1:]):
            total += self._distance_m(p1.lon, p1.lat, p2.lon, p2.lat)
        return total

    def _estimate_duration(self, distance_m: float, capability: CapabilityMetrics) -> float:
        if distance_m <= 0:
            return 0.0
        return distance_m / 5.0

    def _check_obstacles(self, seg: Tuple[Tuple[float, float], Tuple[float, float]], obstacles: Sequence[Obstacle], hard_req: set[str], soft_req: set[str]) -> Tuple[List[str], List[str], List[str]]:
        hard_hits: List[str] = []
        soft_hits: List[str] = []
        violated: List[str] = []
        for obs in obstacles:
            if obs.geometry and self._segment_hits_geom(seg[0], seg[1], obs.geometry):
                key = obs.id or obs.type
                if obs.hard or obs.type in hard_req:
                    hard_hits.append(key)
                else:
                    soft_hits.append(key)
                    if obs.type in soft_req:
                        violated.append(obs.type)
        return hard_hits, soft_hits, violated

    def _segment_hits_geom(self, start: Tuple[float, float], end: Tuple[float, float], geom: dict) -> bool:
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if not gtype or coords is None:
            return False
        if gtype == "LineString":
            pts = [(float(x), float(y)) for x, y in coords]
            for a, b in zip(pts[:-1], pts[1:]):
                if self._segments_intersect(start, end, a, b):
                    return True
            return False
        if gtype == "Polygon":
            return self._segment_hits_polygon(start, end, coords)
        if gtype == "MultiPolygon":
            for poly in coords:
                if self._segment_hits_polygon(start, end, poly):
                    return True
            return False
        return False

    def _segment_hits_polygon(self, start: Tuple[float, float], end: Tuple[float, float], coords: Sequence[Sequence[Sequence[float]]]) -> bool:
        if not coords:
            return False
        outer = coords[0]
        holes = list(coords[1:]) if len(coords) > 1 else []
        start_in = self._point_in_ring(start, outer) and not any(self._point_in_ring(start, h) for h in holes)
        end_in = self._point_in_ring(end, outer) and not any(self._point_in_ring(end, h) for h in holes)
        if start_in or end_in:
            return True
        for a, b in zip(outer[:-1], outer[1:]):
            if self._segments_intersect(start, end, (a[0], a[1]), (b[0], b[1])):
                return True
        return False

    def _point_in_ring(self, pt: Tuple[float, float], ring: Sequence[Sequence[float]]) -> bool:
        x, y = pt
        inside = False
        n = len(ring)
        if n < 3:
            return False
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if self._segments_intersect(pt, pt, (x1, y1), (x2, y2)):
                return True
            if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
                inside = not inside
        return inside

    def _segments_intersect(self, p1: Tuple[float, float], p2: Tuple[float, float], q1: Tuple[float, float], q2: Tuple[float, float]) -> bool:
        def orient(a, b, c) -> float:
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def on_segment(a, b, c) -> bool:
            return (
                min(a[0], c[0]) - 1e-12 <= b[0] <= max(a[0], c[0]) + 1e-12
                and min(a[1], c[1]) - 1e-12 <= b[1] <= max(a[1], c[1]) + 1e-12
            )

        o1 = orient(p1, p2, q1)
        o2 = orient(p1, p2, q2)
        o3 = orient(q1, q2, p1)
        o4 = orient(q1, q2, p2)

        if o1 == 0 and on_segment(p1, q1, p2):
            return True
        if o2 == 0 and on_segment(p1, q2, p2):
            return True
        if o3 == 0 and on_segment(q1, p1, q2):
            return True
        if o4 == 0 and on_segment(q1, p2, q2):
            return True
        return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)

    def _deg_step(self, lat: float, meters: float) -> Tuple[float, float]:
        lat_rad = math.radians(lat)
        dlat = meters / 111000.0
        dlon = meters / (111000.0 * math.cos(lat_rad) if math.cos(lat_rad) != 0 else 1e-6)
        return dlon, dlat

    def _slope_at(self, lon: float, lat: float) -> float:
        row, col = self._dem.index(lon, lat)
        if row <= 0 or col <= 0 or row >= self._dem.height - 1 or col >= self._dem.width - 1:
            raise ValueError("坐标超出 DEM 范围")
        window = ((row - 1, row + 2), (col - 1, col + 2))
        data = self._dem.read(1, window=window)
        nodata = self._dem.nodata
        if nodata is not None and (data == nodata).any():
            raise ValueError("DEM nodata")
        xres, yres = self._dem.res
        meters_per_deg_x = 111000.0 * math.cos(math.radians(lat))
        meters_per_deg_y = 111000.0
        dzdx = (data[1, 2] - data[1, 0]) / (2 * xres * meters_per_deg_x)
        dzdy = (data[2, 1] - data[0, 1]) / (2 * abs(yres) * meters_per_deg_y)
        slope_rad = math.atan(math.sqrt(dzdx**2 + dzdy**2))
        return math.degrees(slope_rad)
