"""侦察调度配置模块"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_CONFIG_DIR = Path(__file__).parent


def load_config(name: str) -> Dict[str, Any]:
    """加载配置文件"""
    config_path = _CONFIG_DIR / f"{name}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_disaster_scenarios() -> Dict[str, Any]:
    """获取灾情场景配置"""
    return load_config("disaster_scenarios")


def get_weather_rules() -> Dict[str, Any]:
    """获取天气规则配置"""
    return load_config("weather_rules")


def get_scan_patterns() -> Dict[str, Any]:
    """获取扫描模式配置"""
    return load_config("scan_patterns")


def get_contingency_plans() -> Dict[str, Any]:
    """获取应急预案配置"""
    return load_config("contingency_plans")
