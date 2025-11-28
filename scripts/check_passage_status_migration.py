#!/usr/bin/env python3
"""
检查 passage_status 字段迁移状态

用法: python scripts/check_passage_status_migration.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncpg


async def check_migration():
    """检查 disaster_affected_areas_v2 表是否已添加 passage_status 字段"""
    dsn = "postgresql://postgres:postgres123@192.168.31.40:5432/emergency_agent"
    
    try:
        conn = await asyncpg.connect(dsn)
        print("=" * 60)
        print("数据库连接成功")
        print("=" * 60)
        
        # 检查表是否存在
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'operational_v2' 
                AND table_name = 'disaster_affected_areas_v2'
            )
        """)
        
        if not table_exists:
            print("[ERROR] 表 operational_v2.disaster_affected_areas_v2 不存在!")
            return False
        
        print("[OK] 表 operational_v2.disaster_affected_areas_v2 存在")
        
        # 检查 passage_status 字段
        columns = await conn.fetch("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'operational_v2'
            AND table_name = 'disaster_affected_areas_v2'
            AND column_name IN ('passage_status', 'reconnaissance_required', 'last_verified_at', 'verified_by')
            ORDER BY column_name
        """)
        
        expected_columns = {
            'passage_status': 'character varying',
            'reconnaissance_required': 'boolean',
            'last_verified_at': 'timestamp with time zone',
            'verified_by': 'uuid',
        }
        
        found_columns = {row['column_name']: row['data_type'] for row in columns}
        
        print("\n字段检查结果:")
        print("-" * 60)
        
        all_ok = True
        for col_name, expected_type in expected_columns.items():
            if col_name in found_columns:
                print(f"[OK] {col_name}: {found_columns[col_name]}")
            else:
                print(f"[MISSING] {col_name}: 字段不存在，需要执行迁移")
                all_ok = False
        
        # 检查约束
        constraint_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.constraint_column_usage
                WHERE table_schema = 'operational_v2'
                AND table_name = 'disaster_affected_areas_v2'
                AND constraint_name = 'disaster_affected_areas_v2_passage_status_check'
            )
        """)
        
        print("\n约束检查:")
        print("-" * 60)
        if constraint_exists:
            print("[OK] passage_status CHECK 约束已存在")
        else:
            print("[MISSING] passage_status CHECK 约束不存在")
            all_ok = False
        
        # 检查索引
        indexes = await conn.fetch("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'operational_v2'
            AND tablename = 'disaster_affected_areas_v2'
            AND indexname LIKE '%passage_status%' OR indexname LIKE '%recon%'
        """)
        
        print("\n索引检查:")
        print("-" * 60)
        if indexes:
            for idx in indexes:
                print(f"[OK] 索引存在: {idx['indexname']}")
        else:
            print("[INFO] passage_status 相关索引未创建（可选）")
        
        # 统计现有数据的 passage_status 分布
        if all_ok:
            stats = await conn.fetch("""
                SELECT passage_status, COUNT(*) as cnt
                FROM operational_v2.disaster_affected_areas_v2
                GROUP BY passage_status
                ORDER BY cnt DESC
            """)
            
            print("\n数据分布统计:")
            print("-" * 60)
            if stats:
                for row in stats:
                    print(f"  {row['passage_status'] or 'NULL'}: {row['cnt']} 条记录")
            else:
                print("  表中暂无数据")
        
        print("\n" + "=" * 60)
        if all_ok:
            print("迁移状态: 已完成 ✓")
        else:
            print("迁移状态: 未完成 ✗")
            print("\n请执行以下命令完成迁移:")
            print("  psql -h 192.168.31.40 -U postgres -d emergency_agent -f sql/v15_passage_status_extension.sql")
        print("=" * 60)
        
        await conn.close()
        return all_ok
        
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(check_migration())
    sys.exit(0 if result else 1)
