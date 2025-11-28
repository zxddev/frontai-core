"""
物资库存服务

提供统一的物资库存查询和调拨功能，供以下智能体共享：
- equipment_preparation: 出发前从仓库选择物资
- emergency_ai: 前线统一调度所有可用物资

并发安全特性:
- 乐观锁（version字段）防止并发更新丢失
- 批量 SELECT FOR UPDATE 减少死锁风险
- 自动重试机制（指数退避）
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


class OptimisticLockError(Exception):
    """乐观锁冲突异常"""
    def __init__(self, supply_id: UUID, expected_version: int, actual_version: int):
        self.supply_id = supply_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"乐观锁冲突: supply_id={supply_id}, "
            f"expected_version={expected_version}, actual_version={actual_version}"
        )


class InsufficientStockError(Exception):
    """库存不足异常"""
    def __init__(self, supply_id: UUID, required: int, available: int):
        self.supply_id = supply_id
        self.required = required
        self.available = available
        super().__init__(
            f"库存不足: supply_id={supply_id}, "
            f"需要={required}, 可用={available}"
        )


@dataclass
class SupplyInventoryItem:
    """物资库存项"""
    inventory_id: UUID
    depot_id: UUID
    depot_code: str
    depot_name: str
    depot_type: str
    supply_id: UUID
    supply_code: str
    supply_name: str
    category: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    min_stock: int
    unit: str
    batch_no: Optional[str]
    expiry_date: Optional[datetime]
    is_expired: bool
    is_low_stock: bool
    latitude: Optional[float]
    longitude: Optional[float]
    # 扩展属性
    weight_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    applicable_disasters: Optional[List[str]] = None
    required_for_disasters: Optional[List[str]] = None
    per_person_per_day: Optional[float] = None
    # 乐观锁版本号
    version: int = 1


@dataclass
class ReserveItem:
    """预留物资项"""
    supply_id: UUID
    quantity: int
    expected_version: Optional[int] = None  # 如果提供，则进行乐观锁校验


@dataclass
class ReserveResult:
    """预留结果"""
    success: bool
    reserved_items: List[Dict[str, Any]] = field(default_factory=list)
    failed_items: List[Dict[str, Any]] = field(default_factory=list)
    retried_count: int = 0


@dataclass
class TransferRequest:
    """调拨申请"""
    from_depot_id: UUID
    to_depot_id: UUID
    items: List[Dict[str, Any]]  # [{supply_id, quantity}]
    scenario_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    note: Optional[str] = None
    requested_by: Optional[UUID] = None
    priority: str = "medium"  # critical/high/medium/low


@dataclass
class TransferResult:
    """调拨结果"""
    transfer_id: UUID
    transfer_code: str
    status: str
    items_count: int


class SupplyInventoryService:
    """
    物资库存服务
    
    统一处理物资库存查询、预留、调拨等操作。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_available_inventory(
        self,
        depot_types: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        depot_ids: Optional[List[UUID]] = None,
        scenario_id: Optional[UUID] = None,
        disaster_type: Optional[str] = None,
        include_expired: bool = False,
        min_available: int = 1,
    ) -> List[SupplyInventoryItem]:
        """
        查询可用库存
        
        Args:
            depot_types: 存放点类型过滤 ['warehouse', 'team_base', 'vehicle', 'field_depot']
            categories: 物资类别过滤 ['medical', 'protection', 'rescue', ...]
            depot_ids: 指定存放点ID列表
            scenario_id: 查询参与该想定的所有存放点（field_depot）
            disaster_type: 按灾害类型过滤适用物资
            include_expired: 是否包含过期物资
            min_available: 最小可用数量
            
        Returns:
            物资库存列表
        """
        logger.info(
            f"[库存查询] depot_types={depot_types}, categories={categories}, "
            f"disaster_type={disaster_type}"
        )

        # 构建查询条件
        conditions = ["sd.is_active = true", "si.quantity > 0"]
        params: Dict[str, Any] = {"min_available": min_available}

        if depot_types:
            conditions.append("sd.depot_type = ANY(:depot_types)")
            params["depot_types"] = depot_types

        if categories:
            conditions.append("s.category = ANY(:categories)")
            params["categories"] = categories

        if depot_ids:
            conditions.append("sd.id = ANY(:depot_ids)")
            params["depot_ids"] = [str(d) for d in depot_ids]

        if scenario_id:
            conditions.append("(sd.scenario_id = :scenario_id OR sd.depot_type != 'field_depot')")
            params["scenario_id"] = str(scenario_id)

        if disaster_type:
            conditions.append(
                "(:disaster_type = ANY(s.applicable_disasters) OR "
                ":disaster_type = ANY(s.required_for_disasters))"
            )
            params["disaster_type"] = disaster_type

        if not include_expired:
            conditions.append("(si.expiry_date IS NULL OR si.expiry_date >= CURRENT_DATE)")

        conditions.append("(si.quantity - si.reserved_quantity) >= :min_available")

        where_clause = " AND ".join(conditions)

        sql = text(f"""
            SELECT 
                si.id AS inventory_id,
                sd.id AS depot_id,
                sd.code AS depot_code,
                sd.name AS depot_name,
                sd.depot_type::text,
                s.id AS supply_id,
                s.code AS supply_code,
                s.name AS supply_name,
                s.category,
                si.quantity,
                si.reserved_quantity,
                (si.quantity - si.reserved_quantity) AS available_quantity,
                COALESCE(si.min_stock, 0) AS min_stock,
                COALESCE(si.unit, s.unit, 'piece') AS unit,
                si.batch_no,
                si.expiry_date,
                CASE 
                    WHEN si.expiry_date IS NOT NULL AND si.expiry_date < CURRENT_DATE THEN true
                    ELSE false
                END AS is_expired,
                CASE 
                    WHEN si.min_stock > 0 AND (si.quantity - si.reserved_quantity) < si.min_stock THEN true
                    ELSE false
                END AS is_low_stock,
                ST_Y(sd.location::geometry) AS latitude,
                ST_X(sd.location::geometry) AS longitude,
                s.weight_kg,
                s.volume_m3,
                s.applicable_disasters,
                s.required_for_disasters,
                COALESCE((s.properties->>'per_person_per_day')::float, 1.0) AS per_person_per_day
            FROM operational_v2.supply_inventory_v2 si
            JOIN operational_v2.supply_depots_v2 sd ON sd.id = si.depot_id
            JOIN operational_v2.supplies_v2 s ON s.id = si.supply_id
            WHERE {where_clause}
            ORDER BY available_quantity DESC, s.category, s.code
        """)

        result = await self._db.execute(sql, params)
        rows = result.fetchall()

        items: List[SupplyInventoryItem] = []
        for row in rows:
            item = SupplyInventoryItem(
                inventory_id=row.inventory_id,
                depot_id=row.depot_id,
                depot_code=row.depot_code,
                depot_name=row.depot_name,
                depot_type=row.depot_type,
                supply_id=row.supply_id,
                supply_code=row.supply_code,
                supply_name=row.supply_name,
                category=row.category,
                quantity=row.quantity,
                reserved_quantity=row.reserved_quantity,
                available_quantity=row.available_quantity,
                min_stock=row.min_stock,
                unit=row.unit,
                batch_no=row.batch_no,
                expiry_date=row.expiry_date,
                is_expired=row.is_expired,
                is_low_stock=row.is_low_stock,
                latitude=row.latitude,
                longitude=row.longitude,
                weight_kg=float(row.weight_kg) if row.weight_kg else None,
                volume_m3=float(row.volume_m3) if row.volume_m3 else None,
                applicable_disasters=list(row.applicable_disasters or []),
                required_for_disasters=list(row.required_for_disasters or []),
                per_person_per_day=row.per_person_per_day,
            )
            items.append(item)

        logger.info(f"[库存查询] 找到{len(items)}条记录")
        return items

    async def reserve_supplies(
        self,
        depot_id: UUID,
        items: List[Dict[str, Any]],
        event_id: Optional[UUID] = None,
        scenario_id: Optional[UUID] = None,
    ) -> bool:
        """
        预留物资（增加 reserved_quantity）- 简化版本
        
        Args:
            depot_id: 存放点ID
            items: [{supply_id, quantity}]
            event_id: 关联事件
            scenario_id: 关联想定
            
        Returns:
            是否成功
        """
        # 转换为 ReserveItem 格式
        reserve_items = [
            ReserveItem(
                supply_id=UUID(str(item["supply_id"])),
                quantity=item["quantity"],
            )
            for item in items
        ]
        
        result = await self.reserve_supplies_safe(depot_id, reserve_items)
        return result.success

    async def reserve_supplies_safe(
        self,
        depot_id: UUID,
        items: List[ReserveItem],
        max_retries: int = 3,
    ) -> ReserveResult:
        """
        并发安全的批量物资预留
        
        特性:
        1. 批量 SELECT FOR UPDATE（单次查询锁定所有物资）
        2. 乐观锁版本校验（如果提供 expected_version）
        3. 自动重试机制（指数退避，最多3次）
        4. 事务原子性（全部成功或全部回滚）
        
        Args:
            depot_id: 存放点ID
            items: 预留物资列表（包含版本号用于乐观锁校验）
            max_retries: 最大重试次数
            
        Returns:
            ReserveResult
        """
        logger.info(f"[安全预留] depot_id={depot_id}, items={len(items)}")
        
        retried = 0
        last_error: Optional[Exception] = None
        
        while retried <= max_retries:
            try:
                result = await self._do_reserve_batch(depot_id, items)
                result.retried_count = retried
                return result
            
            except OptimisticLockError as e:
                last_error = e
                retried += 1
                if retried <= max_retries:
                    # 指数退避 + 随机抖动
                    delay = (2 ** retried) * 0.1 + random.uniform(0, 0.1)
                    logger.warning(
                        f"[安全预留] 乐观锁冲突，重试 {retried}/{max_retries}，"
                        f"等待 {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    
            except InsufficientStockError as e:
                # 库存不足不重试
                logger.error(f"[安全预留] 库存不足: {e}")
                return ReserveResult(
                    success=False,
                    failed_items=[{
                        "supply_id": str(e.supply_id),
                        "required": e.required,
                        "available": e.available,
                        "error": "insufficient_stock",
                    }],
                    retried_count=retried,
                )
                
            except OperationalError as e:
                # 数据库死锁等可重试错误
                last_error = e
                retried += 1
                if retried <= max_retries:
                    delay = (2 ** retried) * 0.2 + random.uniform(0, 0.2)
                    logger.warning(
                        f"[安全预留] 数据库错误，重试 {retried}/{max_retries}，"
                        f"等待 {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
        
        # 超过重试次数
        logger.error(f"[安全预留] 超过最大重试次数: {last_error}")
        return ReserveResult(
            success=False,
            failed_items=[{"error": str(last_error)}],
            retried_count=retried,
        )

    async def _do_reserve_batch(
        self,
        depot_id: UUID,
        items: List[ReserveItem],
    ) -> ReserveResult:
        """执行批量预留（内部方法）"""
        if not items:
            return ReserveResult(success=True)
        
        supply_ids = [str(item.supply_id) for item in items]
        
        # 1. 批量锁定所有相关库存记录
        lock_sql = text("""
            SELECT 
                si.id AS inventory_id,
                si.supply_id,
                si.quantity,
                si.reserved_quantity,
                (si.quantity - si.reserved_quantity) AS available,
                si.version
            FROM operational_v2.supply_inventory_v2 si
            WHERE si.depot_id = :depot_id 
              AND si.supply_id = ANY(:supply_ids)
            ORDER BY si.supply_id
            FOR UPDATE NOWAIT
        """)
        
        result = await self._db.execute(lock_sql, {
            "depot_id": str(depot_id),
            "supply_ids": supply_ids,
        })
        locked_rows = {str(row.supply_id): row for row in result.fetchall()}
        
        # 2. 验证所有物资
        reserved_items: List[Dict[str, Any]] = []
        
        for item in items:
            supply_id_str = str(item.supply_id)
            
            if supply_id_str not in locked_rows:
                raise InsufficientStockError(item.supply_id, item.quantity, 0)
            
            row = locked_rows[supply_id_str]
            
            # 乐观锁校验
            if item.expected_version is not None and row.version != item.expected_version:
                raise OptimisticLockError(
                    item.supply_id,
                    item.expected_version,
                    row.version,
                )
            
            # 库存校验
            if row.available < item.quantity:
                raise InsufficientStockError(
                    item.supply_id,
                    item.quantity,
                    row.available,
                )
            
            reserved_items.append({
                "inventory_id": str(row.inventory_id),
                "supply_id": supply_id_str,
                "quantity": item.quantity,
                "old_version": row.version,
            })
        
        # 3. 批量更新预留量（触发器会自动递增version并记录审计）
        update_sql = text("""
            UPDATE operational_v2.supply_inventory_v2
            SET reserved_quantity = reserved_quantity + :quantity,
                updated_at = NOW()
            WHERE id = :inventory_id
        """)
        
        for item_info in reserved_items:
            await self._db.execute(update_sql, {
                "inventory_id": item_info["inventory_id"],
                "quantity": item_info["quantity"],
            })
        
        await self._db.commit()
        
        logger.info(f"[安全预留] 成功预留 {len(reserved_items)} 种物资")
        
        return ReserveResult(
            success=True,
            reserved_items=reserved_items,
        )

    async def release_reserved(
        self,
        depot_id: UUID,
        items: List[ReserveItem],
    ) -> bool:
        """
        释放预留物资
        
        Args:
            depot_id: 存放点ID
            items: 要释放的物资列表
            
        Returns:
            是否成功
        """
        logger.info(f"[释放预留] depot_id={depot_id}, items={len(items)}")
        
        for item in items:
            release_sql = text("""
                UPDATE operational_v2.supply_inventory_v2
                SET reserved_quantity = GREATEST(0, reserved_quantity - :quantity),
                    updated_at = NOW()
                WHERE depot_id = :depot_id AND supply_id = :supply_id
            """)
            await self._db.execute(release_sql, {
                "depot_id": str(depot_id),
                "supply_id": str(item.supply_id),
                "quantity": item.quantity,
            })
        
        await self._db.commit()
        logger.info(f"[释放预留] 成功释放 {len(items)} 种物资")
        return True

    async def create_transfer(
        self,
        request: TransferRequest,
    ) -> TransferResult:
        """
        创建调拨申请
        
        Args:
            request: 调拨申请
            
        Returns:
            调拨结果
        """
        logger.info(
            f"[创建调拨] from={request.from_depot_id}, to={request.to_depot_id}, "
            f"items={len(request.items)}"
        )

        # 生成调拨单号
        code_sql = text("SELECT operational_v2.generate_transfer_code()")
        result = await self._db.execute(code_sql)
        transfer_code = result.fetchone()[0]

        # 插入调拨主表
        insert_sql = text("""
            INSERT INTO operational_v2.supply_transfers_v2 (
                transfer_code, from_depot_id, to_depot_id,
                scenario_id, event_id, status,
                requested_by, note, priority
            ) VALUES (
                :code, :from_depot, :to_depot,
                :scenario_id, :event_id, 'pending',
                :requested_by, :note, :priority
            )
            RETURNING id
        """)
        result = await self._db.execute(insert_sql, {
            "code": transfer_code,
            "from_depot": str(request.from_depot_id),
            "to_depot": str(request.to_depot_id),
            "scenario_id": str(request.scenario_id) if request.scenario_id else None,
            "event_id": str(request.event_id) if request.event_id else None,
            "requested_by": str(request.requested_by) if request.requested_by else None,
            "note": request.note,
            "priority": request.priority,
        })
        transfer_id = result.fetchone()[0]

        # 插入调拨明细
        for item in request.items:
            item_sql = text("""
                INSERT INTO operational_v2.supply_transfer_items_v2 (
                    transfer_id, supply_id, requested_quantity, unit
                ) VALUES (
                    :transfer_id, :supply_id, :quantity,
                    (SELECT COALESCE(unit, 'piece') FROM operational_v2.supplies_v2 WHERE id = :supply_id)
                )
            """)
            await self._db.execute(item_sql, {
                "transfer_id": str(transfer_id),
                "supply_id": str(item["supply_id"]),
                "quantity": item["quantity"],
            })

        # 预留源存放点的物资
        await self.reserve_supplies(
            depot_id=request.from_depot_id,
            items=request.items,
            event_id=request.event_id,
            scenario_id=request.scenario_id,
        )

        await self._db.commit()

        logger.info(f"[创建调拨] 成功: {transfer_code}")
        return TransferResult(
            transfer_id=transfer_id,
            transfer_code=transfer_code,
            status="pending",
            items_count=len(request.items),
        )

    async def complete_transfer(
        self,
        transfer_id: UUID,
        actual_quantities: Optional[Dict[str, int]] = None,
    ) -> bool:
        """
        完成调拨（更新库存）
        
        Args:
            transfer_id: 调拨ID
            actual_quantities: 实际数量 {supply_id: quantity}，如果为None则使用申请数量
            
        Returns:
            是否成功
        """
        logger.info(f"[完成调拨] transfer_id={transfer_id}")

        # 获取调拨信息
        transfer_sql = text("""
            SELECT t.from_depot_id, t.to_depot_id, t.status,
                   i.supply_id, i.requested_quantity
            FROM operational_v2.supply_transfers_v2 t
            JOIN operational_v2.supply_transfer_items_v2 i ON i.transfer_id = t.id
            WHERE t.id = :transfer_id
        """)
        result = await self._db.execute(transfer_sql, {"transfer_id": str(transfer_id)})
        rows = result.fetchall()

        if not rows:
            logger.error(f"[完成调拨] 调拨不存在: {transfer_id}")
            return False

        from_depot_id = rows[0].from_depot_id
        to_depot_id = rows[0].to_depot_id
        status = rows[0].status

        if status == "completed":
            logger.warning(f"[完成调拨] 已完成，跳过: {transfer_id}")
            return True

        # 处理每个物资
        for row in rows:
            supply_id = row.supply_id
            quantity = actual_quantities.get(str(supply_id), row.requested_quantity) if actual_quantities else row.requested_quantity

            # 减少源存放点库存和预留量
            reduce_sql = text("""
                UPDATE operational_v2.supply_inventory_v2
                SET quantity = quantity - :quantity,
                    reserved_quantity = reserved_quantity - :quantity,
                    updated_at = NOW()
                WHERE depot_id = :from_depot AND supply_id = :supply_id
            """)
            await self._db.execute(reduce_sql, {
                "from_depot": str(from_depot_id),
                "supply_id": str(supply_id),
                "quantity": quantity,
            })

            # 增加目标存放点库存（如果不存在则创建）
            upsert_sql = text("""
                INSERT INTO operational_v2.supply_inventory_v2 (
                    depot_id, supply_id, quantity, reserved_quantity, unit
                ) VALUES (
                    :to_depot, :supply_id, :quantity, 0,
                    (SELECT COALESCE(unit, 'piece') FROM operational_v2.supplies_v2 WHERE id = :supply_id)
                )
                ON CONFLICT (depot_id, supply_id, COALESCE(batch_no, ''))
                DO UPDATE SET 
                    quantity = supply_inventory_v2.quantity + :quantity,
                    updated_at = NOW()
            """)
            await self._db.execute(upsert_sql, {
                "to_depot": str(to_depot_id),
                "supply_id": str(supply_id),
                "quantity": quantity,
            })

            # 更新明细实际数量
            update_item_sql = text("""
                UPDATE operational_v2.supply_transfer_items_v2
                SET actual_quantity = :quantity
                WHERE transfer_id = :transfer_id AND supply_id = :supply_id
            """)
            await self._db.execute(update_item_sql, {
                "transfer_id": str(transfer_id),
                "supply_id": str(supply_id),
                "quantity": quantity,
            })

        # 更新调拨状态
        update_status_sql = text("""
            UPDATE operational_v2.supply_transfers_v2
            SET status = 'completed', received_at = NOW(), updated_at = NOW()
            WHERE id = :transfer_id
        """)
        await self._db.execute(update_status_sql, {"transfer_id": str(transfer_id)})

        await self._db.commit()
        logger.info(f"[完成调拨] 成功: {transfer_id}")
        return True

    async def get_field_available_supplies(
        self,
        scenario_id: UUID,
    ) -> List[SupplyInventoryItem]:
        """
        获取前线可用物资（汇总所有参与该想定的depot）
        
        包括：
        - field_depot 类型且 scenario_id 匹配的存放点
        - 所有 vehicle 类型（已到达现场的车辆）
        - team_base 类型（各队伍自带的物资）
        
        Args:
            scenario_id: 想定ID
            
        Returns:
            前线可用物资列表
        """
        return await self.get_available_inventory(
            depot_types=["field_depot", "vehicle", "team_base"],
            scenario_id=scenario_id,
        )

    async def calculate_shortage(
        self,
        requirements: List[Dict[str, Any]],
        available: List[SupplyInventoryItem],
    ) -> List[Dict[str, Any]]:
        """
        计算物资缺口
        
        Args:
            requirements: [{supply_code, quantity, priority}]
            available: 可用库存列表
            
        Returns:
            缺口列表 [{supply_code, supply_name, required, available, shortage, severity}]
        """
        # 汇总可用量
        available_by_code: Dict[str, int] = {}
        supply_names: Dict[str, str] = {}
        for item in available:
            code = item.supply_code
            available_by_code[code] = available_by_code.get(code, 0) + item.available_quantity
            supply_names[code] = item.supply_name

        shortages: List[Dict[str, Any]] = []
        for req in requirements:
            code = req.get("supply_code", "")
            required = req.get("quantity", 0)
            priority = req.get("priority", "medium")

            avail = available_by_code.get(code, 0)
            if avail < required:
                shortage = required - avail
                severity = "critical" if priority == "critical" or shortage > required * 0.5 else "warning"

                shortages.append({
                    "supply_code": code,
                    "supply_name": supply_names.get(code, req.get("supply_name", code)),
                    "required": required,
                    "available": avail,
                    "shortage": shortage,
                    "severity": severity,
                })

        return shortages
