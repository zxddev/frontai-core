"""
输出节点

生成最终输出结果。
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..state import EmergencyAIState

logger = logging.getLogger(__name__)


def _filter_for_commander(text: str, event_time: Optional[datetime] = None) -> str:
    """
    过滤和转换文本，让指挥员更易读：
    1. 过滤掉队伍类型标识，如（RESCUE_TEAM）、（FIRE_TEAM）等
    2. 将英文灾情级别转换为中文
    3. 将T+时间格式转换为实际时间
    """
    if not text:
        return text
    
    # 1. 过滤队伍类型标识（XXX_TEAM）或（XXX_CENTER）格式
    text = re.sub(r'（[A-Z_]+(?:_TEAM|_CENTER)）', '', text)
    
    # 2. 转换灾情级别为中文
    severity_map = {
        'critical': '特别重大（I级）',
        'high': '重大（II级）',
        'medium': '较大（III级）',
        'low': '一般（IV级）',
    }
    for en, cn in severity_map.items():
        # 匹配 "critical级别" 或 "属critical级别" 等模式
        text = re.sub(rf'属{en}级别', f'属{cn}', text, flags=re.IGNORECASE)
        text = re.sub(rf'{en}级别', f'{cn}', text, flags=re.IGNORECASE)
        text = re.sub(rf'级别[：:]\s*{en}', f'级别：{cn}', text, flags=re.IGNORECASE)
    
    # 3. 转换T+时间为实际时间
    base_time = event_time or datetime.now()
    
    def convert_t_time(match):
        """将T+0h或T+0-0.5h转换为实际时间"""
        t_expr = match.group(0)
        # 提取小时数，如 T+0、T+0.5、T+0-0.5h 等
        nums = re.findall(r'[\d.]+', t_expr)
        if not nums:
            return t_expr
        
        try:
            # 取第一个数字作为起始小时
            start_hour = float(nums[0])
            target_time = base_time + timedelta(hours=start_hour)
            
            # 判断是否跨天
            if target_time.date() == base_time.date():
                # 当天：只显示时间 如 "14:30"
                time_str = target_time.strftime("%H:%M")
            else:
                # 跨天：显示月日+时间 如 "12月3日 08:00"
                time_str = f"{target_time.month}月{target_time.day}日 {target_time.strftime('%H:%M')}"
            
            # 如果是时间范围（T+0-0.5h），显示范围
            if len(nums) >= 2:
                end_hour = float(nums[1])
                end_time = base_time + timedelta(hours=end_hour)
                if end_time.date() == base_time.date():
                    end_str = end_time.strftime("%H:%M")
                else:
                    end_str = f"{end_time.month}月{end_time.day}日 {end_time.strftime('%H:%M')}"
                return f"{time_str}~{end_str}"
            
            return time_str
        except (ValueError, TypeError):
            return t_expr
    
    # 匹配 T+0h、T+0-0.5h、T+24小时 等格式
    text = re.sub(r'T\+[\d.]+-?[\d.]*\s*[hH小时]*', convert_t_time, text)
    
    return text


async def _generate_scheme_text(
    parsed_disaster: Dict[str, Any],
    task_sequence: List[Dict[str, Any]],
    recommended_scheme: Dict[str, Any],
    scheme_explanation: str,
) -> str:
    """
    生成方案文本（供指挥员查看/编辑）
    
    将结构化数据转换为人类可读的方案文本。
    
    Args:
        parsed_disaster: 解析后的灾情信息
        task_sequence: HTN任务序列
        recommended_scheme: 推荐方案
        scheme_explanation: LLM生成的方案解释
        
    Returns:
        方案文本字符串
    """
    lines = []
    
    # 一、灾情概述
    lines.append("一、灾情概述")
    disaster_type_map = {
        "earthquake": "地震",
        "fire": "火灾",
        "flood": "洪涝",
        "hazmat": "危化品泄漏",
        "landslide": "山体滑坡",
    }
    disaster_type = disaster_type_map.get(
        parsed_disaster.get("disaster_type", "unknown"), 
        parsed_disaster.get("disaster_type", "未知灾害")
    )
    # 从数据库获取严重程度显示映射
    from src.agents.services.config_service import ConfigService
    severity_map = await ConfigService.get_severity_display_map()
    severity = severity_map.get(parsed_disaster.get("severity", "medium"), "中等")
    
    lines.append(f"灾害类型：{disaster_type}")
    lines.append(f"严重程度：{severity}")
    if parsed_disaster.get("magnitude"):
        lines.append(f"震级：{parsed_disaster.get('magnitude')}级")
    if parsed_disaster.get("estimated_trapped", 0) > 0:
        lines.append(f"预估被困人数：{parsed_disaster.get('estimated_trapped')}人")
    if parsed_disaster.get("has_building_collapse"):
        lines.append("存在建筑倒塌情况")
    if parsed_disaster.get("has_secondary_fire"):
        lines.append("存在次生火灾风险")
    if parsed_disaster.get("has_hazmat_leak"):
        lines.append("存在危化品泄漏风险")
    lines.append("")
    
    # 二、救援力量部署
    lines.append("二、救援力量部署")
    allocations = recommended_scheme.get("allocations", [])
    for i, alloc in enumerate(allocations, 1):
        team_name = alloc.get("resource_name", "未知队伍")
        capabilities = alloc.get("assigned_capabilities", [])
        eta = alloc.get("eta_minutes", 0)
        distance = alloc.get("distance_km", 0)
        cap_str = "、".join(capabilities[:3]) if capabilities else "综合救援"
        lines.append(f"{i}. {team_name}（距离{distance:.1f}km，预计{eta:.0f}分钟到达）")
        lines.append(f"   负责：{cap_str}")
    lines.append("")
    
    # 三、任务安排
    lines.append("三、任务安排")
    priority_map = await ConfigService.get_priority_display_map()
    for task in task_sequence:
        task_name = task.get("task_name", "未知任务")
        priority = priority_map.get(task.get("priority", "medium"), "中优先")
        phase = task.get("phase", "execute")
        golden_hour = task.get("golden_hour")
        depends = task.get("depends_on", [])
        
        time_hint = f"黄金时间{golden_hour}分钟" if golden_hour else ""
        depend_hint = f"（依赖：{', '.join(depends)}）" if depends else ""
        
        lines.append(f"- {task_name}（{priority}）{time_hint}{depend_hint}")
    lines.append("")
    
    # 四、方案说明
    if scheme_explanation:
        lines.append("四、方案说明")
        # 如果是dict，提取summary
        if isinstance(scheme_explanation, dict):
            lines.append(scheme_explanation.get("summary", ""))
        else:
            lines.append(str(scheme_explanation)[:500])
    
    return "\n".join(lines)


async def generate_output(state: EmergencyAIState) -> Dict[str, Any]:
    """
    输出生成节点：构建最终输出结果
    
    整合所有阶段的结果，生成结构化的最终输出。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行输出生成节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 判断是否成功
    errors = state.get("errors", [])
    recommended_scheme = state.get("recommended_scheme")
    
    success = len(errors) == 0 and recommended_scheme is not None
    
    # 构建输出
    final_output: Dict[str, Any] = {
        "success": success,
        "event_id": state["event_id"],
        "scenario_id": state["scenario_id"],
        "status": "completed" if success else "failed",
        "completed_at": datetime.utcnow().isoformat() + "Z",
        
        # 阶段1: 灾情理解
        "understanding": {
            "parsed_disaster": state.get("parsed_disaster"),
            "similar_cases_count": len(state.get("similar_cases", [])),
            "summary": state.get("understanding_summary", ""),
        },
        
        # 阶段2: 规则推理
        "reasoning": {
            "matched_rules": [
                {
                    "rule_id": r.get("rule_id"),
                    "rule_name": r.get("rule_name"),
                    "priority": r.get("priority"),
                    "match_reason": r.get("match_reason"),
                }
                for r in state.get("matched_rules", [])
            ],
            "task_requirements": state.get("task_requirements", []),
            "capability_requirements": [
                {
                    "code": c.get("capability_code"),
                    "name": c.get("capability_name"),
                    "provided_by": c.get("provided_by", []),
                }
                for c in state.get("capability_requirements", [])
            ],
        },
        
        # 阶段2.5: HTN任务分解
        "htn_decomposition": {
            "scene_codes": state.get("scene_codes", []),
            "task_sequence": [
                {
                    "task_id": t.get("task_id"),
                    "task_name": t.get("task_name"),
                    "sequence": t.get("sequence"),
                    "depends_on": t.get("depends_on", []),
                    "golden_hour": t.get("golden_hour"),
                    "phase": t.get("phase"),
                    "is_parallel": t.get("is_parallel"),
                    "parallel_group_id": t.get("parallel_group_id"),
                    "required_capabilities": t.get("required_capabilities", []),
                }
                for t in state.get("task_sequence", [])
            ],
            "parallel_tasks": [
                {
                    "group_id": g.get("group_id"),
                    "task_ids": g.get("task_ids", []),
                    "reason": g.get("reason"),
                }
                for g in state.get("parallel_tasks", [])
            ],
        },
        
        # 阶段2.6: 战略层（任务域/阶段/模块/运力/安全）
        "strategic": {
            # 任务域分类
            "active_domains": state.get("active_domains", []),
            "domain_priorities": state.get("domain_priorities", []),
            # 灾害阶段
            "disaster_phase": state.get("disaster_phase"),
            "disaster_phase_name": state.get("disaster_phase_name"),
            # 推荐模块
            "recommended_modules": [
                {
                    "module_id": m.get("module_id"),
                    "module_name": m.get("module_name"),
                    "personnel": m.get("personnel"),
                    "dogs": m.get("dogs"),
                    "vehicles": m.get("vehicles"),
                    "match_score": m.get("match_score"),
                    "provided_capabilities": m.get("provided_capabilities", []),
                    "equipment_list": m.get("equipment_list", []),
                }
                for m in state.get("recommended_modules", [])
            ],
            # 运力检查
            "transport_plans": state.get("transport_plans", []),
            "transport_warnings": state.get("transport_warnings", []),
            # 安全规则
            "safety_violations": [
                {
                    "rule_id": v.get("rule_id"),
                    "rule_type": v.get("rule_type"),
                    "rule_name": v.get("rule_name"),
                    "message": v.get("message"),
                    "severity": v.get("severity"),
                }
                for v in state.get("safety_violations", [])
            ],
            # 生成报告
            "generated_reports": state.get("generated_reports", {}),
        },
        
        # 阶段3: 资源匹配（详细信息）
        "matching": {
            "candidates_count": len(state.get("resource_candidates", [])),
            "solutions_count": len(state.get("allocation_solutions", [])),
            "pareto_solutions_count": len(state.get("pareto_solutions", [])),
            # 详细的候选资源列表
            "candidates_detail": [
                {
                    "resource_id": c.get("resource_id"),
                    "resource_name": c.get("resource_name"),
                    "resource_type": c.get("resource_type"),
                    "capabilities": c.get("capabilities", []),
                    "distance_km": round(c.get("distance_km", 0), 1),
                    "eta_minutes": round(c.get("eta_minutes", 0)),
                    "match_score": round(c.get("match_score", 0), 3),
                    "rescue_capacity": c.get("rescue_capacity", 0),  # 救援容量
                }
                for c in state.get("resource_candidates", [])[:20]  # 最多显示20个
            ],
        },
        
        # 阶段4: 方案优化（5维评估）
        "optimization": {
            "scheme_scores": [
                {
                    "scheme_id": s.get("scheme_id"),
                    "passed": s.get("hard_rule_passed"),
                    "violations": s.get("hard_rule_violations", []),
                    "total_score": s.get("weighted_score"),
                    "rank": s.get("rank"),
                    "dimension_scores": s.get("soft_rule_scores", {}),
                }
                for s in state.get("scheme_scores", [])
            ],
        },
        
        # 推荐方案
        "recommended_scheme": recommended_scheme,
        
        # 方案解释（过滤队伍类型标识、转换灾情级别和T+时间为中文，让指挥员更易读）
        "scheme_explanation": _filter_for_commander(
            state.get("scheme_explanation", ""),
            event_time=datetime.now(),  # 使用当前时间作为基准
        ),
        
        # 方案文本（供指挥员查看/编辑）
        "scheme_text": "",
        "scheme_text_hash": "",
        
        # 追踪信息
        "trace": state.get("trace", {}),
        
        # 错误信息
        "errors": errors,
    }
    
    # 生成方案文本（仅在成功时）
    if success and recommended_scheme:
        scheme_text = await _generate_scheme_text(
            parsed_disaster=state.get("parsed_disaster") or {},
            task_sequence=state.get("task_sequence", []),
            recommended_scheme=recommended_scheme,
            scheme_explanation=state.get("scheme_explanation", ""),
        )
        scheme_text_hash = hashlib.md5(scheme_text.encode("utf-8")).hexdigest()
        final_output["scheme_text"] = scheme_text
        final_output["scheme_text_hash"] = scheme_text_hash
    
    # 计算总执行时间
    trace = state.get("trace", {})
    elapsed_ms = int((time.time() - start_time) * 1000)
    total_time = state.get("execution_time_ms", 0) + elapsed_ms
    
    final_output["execution_time_ms"] = total_time
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_output"]
    
    logger.info(
        "输出生成完成",
        extra={
            "success": success,
            "total_time_ms": total_time,
            "phases_count": len(trace.get("phases_executed", [])),
        }
    )
    
    return {
        "final_output": final_output,
        "trace": trace,
        "current_phase": "completed",
        "execution_time_ms": total_time,
    }
