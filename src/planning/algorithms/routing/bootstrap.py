"""路网/DEM/水域加载与资源容器。

约束：
- 缺文件/依赖直接抛错，不做兜底。
- 仅支持 WGS84 数据；道路使用 OSM roads Shapefile，水域使用 OSM water_a Shapefile。
- DEM 用于坡度/高程；越野/路网共享同一 DEM。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import fiona
import rasterio
from shapely.geometry import shape, Polygon

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RoutingResources:
    dem_path: Path
    roads_path: Path
    water_polygons: Sequence[Polygon]
    dem_dataset: rasterio.io.DatasetReader


def _require_file(path: Path, kind: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"缺少{kind}文件: {path}")


def load_water_polygons(shp_path: Path) -> List[Polygon]:
    _require_file(shp_path, "水域 Shapefile")
    geoms: List[Polygon] = []
    with fiona.open(shp_path) as src:
        for feat in src:
            geom = feat.get("geometry")
            if not geom:
                continue
            poly = shape(geom)
            if not poly.is_empty:
                geoms.append(poly)
    logger.info(f"water_polygons_loaded count={len(geoms)}")
    return geoms


def load_routing_resources(dem_path: Path, roads_path: Path, water_path: Path) -> RoutingResources:
    _require_file(dem_path, "DEM")
    _require_file(roads_path, "道路 Shapefile")
    _require_file(water_path, "水域 Shapefile")

    dem_ds = rasterio.open(dem_path)
    logger.info(
        f"dem_loaded path={dem_path} size={dem_ds.width}x{dem_ds.height} "
        f"bounds={list(dem_ds.bounds)} crs={dem_ds.crs}"
    )
    water_polys = load_water_polygons(water_path)
    return RoutingResources(
        dem_path=dem_path,
        roads_path=roads_path,
        water_polygons=water_polys,
        dem_dataset=dem_ds,
    )
