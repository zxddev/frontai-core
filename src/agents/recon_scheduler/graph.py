"""
侦察调度智能体 LangGraph流程定义

完整的10阶段侦察调度流程：
1. 灾情深度理解
2. 环境约束评估
3. 资源盘点
4. 任务规划
5. 资源分配
6. 航线规划
7. 时间线编排
8. 风险评估
9. 计划校验
10. 输出生成
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END

from .state import ReconSchedulerState

logger = logging.getLogger(__name__)

# 最大调整次数（防止无限循环）
MAX_ADJUSTMENT_COUNT = 3


def should_continue_after_environment(state: ReconSchedulerState) -> Literal["resource_inventory", "output_generation"]:
    """
    判断环境评估后是否继续
    
    如果飞行条件为black（禁飞），直接生成输出。
    """
    flight_condition = state.get("flight_condition", "green")
    if flight_condition == "black":
        logger.warning("飞行条件为禁飞(black)，跳转到输出")
        return "output_generation"
    return "resource_inventory"


def should_continue_after_allocation(state: ReconSchedulerState) -> Literal["flight_planning", "plan_adjustment", "output_generation"]:
    """
    判断资源分配后是否继续
    
    - 如果有未分配任务且调整次数未超限，进入调整
    - 如果调整次数超限，直接输出（带警告）
    - 如果分配成功，继续航线规划
    """
    unallocated = state.get("unallocated_tasks", [])
    adjustment_count = state.get("adjustment_count", 0)
    errors = state.get("errors", [])
    
    if errors:
        logger.error(f"资源分配出错: {errors}")
        return "output_generation"
    
    if unallocated:
        if adjustment_count >= MAX_ADJUSTMENT_COUNT:
            logger.warning(f"调整次数已达上限({MAX_ADJUSTMENT_COUNT})，带警告输出")
            return "output_generation"
        logger.info(f"有{len(unallocated)}个任务未分配，进入计划调整")
        return "plan_adjustment"
    
    return "flight_planning"


def should_continue_after_validation(state: ReconSchedulerState) -> Literal["output_generation", "plan_adjustment", "handle_error"]:
    """
    判断计划校验后是否继续
    
    - 校验通过，生成输出
    - 校验有警告但可接受，生成输出
    - 校验失败但可调整，进入调整
    - 校验有严重错误，进入错误处理
    """
    validation = state.get("validation_result")
    adjustment_count = state.get("adjustment_count", 0)
    
    if validation is None:
        logger.error("校验结果为空")
        return "handle_error"
    
    if validation.get("is_valid"):
        return "output_generation"
    
    # 检查是否有严重错误
    critical_errors = [e for e in validation.get("validation_errors", []) 
                       if e.get("severity") == "critical"]
    if critical_errors:
        logger.error(f"存在严重错误: {critical_errors}")
        return "handle_error"
    
    # 可调整的错误
    if adjustment_count >= MAX_ADJUSTMENT_COUNT:
        logger.warning("调整次数已达上限，带警告输出")
        return "output_generation"
    
    return "plan_adjustment"


def build_recon_scheduler_graph() -> StateGraph:
    """
    构建侦察调度智能体状态图
    
    流程：
    ```
    START
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 1: 灾情深度理解               │
    │ - 识别灾情类型和严重程度            │
    │ - 评估黄金救援时间                  │
    │ - 识别优先目标                      │
    └─────────────────────────────────────┘
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 2: 环境约束评估               │
    │ - 天气条件评估                      │
    │ - 空域限制检查                      │
    │ - 地形障碍识别                      │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 飞行条件可接受?)
    ┌─────────────────────────────────────┐
    │ Phase 3: 资源盘点                   │
    │ - 可用设备清单                      │
    │ - 设备能力评估                      │
    │ - 就绪时间估计                      │
    └─────────────────────────────────────┘
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 4: 任务规划                   │
    │ - 分阶段任务定义                    │
    │ - 任务优先级排序                    │
    │ - 任务依赖关系                      │
    └─────────────────────────────────────┘
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 5: 资源分配                   │
    │ - 设备-任务匹配                     │
    │ - 约束检查                          │
    │ - 备份方案                          │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 分配完成?)
    ┌─────────────────────────────────────┐
    │ Phase 6: 航线规划 ⭐                 │
    │ - 扫描模式选择                      │
    │ - 航点序列生成                      │
    │ - 航线优化                          │
    └─────────────────────────────────────┘
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 7: 时间线编排                 │
    │ - 任务时序安排                      │
    │ - 关键路径分析                      │
    │ - 里程碑定义                        │
    └─────────────────────────────────────┘
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 8: 风险评估                   │
    │ - 风险识别                          │
    │ - 应急预案                          │
    │ - 检查清单                          │
    └─────────────────────────────────────┘
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 9: 计划校验                   │
    │ - 覆盖完整性                        │
    │ - 资源冲突检查                      │
    │ - 安全检查                          │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 校验通过?)
    ┌─────────────────────────────────────┐
    │ Phase 10: 输出生成                  │
    │ - 完整侦察计划                      │
    │ - 航线文件                          │
    │ - 执行包                            │
    └─────────────────────────────────────┘
      │
      ▼
    END
    
    (plan_adjustment 节点用于处理分配失败或校验失败的情况)
    ```
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建ReconScheduler LangGraph...")
    
    # 延迟导入节点函数（避免循环依赖）
    from .nodes import (
        disaster_analysis_node,
        environment_assessment_node,
        resource_inventory_node,
        mission_planning_node,
        resource_allocation_node,
        flight_planning_node,
        timeline_scheduling_node,
        risk_assessment_node,
        plan_validation_node,
        output_generation_node,
    )
    
    # 创建状态图
    workflow = StateGraph(ReconSchedulerState)
    
    # ========== 添加节点 ==========
    
    # Phase 1: 灾情深度理解
    workflow.add_node("disaster_analysis", disaster_analysis_node)
    
    # Phase 2: 环境约束评估
    workflow.add_node("environment_assessment", environment_assessment_node)
    
    # Phase 3: 资源盘点
    workflow.add_node("resource_inventory", resource_inventory_node)
    
    # Phase 4: 任务规划
    workflow.add_node("mission_planning", mission_planning_node)
    
    # Phase 5: 资源分配
    workflow.add_node("resource_allocation", resource_allocation_node)
    
    # Phase 6: 航线规划
    workflow.add_node("flight_planning", flight_planning_node)
    
    # Phase 7: 时间线编排
    workflow.add_node("timeline_scheduling", timeline_scheduling_node)
    
    # Phase 8: 风险评估
    workflow.add_node("risk_assessment", risk_assessment_node)
    
    # Phase 9: 计划校验
    workflow.add_node("plan_validation", plan_validation_node)
    
    # Phase 10: 输出生成
    workflow.add_node("output_generation", output_generation_node)
    
    # 辅助节点
    workflow.add_node("plan_adjustment", plan_adjustment_node)
    workflow.add_node("handle_error", handle_error_node)
    
    # ========== 定义边 ==========
    
    # START → Phase 1
    workflow.add_edge(START, "disaster_analysis")
    
    # Phase 1 → Phase 2
    workflow.add_edge("disaster_analysis", "environment_assessment")
    
    # Phase 2 → Phase 3 (conditional: 飞行条件)
    workflow.add_conditional_edges(
        "environment_assessment",
        should_continue_after_environment,
        {
            "resource_inventory": "resource_inventory",
            "output_generation": "output_generation",
        }
    )
    
    # Phase 3 → Phase 4
    workflow.add_edge("resource_inventory", "mission_planning")
    
    # Phase 4 → Phase 5
    workflow.add_edge("mission_planning", "resource_allocation")
    
    # Phase 5 → Phase 6 (conditional: 分配结果)
    workflow.add_conditional_edges(
        "resource_allocation",
        should_continue_after_allocation,
        {
            "flight_planning": "flight_planning",
            "plan_adjustment": "plan_adjustment",
            "output_generation": "output_generation",
        }
    )
    
    # Phase 6 → Phase 7
    workflow.add_edge("flight_planning", "timeline_scheduling")
    
    # Phase 7 → Phase 8
    workflow.add_edge("timeline_scheduling", "risk_assessment")
    
    # Phase 8 → Phase 9
    workflow.add_edge("risk_assessment", "plan_validation")
    
    # Phase 9 → Phase 10 (conditional: 校验结果)
    workflow.add_conditional_edges(
        "plan_validation",
        should_continue_after_validation,
        {
            "output_generation": "output_generation",
            "plan_adjustment": "plan_adjustment",
            "handle_error": "handle_error",
        }
    )
    
    # 调整节点 → 重新进入资源分配
    workflow.add_edge("plan_adjustment", "resource_allocation")
    
    # 错误处理 → 输出
    workflow.add_edge("handle_error", "output_generation")
    
    # 输出 → END
    workflow.add_edge("output_generation", END)
    
    logger.info("ReconScheduler LangGraph构建完成")
    
    return workflow


def plan_adjustment_node(state: ReconSchedulerState) -> dict:
    """
    计划调整节点
    
    处理分配失败或校验失败的情况，尝试调整计划。
    """
    logger.info("进入计划调整节点")
    
    adjustment_count = state.get("adjustment_count", 0) + 1
    unallocated = state.get("unallocated_tasks", [])
    validation_errors = []
    
    if state.get("validation_result"):
        validation_errors = state["validation_result"].get("validation_errors", [])
    
    warnings = state.get("warnings", [])
    
    # 记录调整原因
    if unallocated:
        warnings.append(f"第{adjustment_count}次调整: 有{len(unallocated)}个任务未分配，尝试降级任务优先级")
    
    if validation_errors:
        warnings.append(f"第{adjustment_count}次调整: 校验发现{len(validation_errors)}个问题，尝试调整计划")
    
    # 调整策略：
    # 1. 降低低优先级任务的要求
    # 2. 移除无法满足的任务
    # 3. 合并相似任务
    
    adjusted_tasks = []
    all_tasks = state.get("all_tasks", [])
    
    for task in all_tasks:
        if task.get("task_id") in unallocated:
            # 尝试降低要求
            if task.get("priority") == "low":
                # 低优先级任务直接移除
                warnings.append(f"移除无法分配的低优先级任务: {task.get('task_name')}")
                continue
            else:
                # 降低设备要求
                task_copy = task.copy()
                if task_copy.get("device_requirements"):
                    reqs = task_copy["device_requirements"].copy()
                    # 扩展设备类型偏好
                    if "type_preference" in reqs:
                        reqs["type_preference"] = reqs["type_preference"] + ["multirotor"]
                    task_copy["device_requirements"] = reqs
                adjusted_tasks.append(task_copy)
        else:
            adjusted_tasks.append(task)
    
    return {
        "all_tasks": adjusted_tasks,
        "adjustment_count": adjustment_count,
        "warnings": warnings,
        "unallocated_tasks": [],  # 清空，重新分配
        "current_phase": "plan_adjustment",
    }


def handle_error_node(state: ReconSchedulerState) -> dict:
    """
    错误处理节点
    
    处理严重错误，生成错误报告。
    """
    logger.error("进入错误处理节点")
    
    errors = state.get("errors", [])
    validation_result = state.get("validation_result")
    
    if validation_result:
        critical_errors = [e for e in validation_result.get("validation_errors", [])
                         if e.get("severity") == "critical"]
        for err in critical_errors:
            errors.append(f"严重错误: {err.get('message')}")
    
    return {
        "errors": errors,
        "current_phase": "error",
    }


# 编译图（懒加载）
_compiled_graph = None


def get_recon_scheduler_graph():
    """获取编译后的图（单例）"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_recon_scheduler_graph()
        _compiled_graph = workflow.compile()
        logger.info("ReconScheduler图编译完成")
    return _compiled_graph
