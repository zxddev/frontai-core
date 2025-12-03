"""
阶段5: 仿真闭环节点

将生成的救援方案输入到生命体征仿真引擎中进行验证，
计算预期的生存率和可预防死亡数。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from src.planning.algorithms.simulation.discrete_event_sim import DiscreteEventSimulator, AlgorithmStatus
from ..state import EmergencyAIState

logger = logging.getLogger(__name__)


async def run_simulation(state: EmergencyAIState) -> Dict[str, Any]:
    """
    仿真闭环节点：运行生命体征仿真
    
    1. 从推荐方案中提取资源配置
    2. 从HTN任务序列中提取任务配置
    3. 运行多智能体生命仿真 (ABM)
    4. 将仿真结果（生存率、可预防死亡）回写到最终输出
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    event_id = state["event_id"]
    recommended_scheme = state.get("recommended_scheme")
    
    if not recommended_scheme:
        logger.warning("无推荐方案，跳过仿真闭环", extra={"event_id": event_id})
        return {}
        
    logger.info("执行仿真闭环节点", extra={"event_id": event_id})
    start_time = time.time()
    
    try:
        # 1. 准备仿真输入数据
        sim_tasks = _prepare_sim_tasks(state)
        sim_resources = _prepare_sim_resources(recommended_scheme, state)
        sim_scenario = _prepare_sim_scenario(state)
        
        problem = {
            "tasks": sim_tasks,
            "resources": sim_resources,
            "scenario": sim_scenario,
            "simulation_time": 48 * 60, # 48小时
            "monte_carlo_runs": 30      # 30次蒙特卡洛
        }
        
        # 2. 执行仿真
        simulator = DiscreteEventSimulator()
        result = simulator.run(problem)
        
        if result.status == AlgorithmStatus.SUCCESS:
            solution = result.solution
            summary = solution.get("summary", {})
            
            logger.info(
                "仿真完成",
                extra={
                    "survival_rate": summary.get("avg_survival_rate"),
                    "preventable_deaths": summary.get("avg_preventable_deaths"),
                    "completion_time": summary.get("avg_completion_time_min")
                }
            )
            
            # 3. 更新方案评分和解释
            # 将仿真得出的生存率作为"置信度"或"预期效果"的补充
            simulation_result = {
                "survival_rate": summary.get("avg_survival_rate"),
                "preventable_deaths": summary.get("avg_preventable_deaths"),
                "survival_quality": summary.get("avg_survival_quality"),
                "completion_time_hours": round(summary.get("avg_completion_time_min", 0) / 60, 1)
            }
            
            # 更新最终输出
            final_output = state.get("final_output", {})
            final_output["simulation_result"] = simulation_result
            
            # 如果有方案解释，追加仿真结论
            scheme_explanation = state.get("scheme_explanation", "")
            if scheme_explanation:
                sim_text = (
                    f"\n\n## 十二、数字孪生推演结论\n"
                    f"经多智能体生命仿真（ABM）验证，本方案预期效果如下：\n"
                    f"- **预期生存率**: {simulation_result['survival_rate']*100:.1f}%\n"
                    f"- **可预防死亡**: {simulation_result['preventable_deaths']:.1f}人 (需重点关注)\n"
                    f"- **平均生存质量**: {simulation_result['survival_quality']:.1f}/100\n"
                    f"- **预计完工时间**: {simulation_result['completion_time_hours']}小时\n"
                )
                scheme_explanation += sim_text
            
            # 更新追踪信息
            trace = state.get("trace", {})
            trace["phases_executed"] = trace.get("phases_executed", []) + ["run_simulation"]
            trace["simulation_metrics"] = simulation_result
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                "final_output": final_output,
                "scheme_explanation": scheme_explanation,
                "trace": trace,
                "current_phase": "simulation_completed"
            }
            
        else:
            logger.warning(f"仿真执行失败: {result.message}")
            return {}
            
    except Exception as e:
        logger.error(f"仿真闭环异常: {e}", exc_info=True)
        return {}


def _prepare_sim_tasks(state: EmergencyAIState) -> List[Dict[str, Any]]:
    """准备仿真任务数据"""
    task_sequence = state.get("task_sequence", [])
    sim_tasks = []
    
    # 获取事件位置作为默认任务位置
    structured_input = state.get("structured_input", {})
    loc = structured_input.get("location", {})
    default_loc = [float(loc.get("longitude", 0)), float(loc.get("latitude", 0))]
    
    for task in task_sequence:
        # 根据元任务类型推断参数
        # 这里简化处理，实际应查询知识图谱获取更详细参数
        sim_tasks.append({
            "id": task["task_id"],
            "name": task["task_name"],
            "duration_min": 120, # 默认2小时
            "success_prob": 0.9,
            "required_resources": {"RESCUE_TEAM": 1}, # 默认需求
            "predecessors": task.get("depends_on", []),
            "location": default_loc, # 暂时所有任务都在同一地点
            "coverage_radius": 1.0   # 1km半径
        })
        
    return sim_tasks


def _prepare_sim_resources(scheme: Dict[str, Any], state: EmergencyAIState) -> List[Dict[str, Any]]:
    """准备仿真资源数据"""
    sim_resources = []
    allocations = scheme.get("allocations", [])
    
    # 获取事件位置
    structured_input = state.get("structured_input", {})
    loc = structured_input.get("location", {})
    event_lon = float(loc.get("longitude", 0))
    event_lat = float(loc.get("latitude", 0))
    
    for alloc in allocations:
        # 简单的坐标偏移模拟资源初始位置 (实际应使用 alloc['distance_km'] 反推或查库)
        # 这里我们假设资源已经正在赶往现场，仿真关注的是到达后的作业
        # 为了让仿真器计算 travel time，我们需要设置一个基于 distance_km 的虚拟位置
        distance_km = alloc.get("distance_km", 0)
        # 简化：假设在正北方向 distance_km 处
        # 1度纬度 ≈ 111km
        offset_lat = distance_km / 111.0
        
        sim_resources.append({
            "id": alloc["resource_id"],
            "name": alloc["resource_name"],
            "type": "RESCUE_TEAM", # 简化类型匹配
            "speed_kmh": 60,       # 默认速度
            "location": [event_lon, event_lat + offset_lat]
        })
        
    return sim_resources


def _prepare_sim_scenario(state: EmergencyAIState) -> Dict[str, Any]:
    """准备仿真场景参数"""
    parsed_disaster = state.get("parsed_disaster", {})
    
    return {
        "initial_casualties": parsed_disaster.get("estimated_trapped", 50),
        "casualty_rate_per_hour": 0, # 已由 ABM 模型接管
        "disaster_type": parsed_disaster.get("disaster_type", "earthquake")
    }
