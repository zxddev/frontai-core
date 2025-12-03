"""
战略层节点: 预编组模块装配

根据所需能力推荐预编组救援模块。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import EmergencyAIState, RecommendedModule

logger = logging.getLogger(__name__)


async def assemble_modules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    模块装配节点：根据能力需求推荐预编组模块
    
    1. 获取当前所需的能力列表
    2. 从Neo4j查询能提供这些能力的模块
    3. 按能力覆盖度排序推荐
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段，包含 recommended_modules
    """
    event_id = state["event_id"]
    capability_requirements = state.get("capability_requirements", [])
    
    logger.info(
        "【模块装配】开始执行",
        extra={
            "event_id": event_id,
            "capability_count": len(capability_requirements),
        }
    )
    start_time = time.time()
    
    if not capability_requirements:
        logger.warning(
            "【模块装配】无能力需求，跳过模块推荐",
            extra={"event_id": event_id}
        )
        trace = dict(state.get("trace", {}))
        trace["phases_executed"] = trace.get("phases_executed", []) + ["assemble_modules"]
        trace["module_assembler_skipped"] = True
        return {
            "recommended_modules": [],
            "trace": trace,
        }
    
    # 提取能力编码列表
    required_capabilities = [c["capability_code"] for c in capability_requirements]
    
    logger.info(
        "【模块装配】所需能力",
        extra={"required_capabilities": required_capabilities}
    )
    
    # 从Neo4j查询能提供这些能力的模块
    from ..tools.kg_tools import query_modules_by_capabilities_async
    
    logger.info(
        "【Neo4j】查询模块能力",
        extra={"capability_codes": required_capabilities}
    )
    
    records = await query_modules_by_capabilities_async(required_capabilities)
    
    logger.info(
        "【Neo4j】查询结果",
        extra={"count": len(records), "modules": [r["module_id"] for r in records] if records else []}
    )
    
    if not records:
        raise ValueError(f"【模块装配】Neo4j未找到能提供所需能力的模块，capabilities={required_capabilities}")
    
    # 从PostgreSQL查询模块装备清单
    from sqlalchemy import text
    from src.core.database import AsyncSessionLocal
    
    recommended_modules: List[RecommendedModule] = []
    
    async with AsyncSessionLocal() as db_session:
        for record in records:
            module_id = record["module_id"]
            
            # 查询装备清单
            equipment_query = text("""
                SELECT equipment_type, equipment_name, quantity, unit, is_essential, description
                FROM config.rescue_module_equipment
                WHERE module_id = :module_id
                ORDER BY is_essential DESC, equipment_type
            """)
            
            logger.info(
                "【PostgreSQL】查询模块装备",
                extra={"module_id": module_id}
            )
            
            equipment_result = await db_session.execute(
                equipment_query,
                {"module_id": module_id}
            )
            equipment_rows = equipment_result.fetchall()
            
            equipment_list = [
                {
                    "equipment_type": row.equipment_type,
                    "equipment_name": row.equipment_name,
                    "quantity": row.quantity,
                    "unit": row.unit,
                    "is_essential": row.is_essential,
                    "description": row.description,
                }
                for row in equipment_rows
            ]
            
            logger.info(
                "【PostgreSQL】查询结果",
                extra={"module_id": module_id, "equipment_count": len(equipment_list)}
            )
            
            # 构建推荐模块
            provided_caps = record.get("provided_caps", [])
            recommended_modules.append(RecommendedModule(
                module_id=module_id,
                module_name=record["module_name"],
                personnel=record.get("personnel", 0) or 0,
                dogs=record.get("dogs", 0) or 0,
                vehicles=record.get("vehicles", 0) or 0,
                provided_capabilities=[c["capability_code"] for c in provided_caps],
                match_score=record.get("match_score", 0.0),
                equipment_list=equipment_list,
            ))
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["assemble_modules"]
    trace["kg_calls"] = trace.get("kg_calls", 0) + 1
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【模块装配】执行完成",
        extra={
            "event_id": event_id,
            "recommended_modules": [m["module_id"] for m in recommended_modules],
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "recommended_modules": recommended_modules,
        "trace": trace,
        "current_phase": "strategic_module",
    }
