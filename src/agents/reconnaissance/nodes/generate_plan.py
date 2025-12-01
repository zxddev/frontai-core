"""侦察方案生成节点

使用 CrewAI 为每个设备分配生成具体的侦察执行方案。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from crewai import Agent, Crew, LLM, Process, Task
from pydantic import BaseModel, Field

from src.agents.reconnaissance.state import (
    DeviceAssignment,
    ReconMission,
    ReconMissionStep,
    ReconPlan,
    ReconState,
    ReconTarget,
)

logger = logging.getLogger(__name__)


# ============ Pydantic 输出模型 ============

class MissionStepOutput(BaseModel):
    """执行步骤"""
    step_name: str = Field(description="步骤名称")
    description: str = Field(description="步骤描述")
    duration_minutes: int = Field(description="预计耗时（分钟）")
    key_actions: list[str] = Field(description="关键动作")


class MissionPlanOutput(BaseModel):
    """单个设备的侦察方案"""
    mission_objective: str = Field(description="任务目标，一句话描述")
    recon_focus: list[str] = Field(description="侦察重点，需要关注什么")
    recon_method: str = Field(description="侦察方法，如何执行")
    route_description: str = Field(description="路线描述")
    altitude_or_depth: str = Field(description="飞行高度或作业距离")
    estimated_duration_minutes: int = Field(description="预计总耗时（分钟）")
    steps: list[MissionStepOutput] = Field(description="执行步骤列表")
    coordination_notes: str = Field(description="与其他设备的协同说明")
    safety_notes: list[str] = Field(description="安全注意事项")
    abort_conditions: list[str] = Field(description="中止条件")


class FullReconPlanOutput(BaseModel):
    """完整侦察方案"""
    summary: str = Field(description="方案概述")
    total_duration_minutes: int = Field(description="总预计耗时")
    coordination_strategy: str = Field(description="整体协同策略")
    communication_plan: str = Field(description="通讯方案")
    contingency_plan: str = Field(description="应急预案")
    missions: list[MissionPlanOutput] = Field(description="各设备任务方案")


# ============ CrewAI Agent 和 Task ============

def _create_recon_planner(llm: LLM) -> Agent:
    """创建侦察战术专家 Agent"""
    return Agent(
        role="侦察战术专家",
        goal="为每个无人设备生成详细的侦察执行方案",
        backstory="""你是应急救援指挥中心的侦察战术专家，精通各类无人装备的战术运用。

你的核心职责：
1. 根据设备类型设计侦察方法
   - 无人机(drone)：规划航拍路线、扫描高度、覆盖范围
   - 机器狗(dog)：规划地面搜索路径、进入点、搜索模式
   - 无人艇(ship)：规划水面巡航路线、侦察距离

2. 根据目标特征确定侦察重点
   - 滑坡区：关注滑坡体边界、二次滑坡风险、被困人员
   - 淹没区：关注水位、被困群众、可通行路线
   - 地震废墟：关注建筑结构、生命迹象、危险源
   - 化工设施：关注泄漏迹象、扩散方向、隔离区

3. 设计多设备协同方案
   - 无人机先行航拍，机器狗跟进地面搜索
   - 水域任务无人机+无人艇配合

4. 制定安全规范
   - 设备作业高度/距离限制
   - 中止条件（电量、信号、危险）
   - 应急返航程序

你熟悉ICS事故指挥系统和无人装备作战条令。""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def _create_plan_generation_task(agent: Agent, assignments_json: str, targets_json: str) -> Task:
    """创建方案生成任务"""
    return Task(
        description=f"""根据设备分配结果，为每个侦察任务生成详细的执行方案。

## 设备分配
{assignments_json}

## 目标信息
{targets_json}

## 输出要求

为每个分配的设备生成侦察方案，包括：

1. **任务目标**：一句话描述任务目的
2. **侦察重点**：需要关注的具体内容（3-5项）
3. **侦察方法**：如何执行侦察（航拍扫描/地面搜索/水面巡航等）
4. **路线描述**：具体的侦察路线或区域覆盖方式
5. **作业参数**：飞行高度/地面距离/水面距离
6. **执行步骤**：分步骤的执行流程（3-5步）
7. **协同说明**：与其他设备如何配合
8. **安全注意事项**：作业安全要求（2-4项）
9. **中止条件**：什么情况下应该中止任务

## 设备类型特定指南

### 无人机(drone)侦察方案要点
- 建议飞行高度：50-150米（根据任务调整）
- 航拍模式：往返扫描/环绕/定点悬停
- 关注：整体态势、人员分布、道路情况

### 机器狗(dog)侦察方案要点
- 搜索模式：网格搜索/沿路搜索/重点区域
- 进入路线：选择相对安全的进入点
- 关注：近距离情况、生命迹象、结构安全

### 无人艇(ship)侦察方案要点
- 巡航距离：保持安全距离
- 巡航路线：沿水域边缘/横向扫描
- 关注：水位、漂浮物、被困人员

请输出完整的JSON格式侦察方案。确保JSON语法正确，所有字符串值都用双引号包裹。""",
        expected_output="完整的侦察执行方案JSON",
        agent=agent,
    )


# ============ 主函数 ============

async def generate_recon_plan(state: ReconState) -> Dict[str, Any]:
    """为设备分配生成侦察执行方案
    
    输入：state.assignments（设备分配）、state.scored_targets（目标信息）
    输出：state.recon_plan（侦察方案）
    """
    assignments = state.get("assignments", [])
    targets = state.get("scored_targets", [])
    scenario_id = state.get("scenario_id", "")
    
    if not assignments:
        logger.info("[Recon] 无设备分配，跳过方案生成")
        return {
            "recon_plan": None,
            "current_phase": "generate_plan_skipped",
        }
    
    logger.info(
        "[Recon] 开始生成侦察方案",
        extra={"assignments": len(assignments), "targets": len(targets)},
    )
    
    # 准备输入数据
    assignments_data = []
    for a in assignments:
        assignments_data.append({
            "device_name": a.get("device_name"),
            "device_type": a.get("device_type"),
            "target_name": a.get("target_name"),
            "priority": a.get("priority"),
            "reason": a.get("reason"),
        })
    
    targets_data = []
    target_map = {t.get("target_id"): t for t in targets}
    for a in assignments:
        target = target_map.get(a.get("target_id"), {})
        targets_data.append({
            "name": target.get("name"),
            "area_type": target.get("_area_type"),
            "target_type": target.get("_target_type"),
            "priority": target.get("priority"),
            "features": target.get("features", {}),
        })
    
    assignments_json = json.dumps(assignments_data, ensure_ascii=False, indent=2)
    targets_json = json.dumps(targets_data, ensure_ascii=False, indent=2)
    
    # 创建 LLM（从环境变量读取配置）
    # vLLM返回的model id是完整路径，如"/models/openai/gpt-oss-120b"
    # LiteLLM需要格式: openai/<vllm_model_id>
    import os
    llm_model = os.getenv("LLM_MODEL", "/models/openai/gpt-oss-120b")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    openai_api_key = os.getenv("OPENAI_API_KEY", "dummy_key")
    
    # LiteLLM格式: openai/<model_id>
    if llm_model.startswith("openai/"):
        model = llm_model
    else:
        model = f"openai/{llm_model}"
    
    llm = LLM(
        model=model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0.3,
        timeout=180,
    )
    
    # 创建 Agent 和 Task
    planner = _create_recon_planner(llm)
    task = _create_plan_generation_task(planner, assignments_json, targets_json)
    
    # 创建并执行 Crew
    crew = Crew(
        agents=[planner],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    
    try:
        result = await crew.kickoff_async()
        plan_output = _extract_plan_output(result)
    except Exception as e:
        logger.exception("[Recon] CrewAI 方案生成失败")
        return {
            "errors": state.get("errors", []) + [f"方案生成失败: {e}"],
            "current_phase": "generate_plan_failed",
        }
    
    # 转换为内部数据结构
    recon_plan = _build_recon_plan(
        plan_output=plan_output,
        assignments=assignments,
        scenario_id=scenario_id,
    )
    
    logger.info(
        "[Recon] 侦察方案生成完成",
        extra={"missions": len(recon_plan.get("missions", []))},
    )
    
    return {
        "recon_plan": recon_plan,
        "current_phase": "generate_plan_completed",
    }


def _fix_json_string(text: str) -> str:
    """尝试修复常见的 JSON 语法错误"""
    import re
    
    # 移除 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line.startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end])
    
    # 尝试直接解析
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    
    # 修复缺少引号的字符串值：": 文字 -> ": "文字"
    # 匹配模式：": 后面跟着非引号的中文或字母开头
    def fix_missing_quote(match):
        key = match.group(1)
        value_start = match.group(2)
        # 找到这个值的结尾（逗号、]、}或换行）
        return f'"{key}": "{value_start}'
    
    # 修复 "key": 值 这种情况（值没有引号）
    text = re.sub(
        r'"([^"]+)":\s*([^\s"\[\{][^,\]\}\n]*)',
        lambda m: f'"{m.group(1)}": "{m.group(2)}"' if not m.group(2).replace('.','').replace('-','').isdigit() and m.group(2) not in ('true', 'false', 'null') else m.group(0),
        text
    )
    
    # 修复 safety_note -> safety_notes
    text = text.replace('"safety_note":', '"safety_notes":')
    text = text.replace('"safety_note\n', '"safety_notes":\n')
    
    return text


def _convert_llm_mission_to_standard(llm_mission: dict) -> MissionPlanOutput:
    """将 LLM 输出的任务格式转换为标准格式"""
    import re
    
    # LLM 输出的 execution_steps 是字符串数组，需要转换为 MissionStepOutput
    execution_steps = llm_mission.get("execution_steps", [])
    steps = []
    for i, step_text in enumerate(execution_steps):
        # 解析步骤文本，提取步骤名和描述
        step_text = str(step_text).strip()
        # 去掉开头的序号 "1. " 或 "1) " 等
        step_text = re.sub(r'^[\d]+[.)\s]+', '', step_text)
        steps.append(MissionStepOutput(
            step_name=f"步骤{i+1}",
            description=step_text,
            duration_minutes=5,  # 默认值
            key_actions=[],
        ))
    
    # 获取预计时长
    op_params = llm_mission.get("operation_parameters", {})
    duration = op_params.get("max_flight_time_min") or op_params.get("max_operation_time_min", 30)
    
    # 处理飞行高度（可能是数字或数组）
    altitude = op_params.get("flight_altitude_m", "")
    if isinstance(altitude, list):
        altitude = "/".join(str(a) for a in altitude) + "m"
    elif altitude:
        altitude = str(altitude) + "m"
    else:
        altitude = "地面"
    
    # 任务目标：支持多种字段名
    mission_objective = (
        llm_mission.get("task_objective") or 
        llm_mission.get("task_target") or 
        llm_mission.get("mission_objective", "")
    )
    
    # 侦察重点：支持多种字段名
    recon_focus = (
        llm_mission.get("recon_focus") or 
        llm_mission.get("reconnaissance_focus", [])
    )
    
    # 侦察方法：支持多种字段名
    recon_method = (
        llm_mission.get("recon_method") or 
        llm_mission.get("reconnaissance_method", "")
    )
    
    return MissionPlanOutput(
        mission_objective=mission_objective,
        recon_focus=recon_focus,
        recon_method=recon_method,
        route_description=llm_mission.get("route_description", ""),
        altitude_or_depth=altitude,
        estimated_duration_minutes=duration,
        steps=steps,
        coordination_notes=llm_mission.get("coordination", ""),
        safety_notes=llm_mission.get("safety_considerations", []),
        abort_conditions=llm_mission.get("abort_conditions", []),
    )


def _extract_plan_output(crew_output: Any) -> FullReconPlanOutput:
    """从 Crew 输出提取方案"""
    tasks_output = getattr(crew_output, "tasks_output", [])
    
    if not tasks_output:
        raise ValueError("Crew 未返回任务输出")
    
    task_output = tasks_output[0]
    
    if hasattr(task_output, "pydantic") and task_output.pydantic is not None:
        return task_output.pydantic
    
    if hasattr(task_output, "json_dict") and task_output.json_dict is not None:
        data = task_output.json_dict
        # 检查是否是数组格式（LLM 直接输出任务列表）
        if isinstance(data, list):
            return _convert_llm_array_to_full_plan(data)
        return FullReconPlanOutput.model_validate(data)
    
    # 从 raw 输出解析
    raw = getattr(task_output, "raw", None)
    if raw is None:
        raise ValueError("无法获取 Crew 输出")
    
    if isinstance(raw, dict):
        return FullReconPlanOutput.model_validate(raw)
    
    if isinstance(raw, list):
        return _convert_llm_array_to_full_plan(raw)
    
    # 尝试解析 JSON（带修复）
    text = str(raw).strip()
    
    # 第一次尝试：直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return _convert_llm_array_to_full_plan(data)
        if isinstance(data, dict):
            # 检查是否是 {"reconnaissance_plans": [...]} 格式
            if "reconnaissance_plans" in data and isinstance(data["reconnaissance_plans"], list):
                return _convert_llm_array_to_full_plan(data["reconnaissance_plans"])
            # 检查是否是 {"missions": [...]} 格式
            if "missions" in data and isinstance(data["missions"], list):
                # 可能已经是正确格式，尝试直接验证
                try:
                    return FullReconPlanOutput.model_validate(data)
                except Exception:
                    # 如果验证失败，尝试转换 missions
                    return _convert_llm_array_to_full_plan(data["missions"])
        return FullReconPlanOutput.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[Recon] 第一次 JSON 解析失败: {e}")
    
    # 第二次尝试：提取 JSON 数组或对象
    import re
    # 先尝试匹配数组
    array_match = re.search(r'\[[\s\S]*\]', text)
    if array_match:
        try:
            data = json.loads(array_match.group())
            if isinstance(data, list):
                return _convert_llm_array_to_full_plan(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[Recon] JSON 数组解析失败: {e}")
    
    # 尝试匹配对象
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        json_text = json_match.group()
        try:
            data = json.loads(json_text)
            return FullReconPlanOutput.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[Recon] JSON 对象解析失败: {e}")
        
        # 尝试修复 JSON
        try:
            fixed_text = _fix_json_string(json_text)
            data = json.loads(fixed_text)
            return FullReconPlanOutput.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[Recon] 修复后 JSON 解析失败: {e}")
    
    # 最后尝试：宽松解析，构造默认方案
    logger.error("[Recon] 无法解析 LLM 输出，返回空方案")
    return FullReconPlanOutput(
        summary="方案生成失败，请重试",
        total_duration_minutes=0,
        coordination_strategy="",
        communication_plan="",
        contingency_plan="",
        missions=[],
    )


def _convert_llm_array_to_full_plan(llm_missions: list) -> FullReconPlanOutput:
    """将 LLM 输出的任务数组转换为完整方案结构"""
    missions = []
    total_duration = 0
    
    for m in llm_missions:
        if isinstance(m, dict):
            mission = _convert_llm_mission_to_standard(m)
            missions.append(mission)
            total_duration += mission.estimated_duration_minutes
    
    # 生成摘要
    device_count = len(missions)
    drone_count = sum(1 for m in llm_missions if isinstance(m, dict) and "无人机" in m.get("device_name", ""))
    dog_count = sum(1 for m in llm_missions if isinstance(m, dict) and "机器狗" in m.get("device_name", ""))
    
    summary = f"共部署{device_count}台设备执行侦察任务"
    if drone_count > 0:
        summary += f"，其中{drone_count}台无人机"
    if dog_count > 0:
        summary += f"、{dog_count}台机器狗"
    summary += f"，预计总耗时{total_duration}分钟。"
    
    return FullReconPlanOutput(
        summary=summary,
        total_duration_minutes=total_duration,
        coordination_strategy="空中无人机先行获取宏观影像，地面机器狗进行细化搜索与结构评估，实现空地联动侦察。",
        communication_plan="采用专用数据链路传输，每台设备实时上报位置和状态。",
        contingency_plan="单设备失效时由邻近设备扩大搜索范围；遇恶劣天气立即中止空中任务。",
        missions=missions,
    )


def _build_recon_plan(
    plan_output: FullReconPlanOutput,
    assignments: List[DeviceAssignment],
    scenario_id: str,
) -> ReconPlan:
    """构建 ReconPlan 数据结构"""
    missions: List[ReconMission] = []
    
    for i, (assignment, mission_output) in enumerate(
        zip(assignments, plan_output.missions, strict=False)
    ):
        steps: List[ReconMissionStep] = []
        for j, step in enumerate(mission_output.steps):
            steps.append(
                ReconMissionStep(
                    step_id=f"step-{i+1}-{j+1}",
                    step_name=step.step_name,
                    description=step.description,
                    duration_minutes=step.duration_minutes,
                    key_actions=step.key_actions,
                )
            )
        
        missions.append(
            ReconMission(
                mission_id=f"mission-{i+1}",
                device_id=assignment.get("device_id", ""),
                device_name=assignment.get("device_name", ""),
                device_type=assignment.get("device_type", ""),
                target_id=assignment.get("target_id", ""),
                target_name=assignment.get("target_name", ""),
                priority=assignment.get("priority", "medium"),
                mission_objective=mission_output.mission_objective,
                recon_focus=mission_output.recon_focus,
                recon_method=mission_output.recon_method,
                route_description=mission_output.route_description,
                altitude_or_depth=mission_output.altitude_or_depth,
                estimated_duration_minutes=mission_output.estimated_duration_minutes,
                steps=steps,
                coordination_notes=mission_output.coordination_notes,
                handoff_conditions="发现重要情况立即上报指挥中心",
                safety_notes=mission_output.safety_notes,
                abort_conditions=mission_output.abort_conditions,
            )
        )
    
    return ReconPlan(
        plan_id=str(uuid4()),
        scenario_id=scenario_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        summary=plan_output.summary,
        total_duration_minutes=plan_output.total_duration_minutes,
        phase_count=1,  # 简化为单阶段
        missions=missions,
        coordination_strategy=plan_output.coordination_strategy,
        communication_plan=plan_output.communication_plan,
        contingency_plan=plan_output.contingency_plan,
        phases=[{"phase_id": "phase-1", "name": "首次侦察", "missions": [m["mission_id"] for m in missions]}],
    )


__all__ = ["generate_recon_plan"]
