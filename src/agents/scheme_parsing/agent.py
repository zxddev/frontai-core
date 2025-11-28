"""
SchemeParsingAgent

将修改后的方案文本解析为结构化数据。
使用 with_structured_output 保证LLM输出格式。
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .schemas import ParsedScheme, ParsedTask, TeamAssignment

logger = logging.getLogger(__name__)


def _get_llm(max_tokens: int = 4096) -> ChatOpenAI:
    """获取LLM客户端实例"""
    llm_model = os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    openai_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    request_timeout = int(os.environ.get('REQUEST_TIMEOUT', '180'))
    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        timeout=request_timeout,
        max_tokens=max_tokens,
        max_retries=0,
    )


TASK_TYPE_MAPPING = {
    "生命探测": "EM06",
    "无人机侦察": "EM01",
    "现场评估": "EM03",
    "被困人员救援": "EM10",
    "人员搜救": "EM10",
    "伤员急救": "EM14",
    "医疗救治": "EM14",
    "火灾扑救": "EM07",
    "灭火": "EM07",
    "危化品处置": "EM08",
    "疏散群众": "EM15",
    "交通管制": "EM16",
    "物资配送": "EM17",
    "通信保障": "EM18",
    "心理援助": "EM19",
    "现场警戒": "EM20",
    "遗体处置": "EM21",
}


SYSTEM_PROMPT = """你是应急救灾方案解析专家。你的任务是将自然语言方案文本解析为结构化数据。

【解析规则】
1. 任务识别：从文本中识别所有救援任务，包括任务名称、负责队伍、优先级
2. 队伍提取：识别所有参与救援的队伍及其负责的任务
3. 依赖关系：根据文本描述推断任务之间的依赖关系（如"在XX之后"、"依赖XX"）
4. 时间信息：提取预计到达时间、任务时长等时间信息

【任务类型代码映射】
- 生命探测 → EM06
- 无人机侦察 → EM01
- 现场评估 → EM03
- 被困人员救援/人员搜救 → EM10
- 伤员急救/医疗救治 → EM14
- 火灾扑救/灭火 → EM07
- 危化品处置 → EM08
- 疏散群众 → EM15
- 交通管制 → EM16
- 物资配送 → EM17
- 其他任务 → EM99

【优先级判断】
- critical（紧急）：涉及生命安全、黄金救援时间内的任务
- high（高）：次生灾害控制、重要支援任务
- medium（中）：常规救援任务
- low（低）：后勤保障、善后任务

【注意事项】
- 如果信息不完整，在warnings中说明
- 根据上下文推断缺失信息，并降低confidence
- 保持任务名称与原文一致"""


HUMAN_PROMPT = """请解析以下方案文本：

【方案文本】
{scheme_text}

【可用救援队伍参考】（如果方案中提到的队伍不在此列表中，照常解析）
{available_teams}

请输出结构化的解析结果。"""


class SchemeParsingAgent:
    """
    方案解析智能体
    
    将方案文本解析为结构化数据，使用 with_structured_output 保证格式。
    
    Example:
        ```python
        agent = SchemeParsingAgent()
        result = await agent.parse(
            scheme_text="根据灾情分析，调派XX救援队...",
            available_teams=[{"name": "XX救援队", "capabilities": [...]}]
        )
        print(result.tasks)
        ```
    """
    
    def __init__(self, max_tokens: int = 4096) -> None:
        self._llm = _get_llm(max_tokens)
        self._structured_llm = self._llm.with_structured_output(ParsedScheme)
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ])
        self._chain = self._prompt | self._structured_llm
    
    async def parse(
        self,
        scheme_text: str,
        available_teams: Optional[List[Dict[str, Any]]] = None,
    ) -> ParsedScheme:
        """
        解析方案文本
        
        Args:
            scheme_text: 方案文本（可能被用户编辑过）
            available_teams: 可用救援队伍列表（可选，用于参考）
            
        Returns:
            ParsedScheme结构化结果
        """
        logger.info(f"开始解析方案文本，长度={len(scheme_text)}")
        
        # 格式化可用队伍信息
        teams_info = "无"
        if available_teams:
            team_strs = []
            for team in available_teams:
                name = team.get("name") or team.get("resource_name", "未知")
                caps = team.get("capabilities", [])
                team_strs.append(f"- {name}: {', '.join(caps[:3]) if caps else '综合救援'}")
            teams_info = "\n".join(team_strs)
        
        try:
            result: ParsedScheme = await self._chain.ainvoke({
                "scheme_text": scheme_text,
                "available_teams": teams_info,
            })
            
            # 后处理：补充任务类型代码
            for task in result.tasks:
                if not task.task_type or task.task_type == "unknown":
                    task.task_type = self._infer_task_type(task.task_name)
            
            logger.info(
                f"方案解析完成: {len(result.tasks)}个任务, "
                f"{len(result.team_assignments)}个队伍, "
                f"置信度={result.parsing_confidence:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"方案解析失败: {e}")
            # 返回降级结果
            return ParsedScheme(
                tasks=[],
                team_assignments=[],
                parsing_confidence=0.0,
                warnings=[f"解析失败: {str(e)}"],
                raw_summary="解析失败，请检查方案文本格式",
            )
    
    def _infer_task_type(self, task_name: str) -> str:
        """根据任务名称推断任务类型代码"""
        for keyword, code in TASK_TYPE_MAPPING.items():
            if keyword in task_name:
                return code
        return "EM99"


async def parse_scheme_text(
    scheme_text: str,
    available_teams: Optional[List[Dict[str, Any]]] = None,
) -> ParsedScheme:
    """
    便捷函数：解析方案文本
    
    Args:
        scheme_text: 方案文本
        available_teams: 可用救援队伍列表
        
    Returns:
        ParsedScheme结构化结果
    """
    agent = SchemeParsingAgent()
    return await agent.parse(scheme_text, available_teams)
