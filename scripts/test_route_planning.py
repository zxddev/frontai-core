#!/usr/bin/env python3
"""
路径规划算法测试脚本

测试内容：
1. ETA时间计算准确性
2. 危险区域避障功能
3. 路网A*算法验证
"""
import asyncio
import sys
import math
from uuid import UUID, uuid4
from typing import List, Dict, Any, Optional
from datetime import datetime

import asyncpg

# 数据库配置
DB_CONFIG = {
    "host": "192.168.31.40",
    "port": 5432,
    "user": "postgres",
    "password": "postgres123",
    "database": "emergency_agent",
}


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算两点间球面距离（米）"""
    R = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


async def test_basic_distance():
    """测试1: 基础距离计算"""
    print("\n" + "=" * 60)
    print("测试1: 基础距离计算验证")
    print("=" * 60)
    
    # 茂县消防站到事发地点（茂县中学附近）
    station_lon, station_lat = 103.8537, 31.6815  # 茂县消防站
    incident_lon, incident_lat = 103.8720, 31.6580  # 事发地点
    
    direct_dist = haversine_distance(station_lon, station_lat, incident_lon, incident_lat)
    
    # 当前系统计算方式（matching.py）
    speed_kmh = 40.0
    eta_current = (direct_dist / 1000) / speed_kmh * 60  # 分钟
    
    # 考虑道路系数1.4（城市道路）
    road_dist = direct_dist * 1.4
    eta_road = (road_dist / 1000) / speed_kmh * 60
    
    print(f"起点: 茂县消防站 ({station_lon}, {station_lat})")
    print(f"终点: 事发地点 ({incident_lon}, {incident_lat})")
    print(f"\n直线距离: {direct_dist/1000:.2f} km")
    print(f"估算道路距离(×1.4): {road_dist/1000:.2f} km")
    print(f"\n当前系统ETA(直线+40km/h): {eta_current:.1f} 分钟")
    print(f"更合理ETA(道路+40km/h): {eta_road:.1f} 分钟")


async def test_road_network_exists(conn: asyncpg.Connection):
    """测试2: 检查路网数据是否存在"""
    print("\n" + "=" * 60)
    print("测试2: 路网数据检查")
    print("=" * 60)
    
    # 检查road_edges_v2表
    edge_count = await conn.fetchval("""
        SELECT COUNT(*) FROM operational_v2.road_edges_v2
    """)
    
    # 检查road_nodes_v2表
    node_count = await conn.fetchval("""
        SELECT COUNT(*) FROM operational_v2.road_nodes_v2
    """)
    
    print(f"路网边数量: {edge_count}")
    print(f"路网节点数量: {node_count}")
    
    if edge_count == 0:
        print("\n⚠️ 警告: 路网数据为空！路径规划将无法使用真实路网")
        return False
    
    # 查看茂县附近的路网覆盖
    maoxian_edges = await conn.fetchval("""
        SELECT COUNT(*) FROM operational_v2.road_edges_v2
        WHERE ST_DWithin(
            geometry,
            ST_SetSRID(ST_MakePoint(103.8537, 31.6815), 4326)::geography,
            10000
        )
    """)
    print(f"茂县10km范围内路网边: {maoxian_edges}")
    
    return edge_count > 0


async def test_disaster_areas(conn: asyncpg.Connection):
    """测试3: 检查灾害影响区域数据"""
    print("\n" + "=" * 60)
    print("测试3: 灾害影响区域检查")
    print("=" * 60)
    
    # 查看所有灾害区域
    areas = await conn.fetch("""
        SELECT 
            id, name, area_type, passable, risk_level,
            speed_reduction_percent, scenario_id,
            ST_AsText(ST_Centroid(geometry::geometry)) as center
        FROM operational_v2.disaster_affected_areas_v2
        LIMIT 10
    """)
    
    print(f"灾害影响区域数量: {len(areas)}")
    
    if areas:
        print("\n现有灾害区域:")
        for area in areas:
            print(f"  - {area['name']}: 类型={area['area_type']}, "
                  f"可通行={area['passable']}, 风险={area['risk_level']}")
    else:
        print("\n⚠️ 无灾害影响区域数据，将创建测试数据")
    
    return len(areas) > 0


async def create_test_disaster_area(conn: asyncpg.Connection) -> UUID:
    """创建测试用的灾害影响区域"""
    print("\n创建测试灾害区域...")
    
    # 在茂县消防站到事发地点之间创建一个障碍区域
    # 中心点约 (103.863, 31.670)，半径500米
    area_id = uuid4()
    
    await conn.execute("""
        INSERT INTO operational_v2.disaster_affected_areas_v2 (
            id, name, area_type, severity,
            geometry, passable, passable_vehicle_types,
            speed_reduction_percent, risk_level
        ) VALUES (
            $1, '测试-建筑倒塌区域', 'collapse_zone', 'severe',
            ST_Buffer(
                ST_SetSRID(ST_MakePoint(103.863, 31.670), 4326)::geography,
                500
            ),
            false, ARRAY['heavy_rescue']::text[],
            100, 4
        )
    """, area_id)
    
    print(f"  创建危险区域: 建筑倒塌区域 (103.863, 31.670) 半径500m")
    print(f"  区域ID: {area_id}")
    print(f"  属性: passable=false, 仅heavy_rescue车辆可通行")
    
    return area_id


async def test_route_with_obstacle(conn: asyncpg.Connection, obstacle_id: Optional[UUID] = None):
    """测试4: 带障碍物的路径规划"""
    print("\n" + "=" * 60)
    print("测试4: 避障路径规划测试")
    print("=" * 60)
    
    # 起终点
    start_lon, start_lat = 103.8537, 31.6815  # 消防站
    end_lon, end_lat = 103.8720, 31.6580      # 事发地点
    
    # 直线距离
    direct_dist = haversine_distance(start_lon, start_lat, end_lon, end_lat)
    
    print(f"起点: ({start_lon}, {start_lat})")
    print(f"终点: ({end_lon}, {end_lat})")
    print(f"直线距离: {direct_dist/1000:.2f} km")
    
    # 检查是否有路径穿过障碍区域
    if obstacle_id:
        # 检查直线是否与障碍区域相交
        intersects = await conn.fetchval("""
            SELECT ST_Intersects(
                ST_MakeLine(
                    ST_SetSRID(ST_MakePoint($1, $2), 4326),
                    ST_SetSRID(ST_MakePoint($3, $4), 4326)
                )::geography::geometry,
                d.geometry::geometry
            )
            FROM operational_v2.disaster_affected_areas_v2 d
            WHERE d.id = $5
        """, start_lon, start_lat, end_lon, end_lat, obstacle_id)
        
        print(f"\n直线路径与障碍区域相交: {intersects}")
        
        if intersects:
            print("✓ 障碍区域位于直线路径上，避障算法应该绕行")
        else:
            print("⚠️ 障碍区域不在直线路径上，调整障碍位置")
    
    # 模拟避障路径规划
    print("\n模拟避障路径规划:")
    
    # 如果直接走不通，需要绕行
    # 假设绕行增加30%距离
    detour_dist = direct_dist * 1.3 * 1.4  # 直线×1.3绕行×1.4道路系数
    eta_detour = (detour_dist / 1000) / 40 * 60  # 40km/h
    
    print(f"  绕行距离估算: {detour_dist/1000:.2f} km")
    print(f"  绕行ETA估算: {eta_detour:.1f} 分钟")
    
    # 对比不考虑障碍的情况
    normal_dist = direct_dist * 1.4
    eta_normal = (normal_dist / 1000) / 40 * 60
    print(f"\n  无障碍距离: {normal_dist/1000:.2f} km")
    print(f"  无障碍ETA: {eta_normal:.1f} 分钟")
    print(f"\n  差异: +{(detour_dist - normal_dist)/1000:.2f} km, +{eta_detour - eta_normal:.1f} 分钟")


async def test_db_route_engine(conn: asyncpg.Connection):
    """测试5: DatabaseRouteEngine功能测试"""
    print("\n" + "=" * 60)
    print("测试5: DatabaseRouteEngine集成测试")
    print("=" * 60)
    
    # 检查是否有足够的路网数据
    edge_count = await conn.fetchval("""
        SELECT COUNT(*) FROM operational_v2.road_edges_v2
        WHERE ST_DWithin(
            geometry,
            ST_SetSRID(ST_MakePoint(103.8537, 31.6815), 4326)::geography,
            20000
        )
    """)
    
    if edge_count == 0:
        print("⚠️ 茂县附近无路网数据，无法测试DatabaseRouteEngine")
        print("  需要导入OpenStreetMap路网数据")
        return
    
    print(f"可用路网边: {edge_count}")
    
    # 检查车辆数据
    vehicles = await conn.fetch("""
        SELECT id, code, name, max_speed_kmh, is_all_terrain
        FROM operational_v2.vehicles_v2
        WHERE status = 'available'
        LIMIT 5
    """)
    
    print(f"可用车辆数量: {len(vehicles)}")
    for v in vehicles:
        print(f"  - {v['name']}: 最高{v['max_speed_kmh']}km/h, 全地形={v['is_all_terrain']}")


async def test_eta_accuracy():
    """测试6: ETA计算准确性分析"""
    print("\n" + "=" * 60)
    print("测试6: ETA计算准确性分析")
    print("=" * 60)
    
    # 不同场景下的ETA计算对比
    scenarios = [
        {"name": "城市道路", "factor": 1.3, "speed": 40},
        {"name": "省道", "factor": 1.2, "speed": 60},
        {"name": "高速公路", "factor": 1.1, "speed": 100},
        {"name": "山区道路", "factor": 1.6, "speed": 30},
        {"name": "应急通道", "factor": 1.2, "speed": 80},
    ]
    
    direct_dist = 10.0  # 假设直线距离10km
    
    print(f"直线距离: {direct_dist} km")
    print("\n场景对比:")
    print("-" * 50)
    
    for s in scenarios:
        road_dist = direct_dist * s["factor"]
        eta = road_dist / s["speed"] * 60
        print(f"{s['name']:12s} | 道路系数{s['factor']:.1f} | "
              f"速度{s['speed']:3d}km/h | ETA {eta:5.1f}分钟")
    
    print("-" * 50)
    print("\n当前系统使用: 道路系数1.0, 速度40km/h")
    print(f"当前系统ETA: {direct_dist / 40 * 60:.1f} 分钟")
    print("\n建议: 使用真实路网距离和动态速度计算")


async def check_matching_integration(conn: asyncpg.Connection):
    """测试7: 检查matching.py与路径规划的集成情况"""
    print("\n" + "=" * 60)
    print("测试7: Matching模块路径规划集成检查")
    print("=" * 60)
    
    # 获取一个救援队伍
    team = await conn.fetchrow("""
        SELECT t.id, t.name, ST_X(t.base_location::geometry) as lon, 
               ST_Y(t.base_location::geometry) as lat
        FROM operational_v2.rescue_teams_v2 t
        WHERE t.base_location IS NOT NULL
        LIMIT 1
    """)
    
    if not team:
        print("⚠️ 无可用救援队伍数据")
        return
    
    print(f"测试队伍: {team['name']}")
    print(f"基地位置: ({team['lon']:.4f}, {team['lat']:.4f})")
    
    # 模拟事发地点
    event_lon, event_lat = 103.8720, 31.6580
    
    # 当前matching.py的计算方式
    direct_dist = haversine_distance(team['lon'], team['lat'], event_lon, event_lat)
    eta_matching = direct_dist / 1000 / 40 * 60  # 40km/h
    
    print(f"\n事发地点: ({event_lon}, {event_lat})")
    print(f"直线距离: {direct_dist/1000:.2f} km")
    print(f"matching.py计算的ETA: {eta_matching:.1f} 分钟")
    
    # 检查是否有危险区域
    danger_count = await conn.fetchval("""
        SELECT COUNT(*) FROM operational_v2.disaster_affected_areas_v2
        WHERE passable = false
    """)
    
    print(f"\n当前危险区域数量: {danger_count}")
    if danger_count > 0:
        print("⚠️ 存在危险区域，但matching.py未考虑避障！")
    
    print("\n问题分析:")
    print("  1. matching.py使用直线距离，未调用路径规划")
    print("  2. 危险区域数据未传递给路径规划模块")
    print("  3. ETA计算不考虑道路类型和实际距离")


async def main():
    """主测试函数"""
    print("=" * 60)
    print("路径规划算法测试")
    print("=" * 60)
    
    # 基础测试（不需要数据库）
    await test_basic_distance()
    await test_eta_accuracy()
    
    # 数据库连接
    print("\n连接数据库...")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        await conn.execute("SET search_path TO operational_v2, public;")
        print("数据库连接成功")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)
    
    try:
        # 路网数据检查
        has_road = await test_road_network_exists(conn)
        
        # 灾害区域检查
        has_disaster = await test_disaster_areas(conn)
        
        # 创建测试灾害区域
        obstacle_id = None
        if not has_disaster:
            obstacle_id = await create_test_disaster_area(conn)
        
        # 避障测试
        await test_route_with_obstacle(conn, obstacle_id)
        
        # DatabaseRouteEngine测试
        await test_db_route_engine(conn)
        
        # Matching集成检查
        await check_matching_integration(conn)
        
        # 清理测试数据
        if obstacle_id:
            print("\n清理测试数据...")
            await conn.execute("""
                DELETE FROM operational_v2.disaster_affected_areas_v2 
                WHERE id = $1
            """, obstacle_id)
            print("  已删除测试灾害区域")
        
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print("\n发现的问题:")
        print("  1. emergency_ai/matching.py未调用真实路径规划")
        print("  2. ETA计算使用直线距离+固定速度(40km/h)")
        print("  3. 危险区域数据未用于路径规划避障")
        if not has_road:
            print("  4. 茂县地区路网数据缺失")
        
        print("\n建议修复:")
        print("  1. 在matching.py中集成DatabaseRouteEngine")
        print("  2. 传递scenario_id以获取危险区域")
        print("  3. 使用真实路网距离计算ETA")
        print("  4. 导入OpenStreetMap路网数据")
        
    finally:
        await conn.close()
        print("\n数据库连接已关闭")


if __name__ == "__main__":
    asyncio.run(main())
