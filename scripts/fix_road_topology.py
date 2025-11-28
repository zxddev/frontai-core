#!/usr/bin/env python3
"""
路网交叉口拓扑修复脚本

问题：道路在交叉口几何相交但没有共享节点，导致路网不连通
解决方案：
    1. 检测几何相交的边对
    2. 在交点处创建新节点
    3. 拆分原有的边（在交点处断开）

使用方法:
    python scripts/fix_road_topology.py --batch-size 10000 --max-batches 100

参数:
    --batch-size: 每批处理的交叉口数量（默认 10000）
    --max-batches: 最大批次数（默认 100）
    --dry-run: 只统计不执行修复
"""
import argparse
import asyncio
import logging
import os
import sys
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from src.core.database import AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def count_intersections(db) -> int:
    """统计需要修复的交叉口数量"""
    result = await db.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT 1
            FROM operational_v2.road_edges_v2 e1
            JOIN operational_v2.road_edges_v2 e2 ON e1.id < e2.id
            WHERE ST_Intersects(e1.geometry::geometry, e2.geometry::geometry)
            AND NOT ST_Touches(e1.geometry::geometry, e2.geometry::geometry)
            AND e1.from_node_id != e2.from_node_id
            AND e1.from_node_id != e2.to_node_id
            AND e1.to_node_id != e2.from_node_id
            AND e1.to_node_id != e2.to_node_id
            AND e1.is_accessible = true
            AND e2.is_accessible = true
            AND GeometryType(ST_Intersection(e1.geometry::geometry, e2.geometry::geometry)) = 'POINT'
            LIMIT 100000
        ) t
    """))
    return result.fetchone()[0]


async def fix_batch(db, batch_size: int) -> dict:
    """修复一批交叉口"""
    stats = {
        'intersections_found': 0,
        'nodes_created': 0,
        'edges_created': 0,
        'edges_disabled': 0,
    }
    
    # 步骤 1: 检测交叉口
    await db.execute(text('DROP TABLE IF EXISTS temp_intersection_fixes'))
    await db.execute(text(f"""
        CREATE TEMP TABLE temp_intersection_fixes AS
        WITH crossing_edges AS (
            SELECT 
                e1.id as edge1_id,
                e2.id as edge2_id,
                ST_Intersection(e1.geometry::geometry, e2.geometry::geometry) as intersection_geom
            FROM operational_v2.road_edges_v2 e1
            JOIN operational_v2.road_edges_v2 e2 ON e1.id < e2.id
            WHERE ST_Intersects(e1.geometry::geometry, e2.geometry::geometry)
            AND NOT ST_Touches(e1.geometry::geometry, e2.geometry::geometry)
            AND e1.from_node_id != e2.from_node_id
            AND e1.from_node_id != e2.to_node_id
            AND e1.to_node_id != e2.from_node_id
            AND e1.to_node_id != e2.to_node_id
            AND e1.is_accessible = true
            AND e2.is_accessible = true
            LIMIT {batch_size}
        )
        SELECT 
            edge1_id,
            edge2_id,
            ST_X(intersection_geom) as int_lon,
            ST_Y(intersection_geom) as int_lat,
            intersection_geom::geography as int_location
        FROM crossing_edges
        WHERE GeometryType(intersection_geom) = 'POINT'
    """))
    
    result = await db.execute(text('SELECT COUNT(*) FROM temp_intersection_fixes'))
    stats['intersections_found'] = result.fetchone()[0]
    
    if stats['intersections_found'] == 0:
        return stats
    
    # 步骤 2: 创建交叉口节点
    await db.execute(text("""
        INSERT INTO operational_v2.road_nodes_v2 (
            id, osm_id, lon, lat, location, node_type, edge_count,
            is_accessible, properties, created_at, updated_at
        )
        SELECT DISTINCT ON (ROUND(int_lon::numeric, 6), ROUND(int_lat::numeric, 6))
            gen_random_uuid() as id,
            NULL as osm_id,
            int_lon as lon,
            int_lat as lat,
            int_location as location,
            'intersection' as node_type,
            4 as edge_count,
            true as is_accessible,
            '{"source": "topology_fix"}'::jsonb as properties,
            NOW() as created_at,
            NOW() as updated_at
        FROM temp_intersection_fixes
        WHERE NOT EXISTS (
            SELECT 1 FROM operational_v2.road_nodes_v2 n
            WHERE ST_DWithin(n.location, int_location, 10)
        )
    """))
    
    result = await db.execute(text("""
        SELECT COUNT(*) FROM operational_v2.road_nodes_v2 
        WHERE properties->>'source' = 'topology_fix'
        AND created_at > NOW() - INTERVAL '1 minute'
    """))
    stats['nodes_created'] = result.fetchone()[0]
    
    # 步骤 3: 关联节点 ID
    await db.execute(text('ALTER TABLE temp_intersection_fixes ADD COLUMN IF NOT EXISTS new_node_id UUID'))
    await db.execute(text("""
        UPDATE temp_intersection_fixes f
        SET new_node_id = (
            SELECT n.id 
            FROM operational_v2.road_nodes_v2 n
            WHERE ST_DWithin(n.location, f.int_location, 15)
            ORDER BY ST_Distance(n.location, f.int_location)
            LIMIT 1
        )
    """))
    
    # 步骤 4: 拆分边
    for edge_col in ['edge1_id', 'edge2_id']:
        # 前半段
        await db.execute(text(f"""
            INSERT INTO operational_v2.road_edges_v2 (
                id, osm_id, from_node_id, to_node_id, geometry,
                road_type, name, oneway, length_m, is_accessible, properties, created_at, updated_at
            )
            SELECT DISTINCT ON (f.{edge_col}, f.new_node_id)
                gen_random_uuid() as id,
                e.osm_id,
                e.from_node_id,
                f.new_node_id as to_node_id,
                ST_LineSubstring(
                    e.geometry::geometry,
                    0,
                    GREATEST(0.01, LEAST(0.99, ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326))))
                )::geography as geometry,
                e.road_type, e.name, e.oneway,
                e.length_m * GREATEST(0.01, LEAST(0.99, ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326)))) as length_m,
                true as is_accessible,
                jsonb_build_object('split_from', e.id::text),
                NOW(), NOW()
            FROM temp_intersection_fixes f
            JOIN operational_v2.road_edges_v2 e ON e.id = f.{edge_col}
            WHERE f.new_node_id IS NOT NULL
        """))
        
        # 后半段
        await db.execute(text(f"""
            INSERT INTO operational_v2.road_edges_v2 (
                id, osm_id, from_node_id, to_node_id, geometry,
                road_type, name, oneway, length_m, is_accessible, properties, created_at, updated_at
            )
            SELECT DISTINCT ON (f.{edge_col}, f.new_node_id)
                gen_random_uuid() as id,
                e.osm_id,
                f.new_node_id as from_node_id,
                e.to_node_id,
                ST_LineSubstring(
                    e.geometry::geometry,
                    GREATEST(0.01, LEAST(0.99, ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326)))),
                    1
                )::geography as geometry,
                e.road_type, e.name, e.oneway,
                e.length_m * (1 - GREATEST(0.01, LEAST(0.99, ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326))))) as length_m,
                true as is_accessible,
                jsonb_build_object('split_from', e.id::text),
                NOW(), NOW()
            FROM temp_intersection_fixes f
            JOIN operational_v2.road_edges_v2 e ON e.id = f.{edge_col}
            WHERE f.new_node_id IS NOT NULL
        """))
    
    result = await db.execute(text("""
        SELECT COUNT(*) FROM operational_v2.road_edges_v2 
        WHERE properties ? 'split_from'
        AND created_at > NOW() - INTERVAL '1 minute'
    """))
    stats['edges_created'] = result.fetchone()[0]
    
    # 步骤 5: 禁用原边
    await db.execute(text("""
        UPDATE operational_v2.road_edges_v2
        SET is_accessible = false,
            properties = jsonb_build_object('replaced_by_split', true)
        WHERE id IN (SELECT edge1_id FROM temp_intersection_fixes WHERE new_node_id IS NOT NULL)
           OR id IN (SELECT edge2_id FROM temp_intersection_fixes WHERE new_node_id IS NOT NULL)
    """))
    
    result = await db.execute(text("""
        SELECT COUNT(*) FROM operational_v2.road_edges_v2 
        WHERE properties->>'replaced_by_split' = 'true'
        AND updated_at > NOW() - INTERVAL '1 minute'
    """))
    stats['edges_disabled'] = result.fetchone()[0]
    
    await db.commit()
    return stats


async def verify_connectivity(db) -> dict:
    """验证路网连通性"""
    import networkx as nx
    
    # 加载整个路网
    result = await db.execute(text("""
        SELECT from_node_id, to_node_id
        FROM operational_v2.road_edges_v2
        WHERE is_accessible = true
        LIMIT 500000
    """))
    
    G = nx.Graph()
    for from_id, to_id in result.fetchall():
        G.add_edge(str(from_id), str(to_id))
    
    components = list(nx.connected_components(G))
    sizes = sorted([len(c) for c in components], reverse=True)
    
    return {
        'nodes': G.number_of_nodes(),
        'edges': G.number_of_edges(),
        'components': len(components),
        'largest_component': sizes[0] if sizes else 0,
        'largest_percentage': sizes[0] / G.number_of_nodes() * 100 if G.number_of_nodes() > 0 else 0,
    }


async def main():
    parser = argparse.ArgumentParser(description='修复路网交叉口拓扑')
    parser.add_argument('--batch-size', type=int, default=10000, help='每批处理数量')
    parser.add_argument('--max-batches', type=int, default=100, help='最大批次数')
    parser.add_argument('--dry-run', action='store_true', help='只统计不执行')
    args = parser.parse_args()
    
    async with AsyncSessionLocal() as db:
        # 统计需要修复的数量
        logger.info("统计需要修复的交叉口...")
        total = await count_intersections(db)
        logger.info(f"需要修复的交叉口: {total}")
        
        if args.dry_run:
            logger.info("Dry run 模式，退出")
            return
        
        # 修复前的连通性
        logger.info("检查修复前的连通性...")
        before = await verify_connectivity(db)
        logger.info(f"修复前: {before['components']} 个分量, 最大分量 {before['largest_percentage']:.1f}%")
        
        # 分批修复
        total_stats = {
            'intersections_found': 0,
            'nodes_created': 0,
            'edges_created': 0,
            'edges_disabled': 0,
        }
        
        for batch_num in range(1, args.max_batches + 1):
            logger.info(f"处理第 {batch_num} 批...")
            start_time = time.time()
            
            stats = await fix_batch(db, args.batch_size)
            
            if stats['intersections_found'] == 0:
                logger.info("没有更多需要修复的交叉口")
                break
            
            elapsed = time.time() - start_time
            logger.info(
                f"批次 {batch_num} 完成: "
                f"交叉口={stats['intersections_found']}, "
                f"新节点={stats['nodes_created']}, "
                f"新边={stats['edges_created']}, "
                f"禁用边={stats['edges_disabled']}, "
                f"耗时={elapsed:.1f}s"
            )
            
            for key in total_stats:
                total_stats[key] += stats[key]
        
        # 修复后的连通性
        logger.info("检查修复后的连通性...")
        after = await verify_connectivity(db)
        logger.info(f"修复后: {after['components']} 个分量, 最大分量 {after['largest_percentage']:.1f}%")
        
        # 总结
        logger.info("=" * 60)
        logger.info("修复完成!")
        logger.info(f"处理交叉口: {total_stats['intersections_found']}")
        logger.info(f"创建节点: {total_stats['nodes_created']}")
        logger.info(f"创建边: {total_stats['edges_created']}")
        logger.info(f"禁用边: {total_stats['edges_disabled']}")
        logger.info(f"连通分量: {before['components']} -> {after['components']}")
        logger.info(f"最大分量: {before['largest_percentage']:.1f}% -> {after['largest_percentage']:.1f}%")


if __name__ == '__main__':
    asyncio.run(main())
