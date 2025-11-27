"""
驻扎点选址服务数据库初始化脚本

执行SQL创建表并插入测试数据
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from src.core.database import AsyncSessionLocal


async def execute_sql_file(sql_path: Path) -> None:
    """执行SQL文件"""
    print(f"执行SQL文件: {sql_path}")
    
    sql_content = sql_path.read_text(encoding="utf-8")
    
    # 使用正则表达式分割，处理 $$ 块
    import re
    
    # 先移除注释行
    lines = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        lines.append(line)
    
    clean_sql = '\n'.join(lines)
    
    # 分割语句，考虑 $$ 块
    statements = []
    current = []
    in_dollar = False
    
    for line in clean_sql.split('\n'):
        # 计算这行有多少个 $$
        dollar_count = line.count('$$')
        if dollar_count % 2 == 1:
            in_dollar = not in_dollar
        
        current.append(line)
        
        # 语句结束：以;结尾且不在$$块内
        if line.rstrip().endswith(';') and not in_dollar:
            stmt = '\n'.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
    
    # 处理最后一个语句
    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            statements.append(stmt)
    
    print(f"解析到 {len(statements)} 条SQL语句")
    
    async with AsyncSessionLocal() as db:
        for i, stmt in enumerate(statements, 1):
            if not stmt.strip():
                continue
            
            # 每个语句单独事务
            try:
                await db.execute(text(stmt))
                await db.commit()
                # 截断显示
                preview = stmt[:60].replace('\n', ' ')
                print(f"  [{i}/{len(statements)}] OK: {preview}...")
            except Exception as e:
                await db.rollback()
                err_str = str(e).lower()
                if 'already exists' in err_str or 'duplicate' in err_str:
                    print(f"  [{i}/{len(statements)}] 已存在，跳过")
                else:
                    preview = stmt[:40].replace('\n', ' ')
                    print(f"  [{i}/{len(statements)}] 错误 [{preview}...]: {e}")
    
    print("SQL执行完成")


async def insert_test_data() -> None:
    """插入测试数据"""
    print("\n插入测试数据...")
    
    test_data_sql = """
    -- 插入测试驻扎点数据（四川茂县地震场景）
    INSERT INTO operational_v2.rescue_staging_sites_v2 (
        id, site_code, name, site_type, 
        location, area_m2, slope_degree, ground_stability,
        has_water_supply, has_power_supply, can_helicopter_land,
        primary_network_type, signal_quality,
        nearest_supply_depot_m, nearest_medical_point_m,
        status
    ) VALUES 
    -- 叠溪镇广场
    (
        'a0000001-0001-0001-0001-000000000001',
        'SS-001', '叠溪镇中心广场', 'plaza',
        ST_SetSRID(ST_MakePoint(103.67, 31.45), 4326),
        8000, 3.5, 'good',
        true, true, true,
        '4g_lte', 'good',
        2500, 1800,
        'available'
    ),
    -- 松坪沟停车场
    (
        'a0000001-0001-0001-0001-000000000002',
        'SS-002', '松坪沟游客停车场', 'parking_lot',
        ST_SetSRID(ST_MakePoint(103.70, 31.50), 4326),
        12000, 2.0, 'excellent',
        true, true, false,
        '4g_lte', 'excellent',
        4500, 3200,
        'available'
    ),
    -- 凤仪镇学校操场
    (
        'a0000001-0001-0001-0001-000000000003',
        'SS-003', '凤仪镇小学操场', 'school_yard',
        ST_SetSRID(ST_MakePoint(103.82, 31.62), 4326),
        5500, 1.5, 'good',
        true, true, false,
        '4g_lte', 'good',
        1200, 800,
        'available'
    ),
    -- 茂县体育场
    (
        'a0000001-0001-0001-0001-000000000004',
        'SS-004', '茂县体育中心', 'sports_field',
        ST_SetSRID(ST_MakePoint(103.85, 31.70), 4326),
        25000, 0.5, 'excellent',
        true, true, true,
        '5g', 'excellent',
        800, 500,
        'available'
    ),
    -- 汶川方向中转站
    (
        'a0000001-0001-0001-0001-000000000005',
        'SS-005', '汶川物流中心', 'logistics_center',
        ST_SetSRID(ST_MakePoint(103.58, 31.48), 4326),
        35000, 2.5, 'excellent',
        true, true, true,
        '4g_lte', 'good',
        200, 5500,
        'available'
    ),
    -- 北川方向
    (
        'a0000001-0001-0001-0001-000000000006',
        'SS-006', '北川羌族广场', 'plaza',
        ST_SetSRID(ST_MakePoint(104.46, 31.83), 4326),
        15000, 1.0, 'good',
        true, true, true,
        '4g_lte', 'good',
        3000, 1500,
        'available'
    ),
    -- 绵阳方向
    (
        'a0000001-0001-0001-0001-000000000007',
        'SS-007', '绵阳应急物资储备库', 'logistics_center',
        ST_SetSRID(ST_MakePoint(104.73, 31.47), 4326),
        50000, 0.5, 'excellent',
        true, true, true,
        '5g', 'excellent',
        100, 2000,
        'available'
    ),
    -- 山区临时点
    (
        'a0000001-0001-0001-0001-000000000008',
        'SS-008', '黑虎乡空旷地', 'open_ground',
        ST_SetSRID(ST_MakePoint(103.75, 31.55), 4326),
        3000, 8.0, 'moderate',
        false, false, false,
        'satellite', 'fair',
        8000, 12000,
        'available'
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        location = EXCLUDED.location,
        status = EXCLUDED.status;
    """
    
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(test_data_sql))
            await db.commit()
            print("测试数据插入完成")
        except Exception as e:
            print(f"插入测试数据失败: {e}")
            await db.rollback()


async def verify_data() -> None:
    """验证数据"""
    print("\n验证数据...")
    
    async with AsyncSessionLocal() as db:
        # 检查表是否存在
        result = await db.execute(text("""
            SELECT COUNT(*) FROM operational_v2.rescue_staging_sites_v2
        """))
        count = result.scalar()
        print(f"驻扎点记录数: {count}")
        
        # 列出驻扎点
        result = await db.execute(text("""
            SELECT site_code, name, site_type,
                   ST_X(location::geometry) as lon,
                   ST_Y(location::geometry) as lat
            FROM operational_v2.rescue_staging_sites_v2
            ORDER BY site_code
            LIMIT 10
        """))
        
        print("\n驻扎点列表:")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]} ({row[2]}) @ ({row[3]:.4f}, {row[4]:.4f})")


async def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="驻扎点选址服务数据库初始化")
    parser.add_argument("--skip-sql", action="store_true", help="跳过SQL文件执行")
    parser.add_argument("--skip-data", action="store_true", help="跳过测试数据插入")
    args = parser.parse_args()
    
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "v8_rescue_staging_sites.sql"
    
    if not args.skip_sql:
        if sql_path.exists():
            await execute_sql_file(sql_path)
        else:
            print(f"SQL文件不存在: {sql_path}")
    
    if not args.skip_data:
        await insert_test_data()
    
    await verify_data()
    print("\n初始化完成!")


if __name__ == "__main__":
    asyncio.run(main())
