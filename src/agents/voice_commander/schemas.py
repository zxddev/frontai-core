"""
语音指挥Agent数据模型

使用Pydantic v2定义请求/响应模型。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ============================================================================
# 空间查询相关模型
# ============================================================================

class EntityLocation(BaseModel):
    """实体位置信息"""
    entity_id: str = Field(..., description="实体ID")
    entity_name: str = Field(..., description="实体名称")
    entity_type: str = Field(..., description="实体类型: DRONE/ROBOT_DOG/TEAM/VEHICLE")
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    altitude: Optional[float] = Field(None, description="高度(米)")
    location_desc: Optional[str] = Field(None, description="位置描述（人类可读）")
    status: str = Field("UNKNOWN", description="状态: IDLE/MOVING/WORKING/OFFLINE")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class NearestUnitResult(BaseModel):
    """最近单位查询结果"""
    unit_id: str = Field(..., description="单位ID")
    unit_name: str = Field(..., description="单位名称")
    unit_type: str = Field(..., description="单位类型")
    distance_meters: float = Field(..., description="距离(米)")
    status: str = Field(..., description="状态")
    location: EntityLocation = Field(..., description="位置信息")
    estimated_arrival_minutes: Optional[float] = Field(None, description="预计到达时间(分钟)")


class AreaStatus(BaseModel):
    """区域状态信息"""
    area_id: str = Field(..., description="区域ID")
    area_name: str = Field(..., description="区域名称")
    units_count: int = Field(0, description="区域内单位数量")
    units: List[EntityLocation] = Field(default_factory=list, description="区域内单位列表")
    search_progress: float = Field(0.0, description="搜索进度(0-1)")
    risk_level: str = Field("UNKNOWN", description="风险等级: LOW/MEDIUM/HIGH/CRITICAL")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")


# ============================================================================
# 机器人控制相关模型
# ============================================================================

class ActionType(str, Enum):
    """控制动作类型"""
    NAVIGATE_TO = "NAVIGATE_TO"      # 导航到目标点
    PATROL = "PATROL"                # 巡逻
    RETURN_HOME = "RETURN_HOME"      # 返回基地
    STOP = "STOP"                    # 停止
    FOLLOW = "FOLLOW"                # 跟随
    HOVER = "HOVER"                  # 悬停（无人机）
    SCAN = "SCAN"                    # 扫描/侦查


class CommandPriority(str, Enum):
    """指令优先级"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TacticalCommand(BaseModel):
    """通用战术指令"""
    message_id: str = Field(default_factory=lambda: str(uuid4()), description="消息ID")
    timestamp: int = Field(
        default_factory=lambda: int(datetime.now().timestamp() * 1000),
        description="时间戳(毫秒)"
    )
    issuer_session_id: str = Field(..., description="发起者会话ID")
    target_unit_id: str = Field(..., description="目标单位ID")
    action_type: ActionType = Field(..., description="动作类型")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="动作参数")
    priority: CommandPriority = Field(CommandPriority.NORMAL, description="优先级")
    
    class Config:
        use_enum_values = True


class PendingCommand(BaseModel):
    """待确认指令"""
    command_id: str = Field(default_factory=lambda: str(uuid4()), description="待确认指令ID")
    command: TacticalCommand = Field(..., description="战术指令")
    natural_description: str = Field(..., description="人类可读描述")
    safety_check_passed: bool = Field(..., description="安全检查是否通过")
    safety_warnings: List[str] = Field(default_factory=list, description="安全警告")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    expires_at: datetime = Field(..., description="过期时间")
    
    @classmethod
    def create(
        cls,
        command: TacticalCommand,
        description: str,
        safety_passed: bool,
        warnings: List[str],
        timeout_seconds: int = 30,
    ) -> "PendingCommand":
        """创建待确认指令"""
        now = datetime.now()
        return cls(
            command=command,
            natural_description=description,
            safety_check_passed=safety_passed,
            safety_warnings=warnings,
            created_at=now,
            expires_at=datetime.fromtimestamp(now.timestamp() + timeout_seconds),
        )


class CommandConfirmation(BaseModel):
    """指令确认请求"""
    command_id: str = Field(..., description="待确认指令ID")
    action: str = Field(..., description="确认动作: approve/cancel")
    confirmed_by: str = Field(..., description="确认者会话ID")
    confirmed_at: datetime = Field(default_factory=datetime.now, description="确认时间")


# ============================================================================
# 语义路由相关模型
# ============================================================================

class RouteDecision(BaseModel):
    """路由决策结果"""
    route_name: str = Field(..., description="路由名称")
    confidence: float = Field(..., description="置信度")
    threshold: float = Field(..., description="阈值")
    is_matched: bool = Field(..., description="是否匹配")
    fallback: bool = Field(False, description="是否降级处理")
