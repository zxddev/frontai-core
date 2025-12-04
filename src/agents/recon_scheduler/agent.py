"""
侦察调度智能体 (ReconSchedulerAgent)

完整的救灾侦察调度系统，调度前突车队对内的无人设备，
生成侦察航线和执行计划。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .graph import get_recon_scheduler_graph
from .state import ReconSchedulerState

logger = logging.getLogger(__name__)

# 全局单例
_agent_instance: Optional["ReconSchedulerAgent"] = None


class ReconSchedulerAgent:
    """
    侦察调度智能体
    
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
    
    def __init__(self):
        """初始化Agent"""
        self._graph = None
        logger.info("ReconSchedulerAgent 初始化")
    
    @property
    def graph(self):
        """懒加载图"""
        if self._graph is None:
            self._graph = get_recon_scheduler_graph()
        return self._graph
    
    async def schedule(
        self,
        event_id: str,
        scenario_id: str,
        recon_request: str,
        target_area: Optional[Dict[str, Any]] = None,
        disaster_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行侦察调度
        
        Args:
            event_id: 事件ID
            scenario_id: 场景ID
            recon_request: 侦察需求描述
            target_area: 目标区域（GeoJSON格式）
            disaster_context: 灾情上下文（来自EmergencyAI，可选）
        
        Returns:
            完整的侦察计划
        """
        logger.info(f"开始侦察调度: event_id={event_id}, scenario_id={scenario_id}")
        logger.info(f"侦察需求: {recon_request[:100]}...")
        
        # 构建初始状态
        initial_state: ReconSchedulerState = {
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
        }
        
        try:
            # 执行图
            result = await self.graph.ainvoke(initial_state)
            
            # 提取结果
            recon_plan = result.get("recon_plan", {})
            
            logger.info(f"侦察调度完成: plan_id={recon_plan.get('plan_id', 'N/A')}")
            
            return {
                "success": True,
                "plan_id": recon_plan.get("plan_id"),
                "recon_plan": recon_plan,
                "execution_package": result.get("execution_package"),
                "flight_files": result.get("flight_files", []),
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
                "phase_history": result.get("phase_history", []),
            }
            
        except Exception as e:
            logger.exception(f"侦察调度失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "errors": [str(e)],
                "warnings": [],
            }
    
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
