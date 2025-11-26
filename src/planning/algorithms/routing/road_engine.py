"""路网 A* 引擎（仅道路，路网不通返回 None）。"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import fiona
import networkx as nx
import rasterio

from .types import (
    Audit,
    CapabilityMetrics,
    Obstacle,
    PathCandidate,
    PathSearchMetrics,
    Point,
    dedupe,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RoadEngineConfig:
    resolution_m: float = 80.0


class RoadNetworkEngine:
    def __init__(self, *, roads_path: str, dem: rasterio.io.DatasetReader, config: RoadEngineConfig) -> None:
        self._roads_path = roads_path
        self._dem = dem
        self._cfg = config
        self._soft_penalty = 50.0
        self._violated_penalty = 200.0

    def plan_segment(self, start: Point, end: Point, obstacles: Sequence[Obstacle], hard_req: set[str], soft_req: set[str], capability: CapabilityMetrics) -> Optional[PathCandidate]:
        """路网规划单段：先裁剪路网，移除硬障碍/超坡度边，再按罚权重搜索，输出包含起终点的几何。"""
        bbox = self._bbox_with_buffer([start, end], buffer_m=self._cfg.resolution_m * 5)
        graph = self._load_graph(bbox)
        if graph.number_of_edges() == 0:
            logger.info(f"road_graph_empty bbox={list(bbox)}")
            return None

        node_coords: Dict[int, Tuple[float, float]] = {n: data.get("coord") for n, data in graph.nodes(data=True)}
        start_node = self._nearest_node(node_coords, start)
        end_node = self._nearest_node(node_coords, end)
        if start_node is None or end_node is None:
            logger.info(f"road_no_nearest_node start={start.model_dump()} end={end.model_dump()}")
            return None

        edges_to_remove: List[Tuple[int, int]] = []
        removed_hard = 0
        removed_slope = 0
        weighted_edges = 0
        for u, v, data in graph.edges(data=True):
            geom = data.get("geometry") or []
            if not geom or len(geom) != 2:
                continue
            a = geom[0]
            b = geom[1]
            segment = ((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
            h_hits, s_hits, v_hits = self._check_obstacles(segment, obstacles, hard_req, soft_req)
            if h_hits:
                removed_hard += 1
                edges_to_remove.append((u, v))
                continue
            if not self._slope_ok(segment, capability):
                removed_slope += 1
                edges_to_remove.append((u, v))
                continue
            soft_hits = dedupe(s_hits)
            violated_soft = dedupe(v_hits)
            penalty = len(soft_hits) * self._soft_penalty + len(violated_soft) * self._violated_penalty
            base_weight = data.get("weight", 0.0)
            data["soft_hits"] = soft_hits
            data["violated_soft"] = violated_soft
            data["weight"] = base_weight + penalty
            weighted_edges += 1
        graph.remove_edges_from(edges_to_remove)
        if graph.number_of_edges() == 0:
            logger.info(f"road_all_edges_blocked removed={len(edges_to_remove)} removed_hard={removed_hard} removed_slope={removed_slope}")
            return None
        logger.info(
            f"road_graph_pruned nodes={graph.number_of_nodes()} edges={graph.number_of_edges()} "
            f"removed={len(edges_to_remove)} removed_hard={removed_hard} removed_slope={removed_slope} weighted_edges={weighted_edges}"
        )

        start_ts = time.perf_counter()
        try:
            path_nodes = nx.astar_path(
                graph,
                start_node,
                end_node,
                heuristic=lambda n1, n2: self._haversine(node_coords[n1], node_coords[n2]),
                weight="weight",
            )
        except Exception:
            logger.info("road_astar_failed")
            return None

        points: List[Point] = [Point(lon=start.lon, lat=start.lat)]
        total_distance = 0.0
        soft_hits: List[str] = []
        violated_soft: List[str] = []
        path_edges = list(zip(path_nodes[:-1], path_nodes[1:]))

        first_coord = node_coords.get(path_nodes[0])
        if first_coord is None:
            return None
        if self._haversine((start.lon, start.lat), first_coord) > 0:
            if not self._slope_ok(((start.lon, start.lat), first_coord), capability):
                return None
            h_hits, s_hits, v_hits = self._check_obstacles(((start.lon, start.lat), first_coord), obstacles, hard_req, soft_req)
            if h_hits:
                logger.info(f"road_attach_start_blocked hits={h_hits}")
                return None
            soft_hits.extend(s_hits)
            violated_soft.extend(v_hits)
            total_distance += self._haversine((start.lon, start.lat), first_coord)
            points.append(Point(lon=first_coord[0], lat=first_coord[1]))

        for u, v in path_edges:
            u_coord = node_coords[u]
            v_coord = node_coords[v]
            if u_coord is None or v_coord is None:
                continue
            points.append(Point(lon=v_coord[0], lat=v_coord[1]))
            edge_data = graph.get_edge_data(u, v) or {}
            edge_soft = edge_data.get("soft_hits") or []
            edge_violated = edge_data.get("violated_soft") or []
            soft_hits.extend(edge_soft)
            violated_soft.extend(edge_violated)
            total_distance += self._haversine(u_coord, v_coord)

        last_coord = node_coords.get(path_nodes[-1])
        if last_coord is None:
            return None
        if self._haversine(last_coord, (end.lon, end.lat)) > 0:
            if not self._slope_ok((last_coord, (end.lon, end.lat)), capability):
                return None
            h_hits, s_hits, v_hits = self._check_obstacles((last_coord, (end.lon, end.lat)), obstacles, hard_req, soft_req)
            if h_hits:
                logger.info(f"road_attach_end_blocked hits={h_hits}")
                return None
            soft_hits.extend(s_hits)
            violated_soft.extend(v_hits)
            total_distance += self._haversine(last_coord, (end.lon, end.lat))
            points.append(Point(lon=end.lon, lat=end.lat))

        duration = total_distance / 12.0 if total_distance > 0 else 0.0
        elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
        metrics = PathSearchMetrics(
            iterations=0,
            nodes_expanded=graph.number_of_edges(),
            elapsed_ms=elapsed_ms,
            path_points=len(points),
        )
        audit = Audit(
            soft_hits=dedupe(soft_hits),
            violated_soft=dedupe(violated_soft),
            waivers=[],
            hard_hits=[],
        )
        cost = total_distance + len(audit.soft_hits) * self._soft_penalty + len(audit.violated_soft) * self._violated_penalty
        return PathCandidate(
            id="road",
            points=points,
            distance_m=total_distance,
            duration_s=duration,
            cost=cost,
            audit=audit,
            metadata={"mode": "road"},
            metrics=metrics,
        )

    def _load_graph(self, bbox: Tuple[float, float, float, float]) -> nx.Graph:
        min_lon, min_lat, max_lon, max_lat = bbox
        graph: nx.Graph = nx.Graph()
        with fiona.open(self._roads_path) as src:
            for feat in src.filter(bbox=(min_lon, min_lat, max_lon, max_lat)):
                geom = feat.get("geometry")
                if not geom or geom.get("type") != "LineString":
                    continue
                coords = geom.get("coordinates") or []
                if len(coords) < 2:
                    continue
                road_type = str((feat.get("properties") or {}).get("fclass") or "unknown")
                factor = self._road_factor(road_type)
                for a, b in zip(coords[:-1], coords[1:]):
                    u = self._node_id(a)
                    v = self._node_id(b)
                    dist = self._haversine(a, b)
                    graph.add_node(u, coord=(float(a[0]), float(a[1])))
                    graph.add_node(v, coord=(float(b[0]), float(b[1])))
                    graph.add_edge(u, v, weight=dist * factor, geometry=[(float(a[0]), float(a[1])), (float(b[0]), float(b[1]))], road_type=road_type)
        logger.info(f"road_graph_built bbox={list(bbox)} nodes={graph.number_of_nodes()} edges={graph.number_of_edges()}")
        return graph

    def _bbox_with_buffer(self, points: Sequence[Point], buffer_m: float) -> Tuple[float, float, float, float]:
        lons = [p.lon for p in points]
        lats = [p.lat for p in points]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        deg = buffer_m / 111000.0
        return min_lon - deg, min_lat - deg, max_lon + deg, max_lat + deg

    def _node_id(self, coord: Sequence[float]) -> int:
        return hash((round(float(coord[0]), 6), round(float(coord[1]), 6)))

    def _nearest_node(self, coords: Mapping[int, Tuple[float, float] | None], point: Point) -> Optional[int]:
        best: Optional[int] = None
        best_dist = math.inf
        target = (point.lon, point.lat)
        for nid, c in coords.items():
            if c is None:
                continue
            dist = self._haversine(c, target)
            if dist < best_dist:
                best = nid
                best_dist = dist
        return best

    def _check_obstacles(self, segment: Tuple[Tuple[float, float], Tuple[float, float]], obstacles: Sequence[Obstacle], hard_req: set[str], soft_req: set[str]) -> Tuple[List[str], List[str], List[str]]:
        hard_hits: List[str] = []
        soft_hits: List[str] = []
        violated_soft: List[str] = []
        for obs in obstacles:
            if obs.geometry and self._segment_hits_geom(segment[0], segment[1], obs.geometry):
                key = obs.id or obs.type
                if obs.hard or obs.type in hard_req:
                    hard_hits.append(key)
                else:
                    soft_hits.append(key)
                    if obs.type in soft_req:
                        violated_soft.append(obs.type)
        return hard_hits, soft_hits, violated_soft

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

    def _slope_at(self, coord: Tuple[float, float]) -> float:
        lon, lat = coord
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

    def _road_factor(self, road_type: str) -> float:
        rt = road_type.lower()
        if rt in {"motorway", "motorway_link"}:
            return 1.0
        if rt in {"trunk", "trunk_link"}:
            return 1.1
        if rt in {"primary", "primary_link"}:
            return 1.2
        if rt in {"secondary", "secondary_link"}:
            return 1.4
        if rt in {"tertiary", "tertiary_link"}:
            return 1.6
        if rt in {"residential", "unclassified", "service"}:
            return 1.8
        if rt in {"track", "path", "footway"}:
            return 2.5
        return 2.0

    def _haversine(self, a: Sequence[float], b: Sequence[float]) -> float:
        lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(h))
        return 6371000 * c

    def _slope_ok(self, segment: Tuple[Tuple[float, float], Tuple[float, float]], capability: CapabilityMetrics) -> bool:
        """端点+中点坡度采样，任一点超限则视为不可通行。"""
        if not capability.slope_deg:
            return True
        a, b = segment
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        try:
            s1 = self._slope_at(a)
            s2 = self._slope_at(b)
            sm = self._slope_at(mid)
        except Exception:
            return False
        return max(s1, s2, sm) <= capability.slope_deg
