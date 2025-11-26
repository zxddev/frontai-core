"""
HTN任务分解节点

基于mt_library.json的任务链配置进行任务分解，支持多场景组合和并行任务调度。
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
    load_mt_library,
    get_chain_for_scene,
    get_meta_task,
    TaskChainConfig,
    SCENE_TO_CHAIN,
)
from ..tools.kg_tools import query_task_dependencies_async

logger = logging.getLogger(__name__)


# ============================================================================
# 场景识别
# ============================================================================

def _identify_scenes(parsed_disaster: ParsedDisasterInfo) -> List[str]:
    """
    根据灾情分析结果识别场景
    
    Args:
        parsed_disaster: LLM解析的灾情信息
        
    Returns:
        场景代码列表，如["S1", "S2"]
    """
    scenes: List[str] = []
    disaster_type = parsed_disaster.get("disaster_type", "").lower()
    
    # 详细日志：输入参数
    logger.info(f"[HTN-场景识别] 输入参数:")
    logger.info(f"  - disaster_type: {disaster_type}")
    logger.info(f"  - has_secondary_fire: {parsed_disaster.get('has_secondary_fire')}")
    logger.info(f"  - has_hazmat_leak: {parsed_disaster.get('has_hazmat_leak')}")
    logger.info(f"  - severity: {parsed_disaster.get('severity')}")
    logger.info(f"  - estimated_trapped: {parsed_disaster.get('estimated_trapped')}")
    
    # 地震相关场景
    if disaster_type == "earthquake" or "地震" in disaster_type:
        scenes.append("S1")  # 地震主灾
        logger.info(f"[HTN-场景识别] 识别到地震场景 -> 添加S1")
        
        # 检查次生灾害
        if parsed_disaster.get("has_secondary_fire"):
            scenes.append("S2")  # 次生火灾
            logger.info(f"[HTN-场景识别] 存在次生火灾 -> 添加S2")
        if parsed_disaster.get("has_hazmat_leak"):
            scenes.append("S3")  # 危化品泄漏
            logger.info(f"[HTN-场景识别] 存在危化品泄漏 -> 添加S3")
    
    # 洪水/泥石流场景
    if disaster_type in ["flood", "debris_flow", "landslide"] or "洪" in disaster_type or "泥石流" in disaster_type or "滑坡" in disaster_type:
        scenes.append("S4")  # 山洪泥石流
        logger.info(f"[HTN-场景识别] 识别到洪水/泥石流/滑坡 -> 添加S4")
    
    # 暴雨内涝场景
    if disaster_type == "waterlogging" or "内涝" in disaster_type or "暴雨" in disaster_type:
        scenes.append("S5")  # 暴雨内涝
        logger.info(f"[HTN-场景识别] 识别到暴雨内涝 -> 添加S5")
    
    # 火灾场景（非地震次生）
    if disaster_type == "fire" and "S2" not in scenes:
        scenes.append("S2")  # 火灾处置链
        logger.info(f"[HTN-场景识别] 识别到独立火灾 -> 添加S2")
    
    # 危化品泄漏（非地震次生）
    if disaster_type == "hazmat" and "S3" not in scenes:
        scenes.append("S3")  # 危化品处置链
        logger.info(f"[HTN-场景识别] 识别到独立危化品泄漏 -> 添加S3")
    
    # 默认场景
    if not scenes:
        logger.warning(f"[HTN-场景识别] 无法识别场景，灾害类型: {disaster_type}，使用默认S1")
        scenes.append("S1")
    
    logger.info(f"[HTN-场景识别] 最终识别场景: {scenes}")
    return scenes


# ============================================================================
# 任务链合并
# ============================================================================

def _merge_chains(chains: List[TaskChainConfig]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    合并多条任务链
    
    复合灾害时需要执行多条任务链，合并任务和依赖关系。
    
    Args:
        chains: 任务链配置列表
        
    Returns:
        (合并后的任务列表, 合并后的依赖关系)
    """
    logger.info(f"[HTN-合并] 开始合并{len(chains)}条任务链")
    
    all_tasks: Set[str] = set()
    merged_deps: Dict[str, List[str]] = {}
    
    for chain in chains:
        chain_name = chain.get("name", "未知")
        chain_tasks = chain.get("tasks", [])
        chain_deps = chain.get("dependencies", {})
        logger.info(f"[HTN-合并] 处理任务链: {chain_name}")
        logger.info(f"  - 任务数: {len(chain_tasks)}")
        logger.info(f"  - 依赖关系数: {len(chain_deps)}")
        logger.info(f"  - 任务列表: {chain_tasks}")
        
        # 合并任务
        all_tasks.update(chain_tasks)
        
        # 合并依赖关系
        for task_id, deps in chain_deps.items():
            if task_id in merged_deps:
                # 已有依赖，合并去重
                existing = set(merged_deps[task_id])
                existing.update(deps)
                merged_deps[task_id] = list(existing)
            else:
                merged_deps[task_id] = list(deps)
    
    logger.info(f"[HTN-合并] 合并完成:")
    logger.info(f"  - 总任务数: {len(all_tasks)}")
    logger.info(f"  - 总依赖关系数: {len(merged_deps)}")
    logger.info(f"  - 合并后任务: {sorted(all_tasks)}")
    
    return list(all_tasks), merged_deps


def _identify_parallel_tasks(chains: List[TaskChainConfig]) -> List[ParallelTaskGroup]:
    """
    识别可并行执行的任务组
    
    Args:
        chains: 任务链配置列表
        
    Returns:
        并行任务组列表
    """
    logger.info(f"[HTN-并行识别] 开始识别可并行任务")
    
    parallel_groups: List[ParallelTaskGroup] = []
    seen_groups: Set[frozenset] = set()
    group_index = 0
    
    for chain in chains:
        chain_name = chain.get("name", "未知")
        chain_parallel = chain.get("parallel_groups", [])
        logger.info(f"[HTN-并行识别] 检查任务链: {chain_name}, 配置并行组数: {len(chain_parallel)}")
        
        for group_tasks in chain_parallel:
            # 去重：相同任务组只保留一个
            group_key = frozenset(group_tasks)
            if group_key in seen_groups:
                logger.info(f"  - 跳过重复组: {group_tasks}")
                continue
            seen_groups.add(group_key)
            
            # 生成并行组
            group_index += 1
            reason = _get_parallel_reason(group_tasks)
            group = ParallelTaskGroup(
                group_id=f"PG-{group_index:02d}",
                task_ids=list(group_tasks),
                reason=reason,
            )
            parallel_groups.append(group)
            logger.info(f"  - 发现并行组: PG-{group_index:02d} = {group_tasks}")
            logger.info(f"    原因: {reason}")
    
    logger.info(f"[HTN-并行识别] 完成，共{len(parallel_groups)}个并行组")
    return parallel_groups


def _get_parallel_reason(task_ids: List[str]) -> str:
    """获取并行原因描述"""
    # 根据任务类型推断
    if all(tid.startswith("EM0") for tid in task_ids):
        task_categories = set()
        for tid in task_ids:
            meta = get_meta_task(tid)
            if meta:
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
    HTN任务分解节点
    
    根据灾情分析结果识别场景，加载对应的任务链配置，
    进行拓扑排序生成正确的任务执行序列。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[HTN分解] 开始执行，event_id={state['event_id']}")
    start_time = time.time()
    
    errors: List[str] = list(state.get("errors", []))
    trace: Dict[str, Any] = dict(state.get("trace", {}))
    
    # 检查前置条件
    parsed_disaster = state.get("parsed_disaster")
    if parsed_disaster is None:
        error_msg = "HTN分解失败：缺少灾情解析结果"
        logger.error(f"[HTN分解] {error_msg}")
        errors.append(error_msg)
        return {
            "scene_codes": [],
            "task_sequence": [],
            "parallel_tasks": [],
            "errors": errors,
            "trace": trace,
        }
    
    # 步骤1：场景识别
    scene_codes = _identify_scenes(parsed_disaster)
    logger.info(f"[HTN分解] 识别场景: {scene_codes}")
    
    # 步骤2：加载任务链配置
    chains: List[TaskChainConfig] = []
    for scene_code in scene_codes:
        chain = get_chain_for_scene(scene_code)
        if chain:
            chains.append(chain)
            logger.info(f"[HTN分解] 加载任务链: {chain['name']}")
    
    if not chains:
        error_msg = f"未找到场景对应的任务链: {scene_codes}"
        logger.error(f"[HTN分解] {error_msg}")
        errors.append(error_msg)
        return {
            "scene_codes": scene_codes,
            "task_sequence": [],
            "parallel_tasks": [],
            "errors": errors,
            "trace": trace,
        }
    
    # 步骤3：合并多条任务链
    merged_tasks, merged_deps = _merge_chains(chains)
    logger.info(f"[HTN分解] 合并后任务数: {len(merged_tasks)}")
    
    # 步骤4：拓扑排序
    try:
        sorted_tasks = topological_sort(merged_tasks, merged_deps)
    except ValueError as e:
        error_msg = f"任务拓扑排序失败: {e}"
        logger.error(f"[HTN分解] {error_msg}")
        errors.append(error_msg)
        return {
            "scene_codes": scene_codes,
            "task_sequence": [],
            "parallel_tasks": [],
            "errors": errors,
            "trace": trace,
        }
    
    # 步骤5：识别并行任务
    parallel_groups = _identify_parallel_tasks(chains)
    parallel_task_ids: Set[str] = set()
    task_to_group: Dict[str, str] = {}
    for group in parallel_groups:
        for task_id in group["task_ids"]:
            parallel_task_ids.add(task_id)
            task_to_group[task_id] = group["group_id"]
    
    # 步骤6：查询Neo4j补充golden_hour
    golden_hours: Dict[str, Optional[int]] = {}
    try:
        kg_result = await query_task_dependencies_async(sorted_tasks)
        for item in kg_result:
            task_code = item.get("task_code")
            golden_hours[task_code] = item.get("golden_hour")
        logger.info(f"[HTN分解] 从Neo4j获取golden_hour: {len(golden_hours)}个任务")
    except Exception as e:
        logger.warning(f"[HTN分解] Neo4j查询失败，跳过golden_hour: {e}")
    
    # 步骤7：构建任务序列
    task_sequence: List[TaskSequenceItem] = []
    for idx, task_id in enumerate(sorted_tasks, start=1):
        meta = get_meta_task(task_id)
        task_name = meta["name"] if meta else task_id
        phase = meta["phase"] if meta else "unknown"
        
        item = TaskSequenceItem(
            task_id=task_id,
            task_name=task_name,
            sequence=idx,
            depends_on=merged_deps.get(task_id, []),
            golden_hour=golden_hours.get(task_id),
            phase=phase,
            is_parallel=task_id in parallel_task_ids,
            parallel_group_id=task_to_group.get(task_id),
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
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[HTN分解] 完成，场景{scene_codes}，{len(task_sequence)}个任务，"
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
