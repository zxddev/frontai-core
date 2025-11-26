"""
前端API适配层

为前端提供兼容原Java后端的接口格式，内部调用v2 API服务层。
短期方案：快速对接前端
长期方案：前端逐步迁移到v2 API后废弃此模块
"""

from .router import frontend_router

__all__ = ["frontend_router"]
