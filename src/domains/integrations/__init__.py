"""
第三方数据接入模块

提供灾情上报、传感器告警、设备遥测、天气数据的统一接入能力。
"""

from .router import router as integrations_router

__all__ = ["integrations_router"]
