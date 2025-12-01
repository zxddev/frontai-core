-- 车辆装备实时分配表
-- 用于追踪每个事件中车辆与装备的分配关系

-- 1. 创建分配表
CREATE TABLE IF NOT EXISTS operational_v2.car_item_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    car_id UUID NOT NULL REFERENCES operational_v2.vehicles_v2(id) ON DELETE CASCADE,
    item_id UUID NOT NULL,
    item_type VARCHAR(20) NOT NULL CHECK (item_type IN ('device', 'supply', 'module')),
    parent_device_id UUID,  -- 模块类型时，关联的父设备ID
    is_selected BOOLEAN DEFAULT true,
    is_exclusive BOOLEAN DEFAULT false,
    quantity INT DEFAULT 1,
    assigned_by VARCHAR(50),  -- user_id 或 'ai'
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(event_id, car_id, item_id)
);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_car_item_assignment_event ON operational_v2.car_item_assignment(event_id);
CREATE INDEX IF NOT EXISTS idx_car_item_assignment_car ON operational_v2.car_item_assignment(car_id);
CREATE INDEX IF NOT EXISTS idx_car_item_assignment_item ON operational_v2.car_item_assignment(item_id);
CREATE INDEX IF NOT EXISTS idx_car_item_assignment_event_car ON operational_v2.car_item_assignment(event_id, car_id);

-- 3. 添加注释
COMMENT ON TABLE operational_v2.car_item_assignment IS '车辆装备实时分配表，追踪每个事件中的装备分配';
COMMENT ON COLUMN operational_v2.car_item_assignment.event_id IS '事件ID';
COMMENT ON COLUMN operational_v2.car_item_assignment.car_id IS '车辆ID';
COMMENT ON COLUMN operational_v2.car_item_assignment.item_id IS '装备/物资/模块ID';
COMMENT ON COLUMN operational_v2.car_item_assignment.item_type IS '类型: device/supply/module';
COMMENT ON COLUMN operational_v2.car_item_assignment.parent_device_id IS '模块类型时的父设备ID';
COMMENT ON COLUMN operational_v2.car_item_assignment.is_selected IS '是否选中';
COMMENT ON COLUMN operational_v2.car_item_assignment.is_exclusive IS '是否为专属装备';
COMMENT ON COLUMN operational_v2.car_item_assignment.quantity IS '数量（物资类型时使用）';
COMMENT ON COLUMN operational_v2.car_item_assignment.assigned_by IS '分配人：user_id 或 ai';

-- 4. 创建更新时间触发器
CREATE OR REPLACE FUNCTION operational_v2.update_car_item_assignment_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_car_item_assignment_updated_at ON operational_v2.car_item_assignment;
CREATE TRIGGER trg_car_item_assignment_updated_at
    BEFORE UPDATE ON operational_v2.car_item_assignment
    FOR EACH ROW
    EXECUTE FUNCTION operational_v2.update_car_item_assignment_updated_at();
