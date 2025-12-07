"""
侦察调度智能体 (ReconSchedulerAgent)

完整的救灾侦察调度系统，调度前突车队对内的无人设备，
生成侦察航线和执行计划。

继承BaseAgent，遵循项目架构规范。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from langgraph.graph.state import CompiledStateGraph

from ..base.agent import BaseAgent
from .graph import get_recon_scheduler_graph
from .state import ReconSchedulerState

logger = logging.getLogger(__name__)

# 全局单例
_agent_instance: Optional["ReconSchedulerAgent"] = None


class ReconSchedulerAgent(BaseAgent[ReconSchedulerState]):
    """
    侦察调度智能体
    
    继承BaseAgent，实现标准Agent接口。
    
    负责:
    1. 灾情深度理解
    2. 环境约束评估（天气、空域、地形）
    3. 资源盘点与能力评估
    4. 侦察任务规划
    5. 设备-任务匹配
    6. 航线规划（Z字形/螺旋/环形等）
    7. 时间线编排
    8. 风险评估与应急预案
    9. 计划校验
    10. 输出生成（航线文件、执行包）
    """
    
    def __init__(self) -> None:
        """初始化Agent"""
        super().__init__(name="recon_scheduler")
        self.logger.info("ReconSchedulerAgent 初始化")
    
    def build_graph(self) -> CompiledStateGraph:
        """构建LangGraph状态图"""
        return get_recon_scheduler_graph()
    
    def prepare_input(self, **kwargs: Any) -> ReconSchedulerState:
        """
        准备初始状态
        
        Args:
            event_id: 事件ID
            scenario_id: 场景ID
            recon_request: 侦察需求描述
            target_area: 目标区域（GeoJSON格式）
            disaster_context: 灾情上下文
        
        Returns:
            初始化的ReconSchedulerState
        """
        event_id = kwargs.get("event_id", "")
        scenario_id = kwargs.get("scenario_id", "")
        recon_request = kwargs.get("recon_request", "")
        target_area = kwargs.get("target_area")
        disaster_context = kwargs.get("disaster_context")
        
        return {
            # 输入
            "event_id": event_id,
            "scenario_id": scenario_id,
            "recon_request": recon_request,
            "target_area": target_area,
            "disaster_context": disaster_context,
            
            # Phase outputs (初始为空)
            "disaster_analysis": None,
            "environment_assessment": None,
            "flight_condition": "green",
            "resource_inventory": None,
            "available_devices": [],
            "mission_phases": [],
            "all_tasks": [],
            "task_dependencies": {},
            "resource_allocation": None,
            "unallocated_tasks": [],
            "flight_plans": [],
            "timeline_scheduling": None,
            "milestones": [],
            "critical_path": [],
            "total_duration_min": 0,
            "risk_assessment": None,
            "contingency_plans": [],
            "overall_risk_level": "medium",
            "validation_result": None,
            "recon_plan": None,
            "execution_package": None,
            "flight_files": [],
            
            # 追踪
            "current_phase": "start",
            "phase_history": [],
            "errors": [],
            "warnings": [],
            "adjustment_count": 0,
            "trace": {
                "start_time": datetime.now().isoformat(),
                "request": recon_request,
            },
            
            # V2.1 新增: 重试控制
            "retry_count": 0,
            "max_retries": 3,
            "retry_history": [],
            
            # V2.1 新增: 验证状态
            "validation_level": None,
            "l1_result": None,
            "l2_result": None,
            
            # V2.1 新增: 流式事件
            "stream_events": [],
            "buffered_events": [],
            
            # V2.1 新增: 检查点
            "checkpoint": None,
            "saved_checkpoint_id": None,
            
            # V2.1 新增: 坐标系
            "utm_zone": None,
            "utm_hemisphere": None,
            "home_position_utm": None,
            "current_position_utm": None,
            "route_history": [],
            
            # V2.1 新增: 人工审批
            "approval_status": "not_required",
            "approval_request": None,
            "approval_timeout_s": 300,
            "degradation_options": [],
            "approved_degradation": None,
            
            # V2.1 新增: 安全模式
            "safe_mode_action": None,
            "rth_triggers": [],
            "signal_lost_since": None,
            
            # V2.1 新增: 熔断器状态
            "breaker_state": "closed",
            "fail_safe_triggered": False,
            "l1_breaker_failures": 0,
            "l2_breaker_failures": 0,
            
            # V2.1 新增: 恢复状态
            "is_resumed": False,
            "needs_replan": False,
            "resume_checkpoint_id": None,
            "resume_timestamp": None,
            
            # V2.1 新增: 能耗追踪
            "battery_percent": 95.0,
            "rth_required_percent": 20.0,
            "energy_consumed_percent": 0.0,
            
            # V2.1 新增: 通信状态
            "signal_dbm": -50.0,
            "last_ack_time": None,
            "relay_dwell_total_s": 0.0,
        }
    
    async def arun(self, **kwargs: Any) -> Dict[str, Any]:
        """
        异步执行Agent（覆盖基类方法，设置更高的递归限制）
        
        ReconScheduler有14个节点和复杂的条件边，需要更高的递归限制。
        """
        import time
        
        start_time = time.time()
        task_id = kwargs.get("task_id", f"task-{self.name}-{int(time.time())}")
        
        self.logger.info(
            "ReconScheduler开始异步执行",
            extra={"task_id": task_id, "input_keys": list(kwargs.keys())},
        )
        
        try:
            # 准备输入
            input_state = self.prepare_input(**kwargs)
            input_state["task_id"] = task_id
            input_state["started_at"] = datetime.now()
            input_state["trace"] = {
                **input_state.get("trace", {}),
                "algorithms_used": [],
                "nodes_executed": [],
            }
            
            # 异步执行图（使用更高的递归限制）
            final_state = await self.graph.ainvoke(
                input_state,
                config={"recursion_limit": 100}
            )
            
            # 记录完成时间
            final_state["completed_at"] = datetime.now()
            
            # 处理输出
            result = self.process_output(final_state)
            
            execution_time_ms = (time.time() - start_time) * 1000
            result["execution_time_ms"] = round(execution_time_ms, 2)
            
            self.logger.info(
                "ReconScheduler异步执行完成",
                extra={
                    "task_id": task_id,
                    "execution_time_ms": execution_time_ms,
                    "has_errors": len(final_state.get("errors", [])) > 0,
                },
            )
            
            return result
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.logger.exception(
                "ReconScheduler异步执行失败",
                extra={"task_id": task_id, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
                "errors": [str(e)],
                "warnings": [],
                "execution_time_ms": round(execution_time_ms, 2),
            }
    
    def process_output(self, state: ReconSchedulerState) -> Dict[str, Any]:
        """
        处理输出结果
        
        Args:
            state: 最终状态
            
        Returns:
            格式化的输出结果，包含成功判断
        """
        recon_plan = state.get("recon_plan", {})
        flight_plans = state.get("flight_plans", [])
        errors = state.get("errors", [])
        
        # 成功条件：有航线输出且无错误
        success = len(flight_plans) > 0 and len(errors) == 0
        
        if success:
            self.logger.info(f"侦察调度完成: plan_id={recon_plan.get('plan_id', 'N/A')}, 航线数={len(flight_plans)}")
        else:
            self.logger.warning(f"侦察调度失败: 航线数={len(flight_plans)}, 错误数={len(errors)}")
        
        return {
            "success": success,
            "plan_id": recon_plan.get("plan_id"),
            "recon_plan": recon_plan,
            "flight_plans": flight_plans,
            "execution_package": state.get("execution_package"),
            "flight_files": state.get("flight_files", []),
            "errors": errors,
            "warnings": state.get("warnings", []),
            "phase_history": state.get("phase_history", []),
            "l1_result": state.get("l1_result"),
            "l2_result": state.get("l2_result"),
            "breaker_state": state.get("breaker_state", "closed"),
            "retry_count": state.get("retry_count", 0),
        }
    
    async def schedule(
        self,
        event_id: str,
        scenario_id: str,
        recon_request: str,
        target_area: Optional[Dict[str, Any]] = None,
        disaster_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行侦察调度（便捷方法，内部调用arun）
        
        Args:
            event_id: 事件ID
            scenario_id: 场景ID
            recon_request: 侦察需求描述
            target_area: 目标区域（GeoJSON格式）
            disaster_context: 灾情上下文（来自EmergencyAI，可选）
        
        Returns:
            完整的侦察计划
        """
        self.logger.info(f"开始侦察调度: event_id={event_id}, scenario_id={scenario_id}")
        self.logger.info(f"侦察需求: {recon_request[:100]}...")
        
        return await self.arun(
            event_id=event_id,
            scenario_id=scenario_id,
            recon_request=recon_request,
            target_area=target_area,
            disaster_context=disaster_context,
        )
    
    async def quick_schedule(
        self,
        disaster_type: str,
        target_area: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        快速调度（简化接口）
        
        Args:
            disaster_type: 灾情类型 (earthquake_collapse/flood/fire/hazmat/landslide)
            target_area: 目标区域（GeoJSON或边界框）
            weather: 天气条件（可选，默认良好天气）
        
        Returns:
            侦察计划
        """
        # 构建上下文
        disaster_context = {
            "disaster_type": disaster_type,
            "weather": weather or {
                "wind_speed_ms": 5,
                "wind_direction_deg": 0,
                "rain_level": "none",
                "visibility_m": 10000,
                "temperature_c": 20,
            }
        }
        
        # 生成请求描述
        type_names = {
            "earthquake_collapse": "地震建筑倒塌",
            "flood": "洪涝灾害",
            "fire": "火灾",
            "hazmat": "危化品泄漏",
            "landslide": "山体滑坡",
        }
        type_name = type_names.get(disaster_type, disaster_type)
        recon_request = f"对{type_name}灾区进行全面侦察，搜索被困人员，评估灾情范围"
        
        return await self.schedule(
            event_id=f"evt-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            scenario_id="default",
            recon_request=recon_request,
            target_area=target_area,
            disaster_context=disaster_context,
        )
    
    def get_supported_disaster_types(self) -> Dict[str, str]:
        """获取支持的灾情类型"""
        return {
            "earthquake_collapse": "地震建筑倒塌",
            "flood": "洪涝灾害",
            "fire": "火灾",
            "hazmat": "危化品泄漏",
            "landslide": "山体滑坡",
        }
    
    def get_supported_scan_patterns(self) -> Dict[str, str]:
        """获取支持的扫描模式"""
        return {
            "zigzag": "Z字形扫描 - 适合大面积均匀覆盖",
            "spiral_inward": "向内螺旋 - 适合定点详查",
            "spiral_outward": "向外螺旋 - 适合从已知点展开搜索",
            "circular": "环形扫描 - 适合目标监视（火灾等）",
            "strip": "条带扫描 - 适合线性目标（道路、河流）",
            "grid": "网格扫描 - 适合高精度测绘",
        }


def get_recon_scheduler_agent() -> ReconSchedulerAgent:
    """
    获取ReconSchedulerAgent单例
    
    Returns:
        ReconSchedulerAgent实例
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReconSchedulerAgent()
    return _agent_instance
