"""
战略层节点: 报告自动生成

根据模板自动生成灾情报告。
"""
from __future__ import annotations

import logging
import time
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

from sqlalchemy import text

from ..state import EmergencyAIState

logger = logging.getLogger(__name__)


def render_template(template: str, variables: Dict[str, Any]) -> str:
    """
    渲染模板
    
    支持的语法:
    - {{variable}} - 简单变量替换
    - {{#each array}}...{{/each}} - 数组遍历（简化版）
    
    Args:
        template: 模板字符串
        variables: 变量字典
        
    Returns:
        渲染后的字符串
    """
    result = template
    
    # 处理简单变量
    for key, value in variables.items():
        if not isinstance(value, (list, dict)):
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value) if value is not None else "")
    
    # 处理 {{#each array}}...{{/each}} 语法（简化实现）
    each_pattern = r'\{\{#each (\w+)\}\}(.*?)\{\{/each\}\}'
    matches = re.findall(each_pattern, result, re.DOTALL)
    
    for array_name, item_template in matches:
        array_data = variables.get(array_name, [])
        rendered_items = []
        
        for item in array_data:
            item_result = item_template
            if isinstance(item, dict):
                for k, v in item.items():
                    item_result = item_result.replace("{{this." + k + "}}", str(v) if v is not None else "")
            else:
                item_result = item_result.replace("{{this}}", str(item))
            rendered_items.append(item_result.strip())
        
        full_pattern = "{{#each " + array_name + "}}" + item_template + "{{/each}}"
        result = result.replace(full_pattern, "\n".join(rendered_items))
    
    return result


async def generate_reports(state: EmergencyAIState) -> Dict[str, Any]:
    """
    报告生成节点：根据模板生成灾情报告
    
    1. 从PostgreSQL查询报告模板
    2. 收集状态中的各项数据
    3. 渲染模板生成报告
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段，包含 generated_reports
    """
    event_id = state["event_id"]
    
    logger.info(
        "【报告生成】开始执行",
        extra={"event_id": event_id}
    )
    start_time = time.time()
    
    # 从PostgreSQL查询报告模板
    from src.core.database import AsyncSessionLocal
    
    query = text("""
        SELECT template_id, report_type, name, template, variables
        FROM config.report_templates
        WHERE is_active = TRUE
        ORDER BY report_type
    """)
    
    logger.info("【PostgreSQL】查询报告模板", extra={"query": str(query)})
    
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(query)
        template_rows = result.fetchall()
    
    logger.info(
        "【PostgreSQL】查询结果",
        extra={"count": len(template_rows)}
    )
    
    if not template_rows:
        raise ValueError(f"【报告生成】PostgreSQL未找到报告模板，event_id={event_id}")
    
    # 收集模板变量
    parsed_disaster = state.get("parsed_disaster", {}) or {}
    structured_input = state.get("structured_input", {})
    domain_priorities = state.get("domain_priorities", [])
    recommended_modules = state.get("recommended_modules", [])
    transport_warnings = state.get("transport_warnings", [])
    safety_violations = state.get("safety_violations", [])
    
    variables = {
        # 基本信息
        "event_id": event_id,
        "disaster_type": parsed_disaster.get("disaster_type", "未知"),
        "event_time": structured_input.get("event_time", str(datetime.now(timezone.utc))),
        "location": structured_input.get("location", parsed_disaster.get("location", "未知")),
        "affected_area": structured_input.get("affected_area", "待评估"),
        
        # 灾情概况
        "disaster_summary": state.get("understanding_summary", "待补充"),
        "severity": parsed_disaster.get("severity", "未知"),
        
        # 人员情况
        "estimated_trapped": parsed_disaster.get("estimated_trapped", 0),
        "confirmed_casualties": structured_input.get("confirmed_casualties", 0),
        
        # 任务域
        "active_domains": [
            {"name": d.get("name", d.get("domain_id")), "priority": d.get("priority", 0)}
            for d in domain_priorities
        ],
        
        # 推荐模块
        "recommended_modules": [
            {"name": m.get("module_name", m.get("module_id")), "personnel": m.get("personnel", 0)}
            for m in recommended_modules
        ],
        
        # 阶段
        "current_phase": state.get("disaster_phase_name", state.get("disaster_phase", "未知")),
        
        # 安全警告
        "safety_warnings": [v.get("message", "") for v in safety_violations],
        
        # 运力警告
        "transport_warnings": transport_warnings,
        
        # 下一步行动（基于阶段生成）
        "next_actions": _generate_next_actions(state),
        
        # 报告时间
        "report_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    
    logger.info(
        "【报告生成】模板变量",
        extra={
            "variables_keys": list(variables.keys()),
            "active_domains_count": len(variables["active_domains"]),
            "modules_count": len(variables["recommended_modules"]),
        }
    )
    
    # 渲染报告
    generated_reports: Dict[str, str] = {}
    
    for row in template_rows:
        report_type = row.report_type
        template = row.template
        
        logger.info(
            "【报告生成】渲染模板",
            extra={"report_type": report_type, "template_id": row.template_id}
        )
        
        rendered = render_template(template, variables)
        generated_reports[report_type] = rendered
        
        logger.info(
            "【报告生成】渲染完成",
            extra={"report_type": report_type, "length": len(rendered)}
        )
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_reports"]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【报告生成】执行完成",
        extra={
            "event_id": event_id,
            "reports_generated": list(generated_reports.keys()),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "generated_reports": generated_reports,
        "trace": trace,
        "current_phase": "strategic_report",
    }


def _generate_next_actions(state: EmergencyAIState) -> str:
    """
    根据当前阶段生成下一步行动建议
    """
    phase = state.get("disaster_phase", "")
    domain_priorities = state.get("domain_priorities", [])
    
    if phase == "initial":
        return "1. 快速展开态势评估\n2. 启动生命探测搜救\n3. 建立前线指挥部"
    elif phase == "golden":
        actions = ["1. 全力开展搜救作业"]
        if domain_priorities:
            top_domain = domain_priorities[0].get("name", "")
            actions.append(f"2. 优先执行{top_domain}任务")
        actions.append("3. 持续监测次生灾害风险")
        return "\n".join(actions)
    elif phase == "intensive":
        return "1. 持续搜救不放弃\n2. 加强后勤保障\n3. 关注救援人员身心状态"
    elif phase == "recovery":
        return "1. 转入恢复重建\n2. 灾后评估\n3. 心理疏导和社会稳定"
    else:
        return "待根据态势进一步评估"
