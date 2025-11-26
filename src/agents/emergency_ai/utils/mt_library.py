"""
元任务库加载器

加载并解析config/emergency/mt_library.json，提供任务链配置查询。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


# ============================================================================
# 类型定义
# ============================================================================

class TaskChainConfig(TypedDict):
    """任务链配置"""
    name: str                                  # 任务链名称
    description: str                           # 任务链描述
    tasks: List[str]                           # 任务ID列表
    dependencies: Dict[str, List[str]]         # 任务依赖关系 {task_id: [depends_on]}
    parallel_groups: List[List[str]]           # 可并行执行的任务组


class SceneDefinition(TypedDict):
    """场景定义"""
    name: str                                  # 场景名称
    description: str                           # 场景描述
    triggers: List[str]                        # 触发条件
    typical_tasks: List[str]                   # 典型任务列表
    priority_objectives: List[str]             # 优先目标


class MTLibraryConfig(TypedDict):
    """元任务库完整配置"""
    version: str
    updated_at: str
    domain: str
    unit_decl: Dict[str, str]
    phase_definitions: Dict[str, str]
    scene_definitions: Dict[str, SceneDefinition]
    mt_library: List[Dict[str, Any]]
    task_dependencies: Dict[str, TaskChainConfig]


# ============================================================================
# 场景到任务链的映射
# ============================================================================

SCENE_TO_CHAIN: Dict[str, str] = {
    "S1": "earthquake_main_chain",      # 地震主灾
    "S2": "secondary_fire_chain",       # 次生火灾
    "S3": "hazmat_chain",               # 危化品泄漏
    "S4": "flood_debris_chain",         # 山洪泥石流
    "S5": "waterlogging_chain",         # 暴雨内涝
}


# ============================================================================
# 配置加载函数
# ============================================================================

@lru_cache(maxsize=1)
def load_mt_library() -> MTLibraryConfig:
    """
    加载元任务库配置
    
    从config/emergency/mt_library.json加载配置，使用lru_cache缓存避免重复IO。
    
    Returns:
        元任务库完整配置
        
    Raises:
        FileNotFoundError: 配置文件不存在
        json.JSONDecodeError: 配置文件格式错误
    """
    config_path = Path(__file__).parents[4] / "config" / "emergency" / "mt_library.json"
    
    if not config_path.exists():
        logger.error(f"元任务库配置文件不存在: {config_path}")
        raise FileNotFoundError(f"元任务库配置文件不存在: {config_path}")
    
    logger.info(f"加载元任务库配置: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config: MTLibraryConfig = json.load(f)
    
    # 验证必要字段
    required_fields = ["mt_library", "task_dependencies", "scene_definitions"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"元任务库配置缺少必要字段: {field}")
    
    logger.info(
        f"元任务库加载完成: {len(config['mt_library'])}个元任务, "
        f"{len(config['task_dependencies'])}条任务链"
    )
    
    return config


def get_chain_for_scene(scene_code: str) -> Optional[TaskChainConfig]:
    """
    获取场景对应的任务链配置
    
    Args:
        scene_code: 场景代码，如"S1"
        
    Returns:
        任务链配置，如果场景代码无效返回None
    """
    chain_name = SCENE_TO_CHAIN.get(scene_code)
    if chain_name is None:
        logger.warning(f"未知的场景代码: {scene_code}")
        return None
    
    config = load_mt_library()
    chain = config["task_dependencies"].get(chain_name)
    
    if chain is None:
        logger.warning(f"任务链配置不存在: {chain_name}")
        return None
    
    return chain


def get_meta_task(task_id: str) -> Optional[Dict[str, Any]]:
    """
    获取元任务详情
    
    Args:
        task_id: 任务ID，如"EM06"
        
    Returns:
        元任务配置字典，如果任务ID无效返回None
    """
    config = load_mt_library()
    
    for task in config["mt_library"]:
        if task.get("id") == task_id:
            return task
    
    logger.warning(f"元任务不存在: {task_id}")
    return None


def get_all_chains() -> Dict[str, TaskChainConfig]:
    """
    获取所有任务链配置
    
    Returns:
        任务链配置字典
    """
    config = load_mt_library()
    return config["task_dependencies"]


def get_scene_definition(scene_code: str) -> Optional[SceneDefinition]:
    """
    获取场景定义
    
    Args:
        scene_code: 场景代码，如"S1"
        
    Returns:
        场景定义，如果场景代码无效返回None
    """
    config = load_mt_library()
    return config["scene_definitions"].get(scene_code)
