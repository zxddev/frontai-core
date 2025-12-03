#!/usr/bin/env python3
"""
ETL脚本：导入战略层救援配置数据

执行战略层迁移脚本：
- PostgreSQL: config.safety_rules, config.transport_capacity, config.report_templates, config.rescue_module_equipment
- Neo4j: TaskDomain, DisasterPhase, RescueModule 节点及关系

执行方式:
    python scripts/etl_strategic_rescue.py
    python scripts/etl_strategic_rescue.py --pg-only   # 仅执行PostgreSQL
    python scripts/etl_strategic_rescue.py --neo4j-only # 仅执行Neo4j
"""
import asyncio
import sys
from pathlib import Path

import asyncpg
from neo4j import AsyncGraphDatabase

# 数据库连接配置
PG_CONFIG = {
    "host": "192.168.31.40",
    "port": 5432,
    "user": "postgres",
    "password": "postgres123",
    "database": "emergency_agent",
}

NEO4J_CONFIG = {
    "uri": "bolt://192.168.31.50:7687",
    "user": "neo4j",
    "password": "neo4jzmkj123456",
}

# SQL文件路径
SQL_DIR = Path(__file__).parent.parent / "sql"


async def execute_pg_sql(conn: asyncpg.Connection, sql_file: Path) -> bool:
    """执行PostgreSQL SQL文件"""
    print(f"\n【PostgreSQL】正在执行: {sql_file.name}")
    print("-" * 60)
    
    sql_content = sql_file.read_text(encoding="utf-8")
    
    # 分割SQL语句
    statements = []
    current_stmt = []
    in_block = False
    
    for line in sql_content.split("\n"):
        stripped = line.strip()
        
        # 跳过纯注释行（不在块内）
        if stripped.startswith("--") and not in_block:
            continue
        
        # 检测块开始/结束
        if "$$" in stripped:
            dollar_count = stripped.count("$$")
            if dollar_count % 2 == 1:
                in_block = not in_block
        
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
    
    # 执行每条语句
    success_count = 0
    error_count = 0
    
    for i, stmt in enumerate(statements, 1):
        # 提取语句类型用于日志
        first_word = stmt.split()[0].upper() if stmt.split() else "UNKNOWN"
        
        try:
            await conn.execute(stmt)
            success_count += 1
            
            # 只打印关键语句
            if first_word in ("CREATE", "INSERT", "UPDATE", "DELETE"):
                # 获取表名
                if "TABLE" in stmt.upper():
                    table_match = stmt.upper().split("TABLE")[1].strip().split()[0]
                    print(f"  [{i}/{len(statements)}] {first_word} TABLE {table_match} ✓")
                elif "INTO" in stmt.upper():
                    table_match = stmt.upper().split("INTO")[1].strip().split()[0]
                    print(f"  [{i}/{len(statements)}] {first_word} INTO {table_match} ✓")
                else:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✓")
                    
        except Exception as e:
            error_count += 1
            error_msg = str(e)
            # 忽略"已存在"类错误
            if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                print(f"  [{i}/{len(statements)}] {first_word} ... (已存在，跳过)")
            else:
                print(f"  [{i}/{len(statements)}] {first_word} ... ✗ 错误: {error_msg[:100]}")
    
    print(f"\n【PostgreSQL】执行完成: 成功 {success_count}, 跳过/错误 {error_count}")
    return error_count == 0


async def execute_neo4j_cypher(driver, cypher_file: Path) -> bool:
    """执行Neo4j Cypher文件"""
    print(f"\n【Neo4j】正在执行: {cypher_file.name}")
    print("-" * 60)
    
    cypher_content = cypher_file.read_text(encoding="utf-8")
    
    # 分割Cypher语句（按分号分割，但要处理多行语句）
    statements = []
    current_stmt = []
    
    for line in cypher_content.split("\n"):
        stripped = line.strip()
        
        # 跳过注释行
        if stripped.startswith("//"):
            continue
        
        # 跳过空行
        if not stripped:
            if current_stmt:
                current_stmt.append("")
            continue
        
        current_stmt.append(line)
        
        # 检测语句结束
        if stripped.endswith(";"):
            stmt = "\n".join(current_stmt).strip()
            if stmt and not stmt.startswith("//"):
                # 移除末尾分号
                stmt = stmt.rstrip(";").strip()
                if stmt:
                    statements.append(stmt)
            current_stmt = []
    
    # 如果还有剩余语句
    if current_stmt:
        stmt = "\n".join(current_stmt).strip().rstrip(";").strip()
        if stmt:
            statements.append(stmt)
    
    # 执行每条语句
    success_count = 0
    error_count = 0
    
    async with driver.session() as session:
        for i, stmt in enumerate(statements, 1):
            # 提取语句类型
            first_word = stmt.split()[0].upper() if stmt.split() else "UNKNOWN"
            
            try:
                result = await session.run(stmt)
                summary = await result.consume()
                success_count += 1
                
                # 打印执行结果
                counters = summary.counters
                if counters.nodes_created > 0:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✓ (创建 {counters.nodes_created} 个节点)")
                elif counters.relationships_created > 0:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✓ (创建 {counters.relationships_created} 个关系)")
                elif counters.properties_set > 0:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✓ (设置 {counters.properties_set} 个属性)")
                elif counters.indexes_added > 0:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✓ (创建索引)")
                else:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✓")
                    
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                # 忽略"已存在"类错误
                if "already exists" in error_msg.lower() or "equivalent" in error_msg.lower():
                    print(f"  [{i}/{len(statements)}] {first_word} ... (已存在，跳过)")
                else:
                    print(f"  [{i}/{len(statements)}] {first_word} ... ✗ 错误: {error_msg[:100]}")
    
    print(f"\n【Neo4j】执行完成: 成功 {success_count}, 跳过/错误 {error_count}")
    return error_count == 0


async def run_pg_migration():
    """执行PostgreSQL迁移"""
    print("\n" + "=" * 60)
    print("PostgreSQL 战略层配置迁移")
    print("=" * 60)
    
    sql_file = SQL_DIR / "v31_strategic_tables.sql"
    
    if not sql_file.exists():
        print(f"错误: SQL文件不存在 - {sql_file}")
        return False
    
    try:
        conn = await asyncpg.connect(**PG_CONFIG)
        print(f"已连接到 PostgreSQL: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")
        
        result = await execute_pg_sql(conn, sql_file)
        
        await conn.close()
        return result
        
    except Exception as e:
        print(f"PostgreSQL连接失败: {e}")
        return False


async def run_neo4j_migration():
    """执行Neo4j迁移"""
    print("\n" + "=" * 60)
    print("Neo4j 战略层知识图谱迁移")
    print("=" * 60)
    
    cypher_file = SQL_DIR / "v30_strategic_kg.cypher"
    
    if not cypher_file.exists():
        print(f"错误: Cypher文件不存在 - {cypher_file}")
        return False
    
    try:
        driver = AsyncGraphDatabase.driver(
            NEO4J_CONFIG["uri"],
            auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"])
        )
        print(f"已连接到 Neo4j: {NEO4J_CONFIG['uri']}")
        
        result = await execute_neo4j_cypher(driver, cypher_file)
        
        await driver.close()
        return result
        
    except Exception as e:
        print(f"Neo4j连接失败: {e}")
        return False


async def main():
    """主函数"""
    print("\n" + "#" * 60)
    print("# 战略层救援配置数据导入 (ETL)")
    print("#" * 60)
    
    # 解析命令行参数
    pg_only = "--pg-only" in sys.argv
    neo4j_only = "--neo4j-only" in sys.argv
    
    results = []
    
    if not neo4j_only:
        pg_result = await run_pg_migration()
        results.append(("PostgreSQL", pg_result))
    
    if not pg_only:
        neo4j_result = await run_neo4j_migration()
        results.append(("Neo4j", neo4j_result))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("执行总结")
    print("=" * 60)
    
    all_success = True
    for name, success in results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"  {name}: {status}")
        if not success:
            all_success = False
    
    if all_success:
        print("\n✓ 所有迁移执行成功！")
        print("\n下一步:")
        print("  1. 重启服务: ./scripts/restart.sh")
        print("  2. 测试接口: python scripts/test_emergency_analyze.py")
    else:
        print("\n✗ 部分迁移失败，请检查错误信息")
    
    return 0 if all_success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
