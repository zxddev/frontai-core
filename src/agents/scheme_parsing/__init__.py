"""
方案解析智能体

将方案文本解析为结构化的任务和队伍分配数据。
使用 with_structured_output 保证LLM输出格式。
"""
from __future__ import annotations

from .agent import SchemeParsingAgent, parse_scheme_text
from .schemas import ParsedTask, ParsedScheme, TeamAssignment

__all__ = [
    "SchemeParsingAgent",
    "parse_scheme_text",
    "ParsedTask",
    "ParsedScheme",
    "TeamAssignment",
]
