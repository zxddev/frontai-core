#!/usr/bin/env python3
"""
ETL脚本：创建队伍资源关联表
执行sql/v19_team_resource_association.sql到数据库

业务说明:
    当指挥员下达出发指令后，车辆通过 mobilize 接口转换为救援队伍。
    本脚本创建的关联表用于记录救援队伍携带的设备、物资、模块。
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
SQL_FILE = Path(__file__).parent.parent / "sql" / "v19_team_resource_association.sql"


async def execute_sql_file(conn: asyncpg.Connection, sql_file: Path) -> None:
    """执行单个SQL文件"""
    print(f"正在执行: {sql_file.name}")
    
    sql_content = sql_file.read_text(encoding="utf-8")
    
    # 分割SQL语句
    statements = []
    current_stmt = []
    in_do_block = False
    
    for line in sql_content.split("\n"):
        stripped = line.strip()
        
        # 跳过纯注释行（但保留DO块内的注释）
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
            # 打印成功的关键语句
            if "CREATE TABLE" in stmt.upper():
                table_name = stmt.split("(")[0].split()[-1]
                print(f"  [成功] 创建表: {table_name}")
            elif "CREATE INDEX" in stmt.upper():
                pass  # 索引不打印
            elif "CREATE OR REPLACE VIEW" in stmt.upper():
                view_name = stmt.split(" AS")[0].split()[-1]
                print(f"  [成功] 创建视图: {view_name}")
            elif "COMMENT ON TABLE" in stmt.upper():
                pass  # 注释不打印
        except Exception as e:
            error_count += 1
            stmt_preview = stmt[:80].replace("\n", " ")
            print(f"  [错误] 语句{i}: {stmt_preview}...")
            print(f"         {type(e).__name__}: {str(e)[:200]}")
    
    print(f"\n执行完成: 成功{success_count}条, 失败{error_count}条")


async def main() -> None:
    """主函数"""
    print("=" * 60)
    print("队伍资源关联表ETL")
    print("=" * 60)
    
    # 检查SQL文件
    if not SQL_FILE.exists():
        print(f"[错误] SQL文件不存在: {SQL_FILE}")
        sys.exit(1)
    
    # 连接数据库
    print(f"\n连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("数据库连接成功\n")
    except Exception as e:
        print(f"[错误] 数据库连接失败: {e}")
        sys.exit(1)
    
    try:
        # 执行SQL
        await execute_sql_file(conn, SQL_FILE)
        
        # 验证表创建
        print("\n" + "=" * 60)
        print("验证表结构")
        print("=" * 60)
        
        tables = [
            "operational_v2.team_devices_v2",
            "operational_v2.team_supplies_v2", 
            "operational_v2.team_modules_v2",
        ]
        
        for table in tables:
            result = await conn.fetchval(f"""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema || '.' || table_name = '{table}'
            """)
            status = "✓ 存在" if result > 0 else "✗ 不存在"
            print(f"  {table}: {status}")
        
        # 验证视图
        view_result = await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.views 
            WHERE table_schema = 'operational_v2' AND table_name = 'v_team_resources_summary'
        """)
        status = "✓ 存在" if view_result > 0 else "✗ 不存在"
        print(f"  operational_v2.v_team_resources_summary: {status}")
        
    finally:
        await conn.close()
        print("\n数据库连接已关闭")
    
    print("\n" + "=" * 60)
    print("ETL完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
