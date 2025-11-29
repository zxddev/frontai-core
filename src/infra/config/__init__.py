"""
算法配置服务模块

提供从数据库加载算法参数的能力，支持：
- 地区/部门定制化配置
- 无Fallback设计（配置缺失时明确报错）
- Redis缓存加速
"""

from src.infra.config.algorithm_config_service import (
    AlgorithmConfigService,
    ConfigurationMissingError,
)

__all__ = [
    "AlgorithmConfigService",
    "ConfigurationMissingError",
]
