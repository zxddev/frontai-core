#!/usr/bin/env python3
"""
路网数据ETL脚本
从OSM Shapefile导入道路数据到PostGIS，并从DEM提取坡度信息
"""

import os
import sys
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import numpy as np

try:
    import geopandas as gpd
    import rasterio
    from rasterio.sample import sample_gen
    from shapely.geometry import Point, LineString
    from shapely.ops import linemerge
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请安装: pip install geopandas rasterio shapely psycopg2-binary")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据路径配置
DATA_DIR = Path(__file__).parent.parent / "data"
ROADS_SHP = DATA_DIR / "roads" / "gis_osm_roads_free_1.shp"
LANDUSE_SHP = DATA_DIR / "roads" / "gis_osm_landuse_a_free_1.shp"
DEM_TIF = DATA_DIR / "四川省.tif"

# 数据库配置
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "192.168.31.40"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "emergency_agent"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres123"),
}

# OSM道路类型映射到枚举
ROAD_TYPE_MAPPING = {
    'motorway': 'motorway',
    'motorway_link': 'motorway_link',
    'trunk': 'trunk',
    'trunk_link': 'trunk_link',
    'primary': 'primary',
    'primary_link': 'primary_link',
    'secondary': 'secondary',
    'secondary_link': 'secondary_link',
    'tertiary': 'tertiary',
    'tertiary_link': 'tertiary_link',
    'residential': 'residential',
    'living_street': 'living_street',
    'service': 'service',
    'unclassified': 'unclassified',
    'track': 'track',
    'track_grade1': 'track',
    'track_grade2': 'track',
    'track_grade3': 'track',
    'track_grade4': 'track',
    'track_grade5': 'track',
    'path': 'path',
    'footway': 'footway',
    'cycleway': 'cycleway',
    'bridleway': 'bridleway',
    'steps': 'steps',
}

# 路面类型映射
SURFACE_MAPPING = {
    'paved': 'paved',
    'asphalt': 'asphalt',
    'concrete': 'concrete',
    'concrete:plates': 'concrete',
    'concrete:lanes': 'concrete',
    'cobblestone': 'cobblestone',
    'sett': 'cobblestone',
    'gravel': 'gravel',
    'fine_gravel': 'gravel',
    'compacted': 'gravel',
    'unpaved': 'unpaved',
    'dirt': 'dirt',
    'earth': 'dirt',
    'ground': 'dirt',
    'sand': 'sand',
    'grass': 'grass',
    'mud': 'mud',
}


@dataclass
class RoadEdge:
    """道路边数据"""
    osm_id: int
    geometry: LineString
    road_type: str
    name: Optional[str]
    ref: Optional[str]
    oneway: bool
    maxspeed: Optional[int]
    lanes: Optional[int]
    surface: Optional[str]
    bridge: bool
    tunnel: bool
    length_m: float


class DEMSampler:
    """DEM高程采样器"""
    
    def __init__(self, dem_path: Path):
        self.dem_path = dem_path
        self.dataset = None
        self.nodata = None
        
    def __enter__(self):
        if self.dem_path and self.dem_path.exists() and str(self.dem_path) != '/dev/null':
            self.dataset = rasterio.open(self.dem_path)
            self.nodata = self.dataset.nodata
            logger.info(f"DEM已加载: {self.dem_path}, 分辨率: {self.dataset.res}")
        else:
            logger.warning(f"DEM未加载，跳过高程采样")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.dataset:
            self.dataset.close()
            
    def sample_point(self, lon: float, lat: float) -> Optional[float]:
        """采样单点高程"""
        if not self.dataset:
            return None
        try:
            coords = [(lon, lat)]
            values = list(sample_gen(self.dataset, coords))
            if values and len(values[0]) > 0:
                val = values[0][0]
                if val != self.nodata and not np.isnan(val):
                    return float(val)
        except Exception as e:
            logger.debug(f"采样失败 ({lon}, {lat}): {e}")
        return None
    
    def sample_line(self, line: LineString, sample_interval_m: float = 100) -> Dict[str, Any]:
        """采样线段上的高程，计算坡度信息"""
        if not self.dataset:
            return {}
            
        result = {
            'start_elevation_m': None,
            'end_elevation_m': None,
            'elevation_gain_m': 0.0,
            'elevation_loss_m': 0.0,
            'avg_gradient_percent': None,
            'max_gradient_percent': None,
        }
        
        # 获取采样点 (line.length是度数，1度≈111320米)
        length_deg = line.length
        length_m = length_deg * 111320  # 转为米
        if length_m < 10:  # 小于10米的道路跳过
            return result
            
        # 按间隔采样 (转换为度数)
        sample_interval_deg = sample_interval_m / 111320
        num_samples = max(2, int(length_deg / sample_interval_deg) + 1)
        distances = np.linspace(0, length_deg, num_samples)
        
        coords = []
        for d in distances:
            point = line.interpolate(d)
            coords.append((point.x, point.y))
        
        # 批量采样
        elevations = []
        for coord in coords:
            elev = self.sample_point(coord[0], coord[1])
            if elev is not None:
                elevations.append(elev)
        
        if len(elevations) < 2:
            return result
            
        # 计算统计
        result['start_elevation_m'] = elevations[0]
        result['end_elevation_m'] = elevations[-1]
        
        # 计算累计爬升/下降
        gain = 0.0
        loss = 0.0
        gradients = []
        
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i-1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)
            
            # 计算该段坡度 (使用米为单位)
            segment_length_m = length_m / (num_samples - 1)
            if segment_length_m > 0:
                gradient = (diff / segment_length_m) * 100  # 转为百分比
                gradients.append(abs(gradient))
        
        result['elevation_gain_m'] = float(gain)
        result['elevation_loss_m'] = float(loss)
        
        if gradients:
            result['avg_gradient_percent'] = float(np.mean(gradients))
            result['max_gradient_percent'] = float(np.max(gradients))
        
        return result


class LanduseSampler:
    """土地利用类型采样器"""
    
    TERRAIN_MAPPING = {
        'residential': 'urban',
        'commercial': 'urban',
        'industrial': 'urban',
        'retail': 'urban',
        'construction': 'urban',
        'farmland': 'rural',
        'farmyard': 'rural',
        'meadow': 'grassland',
        'grass': 'grassland',
        'forest': 'forest',
        'wood': 'forest',
        'orchard': 'rural',
        'vineyard': 'rural',
        'scrub': 'grassland',
        'heath': 'grassland',
        'water': 'water_adjacent',
        'wetland': 'wetland',
        'marsh': 'wetland',
        'reservoir': 'water_adjacent',
        'basin': 'water_adjacent',
        'quarry': 'mountain',
        'landfill': 'urban',
        'brownfield': 'urban',
        'greenfield': 'suburban',
        'cemetery': 'urban',
        'allotments': 'suburban',
        'recreation_ground': 'urban',
        'village_green': 'suburban',
    }
    
    def __init__(self, landuse_path: Path):
        self.landuse_path = landuse_path
        self.gdf = None
        self.sindex = None
        
    def load(self):
        """加载土地利用数据"""
        if self.landuse_path and self.landuse_path.exists():
            logger.info(f"加载土地利用数据: {self.landuse_path}")
            self.gdf = gpd.read_file(self.landuse_path)
            self.sindex = self.gdf.sindex
            logger.info(f"土地利用数据加载完成, 共 {len(self.gdf)} 条记录")
        else:
            logger.warning(f"土地利用未加载，跳过地形推断")
            
    def get_terrain_type(self, geometry) -> str:
        """根据几何体查询地形类型"""
        if self.gdf is None:
            return 'unknown'
            
        try:
            # 空间索引查询
            possible_matches_idx = list(self.sindex.intersection(geometry.bounds))
            if not possible_matches_idx:
                return 'unknown'
                
            possible_matches = self.gdf.iloc[possible_matches_idx]
            precise_matches = possible_matches[possible_matches.intersects(geometry)]
            
            if precise_matches.empty:
                return 'unknown'
                
            # 取面积最大的相交区域的类型
            max_area = 0
            result_type = 'unknown'
            
            for idx, row in precise_matches.iterrows():
                intersection = row.geometry.intersection(geometry)
                if hasattr(intersection, 'area') and intersection.area > max_area:
                    max_area = intersection.area
                    fclass = row.get('fclass', '')
                    result_type = self.TERRAIN_MAPPING.get(fclass, 'unknown')
                    
            return result_type
        except Exception as e:
            logger.debug(f"地形类型查询失败: {e}")
            return 'unknown'


class RoadNetworkETL:
    """路网ETL处理器"""
    
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.conn = None
        
    def connect(self):
        """连接数据库"""
        self.conn = psycopg2.connect(**self.db_config)
        logger.info("数据库连接成功")
        
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            
    def load_roads(self, shp_path: Path, limit: Optional[int] = None) -> gpd.GeoDataFrame:
        """加载道路Shapefile"""
        logger.info(f"加载道路数据: {shp_path}")
        
        gdf = gpd.read_file(shp_path)
        logger.info(f"原始道路数据: {len(gdf)} 条")
        
        # 只保留机动车可通行的道路类型
        valid_types = set(ROAD_TYPE_MAPPING.keys())
        gdf = gdf[gdf['fclass'].isin(valid_types)]
        logger.info(f"过滤后道路数据: {len(gdf)} 条")
        
        if limit:
            gdf = gdf.head(limit)
            logger.info(f"限制导入数量: {limit} 条")
            
        return gdf
        
    def extract_nodes(self, gdf: gpd.GeoDataFrame) -> Dict[Tuple[float, float], str]:
        """从道路中提取节点"""
        logger.info("提取路网节点...")
        
        nodes = {}  # (lon, lat) -> node_id
        
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
                
            # 提取起点和终点
            coords = list(geom.coords)
            if len(coords) >= 2:
                start = (round(coords[0][0], 7), round(coords[0][1], 7))
                end = (round(coords[-1][0], 7), round(coords[-1][1], 7))
                
                if start not in nodes:
                    nodes[start] = str(uuid.uuid4())
                if end not in nodes:
                    nodes[end] = str(uuid.uuid4())
                    
        logger.info(f"提取节点: {len(nodes)} 个")
        return nodes
        
    def insert_nodes(self, nodes: Dict[Tuple[float, float], str], dem_sampler: DEMSampler):
        """插入节点到数据库"""
        logger.info("插入节点到数据库...")
        
        cursor = self.conn.cursor()
        
        # 准备数据
        node_data = []
        for (lon, lat), node_id in nodes.items():
            elevation = dem_sampler.sample_point(lon, lat)
            node_data.append((
                node_id,
                lon, lat,
                f'POINT({lon} {lat})',
                elevation
            ))
            
        # 批量插入
        sql = """
            INSERT INTO operational_v2.road_nodes_v2 
            (id, lon, lat, location, elevation_m)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """
        
        template = "(%(id)s::uuid, %(lon)s, %(lat)s, ST_GeogFromText(%(location)s), %(elevation)s)"
        
        batch_size = 5000
        for i in range(0, len(node_data), batch_size):
            batch = node_data[i:i+batch_size]
            values = [
                {'id': n[0], 'lon': n[1], 'lat': n[2], 'location': n[3], 'elevation': n[4]}
                for n in batch
            ]
            cursor.executemany(
                """INSERT INTO operational_v2.road_nodes_v2 
                   (id, lon, lat, location, elevation_m)
                   VALUES (%(id)s::uuid, %(lon)s, %(lat)s, ST_GeogFromText(%(location)s), %(elevation)s)
                   ON CONFLICT DO NOTHING""",
                values
            )
            self.conn.commit()
            logger.info(f"已插入节点: {min(i+batch_size, len(node_data))}/{len(node_data)}")
            
        cursor.close()
        logger.info(f"节点插入完成: {len(node_data)} 个")
        
    def insert_edges(
        self, 
        gdf: gpd.GeoDataFrame, 
        nodes: Dict[Tuple[float, float], str],
        dem_sampler: DEMSampler,
        landuse_sampler: LanduseSampler
    ):
        """插入边到数据库"""
        logger.info("插入边到数据库...")
        
        cursor = self.conn.cursor()
        inserted = 0
        
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
                
            coords = list(geom.coords)
            if len(coords) < 2:
                continue
                
            start = (round(coords[0][0], 7), round(coords[0][1], 7))
            end = (round(coords[-1][0], 7), round(coords[-1][1], 7))
            
            from_node_id = nodes.get(start)
            to_node_id = nodes.get(end)
            
            if not from_node_id or not to_node_id:
                continue
                
            # 解析属性
            road_type = ROAD_TYPE_MAPPING.get(row.get('fclass', ''), 'unclassified')
            name = row.get('name')
            ref = row.get('ref')
            oneway = row.get('oneway', 'B') == 'F'  # F=forward only
            
            maxspeed = None
            maxspeed_str = row.get('maxspeed')
            if maxspeed_str and str(maxspeed_str).isdigit():
                maxspeed = int(maxspeed_str)
                
            bridge = row.get('bridge', '') == 'T'
            tunnel = row.get('tunnel', '') == 'T'
            
            # 计算长度
            length_m = geom.length * 111320  # 近似转换为米
            
            # 从DEM获取高程信息
            elev_info = dem_sampler.sample_line(geom)
            
            # 获取地形类型
            terrain_type = landuse_sampler.get_terrain_type(geom)
            
            # 计算代价系数
            terrain_cost = self._calc_terrain_cost(terrain_type)
            gradient_cost = self._calc_gradient_cost(elev_info.get('avg_gradient_percent'))
            
            # 计算速度系数
            speed_factors = self._calc_speed_factors(road_type, terrain_type)
            
            # WKT几何
            wkt = geom.wkt
            
            # 插入
            cursor.execute("""
                INSERT INTO operational_v2.road_edges_v2 (
                    id, osm_id, from_node_id, to_node_id, geometry,
                    road_type, name, ref, oneway, max_speed_kmh,
                    bridge, tunnel, length_m,
                    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
                    avg_gradient_percent, max_gradient_percent,
                    terrain_type, terrain_cost_factor, gradient_cost_factor,
                    speed_factors, base_cost
                ) VALUES (
                    %s::uuid, %s, %s::uuid, %s::uuid, ST_GeogFromText(%s),
                    %s::operational_v2.road_type_v2, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s::operational_v2.terrain_type_v2, %s, %s,
                    %s::jsonb, %s
                )
                ON CONFLICT DO NOTHING
            """, (
                str(uuid.uuid4()),
                row.get('osm_id'),
                from_node_id,
                to_node_id,
                wkt,
                road_type,
                name,
                ref,
                oneway,
                maxspeed,
                bridge,
                tunnel,
                length_m,
                elev_info.get('start_elevation_m'),
                elev_info.get('end_elevation_m'),
                elev_info.get('elevation_gain_m'),
                elev_info.get('elevation_loss_m'),
                elev_info.get('avg_gradient_percent'),
                elev_info.get('max_gradient_percent'),
                terrain_type,
                terrain_cost,
                gradient_cost,
                str(speed_factors).replace("'", '"'),
                length_m * terrain_cost * gradient_cost
            ))
            
            inserted += 1
            if inserted % 5000 == 0:
                self.conn.commit()
                logger.info(f"已插入边: {inserted}")
                
        self.conn.commit()
        cursor.close()
        logger.info(f"边插入完成: {inserted} 条")
        
    def _calc_terrain_cost(self, terrain_type: str) -> float:
        """计算地形代价系数"""
        costs = {
            'urban': 1.0,
            'suburban': 1.1,
            'rural': 1.2,
            'mountain': 1.5,
            'forest': 1.4,
            'grassland': 1.3,
            'water_adjacent': 1.3,
            'desert': 1.6,
            'wetland': 1.8,
            'unknown': 1.2,
        }
        return costs.get(terrain_type, 1.2)
        
    def _calc_gradient_cost(self, gradient: Optional[float]) -> float:
        """计算坡度代价系数"""
        if gradient is None:
            return 1.0
        if gradient < 5:
            return 1.0
        elif gradient < 10:
            return 1.2
        elif gradient < 15:
            return 1.5
        elif gradient < 20:
            return 2.0
        else:
            return 3.0
            
    def _calc_speed_factors(self, road_type: str, terrain_type: str) -> dict:
        """计算不同车辆类型的速度系数"""
        base = {
            'standard': 1.0,
            'all_terrain': 1.0,
            'truck': 0.8,
            'emergency': 1.2,
        }
        
        # 根据道路类型调整
        if road_type in ('track', 'path'):
            base['standard'] = 0.3
            base['all_terrain'] = 0.7
            base['truck'] = 0.2
            base['emergency'] = 0.5
        elif road_type in ('residential', 'living_street'):
            base['truck'] = 0.6
            
        # 根据地形调整
        if terrain_type == 'mountain':
            for k in base:
                base[k] *= 0.7
        elif terrain_type == 'forest':
            for k in base:
                base[k] *= 0.8
                
        return base
        
    def update_node_edge_counts(self):
        """更新节点的边数量"""
        logger.info("更新节点边数量...")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE operational_v2.road_nodes_v2 n
            SET edge_count = (
                SELECT COUNT(*) 
                FROM operational_v2.road_edges_v2 e 
                WHERE e.from_node_id = n.id OR e.to_node_id = n.id
            ),
            node_type = CASE 
                WHEN (SELECT COUNT(*) FROM operational_v2.road_edges_v2 e 
                      WHERE e.from_node_id = n.id OR e.to_node_id = n.id) > 2 
                THEN 'intersection'
                WHEN (SELECT COUNT(*) FROM operational_v2.road_edges_v2 e 
                      WHERE e.from_node_id = n.id OR e.to_node_id = n.id) = 1 
                THEN 'endpoint'
                ELSE 'waypoint'
            END,
            updated_at = now()
        """)
        self.conn.commit()
        cursor.close()
        logger.info("节点边数量更新完成")
        
    def create_indexes(self):
        """创建额外索引"""
        logger.info("创建索引...")
        
        cursor = self.conn.cursor()
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_road_edges_v2_cost ON operational_v2.road_edges_v2(base_cost)",
            "CREATE INDEX IF NOT EXISTS idx_road_edges_v2_terrain ON operational_v2.road_edges_v2(terrain_type)",
        ]
        
        for idx_sql in indexes:
            cursor.execute(idx_sql)
            
        self.conn.commit()
        cursor.close()
        logger.info("索引创建完成")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='路网数据ETL')
    parser.add_argument('--limit', type=int, help='限制导入数量(用于测试)')
    parser.add_argument('--skip-dem', action='store_true', help='跳过DEM处理')
    parser.add_argument('--skip-landuse', action='store_true', help='跳过土地利用处理')
    args = parser.parse_args()
    
    # 检查文件
    if not ROADS_SHP.exists():
        logger.error(f"道路文件不存在: {ROADS_SHP}")
        sys.exit(1)
        
    # 初始化ETL
    etl = RoadNetworkETL(DB_CONFIG)
    
    try:
        etl.connect()
        
        # 加载道路数据
        gdf = etl.load_roads(ROADS_SHP, limit=args.limit)
        
        # 提取节点
        nodes = etl.extract_nodes(gdf)
        
        # 初始化DEM采样器
        with DEMSampler(DEM_TIF if not args.skip_dem else None) as dem_sampler:
            # 插入节点
            etl.insert_nodes(nodes, dem_sampler)
            
            # 初始化土地利用采样器
            landuse_sampler = LanduseSampler(LANDUSE_SHP if not args.skip_landuse else None)
            if not args.skip_landuse:
                landuse_sampler.load()
            
            # 插入边
            etl.insert_edges(gdf, nodes, dem_sampler, landuse_sampler)
        
        # 更新节点统计
        etl.update_node_edge_counts()
        
        # 创建索引
        etl.create_indexes()
        
        logger.info("ETL完成!")
        
    except Exception as e:
        logger.error(f"ETL失败: {e}", exc_info=True)
        sys.exit(1)
    finally:
        etl.close()


if __name__ == '__main__':
    main()
