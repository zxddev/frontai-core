-- ============================================================================
-- V17 出发前装备准备调度表 (equipment_preparation_dispatch_v2)
-- 
-- 业务场景: 出发前从仓库装车的调度管理
-- 流程: AI推荐 → 指挥员下发 → 各车辆人员准备 → 出发
-- ============================================================================

SET search_path TO operational_v2, public;

-- ============================================================================
-- 创建准备状态枚举
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE operational_v2.preparation_dispatch_status AS ENUM (
        'pending',      -- 待下发
        'dispatched',   -- 已下发（等待人员确认）
        'confirmed',    -- 人员已确认收到
        'preparing',    -- 正在准备（从仓库取装备）
        'ready'         -- 准备完成（装车完毕）
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 创建装备准备调度表
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.equipment_preparation_dispatch_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    event_id UUID NOT NULL,
    recommendation_id UUID,
    vehicle_id UUID NOT NULL,
    
    -- 要装载的设备（从仓库取）
    assigned_device_ids UUID[] DEFAULT '{}',
    
    -- 要装载的物资 [{supply_id, quantity, supply_name}]
    assigned_supplies JSONB DEFAULT '[]',
    
    -- 准备状态
    status operational_v2.preparation_dispatch_status DEFAULT 'pending',
    
    -- 负责人
    assignee_user_id UUID,
    
    -- 下发人（指挥员）
    dispatched_by UUID,
    
    -- 时间记录
    dispatched_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    ready_at TIMESTAMPTZ,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 唯一约束：每个事件每辆车只有一条记录
    UNIQUE(event_id, vehicle_id)
);

-- ============================================================================
-- 创建索引
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_prep_dispatch_event 
    ON operational_v2.equipment_preparation_dispatch_v2(event_id);

CREATE INDEX IF NOT EXISTS idx_prep_dispatch_vehicle 
    ON operational_v2.equipment_preparation_dispatch_v2(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_prep_dispatch_status 
    ON operational_v2.equipment_preparation_dispatch_v2(status);

CREATE INDEX IF NOT EXISTS idx_prep_dispatch_assignee 
    ON operational_v2.equipment_preparation_dispatch_v2(assignee_user_id);

-- ============================================================================
-- 创建触发器 - 自动更新时间戳
-- ============================================================================
DROP TRIGGER IF EXISTS tr_prep_dispatch_updated ON operational_v2.equipment_preparation_dispatch_v2;
CREATE TRIGGER tr_prep_dispatch_updated
    BEFORE UPDATE ON operational_v2.equipment_preparation_dispatch_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- ============================================================================
-- 添加外键约束（允许失败，兼容表不存在的情况）
-- ============================================================================
DO $$ BEGIN
    ALTER TABLE operational_v2.equipment_preparation_dispatch_v2 
        ADD CONSTRAINT fk_prep_dispatch_event 
        FOREIGN KEY (event_id) 
        REFERENCES operational_v2.events_v2(id) 
        ON DELETE CASCADE;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE operational_v2.equipment_preparation_dispatch_v2 
        ADD CONSTRAINT fk_prep_dispatch_recommendation 
        FOREIGN KEY (recommendation_id) 
        REFERENCES operational_v2.equipment_recommendations_v2(id) 
        ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE operational_v2.equipment_preparation_dispatch_v2 
        ADD CONSTRAINT fk_prep_dispatch_vehicle 
        FOREIGN KEY (vehicle_id) 
        REFERENCES operational_v2.vehicles_v2(id) 
        ON DELETE CASCADE;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE operational_v2.equipment_preparation_dispatch_v2 
        ADD CONSTRAINT fk_prep_dispatch_assignee 
        FOREIGN KEY (assignee_user_id) 
        REFERENCES operational_v2.users_v2(id) 
        ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE operational_v2.equipment_preparation_dispatch_v2 
        ADD CONSTRAINT fk_prep_dispatch_dispatcher 
        FOREIGN KEY (dispatched_by) 
        REFERENCES operational_v2.users_v2(id) 
        ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 添加表注释
-- ============================================================================
COMMENT ON TABLE operational_v2.equipment_preparation_dispatch_v2 
    IS '出发前装备准备调度表 - 记录各车辆的装车任务和准备状态';

COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.event_id 
    IS '关联事件ID';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.recommendation_id 
    IS '关联AI推荐记录ID';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.vehicle_id 
    IS '目标车辆ID';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.assigned_device_ids 
    IS '分配的设备ID数组（从仓库取）';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.assigned_supplies 
    IS '分配的物资列表 [{supply_id, quantity, supply_name}]';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.status 
    IS '状态: pending待下发/dispatched已下发/confirmed已确认/preparing准备中/ready已完成';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.assignee_user_id 
    IS '负责准备的用户ID';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.dispatched_by 
    IS '下发指令的指挥员ID';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.dispatched_at 
    IS '下发时间';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.confirmed_at 
    IS '人员确认时间';
COMMENT ON COLUMN operational_v2.equipment_preparation_dispatch_v2.ready_at 
    IS '准备完成时间';

-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'V17 Equipment Preparation Dispatch migration completed!' AS result;
