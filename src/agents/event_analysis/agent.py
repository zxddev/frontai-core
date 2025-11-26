"""
事件分析Agent

封装事件分析LangGraph，提供对外接口
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

from ..base import BaseAgent
from .state import EventAnalysisState
from .graph import build_event_analysis_graph

logger = logging.getLogger(__name__)


class EventAnalysisAgent(BaseAgent[EventAnalysisState]):
    """
    事件分析Agent
    
    功能:
    1. 灾情评估 - 评估灾情等级、影响范围、预估伤亡
    2. 次生灾害预测 - 预测火灾、滑坡等次生灾害风险
    3. 损失估算 - 估算经济损失和基础设施损毁
    4. 确认评分 - 计算确认评分，决定事件状态流转
    
    使用示例:
    ```python
    agent = EventAnalysisAgent()
    result = agent.run(
        event_id="550e8400-e29b-41d4-a716-446655440000",
        scenario_id="scenario-uuid",
        disaster_type="earthquake",
        location={"longitude": 104.0657, "latitude": 30.5728},
        initial_data={"magnitude": 5.5, "depth_km": 10},
        source_system="110",
        source_trust_level=0.95,
        is_urgent=True,
        estimated_victims=20,
        priority="critical",
    )
    ```
    """
    
    def __init__(self) -> None:
        """初始化事件分析Agent"""
        super().__init__(name="EventAnalysisAgent")
    
    def build_graph(self) -> CompiledStateGraph:
        """构建LangGraph"""
        workflow = build_event_analysis_graph()
        return workflow.compile()
    
    def prepare_input(self, **kwargs: Any) -> EventAnalysisState:
        """
        准备输入状态
        
        Args:
            event_id: 事件ID
            scenario_id: 想定ID
            disaster_type: 灾害类型 (earthquake/flood/hazmat/fire/landslide)
            location: 位置 {"longitude": float, "latitude": float}
            initial_data: 灾害参数
            source_system: 来源系统
            source_type: 来源类型
            source_trust_level: 来源可信度
            is_urgent: 是否紧急
            estimated_victims: 预估被困人数
            priority: 优先级
            context: 上下文信息
            nearby_events: 邻近事件列表
            
        Returns:
            初始化的状态
        """
        # 处理位置
        location = kwargs.get("location", {})
        if isinstance(location, dict):
            location_state = {
                "longitude": location.get("longitude", location.get("lng", 0)),
                "latitude": location.get("latitude", location.get("lat", 0)),
            }
        else:
            location_state = {"longitude": 0, "latitude": 0}
        
        # 处理ID（确保是字符串）
        event_id = kwargs.get("event_id", "")
        if isinstance(event_id, UUID):
            event_id = str(event_id)
        
        scenario_id = kwargs.get("scenario_id", "")
        if isinstance(scenario_id, UUID):
            scenario_id = str(scenario_id)
        
        state: EventAnalysisState = {
            "event_id": event_id,
            "scenario_id": scenario_id,
            "disaster_type": kwargs.get("disaster_type", "earthquake"),
            "location": location_state,
            "initial_data": kwargs.get("initial_data", {}),
            "source_system": kwargs.get("source_system", "unknown"),
            "source_type": kwargs.get("source_type", "manual_report"),
            "source_trust_level": float(kwargs.get("source_trust_level", 0.5)),
            "is_urgent": bool(kwargs.get("is_urgent", False)),
            "estimated_victims": int(kwargs.get("estimated_victims", 0)),
            "priority": kwargs.get("priority", "medium"),
            "context": kwargs.get("context", {}),
            "nearby_events": kwargs.get("nearby_events", []),
            "assessment_result": None,
            "secondary_hazards": None,
            "loss_estimation": None,
            "ai_confidence": 0.0,
            "confirmation_decision": None,
            "recommended_actions": [],
            "urgency_score": 0.0,
        }
        
        return state
    
    def process_output(self, state: EventAnalysisState) -> Dict[str, Any]:
        """
        处理输出结果
        
        Args:
            state: 最终状态
            
        Returns:
            格式化的API响应
        """
        # 提取确认决策
        confirmation = state.get("confirmation_decision", {})
        
        # 构造事件状态更新信息
        event_status_update = {
            "previous_status": "pending",
            "new_status": confirmation.get("recommended_status", "pending"),
            "auto_confirmed": confirmation.get("auto_confirmed", False),
        }
        
        # 如果是预确认状态，添加预确认信息
        if confirmation.get("recommended_status") == "pre_confirmed":
            from datetime import timedelta
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            event_status_update["pre_confirmation"] = {
                "countdown_expires_at": expires_at.isoformat() + "Z",
                "countdown_minutes": 30,
                "pre_allocated_resources": [],  # 由后续流程填充
                "pre_generated_scheme_id": None,
                "auto_escalate_if_timeout": True,
            }
        
        # 构造完整响应
        result = {
            "success": True,
            "task_id": state.get("task_id", ""),
            "event_id": state.get("event_id", ""),
            "status": "completed",
            "analysis_result": {
                "disaster_level": state.get("assessment_result", {}).get("disaster_level"),
                "disaster_level_color": state.get("assessment_result", {}).get("disaster_level_color"),
                "response_level": state.get("assessment_result", {}).get("response_level"),
                "ai_confidence": state.get("ai_confidence", 0),
                "assessment": state.get("assessment_result"),
                "secondary_hazards": state.get("secondary_hazards", []),
                "loss_estimation": state.get("loss_estimation"),
                "urgency_score": state.get("urgency_score", 0),
                "recommended_actions": state.get("recommended_actions", []),
            },
            "confirmation_decision": confirmation,
            "event_status_update": event_status_update,
            "trace": state.get("trace", {}),
            "errors": state.get("errors", []),
            "created_at": state.get("started_at").isoformat() + "Z" if state.get("started_at") else None,
            "completed_at": state.get("completed_at").isoformat() + "Z" if state.get("completed_at") else None,
        }
        
        return result
