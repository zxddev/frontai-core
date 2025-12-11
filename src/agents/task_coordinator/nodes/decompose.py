"""
步骤分解节点

从 Neo4j 加载 SOP 步骤并解析依赖关系。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import TaskCoordinatorState
from ..schemas import SOPStep, CoordinatorWarning

logger = logging.getLogger(__name__)


async def _query_steps_from_neo4j(sop_id: str) -> List[SOPStep]:
    """
    从 Neo4j 查询 SOP 步骤

    Args:
        sop_id: SOP 模板ID

    Returns:
        步骤列表（按 sequence 排序）
    """
    try:
        from src.infra.settings import load_settings
        from neo4j import AsyncGraphDatabase

        settings = load_settings()
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

        steps = []
        async with driver.session() as session:
            # 查询步骤及其依赖
            query = """
            MATCH (sop:SOPTemplate {id: $sop_id})-[:HAS_STEP]->(step:SOPStep)
            OPTIONAL MATCH (step)-[:DEPENDS_ON]->(dep:SOPStep)
            RETURN step, collect(dep.id) as depends_on
            ORDER BY step.sequence
            """
            result = await session.run(query, sop_id=sop_id)

            async for record in result:
                step_data = dict(record["step"])
                depends_on = [d for d in record["depends_on"] if d]

                step = SOPStep(
                    id=step_data.get("id", ""),
                    name=step_data.get("name", ""),
                    sequence=step_data.get("sequence", 0),
                    duration_minutes=step_data.get("duration_minutes", 30),
                    roles=step_data.get("roles", []),
                    required_capabilities=step_data.get("required_capabilities", []),
                    required_equipment=step_data.get("required_equipment", []),
                    parallel_allowed=step_data.get("parallel_allowed", False),
                    completion_criteria=step_data.get("completion_criteria"),
                    safety_notes=step_data.get("safety_notes"),
                    depends_on=depends_on,
                )
                steps.append(step)

        await driver.close()
        return steps

    except Exception as e:
        logger.warning(f"[步骤分解] Neo4j 查询失败: {e}")
        return []


def _get_fallback_steps(sop_id: str) -> List[SOPStep]:
    """
    获取默认步骤（当 Neo4j 查询失败时）

    Args:
        sop_id: SOP 模板ID

    Returns:
        默认步骤列表
    """
    # 根据 SOP ID 返回默认步骤
    if "EARTHQUAKE" in sop_id:
        return [
            SOPStep(id="STEP-001", name="生命探测", sequence=1, duration_minutes=30,
                    roles=["主攻"], required_capabilities=["LIFE_DETECTION"],
                    required_equipment=["生命探测仪", "蛇眼探测器"]),
            SOPStep(id="STEP-002", name="破拆通道", sequence=2, duration_minutes=60,
                    roles=["主攻", "配合"], required_capabilities=["HEAVY_RESCUE"],
                    required_equipment=["液压剪", "破拆锤"], depends_on=["STEP-001"]),
            SOPStep(id="STEP-003", name="伤员救出", sequence=3, duration_minutes=45,
                    roles=["主攻", "配合"], required_capabilities=["RESCUE", "MEDICAL_FIRST_AID"],
                    required_equipment=["担架", "医疗包"], depends_on=["STEP-002"]),
            SOPStep(id="STEP-004", name="现场急救转运", sequence=4, duration_minutes=30,
                    roles=["主攻"], required_capabilities=["MEDICAL_EMERGENCY"],
                    required_equipment=["急救设备", "救护车"], depends_on=["STEP-003"]),
        ]
    elif "HAZMAT" in sop_id:
        return [
            SOPStep(id="STEP-001", name="侦检识别", sequence=1, duration_minutes=20,
                    roles=["主攻"], required_capabilities=["HAZMAT_DETECTION"],
                    required_equipment=["气体检测仪", "防化服"]),
            SOPStep(id="STEP-002", name="警戒隔离", sequence=2, duration_minutes=30,
                    roles=["主攻", "配合"], required_capabilities=["CROWD_CONTROL"],
                    required_equipment=["警戒带", "扩音器"], depends_on=["STEP-001"]),
            SOPStep(id="STEP-003", name="堵漏封堵", sequence=3, duration_minutes=90,
                    roles=["主攻"], required_capabilities=["HAZMAT_CONTAINMENT"],
                    required_equipment=["堵漏器材"], depends_on=["STEP-002"]),
        ]
    elif "FIRE" in sop_id:
        return [
            SOPStep(id="STEP-001", name="火情侦察", sequence=1, duration_minutes=15,
                    roles=["主攻"], required_capabilities=["FIRE_RECONNAISSANCE"],
                    required_equipment=["热成像仪"]),
            SOPStep(id="STEP-002", name="人员搜救", sequence=2, duration_minutes=45,
                    roles=["主攻", "配合"], required_capabilities=["FIRE_RESCUE"],
                    required_equipment=["空气呼吸器", "救生绳"], depends_on=["STEP-001"]),
            SOPStep(id="STEP-003", name="火势控制", sequence=3, duration_minutes=60,
                    roles=["主攻", "配合", "保障"], required_capabilities=["FIRE_SUPPRESSION"],
                    required_equipment=["消防水带", "水枪"], depends_on=["STEP-001"]),
        ]
    else:
        # 通用步骤
        return [
            SOPStep(id="STEP-001", name="现场评估", sequence=1, duration_minutes=20,
                    roles=["主攻"], required_capabilities=["RECONNAISSANCE"]),
            SOPStep(id="STEP-002", name="救援行动", sequence=2, duration_minutes=60,
                    roles=["主攻", "配合"], required_capabilities=["RESCUE"],
                    depends_on=["STEP-001"]),
            SOPStep(id="STEP-003", name="伤员转运", sequence=3, duration_minutes=30,
                    roles=["主攻"], required_capabilities=["MEDICAL_SUPPORT"],
                    depends_on=["STEP-002"]),
        ]


async def decompose_steps(state: TaskCoordinatorState) -> Dict[str, Any]:
    """
    步骤分解节点

    从 Neo4j 加载 SOP 步骤，解析依赖关系。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段
    """
    logger.info("[TaskCoordinator] 分解 SOP 步骤")
    start_time = time.time()

    matched_sop = state.get("matched_sop")
    warnings = list(state.get("warnings", []))

    if not matched_sop:
        return {
            "errors": state.get("errors", []) + ["无匹配的 SOP 模板"],
            "current_phase": "failed",
        }

    # 查询步骤
    sop_steps = await _query_steps_from_neo4j(matched_sop.id)

    # 如果查询失败，使用默认步骤
    if not sop_steps:
        sop_steps = _get_fallback_steps(matched_sop.id)
        warnings.append(CoordinatorWarning(
            code="STEPS_FALLBACK",
            message=f"使用默认步骤（共 {len(sop_steps)} 步）",
            severity="info",
        ))

    # 构建依赖关系图
    step_dependencies: Dict[str, List[str]] = {}
    for step in sop_steps:
        step_dependencies[step.id] = step.depends_on

    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"[TaskCoordinator] 步骤分解完成: "
        f"steps={len(sop_steps)}, "
        f"dependencies={sum(len(d) for d in step_dependencies.values())}"
    )

    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["decompose_steps"]
    trace["steps_count"] = len(sop_steps)

    return {
        "sop_steps": sop_steps,
        "step_dependencies": step_dependencies,
        "warnings": warnings,
        "trace": trace,
        "current_phase": "assign_roles",
        "execution_time_ms": state.get("execution_time_ms", 0) + elapsed_ms,
    }
