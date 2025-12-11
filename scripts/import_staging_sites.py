"""
导入驻扎点数据到数据库

使用方法:
    python scripts/import_staging_sites.py --sql scripts/staging_sites_data.sql
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def import_sql(sql_file: str) -> None:
    """导入SQL文件到数据库"""
    from sqlalchemy import text
    from src.core.database import engine as async_engine

    # 读取SQL文件
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # 分割SQL语句
    statements = []
    current_stmt = []
    in_values = False

    for line in sql_content.split("\n"):
        stripped = line.strip()

        # 跳过注释和空行
        if stripped.startswith("--") or not stripped:
            continue

        # 跳过BEGIN/COMMIT（我们用自己的事务管理）
        if stripped.upper() in ("BEGIN;", "COMMIT;"):
            continue

        current_stmt.append(line)

        # 检测语句结束
        if stripped.endswith(";"):
            stmt = "\n".join(current_stmt)
            if stmt.strip():
                statements.append(stmt)
            current_stmt = []

    logger.info(f"[导入] 解析到 {len(statements)} 条SQL语句")

    # 执行SQL
    async with async_engine.begin() as conn:
        success_count = 0
        error_count = 0

        for i, stmt in enumerate(statements):
            try:
                await conn.execute(text(stmt))
                success_count += 1
                if (i + 1) % 50 == 0:
                    logger.info(f"[导入] 已执行 {i + 1}/{len(statements)} 条语句")
            except Exception as e:
                error_count += 1
                # 只显示前几个错误
                if error_count <= 3:
                    logger.error(f"[导入] 执行失败: {str(e)[:100]}")
                    logger.debug(f"SQL: {stmt[:200]}...")

        logger.info(f"[导入] 完成: 成功 {success_count} 条, 失败 {error_count} 条")

    # 验证结果
    async with async_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE site_code LIKE 'POI-%') as poi_count,
                   COUNT(*) FILTER (WHERE site_code LIKE 'SS-%') as manual_count
            FROM operational_v2.rescue_staging_sites_v2
        """))
        row = result.fetchone()
        logger.info(f"[验证] 数据库记录: 总计 {row[0]} 条, POI数据 {row[1]} 条, 手动数据 {row[2]} 条")

        # 按类型统计
        result = await conn.execute(text("""
            SELECT site_type, COUNT(*) as count
            FROM operational_v2.rescue_staging_sites_v2
            GROUP BY site_type
            ORDER BY count DESC
        """))
        logger.info("[验证] 按类型分布:")
        for row in result.fetchall():
            logger.info(f"  - {row[0]}: {row[1]} 条")


async def main():
    parser = argparse.ArgumentParser(description="导入驻扎点数据")
    parser.add_argument(
        "--sql",
        default="scripts/staging_sites_data.sql",
        help="SQL文件路径"
    )
    args = parser.parse_args()

    if not Path(args.sql).exists():
        logger.error(f"SQL文件不存在: {args.sql}")
        return

    await import_sql(args.sql)


if __name__ == "__main__":
    asyncio.run(main())
