"""
救援队伍位置查询模块

提供前端获取救援队伍实时位置的API接口
"""

from .router import router as team_location_router

__all__ = ["team_location_router"]
