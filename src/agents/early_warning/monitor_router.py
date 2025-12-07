"""
监控 API 路由

提供启动/停止/查询监控的 HTTP 接口
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .monitor_loop import get_monitor_manager, AlertLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["emergency-monitor"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class StartMonitorRequest(BaseModel):
    """启动监控请求"""
    task_id: str = Field(..., description="任务ID")
    event_id: str = Field(..., description="事件ID")
    scenario_id: Optional[str] = Field(None, description="想定ID")
    check_interval: float = Field(10.0, ge=1.0, le=300.0, description="检查间隔（秒）")


class MonitorStatusResponse(BaseModel):
    """监控状态响应"""
    task_id: str
    event_id: str
    scenario_id: Optional[str]
    running: bool
    started_at: Optional[str]
    check_interval: float
    watchers: List[Dict[str, Any]]
    total_alerts: int
    recent_alerts: List[Dict[str, Any]]


class AlertResponse(BaseModel):
    """告警响应"""
    type: str
    level: str
    title: str
    message: str
    data: Dict[str, Any]
    recommendation: Optional[str]
    created_at: str


class AlertHistoryResponse(BaseModel):
    """告警历史响应"""
    task_id: str
    total: int
    alerts: List[AlertResponse]


# ============================================================================
# API 端点
# ============================================================================

@router.post("/start", response_model=MonitorStatusResponse)
async def start_monitor(request: StartMonitorRequest):
    """
    启动对指定任务的持续监控
    
    监控内容：
    - 灾情变化（事件状态、优先级、受困人数）
    - 队伍进度（移动状态、延迟检测）
    - 路网状态（道路阻断、危险区域）
    
    告警会通过 WebSocket 实时推送到以下主题：
    - /topic/emergency.monitor.alert（通用告警）
    - /topic/emergency.monitor.{alert_type}（具体类型告警）
    """
    try:
        manager = get_monitor_manager()
        
        loop = await manager.start_monitor(
            task_id=request.task_id,
            event_id=request.event_id,
            scenario_id=request.scenario_id,
            check_interval=request.check_interval,
        )
        
        status = loop.get_status()
        return MonitorStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"启动监控失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{task_id}")
async def stop_monitor(task_id: str):
    """
    停止指定任务的监控
    """
    try:
        manager = get_monitor_manager()
        
        success = await manager.stop_monitor(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"未找到任务 {task_id} 的监控")
        
        return {"success": True, "message": f"监控 {task_id} 已停止"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止监控失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=MonitorStatusResponse)
async def get_monitor_status(task_id: str):
    """
    获取指定任务的监控状态
    """
    manager = get_monitor_manager()
    
    loop = manager.get_monitor(task_id)
    
    if not loop:
        raise HTTPException(status_code=404, detail=f"未找到任务 {task_id} 的监控")
    
    status = loop.get_status()
    return MonitorStatusResponse(**status)


@router.get("/list", response_model=List[MonitorStatusResponse])
async def list_monitors():
    """
    列出所有运行中的监控
    """
    manager = get_monitor_manager()
    
    statuses = manager.list_monitors()
    return [MonitorStatusResponse(**s) for s in statuses]


@router.get("/alerts/{task_id}", response_model=AlertHistoryResponse)
async def get_alert_history(
    task_id: str,
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    level: Optional[str] = Query(None, description="告警级别筛选（info/warning/critical）"),
    alert_type: Optional[str] = Query(None, description="告警类型筛选"),
):
    """
    获取指定任务的告警历史
    """
    manager = get_monitor_manager()
    
    loop = manager.get_monitor(task_id)
    
    if not loop:
        raise HTTPException(status_code=404, detail=f"未找到任务 {task_id} 的监控")
    
    # 转换级别
    alert_level = None
    if level:
        try:
            alert_level = AlertLevel(level)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的告警级别: {level}")
    
    alerts = loop.get_alert_history(
        limit=limit,
        level=alert_level,
        alert_type=alert_type,
    )
    
    return AlertHistoryResponse(
        task_id=task_id,
        total=len(alerts),
        alerts=[AlertResponse(**a) for a in alerts],
    )


@router.post("/stop-all")
async def stop_all_monitors():
    """
    停止所有监控（慎用）
    """
    try:
        manager = get_monitor_manager()
        
        count = len(manager._loops)
        await manager.stop_all()
        
        return {"success": True, "message": f"已停止 {count} 个监控"}
        
    except Exception as e:
        logger.error(f"停止所有监控失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
