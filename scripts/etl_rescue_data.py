#!/usr/bin/env python3
"""
ETL脚本：导入完整救援资源数据
执行sql/v4_complete_rescue_data.sql到数据库
"""
import asyncio
import sys
from pathlib import Path

import asyncpg

# 数据库连接配置
DB_CONFIG = {
    "host": "192.168.31.40",
    "port": 5432,
    "user": "postgres",
    "password": "postgres123",
    "database": "emergency_agent",
}

# SQL文件路径
SQL_DIR = Path(__file__).parent.parent / "sql"


async def execute_sql_file(conn: asyncpg.Connection, sql_file: Path) -> None:
    """执行单个SQL文件"""
    print(f"正在执行: {sql_file.name}")
    
    sql_content = sql_file.read_text(encoding="utf-8")
    
    # 分割SQL语句（按分号+换行分割，保留DO块完整）
    statements = []
    current_stmt = []
    in_do_block = False
    
    for line in sql_content.split("\n"):
        stripped = line.strip()
        
        # 跳过注释行
        if stripped.startswith("--") and not in_do_block:
            continue
            
        # 检测DO块开始
        if stripped.upper().startswith("DO $$") or stripped.upper().startswith("DO $"):
            in_do_block = True
            
        current_stmt.append(line)
        
        # 检测DO块结束
        if in_do_block and stripped.endswith("$$;"):
            in_do_block = False
            statements.append("\n".join(current_stmt))
            current_stmt = []
        # 普通语句结束
        elif not in_do_block and stripped.endswith(";"):
            stmt = "\n".join(current_stmt).strip()
            if stmt and not stmt.startswith("--"):
                statements.append(stmt)
            current_stmt = []
    
    # 处理剩余内容
    if current_stmt:
        stmt = "\n".join(current_stmt).strip()
        if stmt and not stmt.startswith("--"):
            statements.append(stmt)
    
    # 执行每条语句
    success_count = 0
    error_count = 0
    
    for i, stmt in enumerate(statements, 1):
        if not stmt.strip():
            continue
            
        try:
            await conn.execute(stmt)
            success_count += 1
        except Exception as e:
            error_count += 1
            # 只打印前100个字符的语句
            stmt_preview = stmt[:100].replace("\n", " ")
            print(f"  [错误] 语句{i}: {stmt_preview}...")
            print(f"         {type(e).__name__}: {str(e)[:200]}")
    
    print(f"  完成: 成功{success_count}条, 失败{error_count}条")


async def main() -> None:
    """主函数"""
    print("=" * 60)
    print("救援资源数据ETL")
    print("=" * 60)
    
    # 连接数据库
    print(f"\n连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("数据库连接成功\n")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)
    
    try:
        # 设置搜索路径
        await conn.execute("SET search_path TO operational_v2, public;")
        
        # 要执行的SQL文件列表
        sql_files = [
            "v4_complete_rescue_data.sql",
        ]
        
        for sql_name in sql_files:
            sql_file = SQL_DIR / sql_name
            if sql_file.exists():
                await execute_sql_file(conn, sql_file)
            else:
                print(f"文件不存在: {sql_file}")
        
        # 验证数据
        print("\n" + "=" * 60)
        print("数据验证")
        print("=" * 60)
        
        # 统计队伍
        teams = await conn.fetch("""
            SELECT team_type, COUNT(*) as cnt, SUM(total_personnel) as personnel
            FROM rescue_teams_v2
            GROUP BY team_type
            ORDER BY cnt DESC
        """)
        print("\n队伍统计:")
        for row in teams:
            print(f"  {row['team_type']}: {row['cnt']}支, 共{row['personnel']}人")
        
        # 统计能力
        caps = await conn.fetch("""
            SELECT capability_code, COUNT(DISTINCT team_id) as team_count
            FROM team_capabilities_v2
            GROUP BY capability_code
            ORDER BY team_count DESC
            LIMIT 15
        """)
        print("\n能力覆盖(TOP15):")
        for row in caps:
            print(f"  {row['capability_code']}: {row['team_count']}支队伍")
        
        # 统计装备
        equip = await conn.fetch("""
            SELECT category, COUNT(*) as cnt
            FROM equipment_v2
            GROUP BY category
            ORDER BY cnt DESC
        """)
        print("\n装备统计:")
        for row in equip:
            print(f"  {row['category']}: {row['cnt']}种")
        
        print("\n" + "=" * 60)
        print("ETL完成")
        print("=" * 60)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
