"""
Jinja2模板系统

提供7个资源相关模块(1-4, 6-8)的报告渲染模板。
输出格式符合ICS应急管理标准。
"""

from src.agents.overall_plan.templates.modules import (
    render_module_template,
    MODULE_TEMPLATES,
)

__all__ = [
    "render_module_template",
    "MODULE_TEMPLATES",
]
