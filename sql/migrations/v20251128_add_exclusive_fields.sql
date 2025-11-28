-- 添加专有装备和模块字段
-- 用途：设备专属车辆、模块专属设备，防止跨车辆/设备选择

-- 设备专属车辆（为NULL表示非专有，可被任意车辆选择）
ALTER TABLE operational_v2.devices_v2 
ADD COLUMN IF NOT EXISTS exclusive_to_vehicle_id UUID REFERENCES operational_v2.vehicles_v2(id);

-- 模块专属设备（为NULL表示非专有，可被任意设备使用）
ALTER TABLE operational_v2.modules_v2
ADD COLUMN IF NOT EXISTS exclusive_to_device_id UUID REFERENCES operational_v2.devices_v2(id);

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_devices_exclusive_vehicle ON operational_v2.devices_v2(exclusive_to_vehicle_id) WHERE exclusive_to_vehicle_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_modules_exclusive_device ON operational_v2.modules_v2(exclusive_to_device_id) WHERE exclusive_to_device_id IS NOT NULL;

COMMENT ON COLUMN operational_v2.devices_v2.exclusive_to_vehicle_id IS '专属车辆ID，非NULL表示该设备只能被此车辆选择';
COMMENT ON COLUMN operational_v2.modules_v2.exclusive_to_device_id IS '专属设备ID，非NULL表示该模块只能被此设备使用';
