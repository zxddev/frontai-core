"""Neo4j 只读客户端，用于规则/知识查询。"""
from __future__ import annotations

import logging  # 日志
from typing import Any, Iterable, List, Mapping  # 类型提示

from neo4j import GraphDatabase, Driver  # Neo4j 驱动

from infra.settings import Settings  # 配置

logger = logging.getLogger(__name__)  # 日志器


class Neo4jClient:
    """封装只读查询，连接失败直接抛错。"""

    def __init__(self, settings: Settings) -> None:
        self._driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,  # Neo4j 地址
            auth=(settings.neo4j_user, settings.neo4j_password),  # 认证信息
        )
        logger.info("Neo4j 连接已初始化", extra={"uri": settings.neo4j_uri})  # 记录连接信息

    def read(self, cypher: str, parameters: Mapping[str, Any] | None = None) -> List[Mapping[str, Any]]:
        """执行只读查询，返回字典列表。"""
        logger.info("执行 Neo4j 查询", extra={"cypher": cypher})  # 记录查询语句
        with self._driver.session(default_access_mode="READ") as session:  # 打开只读会话
            records = session.run(cypher, parameters or {})  # 执行查询
            rows: List[Mapping[str, Any]] = [dict(r.data()) for r in records]  # 转成字典
        if not rows:
            raise RuntimeError("Neo4j 查询结果为空")  # 空结果直接抛错
        return rows  # 返回结果

    def close(self) -> None:
        """关闭连接。"""
        self._driver.close()  # 关闭驱动
