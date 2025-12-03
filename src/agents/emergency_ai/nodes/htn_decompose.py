"""
HTN任务分解节点

基于Neo4j知识图谱的Scene/TaskChain/MetaTask节点进行任务分解，
支持多场景组合和并行任务调度。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List, Optional, Set, Tuple

from ..state import (
    EmergencyAIState,
    ParsedDisasterInfo,
    TaskSequenceItem,
    ParallelTaskGroup,
)
from ..utils.mt_library import (
    get_meta_task,
    TaskChainConfig,
)
from ..tools.kg_tools import (
    query_task_dependencies_async,
    query_scene_by_disaster_async,
    query_task_chain_async,
    query_metatask_dependencies_async,
    query_metatask_details_async,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 场景识别（Neo4j驱动）
# ============================================================================

async def _identify_scenes_from_kg(parsed_disaster: ParsedDisasterInfo) -> List[str]:
    """
    根据灾情分析结果从Neo4j查询匹配的场景
    
    Args:
        parsed_disaster: LLM解析的灾情信息
        
    Returns:
        场景代码列表，如["S1", "S2"]
        
    Raises:
        RuntimeError: Neo4j查询失败
    """
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    
    conditions = {
        "has_secondary_fire": parsed_disaster.get("has_secondary_fire", False),
        "has_hazmat_leak": parsed_disaster.get("has_hazmat_leak", False),
        "has_building_collapse": parsed_disaster.get("has_building_collapse", False),
    }
    
    logger.info(f"[HTN-场景识别] 从Neo4j查询场景")
    logger.info(f"  - disaster_type: {disaster_type}")
    logger.info(f"  - conditions: {conditions}")
    
    scene_results = await query_scene_by_disaster_async(
        disaster_type=disaster_type,
        conditions=conditions,
    )
    
    if not scene_results:
        raise RuntimeError(
            f"Neo4j未返回匹配场景: disaster_type={disaster_type}, conditions={conditions}"
        )
    
    scene_codes = [s["scene_code"] for s in scene_results]
    scene_names = [s["scene_name"] for s in scene_results]
    
    logger.info(f"[HTN-场景识别] Neo4j返回场景: {scene_codes}")
    for s in scene_results:
        logger.info(f"  - {s['scene_code']}: {s['scene_name']}")
    
    return scene_codes


# ============================================================================
# 任务链加载与合并（Neo4j驱动）
# ============================================================================

async def _load_chains_from_kg(scene_codes: List[str]) -> List[Dict[str, Any]]:
    """
    从Neo4j加载场景对应的任务链配置
    
    Args:
        scene_codes: 场景代码列表
        
    Returns:
        任务链配置列表
        
    Raises:
        RuntimeError: 如果任何场景没有对应的任务链
    """
    chains: List[Dict[str, Any]] = []
    
    for scene_code in scene_codes:
        chain = await query_task_chain_async(scene_code)
        if chain is None:
            raise RuntimeError(f"Neo4j未找到场景{scene_code}对应的任务链")
        chains.append(chain)
        logger.info(f"[HTN-加载] 从Neo4j加载任务链: {chain['chain_name']} ({len(chain['tasks'])}个任务)")
    
    return chains


async def _merge_chains_with_kg_deps(
    chains: List[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    合并多条任务链，并从Neo4j查询依赖关系
    
    Args:
        chains: 从Neo4j加载的任务链配置列表
        
    Returns:
        (合并后的任务ID列表, Neo4j查询的依赖关系)
    """
    logger.info(f"[HTN-合并] 开始合并{len(chains)}条任务链")
    
    all_task_ids: Set[str] = set()
    
    for chain in chains:
        chain_name = chain.get("chain_name", "未知")
        chain_tasks = chain.get("tasks", [])
        task_ids = [t["task_id"] for t in chain_tasks]
        
        logger.info(f"[HTN-合并] 处理任务链: {chain_name}")
        logger.info(f"  - 任务数: {len(task_ids)}")
        logger.info(f"  - 任务列表: {task_ids}")
        
        all_task_ids.update(task_ids)
    
    task_list = list(all_task_ids)
    logger.info(f"[HTN-合并] 合并后任务: {sorted(task_list)}")
    
    # 从Neo4j查询MetaTask之间的DEPENDS_ON关系
    logger.info(f"[HTN-合并] 从Neo4j查询任务依赖关系...")
    merged_deps = await query_metatask_dependencies_async(task_list)
    
    logger.info(f"[HTN-合并] 合并完成:")
    logger.info(f"  - 总任务数: {len(task_list)}")
    logger.info(f"  - 总依赖关系数: {len(merged_deps)}")
    
    return task_list, merged_deps


def _identify_parallel_tasks_from_kg(
    chains: List[Dict[str, Any]],
    dependencies: Dict[str, List[str]],
) -> List[ParallelTaskGroup]:
    """
    基于Neo4j任务链和依赖关系识别可并行执行的任务组
    
    通过分析依赖关系，找出没有相互依赖的同phase任务作为并行组。
    
    Args:
        chains: 从Neo4j加载的任务链配置列表
        dependencies: 任务依赖关系字典
        
    Returns:
        并行任务组列表
    """
    logger.info(f"[HTN-并行识别] 开始识别可并行任务")
    
    # 按phase分组任务
    phase_tasks: Dict[str, List[str]] = {}
    for chain in chains:
        for task in chain.get("tasks", []):
            task_id = task["task_id"]
            phase = task.get("phase", "unknown")
            if phase not in phase_tasks:
                phase_tasks[phase] = []
            if task_id not in phase_tasks[phase]:
                phase_tasks[phase].append(task_id)
    
    parallel_groups: List[ParallelTaskGroup] = []
    group_index = 0
    
    # 对每个phase，找出没有相互依赖的任务组
    for phase, task_ids in phase_tasks.items():
        if len(task_ids) < 2:
            continue
        
        # 找出没有相互依赖的任务
        independent_tasks: List[str] = []
        for task_id in task_ids:
            task_deps = set(dependencies.get(task_id, []))
            # 检查是否与其他同phase任务有依赖
            has_phase_dep = bool(task_deps.intersection(set(task_ids)))
            if not has_phase_dep:
                independent_tasks.append(task_id)
        
        if len(independent_tasks) >= 2:
            group_index += 1
            reason = _get_parallel_reason(independent_tasks)
            group = ParallelTaskGroup(
                group_id=f"PG-{group_index:02d}",
                task_ids=independent_tasks,
                reason=reason,
            )
            parallel_groups.append(group)
            logger.info(f"[HTN-并行识别] 发现并行组: PG-{group_index:02d} ({phase}阶段)")
            logger.info(f"  - 任务: {independent_tasks}")
            logger.info(f"  - 原因: {reason}")
    
    logger.info(f"[HTN-并行识别] 完成，共{len(parallel_groups)}个并行组")
    return parallel_groups


def _get_parallel_reason(task_ids: List[str]) -> str:
    """根据任务类别推断并行执行的原因"""
    if all(tid.startswith("EM0") for tid in task_ids):
        task_categories: set[str] = set()
        for tid in task_ids:
            meta = get_meta_task(tid)
            task_categories.add(meta.get("category", ""))
        
        if "search_rescue" in task_categories or "sensing" in task_categories:
            return "探测类任务可同时执行，提高搜救效率"
        if "utility" in task_categories:
            return "基础设施控制任务可同时执行"
    
    return "任务间无依赖，可并行执行"


# ============================================================================
# 拓扑排序
# ============================================================================

def topological_sort(tasks: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
    """
    Kahn算法拓扑排序
    
    根据任务依赖关系生成正确的执行顺序。
    
    Args:
        tasks: 任务ID列表
        dependencies: 依赖关系 {task_id: [depends_on_task_ids]}
        
    Returns:
        排序后的任务ID列表
        
    Raises:
        ValueError: 检测到循环依赖
    """
    logger.info(f"[HTN-拓扑排序] Kahn算法开始")
    logger.info(f"  - 任务数: {len(tasks)}")
    logger.info(f"  - 依赖关系数: {len(dependencies)}")
    
    # 计算入度
    in_degree: Dict[str, int] = {task: 0 for task in tasks}
    
    for task_id in tasks:
        deps = dependencies.get(task_id, [])
        for dep in deps:
            if dep in in_degree:
                in_degree[task_id] += 1
    
    # 日志：入度统计
    logger.info(f"[HTN-拓扑排序] 入度计算完成:")
    for task_id, degree in sorted(in_degree.items(), key=lambda x: x[1]):
        deps = dependencies.get(task_id, [])
        logger.info(f"  - {task_id}: 入度={degree}, 依赖={deps}")
    
    # 初始队列：入度为0的任务
    queue: List[str] = [t for t in tasks if in_degree[t] == 0]
    logger.info(f"[HTN-拓扑排序] 初始队列(入度=0): {queue}")
    
    result: List[str] = []
    step = 0
    
    while queue:
        # 取出入度为0的任务
        task = queue.pop(0)
        result.append(task)
        step += 1
        logger.info(f"[HTN-拓扑排序] 步骤{step}: 处理 {task}")
        
        # 更新后续任务的入度
        for other_task in tasks:
            if task in dependencies.get(other_task, []):
                in_degree[other_task] -= 1
                if in_degree[other_task] == 0:
                    queue.append(other_task)
                    logger.info(f"  - {other_task} 入度变为0，加入队列")
    
    # 检测循环依赖
    if len(result) != len(tasks):
        unresolved = [t for t in tasks if t not in result]
        logger.error(f"[HTN-拓扑排序] 检测到循环依赖，无法排序的任务: {unresolved}")
        raise ValueError(f"任务依赖存在循环: {unresolved}")
    
    logger.info(f"[HTN-拓扑排序] 排序完成，执行顺序: {result}")
    return result


# ============================================================================
# 主函数
# ============================================================================

async def htn_decompose(state: EmergencyAIState) -> Dict[str, Any]:
    """
    HTN任务分解节点（Neo4j驱动）
    
    从Neo4j知识图谱查询场景、任务链和依赖关系，
    进行拓扑排序生成正确的任务执行序列。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
        
    Raises:
        RuntimeError: Neo4j查询失败
    """
    logger.info(f"[HTN分解] 开始执行（Neo4j驱动），event_id={state['event_id']}")
    start_time = time.time()
    
    errors: List[str] = list(state.get("errors", []))
    trace: Dict[str, Any] = dict(state.get("trace", {}))
    
    # 检查前置条件
    parsed_disaster = state.get("parsed_disaster")
    if parsed_disaster is None:
        raise RuntimeError("HTN分解失败：缺少灾情解析结果")
    
    # 检查前置条件
    parsed_disaster = state.get("parsed_disaster")
    if parsed_disaster is None:
        raise RuntimeError("HTN分解失败：缺少灾情解析结果")
    
    # 步骤1：从Neo4j查询匹配场景
    scene_codes = await _identify_scenes_from_kg(parsed_disaster)
    logger.info(f"[HTN分解] Neo4j返回场景: {scene_codes}")
    
    # 步骤2：从Neo4j加载任务链配置
    chains = await _load_chains_from_kg(scene_codes)
    logger.info(f"[HTN分解] 加载{len(chains)}条任务链")
    
    # 步骤3：合并任务链，从Neo4j查询依赖关系
    merged_tasks, merged_deps = await _merge_chains_with_kg_deps(chains)
    logger.info(f"[HTN分解] 合并后任务数: {len(merged_tasks)}")
    
    # 步骤4：拓扑排序
    sorted_tasks = topological_sort(merged_tasks, merged_deps)
    
    # 步骤5：识别并行任务（基于Neo4j依赖关系）
    parallel_groups = _identify_parallel_tasks_from_kg(chains, merged_deps)
    parallel_task_ids: Set[str] = set()
    task_to_group: Dict[str, str] = {}
    for group in parallel_groups:
        for task_id in group["task_ids"]:
            parallel_task_ids.add(task_id)
            task_to_group[task_id] = group["group_id"]
    
    # 步骤6：从Neo4j查询MetaTask详情（包含golden_hour等）
    task_details = await query_metatask_details_async(sorted_tasks)
    logger.info(f"[HTN分解] 从Neo4j获取任务详情: {len(task_details)}个任务")
    
    # 构建任务ID到chain任务的映射（用于补充信息）
    chain_task_map: Dict[str, Dict[str, Any]] = {}
    for chain in chains:
        for task in chain.get("tasks", []):
            chain_task_map[task["task_id"]] = task
    
    # 步骤7：构建任务序列
    task_sequence: List[TaskSequenceItem] = []
    for idx, task_id in enumerate(sorted_tasks, start=1):
        # 从Neo4j获取MetaTask详情
        detail = task_details.get(task_id, {})
        chain_task = chain_task_map.get(task_id, {})
        meta = get_meta_task(task_id)
        
        task_name = detail.get("name") or chain_task.get("task_name") or meta["name"]
        phase = detail.get("phase") or chain_task.get("phase") or meta["phase"]
        
        item = TaskSequenceItem(
            task_id=task_id,
            task_name=task_name,
            sequence=idx,
            depends_on=merged_deps.get(task_id, []),
            golden_hour=None,  # MetaTask暂无golden_hour字段
            phase=phase,
            is_parallel=task_id in parallel_task_ids,
            parallel_group_id=task_to_group.get(task_id),
            required_capabilities=detail.get("required_capabilities", []),
        )
        task_sequence.append(item)
    
    # 更新追踪信息
    trace["phases_executed"] = trace.get("phases_executed", []) + ["htn_decompose"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + ["kahn_topological_sort"]
    trace["htn_decompose"] = {
        "scene_codes": scene_codes,
        "chains_merged": len(chains),
        "tasks_count": len(task_sequence),
        "parallel_groups_count": len(parallel_groups),
    }
    
    # 打印任务序列详情（含能力需求）
    logger.info(f"【HTN-任务序列】构建完成，共{len(task_sequence)}个任务:")
    for task in task_sequence:
        caps = task.get("required_capabilities", [])
        deps = task.get("depends_on", [])
        parallel = "并行" if task.get("is_parallel") else "串行"
        logger.info(f"  {task['sequence']}. {task['task_id']} ({task['task_name']}) [{parallel}]")
        logger.info(f"     需要能力: {caps}")
        if deps:
            logger.info(f"     前置依赖: {deps}")
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"【HTN分解】完成，场景{scene_codes}，{len(task_sequence)}个任务，"
        f"{len(parallel_groups)}个并行组，耗时{elapsed_ms}ms"
    )
    
    return {
        "scene_codes": scene_codes,
        "task_sequence": task_sequence,
        "parallel_tasks": parallel_groups,
        "trace": trace,
        "errors": errors,
        "current_phase": "htn_decompose",
    }


