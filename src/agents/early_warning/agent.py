"""
预警监测智能体

提供预警处理的高级API。
"""
import logging
from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime

from .state import create_initial_state, EarlyWarningState
from .graph import early_warning_graph

logger = logging.getLogger(__name__)


class EarlyWarningAgent:
    """
    预警监测智能体
    
    职责：
    1. 接收灾害数据更新
    2. 分析对车辆和队伍的影响
    3. 生成预警决策
    4. 通过WebSocket推送预警
    """
    
    def __init__(self):
        self.graph = early_warning_graph
    
    def process_disaster_update(
        self,
        disaster_data: Dict[str, Any],
        scenario_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理灾害数据更新
        
        Args:
            disaster_data: 灾害数据（包含boundary、disaster_type等）
            scenario_id: 想定ID
            request_id: 请求ID（可选，自动生成）
            
        Returns:
            处理结果，包含：
            - success: 是否成功
            - warnings_generated: 生成的预警数量
            - notifications_sent: 发送的通知数量
            - summary: 处理摘要
            - errors: 错误列表
        """
        if not request_id:
            request_id = str(uuid4())
        
        logger.info(f"[EarlyWarningAgent] Processing disaster update, request_id={request_id}")
        
        start_time = datetime.utcnow()
        
        # 创建初始状态
        initial_state = create_initial_state(
            request_id=request_id,
            scenario_id=scenario_id,
            disaster_input=disaster_data,
        )
        
        try:
            # 执行图
            final_state = self.graph.invoke(initial_state)
            
            # 计算执行时间
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # 构建结果
            result = {
                "success": final_state.get("success", False),
                "request_id": request_id,
                "disaster_id": final_state.get("disaster_situation", {}).get("id") if final_state.get("disaster_situation") else None,
                "warnings_generated": len(final_state.get("warning_records", [])),
                "affected_vehicles": len(final_state.get("affected_vehicles", [])),
                "affected_teams": len(final_state.get("affected_teams", [])),
                "notifications_sent": final_state.get("notifications_sent", 0),
                "summary": final_state.get("summary", ""),
                "errors": final_state.get("errors", []),
                "execution_time_ms": execution_time_ms,
                "trace": final_state.get("trace", {}),
            }
            
            logger.info(
                f"[EarlyWarningAgent] Completed: warnings={result['warnings_generated']}, "
                f"notifications={result['notifications_sent']}, time={execution_time_ms}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[EarlyWarningAgent] Error processing disaster update: {e}")
            return {
                "success": False,
                "request_id": request_id,
                "warnings_generated": 0,
                "notifications_sent": 0,
                "summary": f"Processing failed: {str(e)}",
                "errors": [str(e)],
            }
    
    def get_warning_level(self, distance_m: float) -> str:
        """
        根据距离获取预警级别
        
        Args:
            distance_m: 距离（米）
            
        Returns:
            预警级别: red/orange/yellow/blue
        """
        if distance_m < 1000:
            return "red"
        elif distance_m < 3000:
            return "orange"
        elif distance_m < 5000:
            return "yellow"
        else:
            return "blue"


# 全局实例
_early_warning_agent: Optional[EarlyWarningAgent] = None


def get_early_warning_agent() -> EarlyWarningAgent:
    """获取预警监测智能体实例（单例）"""
    global _early_warning_agent
    if _early_warning_agent is None:
        _early_warning_agent = EarlyWarningAgent()
    return _early_warning_agent
