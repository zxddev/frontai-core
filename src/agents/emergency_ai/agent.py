"""
EmergencyAIAgent主类

封装LangGraph流程，提供统一的分析接口。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal

from .state import create_initial_state, EmergencyAIState
from .graph import get_emergency_ai_graph

logger = logging.getLogger(__name__)


class EmergencyAIAgent:
    """
    应急救灾AI+规则混合Agent
    
    集成LLM/RAG/知识图谱/规则引擎，实现5阶段智能决策：
    1. 灾情理解：LLM语义解析 + RAG案例增强
    2. 规则推理：KG规则查询 + TRR引擎匹配
    2.5. HTN任务分解：场景识别 + 任务链合并 + Kahn拓扑排序
    3. 资源匹配：数据库查询 + NSGA-II多目标优化
    4. 方案优化：硬/软规则过滤 + 5维评估(成功率0.35) + LLM解释生成
    
    5维评估权重（严格对齐军事版）：
    - 成功率: 0.35 (人命关天，最高权重)
    - 响应时间: 0.30 (黄金救援期72小时)
    - 覆盖率: 0.20 (全区域覆盖)
    - 风险: 0.05 (生命优先于风险规避)
    - 冗余性: 0.10 (备用资源保障)
    
    Example:
        ```python
        agent = EmergencyAIAgent()
        result = await agent.analyze(
            event_id="evt-001",
            scenario_id="scn-001",
            disaster_description="XX市发生5.5级地震，多栋建筑倒塌，预计30人被困",
        )
        ```
    """
    
    def __init__(self) -> None:
        """初始化Agent"""
        self._graph = get_emergency_ai_graph()
        logger.info("EmergencyAIAgent初始化完成")
    
    async def analyze(
        self,
        event_id: str,
        scenario_id: str,
        disaster_description: str,
        structured_input: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        optimization_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        执行应急分析
        
        Args:
            event_id: 事件ID
            scenario_id: 想定ID
            disaster_description: 灾情描述（自然语言）
            structured_input: 结构化输入（位置、时间等）
            constraints: 约束条件
            optimization_weights: 优化权重配置
            
        Returns:
            分析结果，包含：
            - success: 是否成功
            - understanding: 灾情理解结果
            - reasoning: 规则推理结果
            - htn_decomposition: HTN任务分解结果（scene_codes, task_sequence, parallel_tasks）
            - matching: 资源匹配结果
            - optimization: 方案优化结果（5维评估得分）
            - recommended_scheme: 推荐方案
            - scheme_explanation: 方案解释
            - trace: 执行追踪
            - errors: 错误列表
        """
        logger.info(
            "开始应急AI分析",
            extra={
                "event_id": event_id,
                "scenario_id": scenario_id,
                "description_length": len(disaster_description),
            }
        )
        start_time = time.time()
        
        # 创建初始状态
        initial_state = create_initial_state(
            event_id=event_id,
            scenario_id=scenario_id,
            disaster_description=disaster_description,
            structured_input=structured_input,
            constraints=constraints,
            optimization_weights=optimization_weights,
        )
        
        # 执行图
        try:
            final_state = await self._graph.ainvoke(initial_state)
        except Exception as e:
            logger.exception("EmergencyAI执行失败", extra={"error": str(e)})
            return {
                "success": False,
                "event_id": event_id,
                "scenario_id": scenario_id,
                "status": "failed",
                "errors": [str(e)],
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        
        # 获取最终输出
        result = final_state.get("final_output", {})
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "应急AI分析完成",
            extra={
                "event_id": event_id,
                "success": result.get("success", False),
                "elapsed_ms": elapsed_ms,
            }
        )
        
        # 确保执行时间正确
        result["execution_time_ms"] = elapsed_ms
        
        return result
    
    async def analyze_and_save(
        self,
        event_id: str,
        scenario_id: str,
        disaster_description: str,
        structured_input: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        optimization_weights: Optional[Dict[str, float]] = None,
        db_session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        执行应急分析并保存决策日志
        
        Args:
            event_id: 事件ID
            scenario_id: 想定ID
            disaster_description: 灾情描述
            structured_input: 结构化输入
            constraints: 约束条件
            optimization_weights: 优化权重
            db_session: 数据库会话（可选）
            
        Returns:
            分析结果
        """
        # 执行分析
        result = await self.analyze(
            event_id=event_id,
            scenario_id=scenario_id,
            disaster_description=disaster_description,
            structured_input=structured_input,
            constraints=constraints,
            optimization_weights=optimization_weights,
        )
        
        # 保存决策日志
        if db_session:
            await self._save_decision_log(
                db_session=db_session,
                event_id=event_id,
                scenario_id=scenario_id,
                result=result,
            )
        
        return result
    
    async def _save_decision_log(
        self,
        db_session: Any,
        event_id: str,
        scenario_id: str,
        result: Dict[str, Any],
    ) -> None:
        """保存AI决策日志到数据库"""
        try:
            from src.domains.ai_decisions import (
                AIDecisionLogRepository,
                CreateAIDecisionLogRequest,
            )
            
            repo = AIDecisionLogRepository(db_session)
            
            # 提取推荐方案的置信度
            recommended = result.get("recommended_scheme", {})
            confidence = recommended.get("total_score") if recommended else None
            
            log_data = CreateAIDecisionLogRequest(
                scenario_id=UUID(scenario_id),
                event_id=UUID(event_id),
                scheme_id=None,
                decision_type="emergency_ai_analysis",
                algorithm_used="LLM+RAG+KG+Rules",
                input_snapshot={
                    "disaster_description": result.get("understanding", {}).get("summary", ""),
                    "constraints": result.get("constraints", {}),
                },
                output_result={
                    "success": result.get("success"),
                    "matched_rules_count": len(result.get("reasoning", {}).get("matched_rules", [])),
                    "recommended_scheme_id": recommended.get("solution_id") if recommended else None,
                },
                confidence_score=Decimal(str(confidence)) if confidence else None,
                reasoning_chain=result.get("trace", {}),
                processing_time_ms=result.get("execution_time_ms"),
            )
            
            await repo.create(log_data)
            await db_session.commit()
            
            logger.info(
                "AI决策日志保存成功",
                extra={"event_id": event_id, "decision_type": "emergency_ai_analysis"}
            )
            
        except Exception as e:
            logger.error("AI决策日志保存失败", extra={"event_id": event_id, "error": str(e)})
            # 不阻塞主流程


# 单例实例
_agent_instance: Optional[EmergencyAIAgent] = None


def get_emergency_ai_agent() -> EmergencyAIAgent:
    """获取EmergencyAIAgent单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = EmergencyAIAgent()
    return _agent_instance
