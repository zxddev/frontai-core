"""
地图实体ORM模型

对应SQL表: 
- layers_v2 (图层表)
- entities_v2 (实体表)
- layer_type_defaults_v2 (图层类型定义)
- role_layer_bindings_v2 (角色图层权限)

参考: sql/v2_layer_entity_model.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, ForeignKey, ARRAY, Numeric, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from geoalchemy2 import Geometry

from src.core.database import Base


# 实体类型枚举
EntityTypeEnum = ENUM(
    'command_vehicle', 'uav', 'drone', 'robotic_dog', 'usv', 'ship',
    'realTime_uav', 'realTime_robotic_dog', 'realTime_usv', 'realTime_command_vhicle',
    'start_point', 'end_point', 'planned_route',
    'rescue_target', 'resettle_point', 'rescue_team', 'resource_point',
    'danger_area', 'danger_zone', 'safety_area', 'investigation_area', 'weather_area',
    'event_point', 'event_range', 'situation_point', 'command_post_candidate',
    'earthquake_epicenter',
    name='entity_type_v2',
    create_type=False,
)

# 实体来源枚举
EntitySourceEnum = ENUM(
    'system', 'manual',
    name='entity_source_v2',
    create_type=False,
)

# 图层分类枚举
LayerCategoryEnum = ENUM(
    'system', 'manual', 'hybrid',
    name='layer_category_v2',
    create_type=False,
)

# 图层访问范围枚举
LayerAccessScopeEnum = ENUM(
    'full', 'read_only', 'hidden',
    name='layer_access_scope_v2',
    create_type=False,
)

# 几何类型枚举
GeometryKindEnum = ENUM(
    'point', 'line', 'polygon', 'circle',
    name='geometry_kind_v2',
    create_type=False,
)


class Layer(Base):
    """
    图层表 ORM 模型
    
    业务说明:
    - 图层是实体的容器，每个实体属于一个图层
    - 图层决定实体的显示样式和访问权限
    """
    __tablename__ = "layers_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 图层标识 ====================
    code: str = Column(
        String(100), 
        unique=True, 
        nullable=False,
        comment="图层编码，如 layer.event, layer.resource"
    )
    name: str = Column(
        String(200), 
        nullable=False,
        comment="图层名称"
    )
    
    # ==================== 图层配置 ====================
    category: str = Column(
        LayerCategoryEnum, 
        nullable=False, 
        default='system',
        comment="图层分类: system/manual/hybrid"
    )
    visible_by_default: bool = Column(
        Boolean, 
        nullable=False, 
        default=True,
        comment="是否默认可见"
    )
    
    # ==================== 样式配置 ====================
    style_config: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="样式配置: {point: {...}, line: {...}, polygon: {...}}"
    )
    
    # ==================== 刷新配置 ====================
    update_interval_seconds: Optional[int] = Column(
        Integer,
        comment="刷新间隔(秒)，NULL表示不自动刷新"
    )
    
    # ==================== 其他 ====================
    description: Optional[str] = Column(
        Text,
        comment="图层描述"
    )
    sort_order: int = Column(
        Integer, 
        nullable=False, 
        default=0,
        comment="排序序号"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    deleted_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="软删除时间"
    )


class Entity(Base):
    """
    实体表 ORM 模型
    
    业务说明:
    - 实体是地图上显示的各类对象
    - 包括灾情点、救援队伍、设备、避难所等
    - 支持动态实体（实时位置更新）
    """
    __tablename__ = "entities_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 实体类型 ====================
    type: str = Column(
        EntityTypeEnum, 
        nullable=False,
        comment="实体类型: event_point/rescue_team/uav/danger_area等"
    )
    
    # ==================== 图层关联 ====================
    layer_code: str = Column(
        String(100), 
        ForeignKey("layers_v2.code"), 
        nullable=False,
        comment="所属图层编码"
    )
    
    # ==================== 设备关联 ====================
    device_id: Optional[str] = Column(
        String(100),
        comment="关联设备ID（如果是设备实体）"
    )
    
    # ==================== 几何信息 ====================
    geometry = Column(
        Geometry(srid=4326), 
        nullable=False,
        comment="几何形状（点/线/面）"
    )
    
    # ==================== 属性 ====================
    properties: dict[str, Any] = Column(
        JSONB, 
        nullable=False, 
        default={},
        comment="动态属性，不同类型有不同属性"
    )
    
    # ==================== 实体来源 ====================
    source: str = Column(
        EntitySourceEnum, 
        nullable=False, 
        default='system',
        comment="实体来源: system/manual"
    )
    
    # ==================== 显示控制 ====================
    visible_on_map: bool = Column(
        Boolean, 
        nullable=False, 
        default=True,
        comment="是否在地图显示"
    )
    is_dynamic: bool = Column(
        Boolean, 
        nullable=False, 
        default=False,
        comment="是否为动态实体（可实时更新位置）"
    )
    last_position_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="最新定位时间（动态实体）"
    )
    
    # ==================== 样式覆盖 ====================
    style_overrides: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="样式覆盖配置"
    )
    
    # ==================== 关联 ====================
    scenario_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="所属场景ID"
    )
    event_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联事件ID"
    )
    
    # ==================== 审计 ====================
    created_by: Optional[str] = Column(
        String(100),
        comment="创建者"
    )
    updated_by: Optional[str] = Column(
        String(100),
        comment="更新者"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    deleted_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="软删除时间"
    )


class LayerTypeDefault(Base):
    """
    图层类型定义表 ORM 模型
    
    业务说明:
    - 定义每个图层支持的实体类型
    - 包含图标、默认样式等元数据
    """
    __tablename__ = "layer_type_defaults_v2"
    
    id: int = Column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    
    layer_code: str = Column(
        String(100), 
        ForeignKey("layers_v2.code", ondelete="CASCADE"), 
        nullable=False,
        comment="图层编码"
    )
    entity_type: str = Column(
        EntityTypeEnum, 
        nullable=False,
        comment="实体类型"
    )
    geometry_kind: str = Column(
        GeometryKindEnum, 
        nullable=False, 
        default='point',
        comment="几何类型: point/line/polygon/circle"
    )
    icon: Optional[str] = Column(
        String(100),
        comment="图标标识（前端映射）"
    )
    property_keys: list[str] = Column(
        ARRAY(Text), 
        default=[],
        comment="属性键列表（前端弹窗显示优先级）"
    )
    default_style: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="类型默认样式"
    )


class RoleLayerBinding(Base):
    """
    角色图层权限绑定表 ORM 模型
    
    业务说明:
    - 控制不同角色对图层的访问权限
    """
    __tablename__ = "role_layer_bindings_v2"
    
    id: int = Column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    
    role_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        comment="角色ID"
    )
    layer_code: str = Column(
        String(100), 
        ForeignKey("layers_v2.code", ondelete="CASCADE"), 
        nullable=False,
        comment="图层编码"
    )
    access_scope: str = Column(
        LayerAccessScopeEnum, 
        nullable=False, 
        default='read_only',
        comment="访问范围: full/read_only/hidden"
    )
    visible_by_default: Optional[bool] = Column(
        Boolean,
        comment="是否默认可见（覆盖图层默认值）"
    )
    sort_order: int = Column(
        Integer, 
        nullable=False, 
        default=0,
        comment="排序序号"
    )


class EntityTrack(Base):
    """
    实体轨迹表 ORM 模型
    
    业务说明:
    - 记录动态实体的历史位置轨迹
    - 用于轨迹回放和路径分析
    
    对应SQL表: entity_tracks_v2
    参考: sql/v2_entity_tracks.sql
    """
    __tablename__ = "entity_tracks_v2"
    
    # 主键：BIGSERIAL提高插入性能
    id: int = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="轨迹点ID"
    )
    
    # 关联实体
    entity_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("entities_v2.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联实体ID"
    )
    
    # 轨迹点位置
    location = Column(
        Geometry("POINT", srid=4326),
        nullable=False,
        comment="轨迹点坐标(WGS84)"
    )
    
    # 运动状态
    speed_kmh: Optional[float] = Column(
        Numeric(6, 2),
        comment="速度(km/h)"
    )
    heading: Optional[int] = Column(
        Integer,
        comment="航向角度(0-360)"
    )
    altitude_m: Optional[float] = Column(
        Numeric(8, 2),
        comment="海拔高度(米)"
    )
    
    # 时间戳
    recorded_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="记录时间"
    )
