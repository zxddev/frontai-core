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
    
    logger.info(f"【Neo4j-TRR规则】查询{disaster_type}类型，返回{len(rules)}条规则:")
    for rule in rules:
        logger.info(f"  - {rule['rule_id']}: {rule['rule_name']} (优先级={rule['priority']}, 权重={rule['weight']})")
        logger.info(f"    触发任务: {[t['task_code'] for t in rule['triggered_tasks']]}")
        logger.info(f"    需要能力: {[c['capability_code'] for c in rule['required_capabilities']]}")
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


# ============================================================================
# HTN分解专用查询函数（基于Scene/TaskChain/MetaTask节点）
# ============================================================================

@tool
def query_scene_by_disaster(
    disaster_type: str,
    conditions: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    根据灾情条件查询匹配的场景。
    
    从Neo4j的Scene节点中查询与灾情匹配的场景代码，
    基于Scene.triggers数组进行条件匹配。
    
    Args:
        disaster_type: 灾害类型 (earthquake/flood/fire/hazmat等)
        conditions: 灾情条件字典，包含:
            - has_secondary_fire: 是否有次生火灾
            - has_hazmat_leak: 是否有危化品泄漏
            - has_building_collapse: 是否有建筑倒塌
            
    Returns:
        匹配的场景列表，每个包含:
        - scene_code: 场景代码 (S1/S2/S3/S4/S5)
        - scene_name: 场景名称
        - description: 场景描述
        - priority_objectives: 优先目标列表
    """
    logger.info(
        "[KG] 查询场景",
        extra={"disaster_type": disaster_type, "conditions": conditions}
    )
    
    driver = _get_neo4j_driver()
    
    # 场景匹配逻辑：根据灾害类型和条件确定场景
    # S1: 地震主灾, S2: 次生火灾, S3: 危化品泄漏, S4: 山洪泥石流, S5: 暴雨内涝
    cypher = """
    MATCH (s:Scene)
    WHERE 
        // S1: 地震主灾
        (s.code = 'S1' AND $disaster_type IN ['earthquake', '地震'])
        // S2: 次生火灾或独立火灾
        OR (s.code = 'S2' AND ($has_secondary_fire = true OR $disaster_type IN ['fire', '火灾']))
        // S3: 危化品泄漏
        OR (s.code = 'S3' AND ($has_hazmat_leak = true OR $disaster_type IN ['hazmat', '危化品']))
        // S4: 山洪泥石流
        OR (s.code = 'S4' AND $disaster_type IN ['flood', 'landslide', 'debris_flow', '洪水', '泥石流', '滑坡'])
        // S5: 暴雨内涝
        OR (s.code = 'S5' AND $disaster_type IN ['waterlogging', '内涝', '暴雨'])
    RETURN 
        s.code AS scene_code,
        s.name AS scene_name,
        s.description AS description,
        s.priority_objectives AS priority_objectives,
        s.typical_tasks AS typical_tasks
    ORDER BY s.code
    """
    
    params = {
        "disaster_type": disaster_type.lower() if disaster_type else "earthquake",
        "has_secondary_fire": conditions.get("has_secondary_fire", False),
        "has_hazmat_leak": conditions.get("has_hazmat_leak", False),
    }
    
    try:
        with driver.session() as session:
            result = session.run(cypher, params)
            records = list(result)
    except Exception as e:
        logger.error("[KG] 场景查询失败", extra={"error": str(e)})
        raise RuntimeError(f"Neo4j场景查询失败: {e}") from e
    
    scenes: List[Dict[str, Any]] = []
    for record in records:
        scene = {
            "scene_code": record["scene_code"],
            "scene_name": record["scene_name"],
            "description": record["description"],
            "priority_objectives": record["priority_objectives"] or [],
            "typical_tasks": record["typical_tasks"] or [],
        }
        scenes.append(scene)
    
    logger.info(f"【Neo4j-场景识别】查询{disaster_type}类型，条件={conditions}，匹配{len(scenes)}个场景:")
    for scene in scenes:
        logger.info(f"  - {scene['scene_code']}: {scene['scene_name']}")
        logger.info(f"    典型任务: {scene.get('typical_tasks', [])}")
    return scenes


@tool
def query_task_chain(
    scene_code: str,
) -> Optional[Dict[str, Any]]:
    """
    根据场景代码查询任务链配置。
    
    从Neo4j查询Scene→ACTIVATES→TaskChain→INCLUDES→MetaTask链路，
    返回完整的任务链配置包括任务序列和依赖关系。
    
    Args:
        scene_code: 场景代码 (S1/S2/S3/S4/S5)
        
    Returns:
        任务链配置字典，包含:
        - chain_id: 任务链ID
        - chain_name: 任务链名称
        - description: 任务链描述
        - tasks: 任务列表（按sequence排序）
        - parallel_groups: 并行任务组（从MetaTask的typical_scenes推断）
    """
    logger.info("[KG] 查询任务链", extra={"scene_code": scene_code})
    
    driver = _get_neo4j_driver()
    
    cypher = """
    MATCH (s:Scene {code: $scene_code})-[:ACTIVATES]->(tc:TaskChain)
    MATCH (tc)-[inc:INCLUDES]->(m:MetaTask)
    WITH tc, m, inc.sequence AS seq
    ORDER BY seq
    WITH tc, collect({
        task_id: m.id,
        task_name: m.name,
        category: m.category,
        phase: m.phase,
        duration_min: m.duration_min,
        duration_max: m.duration_max,
        required_capabilities: m.required_capabilities,
        risk_level: m.risk_level,
        sequence: seq
    }) AS tasks
    RETURN 
        tc.id AS chain_id,
        tc.name AS chain_name,
        tc.description AS description,
        tc.task_sequence AS task_sequence,
        tasks
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"scene_code": scene_code})
            record = result.single()
    except Exception as e:
        logger.error("[KG] 任务链查询失败", extra={"error": str(e), "scene_code": scene_code})
        raise RuntimeError(f"Neo4j任务链查询失败: {e}") from e
    
    if record is None:
        logger.warning("[KG] 未找到场景对应的任务链", extra={"scene_code": scene_code})
        return None
    
    chain = {
        "chain_id": record["chain_id"],
        "chain_name": record["chain_name"],
        "description": record["description"],
        "task_sequence": record["task_sequence"] or [],
        "tasks": record["tasks"],
    }
    
    logger.info(f"【Neo4j-任务链】场景{scene_code}的任务链:")
    logger.info(f"  - 链ID: {chain['chain_id']}, 名称: {chain['chain_name']}")
    logger.info(f"  - 任务序列: {chain.get('task_sequence', [])}")
    logger.info(f"  - 包含{len(chain['tasks'])}个任务: {[t.get('task_id') for t in chain['tasks']]}")
    return chain


@tool
def query_metatask_dependencies(
    task_ids: List[str],
) -> Dict[str, List[str]]:
    """
    查询MetaTask之间的依赖关系。
    
    从Neo4j查询指定MetaTask节点之间的DEPENDS_ON关系，
    返回依赖关系字典用于拓扑排序。
    
    Args:
        task_ids: MetaTask的ID列表 (如 ["EM01", "EM06", "EM10"])
        
    Returns:
        依赖关系字典: {task_id: [depends_on_task_ids]}
        示例: {"EM10": ["EM11"], "EM11": ["EM06"], "EM06": ["EM03"]}
    """
    logger.info("[KG] 查询MetaTask依赖", extra={"task_ids": task_ids})
    
    driver = _get_neo4j_driver()
    
    cypher = """
    MATCH (m1:MetaTask)-[:DEPENDS_ON]->(m2:MetaTask)
    WHERE m1.id IN $task_ids AND m2.id IN $task_ids
    RETURN m1.id AS task_id, collect(DISTINCT m2.id) AS depends_on
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"task_ids": task_ids})
            records = list(result)
    except Exception as e:
        logger.error("[KG] MetaTask依赖查询失败", extra={"error": str(e)})
        raise RuntimeError(f"Neo4j MetaTask依赖查询失败: {e}") from e
    
    dependencies: Dict[str, List[str]] = {}
    for record in records:
        task_id = record["task_id"]
        deps = record["depends_on"]
        if deps:
            dependencies[task_id] = deps
    
    logger.info(f"【Neo4j-任务依赖】查询{len(task_ids)}个任务的依赖关系:")
    for task_id, deps in dependencies.items():
        logger.info(f"  - {task_id} 依赖于: {deps}")
    logger.info(f"  共{len(dependencies)}个任务有前置依赖")
    return dependencies


@tool
def query_metatask_details(
    task_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    查询MetaTask的详细信息。
    
    Args:
        task_ids: MetaTask的ID列表
        
    Returns:
        任务详情字典: {task_id: {name, category, phase, ...}}
    """
    logger.info("[KG] 查询MetaTask详情", extra={"task_ids": task_ids})
    
    driver = _get_neo4j_driver()
    
    cypher = """
    MATCH (m:MetaTask)
    WHERE m.id IN $task_ids
    RETURN 
        m.id AS task_id,
        m.name AS name,
        m.category AS category,
        m.phase AS phase,
        m.precondition AS precondition,
        m.effect AS effect,
        m.duration_min AS duration_min,
        m.duration_max AS duration_max,
        m.required_capabilities AS required_capabilities,
        m.risk_level AS risk_level,
        m.outputs AS outputs
    """
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"task_ids": task_ids})
            records = list(result)
    except Exception as e:
        logger.error("[KG] MetaTask详情查询失败", extra={"error": str(e)})
        raise RuntimeError(f"Neo4j MetaTask详情查询失败: {e}") from e
    
    details: Dict[str, Dict[str, Any]] = {}
    for record in records:
        task_id = record["task_id"]
        details[task_id] = {
            "name": record["name"],
            "category": record["category"],
            "phase": record["phase"],
            "precondition": record["precondition"],
            "effect": record["effect"],
            "duration_min": record["duration_min"],
            "duration_max": record["duration_max"],
            "required_capabilities": record["required_capabilities"] or [],
            "risk_level": record["risk_level"],
            "outputs": record["outputs"] or [],
        }
    
    logger.info(f"【Neo4j-MetaTask详情】查询完成，共{len(details)}个任务:")
    for task_id, detail in details.items():
        caps = detail.get("required_capabilities", [])
        logger.info(f"  - {task_id}: 名称={detail.get('name', '未知')}, 能力需求={caps}")
    return details


# ============================================================================
# HTN分解专用异步版本
# ============================================================================

async def query_scene_by_disaster_async(
    disaster_type: str,
    conditions: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """异步版本的场景查询"""
    return query_scene_by_disaster.invoke({
        "disaster_type": disaster_type,
        "conditions": conditions,
    })


async def query_task_chain_async(
    scene_code: str,
) -> Optional[Dict[str, Any]]:
    """异步版本的任务链查询"""
    return query_task_chain.invoke({
        "scene_code": scene_code,
    })


async def query_metatask_dependencies_async(
    task_ids: List[str],
) -> Dict[str, List[str]]:
    """异步版本的MetaTask依赖查询"""
    return query_metatask_dependencies.invoke({
        "task_ids": task_ids,
    })


async def query_metatask_details_async(
    task_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    """异步版本的MetaTask详情查询"""
    return query_metatask_details.invoke({
        "task_ids": task_ids,
    })


# ============================================================================
# 战略层查询函数
# ============================================================================

def query_rule_domains(rule_ids: List[str]) -> List[Dict[str, Any]]:
    """
    查询规则的任务域属性
    
    Args:
        rule_ids: 规则ID列表
        
    Returns:
        规则域信息列表
    """
    driver = _get_neo4j_driver()
    
    query = """
        MATCH (r:TRRRule)
        WHERE r.rule_id IN $rule_ids
        RETURN r.rule_id AS rule_id, r.domain AS domain
    """
    
    with driver.session() as session:
        result = session.run(query, {"rule_ids": rule_ids})
        return [dict(record) for record in result]


async def query_rule_domains_async(rule_ids: List[str]) -> List[Dict[str, Any]]:
    """异步版本的规则域查询"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_rule_domains, rule_ids)


def query_phase_priorities(phase_id: str) -> List[Dict[str, Any]]:
    """
    查询阶段的任务域优先级
    
    Args:
        phase_id: 阶段ID (initial/golden/intensive/recovery)
        
    Returns:
        优先级列表
    """
    driver = _get_neo4j_driver()
    
    query = """
        MATCH (p:DisasterPhase {phase_id: $phase_id})-[r:PRIORITY_ORDER]->(d:TaskDomain)
        RETURN d.domain_id AS domain_id, d.name AS name, d.description AS description, r.rank AS rank
        ORDER BY r.rank
    """
    
    with driver.session() as session:
        result = session.run(query, {"phase_id": phase_id})
        return [dict(record) for record in result]


def query_phase_info(phase_id: str) -> Optional[Dict[str, Any]]:
    """查询阶段信息"""
    driver = _get_neo4j_driver()
    
    query = """
        MATCH (p:DisasterPhase {phase_id: $phase_id})
        RETURN p.phase_id AS phase_id, p.name AS name, p.hours_start AS hours_start, p.hours_end AS hours_end
    """
    
    with driver.session() as session:
        result = session.run(query, {"phase_id": phase_id})
        record = result.single()
        return dict(record) if record else None


async def query_phase_priorities_async(phase_id: str) -> List[Dict[str, Any]]:
    """异步版本的阶段优先级查询"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_phase_priorities, phase_id)


async def query_phase_info_async(phase_id: str) -> Optional[Dict[str, Any]]:
    """异步版本的阶段信息查询"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_phase_info, phase_id)


def query_modules_by_capabilities(capability_codes: List[str]) -> List[Dict[str, Any]]:
    """
    根据能力需求查询推荐模块
    
    Args:
        capability_codes: 能力编码列表
        
    Returns:
        模块信息列表（按能力匹配度排序）
    """
    driver = _get_neo4j_driver()
    
    query = """
        MATCH (m:RescueModule)-[p:PROVIDES]->(c:Capability)
        WHERE c.code IN $capability_codes
        WITH m, COLLECT({
            capability_code: c.code,
            capability_name: c.name,
            level: p.level,
            quantity: p.quantity
        }) AS provided_caps, COUNT(DISTINCT c.code) AS match_count
        RETURN 
            m.module_id AS module_id,
            m.name AS module_name,
            m.personnel AS personnel,
            m.dogs AS dogs,
            m.vehicles AS vehicles,
            m.description AS description,
            provided_caps,
            match_count,
            toFloat(match_count) / toFloat($total_required) AS match_score
        ORDER BY match_score DESC, match_count DESC
    """
    
    with driver.session() as session:
        result = session.run(query, {
            "capability_codes": capability_codes,
            "total_required": len(capability_codes) if capability_codes else 1,
        })
        return [dict(record) for record in result]


async def query_modules_by_capabilities_async(capability_codes: List[str]) -> List[Dict[str, Any]]:
    """异步版本的模块能力查询"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_modules_by_capabilities, capability_codes)
