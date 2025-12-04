"""
Phase 10: 输出生成节点

生成完整侦察计划、航线文件、执行包。
支持CrewAI增强：生成指挥员级别的任务简报。
"""
from __future__ import annotations

import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, List
import uuid

from ..state import (
    ReconSchedulerState,
    ReconPlan,
    ExecutiveSummary,
    FlightFile,
    ExecutionPackage,
)

logger = logging.getLogger(__name__)

# CrewAI开关
USE_CREWAI = os.getenv("RECON_USE_CREWAI", "false").lower() == "true"


async def output_generation_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    输出生成节点
    
    输入:
        - 所有前序阶段的输出
    
    输出:
        - recon_plan: 完整侦察计划
        - execution_package: 执行包
        - flight_files: 航线文件
    """
    logger.info("Phase 10: 输出生成")
    
    # 收集所有数据
    disaster_analysis = state.get("disaster_analysis", {})
    environment = state.get("environment_assessment", {})
    resource_inventory = state.get("resource_inventory", {})
    resource_allocation = state.get("resource_allocation", {})
    mission_phases = state.get("mission_phases", [])
    flight_plans = state.get("flight_plans", [])
    timeline = state.get("timeline_scheduling", {})
    risk_assessment = state.get("risk_assessment", {})
    validation = state.get("validation_result", {})
    
    event_id = state.get("event_id", "")
    scenario_id = state.get("scenario_id", "")
    errors = state.get("errors", [])
    warnings = state.get("warnings", [])
    
    # 生成执行摘要
    executive_summary = _generate_executive_summary(
        disaster_analysis=disaster_analysis,
        resource_allocation=resource_allocation,
        mission_phases=mission_phases,
        timeline=timeline,
        risk_assessment=risk_assessment,
    )
    
    # 生成航线文件
    flight_files = _generate_flight_files(flight_plans)
    
    # 生成执行包
    execution_package = _generate_execution_package(
        resource_allocation=resource_allocation,
        timeline=timeline,
        risk_assessment=risk_assessment,
        flight_plans=flight_plans,
    )
    
    # 计算预期产出
    expected_outputs = _collect_expected_outputs(mission_phases)
    
    # 构建完整计划
    plan_id = f"RECON-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    recon_plan: ReconPlan = {
        "plan_id": plan_id,
        "event_id": event_id,
        "scenario_id": scenario_id,
        "created_at": datetime.now().isoformat(),
        "version": "1.0",
        
        "executive_summary": executive_summary,
        
        "disaster_analysis": disaster_analysis,
        "environment_assessment": environment,
        
        "resource_inventory": resource_inventory,
        "resource_allocation": resource_allocation,
        
        "mission_phases": mission_phases,
        
        "flight_plans": flight_plans,
        
        "timeline": timeline,
        
        "risk_assessment": risk_assessment,
        
        "validation": validation,
        
        "flight_files": flight_files,
        "execution_package": execution_package,
        
        "expected_outputs": expected_outputs,
    }
    
    # 如果有错误，添加到计划中
    if errors:
        recon_plan["errors"] = errors
    if warnings:
        recon_plan["warnings"] = warnings
    
    # CrewAI增强：生成指挥员简报（无fallback，失败直接抛异常）
    commander_briefing = None
    if USE_CREWAI:
        from ..crewai import PlanPresentationCrew
        crew = PlanPresentationCrew()
        presentation = await crew.present(recon_plan)
        commander_briefing = {
            "executive_summary": presentation.executive_summary,
            "mission_overview": presentation.mission_overview,
            "force_deployment": [fd.model_dump() if hasattr(fd, 'model_dump') else fd for fd in presentation.force_deployment],
            "key_milestones": [m.model_dump() if hasattr(m, 'model_dump') else m for m in presentation.key_milestones],
            "risk_warnings": [r.model_dump() if hasattr(r, 'model_dump') else r for r in presentation.risk_warnings],
            "coordination_notes": presentation.coordination_notes,
            "commander_decisions_needed": presentation.commander_decisions_needed,
            "full_briefing": presentation.full_briefing,
        }
        recon_plan["commander_briefing"] = commander_briefing
        logger.info("[CrewAI] 指挥员简报生成完成")
    
    logger.info(f"输出生成完成: 计划ID={plan_id}, "
                f"航线数={len(flight_plans)}, 航线文件数={len(flight_files)}")
    
    return {
        "recon_plan": recon_plan,
        "execution_package": execution_package,
        "flight_files": flight_files,
        "commander_briefing": commander_briefing,
        "current_phase": "output_generation",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "output_generation",
            "timestamp": datetime.now().isoformat(),
            "plan_id": plan_id,
        }],
    }


def _generate_executive_summary(
    disaster_analysis: Dict,
    resource_allocation: Dict,
    mission_phases: List[Dict],
    timeline: Dict,
    risk_assessment: Dict,
) -> ExecutiveSummary:
    """生成执行摘要"""
    disaster_analysis = disaster_analysis or {}
    resource_allocation = resource_allocation or {}
    timeline = timeline or {}
    risk_assessment = risk_assessment or {}
    
    allocations = resource_allocation.get("allocations", [])
    devices = list(set(a.get("device_name", "") for a in allocations))
    
    # 计算覆盖面积（简化）
    target_coverage = 0
    affected_area = disaster_analysis.get("affected_area", {})
    if affected_area:
        target_coverage = 1.0  # 默认1 km²
    
    return {
        "mission_name": f"{disaster_analysis.get('disaster_type', '未知')}灾区侦察任务",
        "disaster_type": disaster_analysis.get("disaster_type", "未知"),
        "disaster_location": "目标区域",
        
        "total_devices": len(devices),
        "total_phases": len(mission_phases),
        "total_tasks": len(allocations),
        "estimated_duration_min": timeline.get("total_duration_min", 0),
        "target_coverage_km2": target_coverage,
        
        "planned_start": datetime.now().isoformat(),
        "estimated_completion": "",  # 基于总时长计算
        
        "priority_targets": [t.get("description", "") for t in disaster_analysis.get("priority_targets", [])[:3]],
        
        "overall_risk_level": risk_assessment.get("overall_risk_level", "medium"),
        "weather_window_hours": 4.0,
    }


def _generate_flight_files(flight_plans: List[Dict]) -> List[FlightFile]:
    """生成航线文件"""
    flight_files = []
    
    for fp in flight_plans:
        device_id = fp.get("device_id", "")
        device_name = fp.get("device_name", "")
        waypoints = fp.get("waypoints", [])
        
        if not waypoints:
            continue
        
        # 生成JSON格式航点
        waypoints_json = waypoints
        
        # 生成KML格式
        kml_content = _generate_kml(waypoints, fp.get("task_name", "任务"))
        
        flight_files.append({
            "device_id": device_id,
            "device_name": device_name,
            "file_format": "kml",
            "file_content": kml_content,
            "waypoints_json": waypoints_json,
        })
    
    return flight_files


def _generate_kml(waypoints: List[Dict], name: str) -> str:
    """生成KML格式航线文件"""
    coordinates = []
    for wp in waypoints:
        # KML格式是 lng,lat,alt
        coordinates.append(f"{wp['lng']},{wp['lat']},{wp['alt_m']}")
    
    coords_str = " ".join(coordinates)
    
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <Placemark>
      <name>航线</name>
      <LineString>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>{coords_str}</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    
    return kml


def _generate_execution_package(
    resource_allocation: Dict,
    timeline: Dict,
    risk_assessment: Dict,
    flight_plans: List[Dict],
) -> ExecutionPackage:
    """生成执行包"""
    resource_allocation = resource_allocation or {}
    timeline = timeline or {}
    risk_assessment = risk_assessment or {}
    
    allocations = resource_allocation.get("allocations", [])
    gantt_data = timeline.get("gantt_data", [])
    contingency_plans = risk_assessment.get("contingency_plans", [])
    checklist = risk_assessment.get("pre_flight_checklist", [])
    
    # 任务分配表
    task_assignment_table = []
    for alloc in allocations:
        task_assignment_table.append({
            "任务ID": alloc.get("task_id", ""),
            "设备": alloc.get("device_name", ""),
            "预计开始(分钟)": alloc.get("estimated_start_min", 0),
            "预计时长(分钟)": alloc.get("estimated_duration_min", 0),
            "备注": "主要分配" if not alloc.get("is_backup") else "备份",
        })
    
    # 时间表
    schedule_table = []
    for bar in gantt_data:
        schedule_table.append({
            "任务": bar.get("task_name", ""),
            "设备": bar.get("device_name", ""),
            "开始": bar.get("start_min", 0),
            "结束": bar.get("end_min", 0),
            "阶段": bar.get("phase", 1),
        })
    
    # 检查清单分类
    checklists = {
        "飞行前检查": [c for c in checklist if c.get("category") in ["设备", "通信"]],
        "空域检查": [c for c in checklist if c.get("category") == "空域"],
    }
    
    # 通信计划
    communication_plan = {
        "primary_channel": "主频道",
        "backup_channel": "备用频道",
        "report_frequency_min": 10,
        "emergency_contact": "指挥中心",
    }
    
    # 应急卡片
    emergency_cards = []
    for plan in contingency_plans[:5]:  # 最多5个
        emergency_cards.append({
            "标题": plan.get("plan_id", ""),
            "触发条件": plan.get("trigger_condition", ""),
            "立即行动": plan.get("immediate_actions", []),
            "后续行动": plan.get("follow_up_actions", []),
        })
    
    return {
        "task_assignment_table": task_assignment_table,
        "schedule_table": schedule_table,
        "checklists": checklists,
        "communication_plan": communication_plan,
        "emergency_cards": emergency_cards,
    }


def _collect_expected_outputs(mission_phases: List[Dict]) -> List[str]:
    """收集预期产出"""
    outputs = []
    for phase in mission_phases:
        phase_outputs = phase.get("expected_outputs", [])
        outputs.extend(phase_outputs)
    return list(set(outputs))
