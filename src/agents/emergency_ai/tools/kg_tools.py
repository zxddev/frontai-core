"""
知识图谱工具封装

使用Neo4j查询TRR规则、能力映射、任务依赖等知识。
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)


# ============================================================================
# Neo4j客户端管理
# ============================================================================

_neo4j_driver: Optional[Driver] = None


def _get_neo4j_driver() -> Driver:
    """获取Neo4j驱动实例（单例）"""
    global _neo4j_driver
    if _neo4j_driver is None:
        neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://192.168.31.50:7687')
        neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
        neo4j_password = os.environ.get('NEO4J_PASSWORD', 'neo4jzmkj123456')
        _neo4j_driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password),
        )
        logger.info("Neo4j驱动初始化完成", extra={"uri": neo4j_uri})
    return _neo4j_driver


def close_neo4j_driver() -> None:
    """关闭Neo4j驱动"""
    global _neo4j_driver
    if _neo4j_driver is not None:
        _neo4j_driver.close()
        _neo4j_driver = None
        logger.info("Neo4j驱动已关闭")


# ============================================================================
# 工具函数定义
# ============================================================================

@tool
def query_trr_rules(
    disaster_type: str,
    conditions: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    查询TRR触发规则。
    
    从知识图谱中查询与灾害类型匹配的TRR规则，
    并根据条件返回触发的任务和能力需求。
    
    Args:
        disaster_type: 灾害类型 (earthquake/fire/hazmat/landslide等)
        conditions: 触发条件字典（用于更精确的规则匹配）
        
    Returns:
        匹配的TRR规则列表，每条规则包含：
        - rule_id: 规则ID
        - rule_name: 规则名称
        - priority: 优先级
        - weight: 权重
        - triggered_tasks: 触发的任务类型列表
        - required_capabilities: 需要的能力列表
    """
    logger.info(
        "调用KG查询TRR规则",
        extra={"disaster_type": disaster_type, "conditions": conditions}
    )
    
    driver = _get_neo4j_driver()
    
    # 查询规则及其关联的任务和能力
    cypher = """
    MATCH (r:TRRRule {disaster_type: $disaster_type, is_active: true})
    OPTIONAL MATCH (r)-[tr:TRIGGERS]->(t:TaskType)
    OPTIONAL MATCH (r)-[rc:REQUIRES_CAPABILITY]->(c:Capability)
    RETURN 
        r.rule_id AS rule_id,
        r.name AS rule_name,
        r.description AS description,
        r.priority AS priority,
        r.weight AS weight,
        r.trigger_conditions AS trigger_conditions,
        r.trigger_logic AS trigger_logic,
        collect(DISTINCT {
            task_code: t.code,
            task_name: t.name,
            sequence: tr.sequence,
            task_priority: tr.priority
        }) AS tasks,
        collect(DISTINCT {
            capability_code: c.code,
            capability_name: c.name,
            cap_priority: rc.priority
        }) AS capabilities
    ORDER BY r.weight DESC
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"disaster_type": disaster_type})
            records = list(result)
    except Exception as e:
        logger.error("Neo4j查询TRR规则失败", extra={"error": str(e)})
        # 如果查询失败，尝试使用本地YAML规则作为降级（但不静默）
        raise RuntimeError(f"知识图谱查询失败: {e}") from e
    
    # 格式化结果
    rules: List[Dict[str, Any]] = []
    for record in records:
        # 过滤空任务和空能力
        tasks = [t for t in record["tasks"] if t.get("task_code")]
        capabilities = [c for c in record["capabilities"] if c.get("capability_code")]
        
        rule = {
            "rule_id": record["rule_id"],
            "rule_name": record["rule_name"],
            "description": record["description"],
            "priority": record["priority"],
            "weight": record["weight"],
            "trigger_conditions": record["trigger_conditions"],
            "trigger_logic": record["trigger_logic"],
            "triggered_tasks": [
                {
                    "task_code": t["task_code"],
                    "task_name": t["task_name"],
                    "priority": t["task_priority"],
                    "sequence": t["sequence"],
                }
                for t in sorted(tasks, key=lambda x: x.get("sequence", 999))
            ],
            "required_capabilities": [
                {
                    "capability_code": c["capability_code"],
                    "capability_name": c["capability_name"],
                    "priority": c["cap_priority"],
                }
                for c in capabilities
            ],
        }
        rules.append(rule)
    
    logger.info("TRR规则查询完成", extra={"rules_count": len(rules)})
    return rules


@tool
def query_capability_mapping(
    capability_codes: List[str],
) -> List[Dict[str, Any]]:
    """
    查询能力-资源映射关系。
    
    根据能力编码查询能够提供该能力的资源类型。
    
    Args:
        capability_codes: 能力编码列表
        
    Returns:
        能力-资源映射列表，每个映射包含：
        - capability_code: 能力编码
        - capability_name: 能力名称
        - resource_types: 可提供该能力的资源类型列表
    """
    logger.info("调用KG查询能力映射", extra={"capabilities": capability_codes})
    
    driver = _get_neo4j_driver()
    
    cypher = """
    MATCH (c:Capability)-[:PROVIDED_BY]->(rt:ResourceType)
    WHERE c.code IN $capability_codes
    RETURN 
        c.code AS capability_code,
        c.name AS capability_name,
        c.description AS description,
        c.equipment_required AS equipment,
        collect({
            resource_code: rt.code,
            resource_name: rt.name,
            resource_category: rt.category
        }) AS resource_types
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"capability_codes": capability_codes})
            records = list(result)
    except Exception as e:
        logger.error("Neo4j查询能力映射失败", extra={"error": str(e)})
        raise RuntimeError(f"知识图谱查询失败: {e}") from e
    
    # 格式化结果
    mappings: List[Dict[str, Any]] = []
    for record in records:
        mapping = {
            "capability_code": record["capability_code"],
            "capability_name": record["capability_name"],
            "description": record["description"],
            "equipment_required": record["equipment"],
            "resource_types": record["resource_types"],
        }
        mappings.append(mapping)
    
    logger.info("能力映射查询完成", extra={"mappings_count": len(mappings)})
    return mappings


@tool
def query_task_dependencies(
    task_codes: List[str],
) -> List[Dict[str, Any]]:
    """
    查询任务依赖关系。
    
    获取任务之间的前置依赖关系，用于确定执行顺序。
    
    Args:
        task_codes: 任务编码列表
        
    Returns:
        任务依赖列表，每个包含：
        - task_code: 任务编码
        - depends_on: 依赖的任务列表
        - enables: 该任务使能的任务列表
    """
    logger.info("调用KG查询任务依赖", extra={"tasks": task_codes})
    
    driver = _get_neo4j_driver()
    
    cypher = """
    MATCH (t:TaskType)
    WHERE t.code IN $task_codes
    OPTIONAL MATCH (t)-[d:DEPENDS_ON]->(dep:TaskType)
    OPTIONAL MATCH (enabled:TaskType)-[:DEPENDS_ON]->(t)
    RETURN 
        t.code AS task_code,
        t.name AS task_name,
        t.golden_hour AS golden_hour,
        collect(DISTINCT {
            dep_code: dep.code,
            dep_name: dep.name,
            is_strict: d.is_strict,
            description: d.description
        }) AS depends_on,
        collect(DISTINCT enabled.code) AS enables
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"task_codes": task_codes})
            records = list(result)
    except Exception as e:
        logger.error("Neo4j查询任务依赖失败", extra={"error": str(e)})
        raise RuntimeError(f"知识图谱查询失败: {e}") from e
    
    # 格式化结果
    dependencies: List[Dict[str, Any]] = []
    for record in records:
        # 过滤空依赖
        deps = [d for d in record["depends_on"] if d.get("dep_code")]
        enables = [e for e in record["enables"] if e]
        
        dep = {
            "task_code": record["task_code"],
            "task_name": record["task_name"],
            "golden_hour": record["golden_hour"],
            "depends_on": deps,
            "enables": enables,
        }
        dependencies.append(dep)
    
    logger.info("任务依赖查询完成", extra={"dependencies_count": len(dependencies)})
    return dependencies


# ============================================================================
# 非工具版本（供节点直接调用）
# ============================================================================

async def query_trr_rules_async(
    disaster_type: str,
    conditions: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """异步版本的TRR规则查询"""
    # Neo4j Python驱动是同步的，直接调用
    return query_trr_rules.invoke({
        "disaster_type": disaster_type,
        "conditions": conditions,
    })


async def query_capability_mapping_async(
    capability_codes: List[str],
) -> List[Dict[str, Any]]:
    """异步版本的能力映射查询"""
    return query_capability_mapping.invoke({
        "capability_codes": capability_codes,
    })


async def query_task_dependencies_async(
    task_codes: List[str],
) -> List[Dict[str, Any]]:
    """异步版本的任务依赖查询"""
    return query_task_dependencies.invoke({
        "task_codes": task_codes,
    })
