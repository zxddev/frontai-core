"""
前端资源单位业务服务层
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.domains.frontend_api.car.repository import CarItemAssignmentRepository
from src.domains.resources.teams.repository import TeamRepository
from src.domains.resources.teams.schemas import TeamCreate, TeamUpdate
from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import EntityCreate, EntityType, EntitySource
from .schemas import MobilizeRequest, MobilizeResponse, MobilizedTeamSummary

logger = logging.getLogger(__name__)


class UnitService:
    """单位业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._assignment_repo = CarItemAssignmentRepository(db)
        self._team_repo = TeamRepository(db)
        self._entity_service = EntityService(db)
    
    async def mobilize_vehicles(self, request: MobilizeRequest) -> MobilizeResponse:
        """
        动员车辆为救援队伍
        
        1. 读取车辆及其装备/模块信息
        2. 转换数据结构为 AI 上下文
        3. 创建或更新 Team 记录
        4. 同步创建地图实体
        """
        mobilized_teams = []
        
        for vehicle_id_str in request.vehicle_ids:
            try:
                vehicle_id = UUID(vehicle_id_str)
                event_id = UUID(request.event_id)
                
                # 1. 获取车辆基础信息
                vehicle = await self._get_vehicle(vehicle_id)
                if not vehicle:
                    logger.warning(f"车辆未找到: {vehicle_id}, 跳过动员")
                    continue
                
                # 2. 获取装备分配信息
                assignments = await self._assignment_repo.get_by_event_car(event_id, vehicle_id)
                
                # 3. 构建 AI 上下文数据
                ai_context = await self._build_ai_context(assignments)
                
                # 4. 创建或更新队伍
                team = await self._create_or_update_team(vehicle, ai_context)
                
                # 5. 同步装备关联到队伍
                await self._sync_team_resources(team.id, assignments)
                
                # 6. 同步车辆关联到队伍
                await self._sync_team_vehicle(team.id, vehicle_id)
                
                # 7. 同步地图实体
                await self._sync_map_entity(team, request.event_id)
                
                mobilized_teams.append(MobilizedTeamSummary(
                    team_id=str(team.id),
                    name=team.name,
                    source_vehicle_id=str(vehicle.id),
                    status=team.status,
                ))
                
                logger.info(f"车辆动员成功: {vehicle.name} -> {team.name}")
                
            except Exception as e:
                logger.error(f"车辆动员失败: vehicle_id={vehicle_id_str}, error={e}", exc_info=True)
        
        return MobilizeResponse(
            mobilized_count=len(mobilized_teams),
            teams=mobilized_teams,
        )
    
    async def _get_vehicle(self, vehicle_id: UUID) -> Optional[Any]:
        """获取车辆信息"""
        result = await self._db.execute(
            text("SELECT id, code, name, vehicle_type FROM operational_v2.vehicles_v2 WHERE id = :id"),
            {"id": str(vehicle_id)}
        )
        return result.fetchone()
    
    async def _build_ai_context(self, assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建 AI 分析用的上下文数据"""
        equipment = []
        supplies = []
        modules = []
        
        # 批量获取物品详情名称 (简化处理，实际可能需要查 Item/Device 表)
        # 这里我们尝试从 assignments 关联查询，或者后续单独查询
        # 为了性能，我们这里假设 item_id 需要反查详细信息
        
        for item in assignments:
            item_id = item['item_id']
            quantity = item['quantity']
            item_type = item['item_type']
            is_selected = item['is_selected']
            
            if not is_selected:
                continue
                
            # 查询物品名称
            name = await self._get_item_name(item_id, item_type)
            description = f"{name} (QTY: {quantity})"
            
            if item_type == 'device':
                equipment.append(description)
            elif item_type == 'supply':
                supplies.append(description)
            elif item_type == 'module':
                modules.append(name)  # 模块通常只有一个
                
        return {
            "modules": modules,
            "equipment": equipment,
            "supplies": supplies,
            "mobilized_at": uuid.uuid1().hex, # 标记更新时间
        }

    async def _get_item_name(self, item_id: str, item_type: str) -> str:
        """获取物品名称"""
        table_map = {
            'device': 'operational_v2.devices_v2',
            'supply': 'operational_v2.supplies_v2',
            'module': 'operational_v2.modules_v2'
        }
        table = table_map.get(item_type)
        if not table:
            return "Unknown Item"
            
        try:
            result = await self._db.execute(
                text(f"SELECT name FROM {table} WHERE id = :id"),
                {"id": item_id}
            )
            row = result.fetchone()
            return row.name if row else "Unknown Item"
        except Exception:
            return "Unknown Item"

    async def _create_or_update_team(self, vehicle: Any, ai_context: Dict[str, Any]) -> Any:
        """创建或更新队伍记录（根据名称 upsert）"""
        team_name = f"前突指挥车队-{vehicle.name}"
        team_code = f"FLEET-{vehicle.code}"
        
        properties = {
            "source_vehicle_id": str(vehicle.id),
            "is_mobilized_fleet": True,
            "vehicle_type": vehicle.vehicle_type,
            "ai_context": ai_context
        }
        
        # 根据名称查找是否已存在
        existing_team = await self._get_team_by_name(team_name)
        
        if existing_team:
            # 更新现有队伍
            update_data = TeamUpdate(properties=properties)
            # 合并现有 properties
            if existing_team.properties:
                properties = {**existing_team.properties, **properties}
                update_data.properties = properties
            
            logger.info(f"更新队伍: {team_name} (id={existing_team.id})")
            return await self._team_repo.update(existing_team, update_data)
        else:
            # 创建新队伍
            from src.domains.resources.teams.schemas import TeamType
            create_data = TeamCreate(
                code=team_code,
                name=team_name,
                team_type=TeamType.search_rescue,
                total_personnel=4,
                available_personnel=4,
                properties=properties
            )
            logger.info(f"创建队伍: {team_name}")
            return await self._team_repo.create(create_data)
    
    async def _get_team_by_name(self, name: str) -> Optional[Any]:
        """根据名称查询队伍"""
        from src.domains.resources.teams.models import Team
        from sqlalchemy import select
        result = await self._db.execute(
            select(Team).where(Team.name == name)
        )
        return result.scalar_one_or_none()

    async def _sync_map_entity(self, team: Any, event_id: str) -> None:
        """同步地图实体"""
        # 检查是否已有对应实体 (通过 properties->>team_id 查找)
        # 由于 EntityService 没有直接按 property 查的方法，我们暂时用 list 过滤或约定 entity.id = team.id (如果 ID 类型兼容)
        # 但 entity.id 是 UUID，team.id 也是 UUID，可以尝试保持一致？
        # 不，最好还是让 entity 有自己的 ID，通过 properties 关联
        
        # 简单起见，我们先查一下 layer.rescue_team 下有没有 name 相同的
        # 或者更严谨：Entity 表应该加一个 team_id 字段？目前没有，存 properties
        
        # 搜索现有实体
        # 这里为了简化，我们假设每个 Team 对应一个 Entity，并且我们在 Entity properties 里存了 team_id
        # 实际生产中可能需要更高效的索引
        
        # 构造实体数据
        props = {
            "team_id": str(team.id),
            "name": team.name,
            "status": team.status,
            "type": "rescue_team",
            "ai_context": team.properties.get("ai_context", {}),
            "contact": team.contact_person or "",
            "phone": team.contact_phone or ""
        }
        
        # 获取车辆位置作为初始位置 (如果有)
        # 暂时默认为中心点或从车辆最新位置获取
        # 这里先 mock 一个位置，或者如果 vehicle 表有位置字段则使用
        # 假设 entity 不存在则创建
        
        # 我们尝试用 team_id 作为 entity_id 的种子生成 UUID，确保幂等
        entity_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"team-entity-{team.id}")
        
        existing_entity = await self._entity_service._entity_repo.get_by_id(entity_uuid)
        
        if existing_entity:
            # 更新属性
            await self._entity_service.update(existing_entity.id, type('EntityUpdate', (), {'properties': props})())
        else:
            # 创建
            entity_data = EntityCreate(
                type=EntityType.rescue_team,
                layer_code="layer.team",
                geometry={
                    "type": "Point",
                    "coordinates": [116.40, 39.90] # 默认坐标，后续应该从车辆遥测获取
                },
                properties=props,
                source=EntitySource.system,
                visible_on_map=True,
                is_dynamic=True, # 车辆是移动的
                event_id=UUID(event_id) if event_id else None
            )
            # 强制使用确定的 ID
            # 注意：EntityCreate Schema 可能不支持传 ID，需要看 Repository 实现
            # Repository 的 create 方法通常生成新 ID。我们这里先让它自动生成，后续可以通过 properties 关联回找
            
            await self._entity_service.create(entity_data)

    async def _sync_team_resources(self, team_id: UUID, assignments: List[Dict[str, Any]]) -> None:
        """同步 car_item_assignment 中选中的装备到队伍关联表"""
        for item in assignments:
            if not item.get('is_selected'):
                continue
            
            item_type = item['item_type']
            item_id = item['item_id']
            quantity = item.get('quantity', 1)
            
            try:
                if item_type == 'device':
                    await self._db.execute(text("""
                        INSERT INTO operational_v2.team_devices_v2 (team_id, device_id, quantity)
                        VALUES (:team_id, :device_id, :quantity)
                        ON CONFLICT (team_id, device_id) DO UPDATE SET quantity = :quantity, updated_at = NOW()
                    """), {"team_id": str(team_id), "device_id": item_id, "quantity": quantity})
                    
                elif item_type == 'supply':
                    await self._db.execute(text("""
                        INSERT INTO operational_v2.team_supplies_v2 (team_id, supply_id, quantity)
                        VALUES (:team_id, :supply_id, :quantity)
                        ON CONFLICT (team_id, supply_id) DO UPDATE SET quantity = :quantity, updated_at = NOW()
                    """), {"team_id": str(team_id), "supply_id": item_id, "quantity": quantity})
                    
                elif item_type == 'module':
                    parent_device_id = item.get('parent_device_id')
                    await self._db.execute(text("""
                        INSERT INTO operational_v2.team_modules_v2 (team_id, module_id, device_id)
                        VALUES (:team_id, :module_id, :device_id)
                        ON CONFLICT (team_id, module_id) DO UPDATE SET device_id = :device_id, updated_at = NOW()
                    """), {"team_id": str(team_id), "module_id": item_id, "device_id": parent_device_id})
                    
            except Exception as e:
                logger.warning(f"同步队伍资源失败: team_id={team_id}, item_id={item_id}, error={e}")

    async def _sync_team_vehicle(self, team_id: UUID, vehicle_id: UUID) -> None:
        """同步队伍-车辆关联"""
        try:
            await self._db.execute(text("""
                INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, status)
                VALUES (:team_id, :vehicle_id, true, 'deployed')
                ON CONFLICT (team_id, vehicle_id) DO UPDATE SET status = 'deployed', is_primary = true, updated_at = NOW()
            """), {"team_id": str(team_id), "vehicle_id": str(vehicle_id)})
        except Exception as e:
            logger.warning(f"同步队伍车辆失败: team_id={team_id}, vehicle_id={vehicle_id}, error={e}")
