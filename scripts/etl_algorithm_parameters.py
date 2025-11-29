#!/usr/bin/env python3
"""
ETL脚本：导入算法参数配置数据

执行v19迁移脚本，将所有算法参数配置到数据库：
- config.algorithm_parameters 表结构
- Sphere人道主义标准 (25条)
- 伤亡估算模型参数
- 道路/地形参数
- 灾情等级阈值

执行方式:
    python scripts/etl_algorithm_parameters.py
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


async def execute_sql_file(conn: asyncpg.Connection, sql_file: Path) -> bool:
    """执行单个SQL文件"""
    print(f"\n正在执行: {sql_file.name}")
    print("-" * 50)
    
    sql_content = sql_file.read_text(encoding="utf-8")
    
    # 分割SQL语句（按分号+换行分割，保留DO块和函数定义完整）
    statements = []
    current_stmt = []
    in_block = False
    block_depth = 0
    
    for line in sql_content.split("\n"):
        stripped = line.strip()
        
        # 跳过纯注释行（不在块内）
        if stripped.startswith("--") and not in_block:
            continue
        
        # 跳过 \i 引用指令（我们会单独处理子文件）
        if stripped.startswith("\\i "):
            continue
            
        # 检测块开始（DO块、函数定义等）
        if "$$" in stripped:
            dollar_count = stripped.count("$$")
            if dollar_count % 2 == 1:  # 奇数个$$表示进入/退出块
                in_block = not in_block
        
        # CREATE FUNCTION / CREATE OR REPLACE FUNCTION 块
        upper_stripped = stripped.upper()
        if "CREATE " in upper_stripped and "FUNCTION" in upper_stripped:
            in_block = True
        
        current_stmt.append(line)
        
        # 检测语句结束
        if not in_block and stripped.endswith(";"):
            stmt = "\n".join(current_stmt).strip()
            if stmt and not stmt.startswith("--"):
                statements.append(stmt)
            current_stmt = []
        elif in_block and stripped.endswith("$$;"):
            in_block = False
            statements.append("\n".join(current_stmt))
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
            # 打印错误信息
            stmt_preview = stmt[:80].replace("\n", " ")
            print(f"  [错误] 语句{i}: {stmt_preview}...")
            print(f"         {type(e).__name__}: {str(e)[:200]}")
    
    print(f"  执行完成: 成功{success_count}条, 失败{error_count}条")
    return error_count == 0


async def verify_data(conn: asyncpg.Connection) -> None:
    """验证导入的数据"""
    print("\n" + "=" * 60)
    print("数据验证")
    print("=" * 60)
    
    # 检查表是否存在
    table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'config' 
            AND table_name = 'algorithm_parameters'
        )
    """)
    
    if not table_exists:
        print("  [错误] config.algorithm_parameters 表不存在!")
        return
    
    print("  [OK] config.algorithm_parameters 表已创建")
    
    # 按类别统计
    stats = await conn.fetch("""
        SELECT category, COUNT(*) as cnt
        FROM config.algorithm_parameters
        WHERE is_active = TRUE
        GROUP BY category
        ORDER BY category
    """)
    
    print("\n按类别统计:")
    total = 0
    for row in stats:
        print(f"  - {row['category']}: {row['cnt']} 条")
        total += row['cnt']
    print(f"  ────────────────")
    print(f"  总计: {total} 条")
    
    # 检查关键配置是否存在
    print("\n关键配置检查:")
    
    key_configs = [
        ("sphere", "SPHERE-WASH-001", "生存用水标准"),
        ("sphere", "SPHERE-FOOD-001", "食物热量标准"),
        ("sphere", "SPHERE-SHELTER-002", "帐篷配置标准"),
        ("casualty", "CASUALTY-BUILDING-C", "砖混结构脆弱性"),
        ("routing", "ROAD-SPEED-MOTORWAY", "高速公路速度"),
        ("assessment", "DISASTER-LEVEL-EARTHQUAKE-I", "地震I级阈值"),
    ]
    
    for category, code, name in key_configs:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM config.algorithm_parameters
                WHERE category = $1 AND code = $2 AND is_active = TRUE
            )
        """, category, code)
        
        status = "[OK]" if exists else "[缺失]"
        print(f"  {status} {code}: {name}")


async def main() -> None:
    """主函数"""
    print("=" * 60)
    print("v19 算法参数配置 ETL")
    print("=" * 60)
    
    # 连接数据库
    print(f"\n连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("数据库连接成功")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)
    
    try:
        # 要执行的SQL文件列表（按顺序）
        sql_files = [
            "v19_algorithm_parameters_schema.sql",
            "v19_algorithm_parameters_sphere.sql",
            "v19_algorithm_parameters_casualty.sql",
            "v19_algorithm_parameters_routing.sql",
            "v19_algorithm_parameters_assessment.sql",
        ]
        
        all_success = True
        for sql_name in sql_files:
            sql_file = SQL_DIR / sql_name
            if sql_file.exists():
                success = await execute_sql_file(conn, sql_file)
                if not success:
                    all_success = False
            else:
                print(f"\n[警告] 文件不存在: {sql_file}")
                all_success = False
        
        # 验证数据
        await verify_data(conn)
        
        # 最终结果
        print("\n" + "=" * 60)
        if all_success:
            print("ETL 完成 - 所有迁移成功执行")
        else:
            print("ETL 完成 - 部分迁移存在错误，请检查日志")
        print("=" * 60)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
