"""PostgreSQL 访问层，读取规则/任务等结构化数据。"""
from __future__ import annotations

import logging  # 日志
from typing import Any, List, Mapping, Sequence  # 类型提示

import psycopg  # psycopg 同步客户端
from psycopg import OperationalError, InterfaceError

from infra.settings import Settings  # 配置

logger = logging.getLogger(__name__)  # 日志器


class PostgresDao:
    """封装基础查询，连接失败直接抛错。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings  # 保存配置
        self._conn = None
        self._connect()

    def _connect(self) -> None:
        """建立新连接，启用 autocommit。"""
        logger.info("初始化 Postgres 连接", extra={"dsn": self._settings.postgres_dsn})
        self._conn = psycopg.connect(self._settings.postgres_dsn)
        self._conn.autocommit = True

    def _ensure_conn(self) -> None:
        """若连接关闭或 None，重新建立。"""
        if self._conn is None or getattr(self._conn, "closed", False):
            logger.warning("Postgres 连接已关闭，重新建立")
            self._connect()

    def _query(self, sql: str, params: tuple) -> tuple[list[str], list[tuple]]:
        """执行查询，若遇到连接断开则重连一次重试。"""
        self._ensure_conn()
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return columns, rows
        except (OperationalError, InterfaceError) as exc:
            logger.warning("Postgres 连接异常，重连后重试", exc_info=exc)
            self._connect()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return columns, rows

    def fetch_rules(self, scene_id: str) -> List[Mapping[str, Any]]:
        """按场景读取规则列表，若无数据则报错。"""
        sql = """
        SELECT r.id, r.name, r.category, r.priority, t.condition, a.action, a.action_type
        FROM planning.rules r
        LEFT JOIN planning.rule_triggers t ON t.rule_id = r.id
        LEFT JOIN planning.rule_actions a ON a.rule_id = r.id
        WHERE r.active = TRUE AND (r.scenes IS NULL OR %s = ANY(r.scenes))
        ORDER BY r.priority DESC;
        """  # 定义查询语句
        logger.info("查询规则", extra={"scene": scene_id})  # 记录查询
        columns, rows = self._query(sql, (scene_id,))
        if not rows:  # 无结果
            raise RuntimeError("规则查询为空")
        return [dict(zip(columns, row)) for row in rows]

    def fetch_tasks(self, scene_id: str) -> List[Mapping[str, Any]]:
        """按场景读取任务 ID 列表，需保证有数据。"""
        sql = """
        SELECT id, name, phase, required_capabilities FROM planning.tasks
        WHERE typical_scenes @> ARRAY[%s]::text[]
        ORDER BY id;
        """  # 定义查询
        logger.info("查询任务", extra={"scene": scene_id})  # 记录查询
        columns, rows = self._query(sql, (scene_id,))
        if not rows:
            raise RuntimeError("任务查询为空")
        return [dict(zip(columns, row)) for row in rows]

    def fetch_resources(self, scene_id: str) -> List[Mapping[str, Any]]:
        """获取可用资源列表。"""
        # 查询数据库中的资源
        sql = """
        SELECT id as resource_id, type, capabilities, location, properties 
        FROM planning.resources 
        WHERE status = 'ready';
        """
        logger.info("查询资源", extra={"scene": scene_id})
        columns, rows = self._query(sql, ())
        if not rows:
            logger.warning("场景 %s 未发现可用资源", scene_id)
            return []

        results = []
        for row in rows:
            res_dict = dict(zip(columns, row))
            props = res_dict.get("properties", {}) or {}
            res_dict["risk"] = props.get("risk", 0.0)
            results.append(res_dict)
        return results

    def close(self) -> None:
        """关闭连接。"""
        if self._conn:
            self._conn.close()  # 关闭连接
