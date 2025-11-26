-- ============================================================================
-- 车辆-设备-模块-物资 数据模型 V2
-- 支持：载物约束、模块系统、灾害适配、等级配置
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建新schema
CREATE SCHEMA IF NOT EXISTS operational_v2;

-- ============================================================================
-- 1. 车辆类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.vehicle_type_v2 CASCADE;
CREATE TYPE operational_v2.vehicle_type_v2 AS ENUM (
    'reconnaissance',        -- 侦察控制车
    'drone_transport',       -- 无人机输送车
    'ship_transport',        -- 无人艇输送车
    'medical',               -- 医疗救援车
    'logistics',             -- 综合保障车
    'command'                -- 指挥车
);

-- ============================================================================
-- 2. 设备类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.device_type_v2 CASCADE;
CREATE TYPE operational_v2.device_type_v2 AS ENUM (
    'drone',                 -- 无人机
    'dog',                   -- 机器狗
    'ship',                  -- 无人艇
    'robot'                  -- 其他机器人
);

-- ============================================================================
-- 3. 模块类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.module_type_v2 CASCADE;
CREATE TYPE operational_v2.module_type_v2 AS ENUM (
    'sensor',                -- 传感器模块（热成像、生命探测等）
    'communication',         -- 通信模块（中继、喊话等）
    'utility',               -- 功能模块（投放、采样等）
    'power'                  -- 电源模块（扩展电池等）
);

-- ============================================================================
-- 4. 车辆表 (vehicles_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.vehicles_v2 CASCADE;
CREATE TABLE operational_v2.vehicles_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    vehicle_type operational_v2.vehicle_type_v2 NOT NULL,
    
    -- 载物能力约束
    max_weight_kg DECIMAL(10,2) NOT NULL,
    max_volume_m3 DECIMAL(10,4) NOT NULL,
    max_device_slots INT NOT NULL,
    
    -- 兼容性（可装载的设备类型）
    compatible_device_types operational_v2.device_type_v2[] NOT NULL,
    
    -- 当前装载状态（由触发器维护）
    current_weight_kg DECIMAL(10,2) DEFAULT 0,
    current_volume_m3 DECIMAL(10,4) DEFAULT 0,
    current_device_count INT DEFAULT 0,
    
    -- 车辆本身属性
    self_weight_kg DECIMAL(10,2),
    crew_capacity INT DEFAULT 4,
    
    -- 地形通过能力
    terrain_capabilities TEXT[] DEFAULT '{}',      -- 地形能力: {all_terrain,mountain,flood,urban,forest}
    is_all_terrain BOOLEAN DEFAULT false,          -- 是否全地形越野
    max_gradient_percent INT,                      -- 最大爬坡度(%)
    max_wading_depth_m DECIMAL(4,2),               -- 最大涉水深度(米)
    min_turning_radius_m DECIMAL(4,2),             -- 最小转弯半径(米)
    
    -- 通过性参数
    ground_clearance_mm INT,                       -- 最小离地间隙(毫米)
    approach_angle_deg INT,                        -- 接近角(度)
    departure_angle_deg INT,                       -- 离去角(度)
    breakover_angle_deg INT,                       -- 纵向通过角(度)
    
    -- 速度/续航参数
    max_speed_kmh INT,                             -- 最大速度(km/h)
    terrain_speed_factors JSONB DEFAULT '{}',      -- 地形速度系数 {"mountain":0.6,"forest":0.5}
    fuel_capacity_l DECIMAL(6,2),                  -- 油箱容量(升)
    fuel_consumption_per_100km DECIMAL(5,2),       -- 百公里油耗(升)
    range_km INT,                                  -- 续航里程(公里)
    
    -- 尺寸限制
    length_m DECIMAL(4,2),                         -- 车长(米)
    width_m DECIMAL(4,2),                          -- 车宽(米)
    height_m DECIMAL(4,2),                         -- 车高(米)
    
    -- 状态
    status VARCHAR(20) DEFAULT 'available',
    entity_id UUID,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.vehicles_v2 IS '车辆表 - 救援车辆及其载物能力';
COMMENT ON COLUMN operational_v2.vehicles_v2.id IS '车辆唯一标识符';
COMMENT ON COLUMN operational_v2.vehicles_v2.code IS '车辆编号，如VH-001';
COMMENT ON COLUMN operational_v2.vehicles_v2.name IS '车辆名称';
COMMENT ON COLUMN operational_v2.vehicles_v2.vehicle_type IS '车辆类型枚举';
COMMENT ON COLUMN operational_v2.vehicles_v2.max_weight_kg IS '最大载重（公斤），不含车辆自重';
COMMENT ON COLUMN operational_v2.vehicles_v2.max_volume_m3 IS '最大载物容积（立方米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.max_device_slots IS '最大设备位数量';
COMMENT ON COLUMN operational_v2.vehicles_v2.compatible_device_types IS '可装载的设备类型数组';
COMMENT ON COLUMN operational_v2.vehicles_v2.current_weight_kg IS '当前已装载重量（触发器维护）';
COMMENT ON COLUMN operational_v2.vehicles_v2.current_volume_m3 IS '当前已占用体积（触发器维护）';
COMMENT ON COLUMN operational_v2.vehicles_v2.current_device_count IS '当前已装载设备数（触发器维护）';
COMMENT ON COLUMN operational_v2.vehicles_v2.self_weight_kg IS '车辆自重（公斤）';
COMMENT ON COLUMN operational_v2.vehicles_v2.crew_capacity IS '乘员容量';
COMMENT ON COLUMN operational_v2.vehicles_v2.terrain_capabilities IS '地形通过能力数组: {all_terrain全地形/mountain山地/flood涉水/urban城市/forest林地/desert沙漠/snow雪地}';
COMMENT ON COLUMN operational_v2.vehicles_v2.is_all_terrain IS '是否全地形越野车辆';
COMMENT ON COLUMN operational_v2.vehicles_v2.max_gradient_percent IS '最大爬坡度百分比，如60表示60%坡度';
COMMENT ON COLUMN operational_v2.vehicles_v2.max_wading_depth_m IS '最大涉水深度（米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.min_turning_radius_m IS '最小转弯半径（米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.ground_clearance_mm IS '最小离地间隙（毫米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.approach_angle_deg IS '接近角（度），车辆能爬上坡道的最大角度';
COMMENT ON COLUMN operational_v2.vehicles_v2.departure_angle_deg IS '离去角（度），车辆能离开坡道的最大角度';
COMMENT ON COLUMN operational_v2.vehicles_v2.breakover_angle_deg IS '纵向通过角（度），车辆能通过凸起地形的最大角度';
COMMENT ON COLUMN operational_v2.vehicles_v2.max_speed_kmh IS '最大速度（公里/小时）';
COMMENT ON COLUMN operational_v2.vehicles_v2.terrain_speed_factors IS '地形速度系数JSON，如{"mountain":0.6,"forest":0.5}，1.0为标准路面';
COMMENT ON COLUMN operational_v2.vehicles_v2.fuel_capacity_l IS '油箱容量（升）';
COMMENT ON COLUMN operational_v2.vehicles_v2.fuel_consumption_per_100km IS '百公里油耗（升）';
COMMENT ON COLUMN operational_v2.vehicles_v2.range_km IS '满油续航里程（公里）';
COMMENT ON COLUMN operational_v2.vehicles_v2.length_m IS '车长（米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.width_m IS '车宽（米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.height_m IS '车高（米）';
COMMENT ON COLUMN operational_v2.vehicles_v2.status IS '状态: available可用/deployed已出动/maintenance维护中';
COMMENT ON COLUMN operational_v2.vehicles_v2.entity_id IS '关联地图实体ID';
COMMENT ON COLUMN operational_v2.vehicles_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.vehicles_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.vehicles_v2.updated_at IS '更新时间';

CREATE INDEX idx_vehicles_v2_type ON operational_v2.vehicles_v2(vehicle_type);
CREATE INDEX idx_vehicles_v2_status ON operational_v2.vehicles_v2(status);

-- ============================================================================
-- 5. 设备表 (devices_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.devices_v2 CASCADE;
CREATE TABLE operational_v2.devices_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    device_type operational_v2.device_type_v2 NOT NULL,
    env_type VARCHAR(20) NOT NULL,
    
    -- 物理属性
    weight_kg DECIMAL(10,2) NOT NULL,
    volume_m3 DECIMAL(10,4) NOT NULL,
    
    -- 模块系统
    module_slots INT DEFAULT 0,
    current_module_count INT DEFAULT 0,
    compatible_module_types operational_v2.module_type_v2[],
    
    -- 灾害适用性
    applicable_disasters TEXT[],
    forbidden_disasters TEXT[],
    min_response_level VARCHAR(10),
    
    -- 设备能力（不通过模块，设备自带的能力）
    base_capabilities TEXT[],
    
    -- 型号信息
    model VARCHAR(100),
    manufacturer VARCHAR(100),
    
    -- 状态
    status VARCHAR(20) DEFAULT 'available',
    in_vehicle_id UUID,
    entity_id UUID,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.devices_v2 IS '设备表 - 无人机/机器狗/无人艇等设备';
COMMENT ON COLUMN operational_v2.devices_v2.id IS '设备唯一标识符';
COMMENT ON COLUMN operational_v2.devices_v2.code IS '设备编号，如DV-DRONE-001';
COMMENT ON COLUMN operational_v2.devices_v2.name IS '设备名称';
COMMENT ON COLUMN operational_v2.devices_v2.device_type IS '设备类型: drone无人机/dog机器狗/ship无人艇/robot机器人';
COMMENT ON COLUMN operational_v2.devices_v2.env_type IS '作业环境: air空中/land地面/sea水上';
COMMENT ON COLUMN operational_v2.devices_v2.weight_kg IS '设备重量（公斤）';
COMMENT ON COLUMN operational_v2.devices_v2.volume_m3 IS '设备体积（立方米）';
COMMENT ON COLUMN operational_v2.devices_v2.module_slots IS '模块插槽数量';
COMMENT ON COLUMN operational_v2.devices_v2.current_module_count IS '当前已安装模块数（触发器维护）';
COMMENT ON COLUMN operational_v2.devices_v2.compatible_module_types IS '可安装的模块类型数组';
COMMENT ON COLUMN operational_v2.devices_v2.applicable_disasters IS '适用灾害类型数组';
COMMENT ON COLUMN operational_v2.devices_v2.forbidden_disasters IS '禁用灾害类型数组（如危化品场景禁用有火花风险设备）';
COMMENT ON COLUMN operational_v2.devices_v2.min_response_level IS '最低响应等级要求（某些设备仅用于重大灾害）';
COMMENT ON COLUMN operational_v2.devices_v2.base_capabilities IS '设备自带能力（不依赖模块）';
COMMENT ON COLUMN operational_v2.devices_v2.model IS '设备型号';
COMMENT ON COLUMN operational_v2.devices_v2.manufacturer IS '生产厂商';
COMMENT ON COLUMN operational_v2.devices_v2.status IS '状态: available可用/deployed已部署/charging充电中/maintenance维护中';
COMMENT ON COLUMN operational_v2.devices_v2.in_vehicle_id IS '当前所在车辆ID';
COMMENT ON COLUMN operational_v2.devices_v2.entity_id IS '关联地图实体ID';
COMMENT ON COLUMN operational_v2.devices_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.devices_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.devices_v2.updated_at IS '更新时间';

CREATE INDEX idx_devices_v2_type ON operational_v2.devices_v2(device_type);
CREATE INDEX idx_devices_v2_status ON operational_v2.devices_v2(status);
CREATE INDEX idx_devices_v2_vehicle ON operational_v2.devices_v2(in_vehicle_id);

-- ============================================================================
-- 6. 模块表 (modules_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.modules_v2 CASCADE;
CREATE TABLE operational_v2.modules_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    module_type operational_v2.module_type_v2 NOT NULL,
    
    -- 物理属性
    weight_kg DECIMAL(10,2) NOT NULL,
    slots_required INT DEFAULT 1,
    
    -- 兼容性
    compatible_device_types operational_v2.device_type_v2[] NOT NULL,
    
    -- 能力
    provides_capability VARCHAR(100) NOT NULL,
    capability_params JSONB DEFAULT '{}',
    
    -- 灾害适用性
    applicable_disasters TEXT[],
    forbidden_disasters TEXT[],
    required_for_disasters TEXT[],
    
    -- 型号信息
    model VARCHAR(100),
    manufacturer VARCHAR(100),
    
    -- 状态
    status VARCHAR(20) DEFAULT 'available',
    mounted_on_device_id UUID,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.modules_v2 IS '模块表 - 设备可携带的功能模块';
COMMENT ON COLUMN operational_v2.modules_v2.id IS '模块唯一标识符';
COMMENT ON COLUMN operational_v2.modules_v2.code IS '模块编号，如MD-THERMAL-001';
COMMENT ON COLUMN operational_v2.modules_v2.name IS '模块名称';
COMMENT ON COLUMN operational_v2.modules_v2.module_type IS '模块类型: sensor传感器/communication通信/utility功能/power电源';
COMMENT ON COLUMN operational_v2.modules_v2.weight_kg IS '模块重量（公斤）';
COMMENT ON COLUMN operational_v2.modules_v2.slots_required IS '占用插槽数';
COMMENT ON COLUMN operational_v2.modules_v2.compatible_device_types IS '可安装的设备类型';
COMMENT ON COLUMN operational_v2.modules_v2.provides_capability IS '提供的能力编码';
COMMENT ON COLUMN operational_v2.modules_v2.capability_params IS '能力参数JSON，如探测范围、精度等';
COMMENT ON COLUMN operational_v2.modules_v2.applicable_disasters IS '适用灾害类型';
COMMENT ON COLUMN operational_v2.modules_v2.forbidden_disasters IS '禁用灾害类型';
COMMENT ON COLUMN operational_v2.modules_v2.required_for_disasters IS '某些灾害必须携带此模块';
COMMENT ON COLUMN operational_v2.modules_v2.model IS '模块型号';
COMMENT ON COLUMN operational_v2.modules_v2.manufacturer IS '生产厂商';
COMMENT ON COLUMN operational_v2.modules_v2.status IS '状态: available可用/mounted已安装/maintenance维护中';
COMMENT ON COLUMN operational_v2.modules_v2.mounted_on_device_id IS '当前安装在哪个设备上';
COMMENT ON COLUMN operational_v2.modules_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.modules_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.modules_v2.updated_at IS '更新时间';

CREATE INDEX idx_modules_v2_type ON operational_v2.modules_v2(module_type);
CREATE INDEX idx_modules_v2_capability ON operational_v2.modules_v2(provides_capability);
CREATE INDEX idx_modules_v2_device ON operational_v2.modules_v2(mounted_on_device_id);

-- ============================================================================
-- 7. 物资表 (supplies_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.supplies_v2 CASCADE;
CREATE TABLE operational_v2.supplies_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    
    -- 物理属性
    weight_kg DECIMAL(10,2) NOT NULL,
    volume_m3 DECIMAL(10,4),
    unit VARCHAR(20) DEFAULT 'piece',
    
    -- 灾害适用性
    applicable_disasters TEXT[],
    required_for_disasters TEXT[],
    
    -- 消耗性
    is_consumable BOOLEAN DEFAULT true,
    shelf_life_days INT,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.supplies_v2 IS '物资表 - 救援物资';
COMMENT ON COLUMN operational_v2.supplies_v2.id IS '物资唯一标识符';
COMMENT ON COLUMN operational_v2.supplies_v2.code IS '物资编号，如SP-MED-001';
COMMENT ON COLUMN operational_v2.supplies_v2.name IS '物资名称';
COMMENT ON COLUMN operational_v2.supplies_v2.category IS '物资类别: medical医疗/protection防护/rescue救援/communication通信/life生活/tool工具';
COMMENT ON COLUMN operational_v2.supplies_v2.weight_kg IS '单件重量（公斤）';
COMMENT ON COLUMN operational_v2.supplies_v2.volume_m3 IS '单件体积（立方米）';
COMMENT ON COLUMN operational_v2.supplies_v2.unit IS '计量单位: piece件/box箱/kg公斤/set套';
COMMENT ON COLUMN operational_v2.supplies_v2.applicable_disasters IS '适用灾害类型';
COMMENT ON COLUMN operational_v2.supplies_v2.required_for_disasters IS '某些灾害必须携带此物资';
COMMENT ON COLUMN operational_v2.supplies_v2.is_consumable IS '是否消耗品';
COMMENT ON COLUMN operational_v2.supplies_v2.shelf_life_days IS '保质期（天）';
COMMENT ON COLUMN operational_v2.supplies_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.supplies_v2.created_at IS '创建时间';

CREATE INDEX idx_supplies_v2_category ON operational_v2.supplies_v2(category);

-- ============================================================================
-- 8. 车辆装载设备关系表 (vehicle_device_loads_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.vehicle_device_loads_v2 CASCADE;
CREATE TABLE operational_v2.vehicle_device_loads_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id UUID NOT NULL REFERENCES operational_v2.vehicles_v2(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES operational_v2.devices_v2(id) ON DELETE CASCADE,
    
    quantity INT DEFAULT 1,
    
    loaded_at TIMESTAMPTZ DEFAULT now(),
    loaded_by VARCHAR(100),
    unloaded_at TIMESTAMPTZ,
    
    status VARCHAR(20) DEFAULT 'loaded',
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vehicle_id, device_id)
);

COMMENT ON TABLE operational_v2.vehicle_device_loads_v2 IS '车辆装载设备关系表';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.vehicle_id IS '车辆ID';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.device_id IS '设备ID';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.quantity IS '装载数量（通常为1）';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.loaded_at IS '装载时间';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.loaded_by IS '装载操作人';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.unloaded_at IS '卸载时间';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.status IS '状态: loaded已装载/deployed已部署/returned已归还';
COMMENT ON COLUMN operational_v2.vehicle_device_loads_v2.created_at IS '创建时间';

CREATE INDEX idx_vehicle_device_loads_v2_vehicle ON operational_v2.vehicle_device_loads_v2(vehicle_id);
CREATE INDEX idx_vehicle_device_loads_v2_device ON operational_v2.vehicle_device_loads_v2(device_id);

-- ============================================================================
-- 9. 车辆装载物资关系表 (vehicle_supply_loads_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.vehicle_supply_loads_v2 CASCADE;
CREATE TABLE operational_v2.vehicle_supply_loads_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id UUID NOT NULL REFERENCES operational_v2.vehicles_v2(id) ON DELETE CASCADE,
    supply_id UUID NOT NULL REFERENCES operational_v2.supplies_v2(id) ON DELETE CASCADE,
    
    quantity INT NOT NULL,
    
    loaded_at TIMESTAMPTZ DEFAULT now(),
    loaded_by VARCHAR(100),
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vehicle_id, supply_id)
);

COMMENT ON TABLE operational_v2.vehicle_supply_loads_v2 IS '车辆装载物资关系表';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.vehicle_id IS '车辆ID';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.supply_id IS '物资ID';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.quantity IS '装载数量';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.loaded_at IS '装载时间';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.loaded_by IS '装载操作人';
COMMENT ON COLUMN operational_v2.vehicle_supply_loads_v2.created_at IS '创建时间';

CREATE INDEX idx_vehicle_supply_loads_v2_vehicle ON operational_v2.vehicle_supply_loads_v2(vehicle_id);
CREATE INDEX idx_vehicle_supply_loads_v2_supply ON operational_v2.vehicle_supply_loads_v2(supply_id);

-- ============================================================================
-- 10. 设备安装模块关系表 (device_module_mounts_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.device_module_mounts_v2 CASCADE;
CREATE TABLE operational_v2.device_module_mounts_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id UUID NOT NULL REFERENCES operational_v2.devices_v2(id) ON DELETE CASCADE,
    module_id UUID NOT NULL REFERENCES operational_v2.modules_v2(id) ON DELETE CASCADE,
    
    slot_position INT NOT NULL,
    
    mounted_at TIMESTAMPTZ DEFAULT now(),
    mounted_by VARCHAR(100),
    unmounted_at TIMESTAMPTZ,
    
    status VARCHAR(20) DEFAULT 'mounted',
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(device_id, slot_position),
    UNIQUE(device_id, module_id)
);

COMMENT ON TABLE operational_v2.device_module_mounts_v2 IS '设备安装模块关系表';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.device_id IS '设备ID';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.module_id IS '模块ID';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.slot_position IS '安装槽位（1,2,3...）';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.mounted_at IS '安装时间';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.mounted_by IS '安装操作人';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.unmounted_at IS '卸载时间';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.status IS '状态: mounted已安装/unmounted已卸载';
COMMENT ON COLUMN operational_v2.device_module_mounts_v2.created_at IS '创建时间';

CREATE INDEX idx_device_module_mounts_v2_device ON operational_v2.device_module_mounts_v2(device_id);
CREATE INDEX idx_device_module_mounts_v2_module ON operational_v2.device_module_mounts_v2(module_id);

-- ============================================================================
-- 11. 灾害装备配置规则表 (disaster_equipment_rules_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.disaster_equipment_rules_v2 CASCADE;
CREATE TABLE operational_v2.disaster_equipment_rules_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 适用条件
    disaster_type VARCHAR(50) NOT NULL,
    response_level VARCHAR(10),
    event_subtype VARCHAR(50),
    
    -- 规则内容
    rule_type VARCHAR(20) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    target_code VARCHAR(50),
    target_category VARCHAR(50),
    
    -- 数量要求
    min_quantity INT DEFAULT 1,
    recommended_quantity INT,
    max_quantity INT,
    
    -- 优先级
    priority INT DEFAULT 50,
    
    -- 说明
    rule_name VARCHAR(200),
    description TEXT,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.disaster_equipment_rules_v2 IS '灾害装备配置规则表 - 定义不同灾害/等级需要的装备配置';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.id IS '规则唯一标识符';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.disaster_type IS '灾害类型: earthquake/flood/fire/hazmat/landslide';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.response_level IS '响应等级: I/II/III/IV';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.event_subtype IS '事件子类型: building_collapse/people_trapped等';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.rule_type IS '规则类型: required必须/recommended推荐/forbidden禁止';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.target_type IS '目标类型: device/module/supply';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.target_code IS '目标编码（具体某个设备/模块/物资）';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.target_category IS '目标类别（按类别配置，如所有sensor类型模块）';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.min_quantity IS '最少数量';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.recommended_quantity IS '推荐数量';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.max_quantity IS '最大数量';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.priority IS '优先级0-100，越大越优先';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.rule_name IS '规则名称';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.description IS '规则描述';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.disaster_equipment_rules_v2.created_at IS '创建时间';

CREATE INDEX idx_disaster_equipment_rules_v2_disaster ON operational_v2.disaster_equipment_rules_v2(disaster_type);
CREATE INDEX idx_disaster_equipment_rules_v2_level ON operational_v2.disaster_equipment_rules_v2(response_level);
CREATE INDEX idx_disaster_equipment_rules_v2_type ON operational_v2.disaster_equipment_rules_v2(rule_type);

-- ============================================================================
-- 12. 约束检查函数
-- ============================================================================

-- 函数: 检查车辆是否可以装载设备
CREATE OR REPLACE FUNCTION operational_v2.check_vehicle_can_load_device(
    p_vehicle_id UUID,
    p_device_id UUID
) RETURNS TABLE (
    can_load BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_vehicle operational_v2.vehicles_v2%ROWTYPE;
    v_device operational_v2.devices_v2%ROWTYPE;
BEGIN
    SELECT * INTO v_vehicle FROM operational_v2.vehicles_v2 WHERE id = p_vehicle_id;
    SELECT * INTO v_device FROM operational_v2.devices_v2 WHERE id = p_device_id;
    
    IF v_vehicle.id IS NULL THEN
        RETURN QUERY SELECT FALSE, '车辆不存在';
        RETURN;
    END IF;
    
    IF v_device.id IS NULL THEN
        RETURN QUERY SELECT FALSE, '设备不存在';
        RETURN;
    END IF;
    
    -- 检查类型兼容性
    IF NOT v_device.device_type = ANY(v_vehicle.compatible_device_types) THEN
        RETURN QUERY SELECT FALSE, '设备类型与车辆不兼容: ' || v_device.device_type::TEXT;
        RETURN;
    END IF;
    
    -- 检查重量
    IF v_vehicle.current_weight_kg + v_device.weight_kg > v_vehicle.max_weight_kg THEN
        RETURN QUERY SELECT FALSE, '超过最大载重: 当前' || v_vehicle.current_weight_kg || 'kg + 设备' || v_device.weight_kg || 'kg > 最大' || v_vehicle.max_weight_kg || 'kg';
        RETURN;
    END IF;
    
    -- 检查体积
    IF v_vehicle.current_volume_m3 + v_device.volume_m3 > v_vehicle.max_volume_m3 THEN
        RETURN QUERY SELECT FALSE, '超过最大容积';
        RETURN;
    END IF;
    
    -- 检查设备位
    IF v_vehicle.current_device_count >= v_vehicle.max_device_slots THEN
        RETURN QUERY SELECT FALSE, '超过最大设备位: 当前' || v_vehicle.current_device_count || ' >= 最大' || v_vehicle.max_device_slots;
        RETURN;
    END IF;
    
    RETURN QUERY SELECT TRUE, '可以装载';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.check_vehicle_can_load_device IS '检查车辆是否可以装载指定设备，返回是否可装载及原因';

-- 函数: 检查设备是否可以安装模块
CREATE OR REPLACE FUNCTION operational_v2.check_device_can_mount_module(
    p_device_id UUID,
    p_module_id UUID,
    p_slot_position INT
) RETURNS TABLE (
    can_mount BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_device operational_v2.devices_v2%ROWTYPE;
    v_module operational_v2.modules_v2%ROWTYPE;
    v_existing_count INT;
BEGIN
    SELECT * INTO v_device FROM operational_v2.devices_v2 WHERE id = p_device_id;
    SELECT * INTO v_module FROM operational_v2.modules_v2 WHERE id = p_module_id;
    
    IF v_device.id IS NULL THEN
        RETURN QUERY SELECT FALSE, '设备不存在';
        RETURN;
    END IF;
    
    IF v_module.id IS NULL THEN
        RETURN QUERY SELECT FALSE, '模块不存在';
        RETURN;
    END IF;
    
    -- 检查模块类型兼容性
    IF v_device.compatible_module_types IS NOT NULL AND 
       NOT v_module.module_type = ANY(v_device.compatible_module_types) THEN
        RETURN QUERY SELECT FALSE, '模块类型与设备不兼容';
        RETURN;
    END IF;
    
    -- 检查设备类型兼容性
    IF NOT v_device.device_type = ANY(v_module.compatible_device_types) THEN
        RETURN QUERY SELECT FALSE, '设备类型与模块不兼容';
        RETURN;
    END IF;
    
    -- 检查槽位是否超出
    IF p_slot_position > v_device.module_slots THEN
        RETURN QUERY SELECT FALSE, '槽位超出范围: 位置' || p_slot_position || ' > 最大槽位' || v_device.module_slots;
        RETURN;
    END IF;
    
    -- 检查槽位是否已占用
    SELECT COUNT(*) INTO v_existing_count 
    FROM operational_v2.device_module_mounts_v2 
    WHERE device_id = p_device_id AND slot_position = p_slot_position AND status = 'mounted';
    
    IF v_existing_count > 0 THEN
        RETURN QUERY SELECT FALSE, '槽位' || p_slot_position || '已被占用';
        RETURN;
    END IF;
    
    RETURN QUERY SELECT TRUE, '可以安装';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.check_device_can_mount_module IS '检查设备是否可以安装指定模块到指定槽位';

-- ============================================================================
-- 13. 触发器：装载设备时更新车辆状态
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.trg_update_vehicle_on_device_load()
RETURNS TRIGGER AS $$
DECLARE
    v_device operational_v2.devices_v2%ROWTYPE;
BEGIN
    SELECT * INTO v_device FROM operational_v2.devices_v2 WHERE id = NEW.device_id;
    
    IF TG_OP = 'INSERT' THEN
        -- 更新车辆当前载重
        UPDATE operational_v2.vehicles_v2 SET
            current_weight_kg = current_weight_kg + v_device.weight_kg,
            current_volume_m3 = current_volume_m3 + v_device.volume_m3,
            current_device_count = current_device_count + 1,
            updated_at = now()
        WHERE id = NEW.vehicle_id;
        
        -- 更新设备所在车辆
        UPDATE operational_v2.devices_v2 SET
            in_vehicle_id = NEW.vehicle_id,
            updated_at = now()
        WHERE id = NEW.device_id;
        
    ELSIF TG_OP = 'DELETE' THEN
        SELECT * INTO v_device FROM operational_v2.devices_v2 WHERE id = OLD.device_id;
        
        UPDATE operational_v2.vehicles_v2 SET
            current_weight_kg = current_weight_kg - v_device.weight_kg,
            current_volume_m3 = current_volume_m3 - v_device.volume_m3,
            current_device_count = current_device_count - 1,
            updated_at = now()
        WHERE id = OLD.vehicle_id;
        
        UPDATE operational_v2.devices_v2 SET
            in_vehicle_id = NULL,
            updated_at = now()
        WHERE id = OLD.device_id;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vehicle_device_load ON operational_v2.vehicle_device_loads_v2;
CREATE TRIGGER trg_vehicle_device_load
    AFTER INSERT OR DELETE ON operational_v2.vehicle_device_loads_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.trg_update_vehicle_on_device_load();

-- ============================================================================
-- 14. 触发器：安装模块时更新设备状态
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.trg_update_device_on_module_mount()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE operational_v2.devices_v2 SET
            current_module_count = current_module_count + 1,
            updated_at = now()
        WHERE id = NEW.device_id;
        
        UPDATE operational_v2.modules_v2 SET
            mounted_on_device_id = NEW.device_id,
            status = 'mounted',
            updated_at = now()
        WHERE id = NEW.module_id;
        
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE operational_v2.devices_v2 SET
            current_module_count = current_module_count - 1,
            updated_at = now()
        WHERE id = OLD.device_id;
        
        UPDATE operational_v2.modules_v2 SET
            mounted_on_device_id = NULL,
            status = 'available',
            updated_at = now()
        WHERE id = OLD.module_id;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_device_module_mount ON operational_v2.device_module_mounts_v2;
CREATE TRIGGER trg_device_module_mount
    AFTER INSERT OR DELETE ON operational_v2.device_module_mounts_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.trg_update_device_on_module_mount();

-- ============================================================================
-- 15. 插入车辆数据
-- ============================================================================
INSERT INTO operational_v2.vehicles_v2 (
    code, name, vehicle_type, max_weight_kg, max_volume_m3, max_device_slots, compatible_device_types, 
    self_weight_kg, crew_capacity, 
    -- 地形通过能力
    terrain_capabilities, is_all_terrain, max_gradient_percent, max_wading_depth_m, min_turning_radius_m,
    -- 通过性参数
    ground_clearance_mm, approach_angle_deg, departure_angle_deg, breakover_angle_deg,
    -- 速度/续航
    max_speed_kmh, terrain_speed_factors, fuel_capacity_l, fuel_consumption_per_100km, range_km,
    -- 尺寸
    length_m, width_m, height_m
) VALUES
-- 前突侦察控制车 - 全地形越野
('VH-001', '前突侦察控制车', 'reconnaissance', 500, 3.0, 8, '{drone,dog}', 
 3500, 4, 
 '{all_terrain,mountain,forest}', true, 60, 0.8, 6.5,
 350, 45, 40, 25,
 120, '{"urban":1.0,"mountain":0.6,"forest":0.5,"desert":0.7,"snow":0.4}', 80, 15, 530,
 5.2, 2.1, 2.3),

-- 综合保障车 - 城市/山地
('VH-002', '综合保障车', 'logistics', 800, 5.0, 6, '{drone,dog}', 
 4000, 6, 
 '{urban,mountain}', false, 40, 0.5, 8.0,
 250, 30, 25, 18,
 100, '{"urban":1.0,"mountain":0.5,"forest":0.4}', 120, 20, 600,
 6.5, 2.3, 2.8),

-- 多功能无人机输送车 - 全地形
('VH-003', '多功能无人机输送车', 'drone_transport', 400, 4.0, 10, '{drone}', 
 3000, 3, 
 '{all_terrain,mountain,desert}', true, 55, 0.6, 7.0,
 320, 42, 38, 22,
 110, '{"urban":1.0,"mountain":0.6,"forest":0.5,"desert":0.8}', 70, 14, 500,
 5.0, 2.0, 2.2),

-- 多功能无人艇输送车 - 城市/涉水
('VH-004', '多功能无人艇输送车', 'ship_transport', 600, 6.0, 4, '{ship}', 
 4500, 3, 
 '{urban,flood}', false, 30, 1.2, 9.0,
 280, 28, 25, 15,
 90, '{"urban":1.0,"flood":0.3}', 100, 18, 550,
 7.0, 2.4, 2.6),

-- 医疗救援车 - 城市/山地
('VH-005', '医疗救援车', 'medical', 500, 4.0, 4, '{drone,dog,ship}', 
 3800, 4, 
 '{urban,mountain}', false, 35, 0.4, 7.5,
 220, 25, 22, 16,
 130, '{"urban":1.0,"mountain":0.5}', 90, 16, 560,
 5.8, 2.2, 2.5),

-- 全地形越野指挥车 - 最强通过性
('VH-006', '全地形越野指挥车', 'command', 400, 2.5, 4, '{drone,dog}', 
 2800, 4, 
 '{all_terrain,mountain,forest,desert,snow}', true, 70, 1.0, 5.5,
 400, 52, 48, 30,
 140, '{"urban":1.0,"mountain":0.7,"forest":0.6,"desert":0.8,"snow":0.5}', 85, 18, 470,
 4.8, 1.9, 2.0);

-- ============================================================================
-- 16. 插入设备数据
-- ============================================================================
INSERT INTO operational_v2.devices_v2 (code, name, device_type, env_type, weight_kg, volume_m3, module_slots, compatible_module_types, applicable_disasters, base_capabilities, model, manufacturer) VALUES
-- 无人机
('DV-DRONE-001', '扫图建模无人机', 'drone', 'air', 15.0, 0.08, 2, '{sensor}', '{earthquake,flood,landslide}', '{aerial_recon,3d_mapping}', 'Matrice4TD', 'DJI'),
('DV-DRONE-002', '灾情侦察无人机', 'drone', 'air', 10.0, 0.05, 3, '{sensor,communication}', '{earthquake,flood,fire,landslide}', '{aerial_recon,video_stream}', 'Matrice4D', 'DJI'),
('DV-DRONE-003', '物资投送无人机', 'drone', 'air', 25.0, 0.12, 1, '{utility}', '{earthquake,flood}', '{cargo_delivery}', 'FC100', 'DJI'),
('DV-DRONE-004', '医疗救援无人机', 'drone', 'air', 18.0, 0.09, 2, '{utility,communication}', '{earthquake,flood,landslide}', '{medical_delivery}', 'FC100', 'DJI'),

-- 机器狗
('DV-DOG-001', '灾情侦察机器狗', 'dog', 'land', 30.0, 0.15, 2, '{sensor}', '{earthquake,hazmat,fire}', '{ground_recon}', 'B1', 'Unitree'),
('DV-DOG-002', '人员搜救机器狗', 'dog', 'land', 35.0, 0.18, 3, '{sensor,communication}', '{earthquake,landslide}', '{search_rescue,life_detection}', 'B2', 'Unitree'),
('DV-DOG-003', '灾情分析机器狗', 'dog', 'land', 32.0, 0.16, 2, '{sensor}', '{earthquake,hazmat}', '{environment_analysis}', 'A1', 'Unitree'),
('DV-DOG-004', '通讯组网机器狗', 'dog', 'land', 28.0, 0.14, 1, '{communication}', '{earthquake,flood,landslide}', '{communication_relay}', 'Go2', 'Unitree'),

-- 无人艇
('DV-SHIP-001', '灾情侦察无人艇', 'ship', 'sea', 80.0, 0.6, 2, '{sensor,communication}', '{flood}', '{water_recon}', 'Orca-S', 'Orca'),
('DV-SHIP-002', '人员搜救无人艇', 'ship', 'sea', 120.0, 0.9, 2, '{sensor,utility}', '{flood}', '{water_rescue}', 'Orca-R', 'Orca'),
('DV-SHIP-003', '物资运输无人艇', 'ship', 'sea', 100.0, 0.8, 1, '{utility}', '{flood}', '{cargo_transport}', 'Orca-T', 'Orca');

-- ============================================================================
-- 17. 插入模块数据
-- ============================================================================
INSERT INTO operational_v2.modules_v2 (code, name, module_type, weight_kg, slots_required, compatible_device_types, provides_capability, capability_params, applicable_disasters, required_for_disasters) VALUES
-- 传感器模块
('MD-THERMAL-001', '热成像相机模块', 'sensor', 1.5, 1, '{drone,dog}', 'THERMAL_IMAGING', '{"resolution": "640x480", "range_m": 500}', '{earthquake,fire}', '{fire}'),
('MD-LIFE-001', '生命探测模块', 'sensor', 2.5, 1, '{drone,dog}', 'LIFE_DETECTION', '{"detection_depth_m": 10, "accuracy": 0.85}', '{earthquake,landslide}', '{earthquake}'),
('MD-GAS-001', '气体探测模块', 'sensor', 1.8, 1, '{drone,dog}', 'GAS_DETECTION', '{"gases": ["CO","CH4","H2S"], "range_ppm": "0-1000"}', '{hazmat,fire}', '{hazmat}'),
('MD-LIDAR-001', '激光雷达模块', 'sensor', 2.0, 1, '{drone}', '3D_SCANNING', '{"range_m": 300, "points_per_sec": 300000}', '{earthquake,landslide}', NULL),
('MD-SONAR-001', '声纳探测模块', 'sensor', 3.0, 1, '{ship}', 'UNDERWATER_DETECTION', '{"depth_m": 50, "range_m": 100}', '{flood}', NULL),

-- 通信模块
('MD-RELAY-001', '通信中继模块', 'communication', 1.2, 1, '{drone,dog}', 'COMM_RELAY', '{"range_km": 10, "bandwidth_mbps": 50}', '{earthquake,flood,landslide}', NULL),
('MD-SPEAKER-001', '广播喊话模块', 'communication', 0.8, 1, '{drone}', 'BROADCAST', '{"power_w": 50, "range_m": 500}', '{earthquake,flood}', NULL),
('MD-5G-001', '5G通信模块', 'communication', 1.0, 1, '{drone,dog,ship}', '5G_LINK', '{"bandwidth_mbps": 100}', '{earthquake,flood,landslide}', NULL),

-- 功能模块
('MD-DROP-001', '物资投放模块', 'utility', 2.0, 1, '{drone}', 'CARGO_DROP', '{"capacity_kg": 5, "accuracy_m": 3}', '{earthquake,flood}', NULL),
('MD-SAMPLE-001', '水质采样模块', 'utility', 1.5, 1, '{ship}', 'WATER_SAMPLING', '{"volume_ml": 500}', '{flood,hazmat}', NULL),
('MD-RESCUE-001', '救生设备模块', 'utility', 5.0, 1, '{ship}', 'RESCUE_EQUIPMENT', '{"lifebuoys": 4, "rope_m": 50}', '{flood}', '{flood}'),

-- 电源模块
('MD-BATTERY-001', '扩展电池模块', 'power', 3.0, 1, '{drone,dog}', 'EXTENDED_BATTERY', '{"capacity_wh": 500, "extra_time_min": 30}', '{earthquake,flood,landslide}', NULL);

-- ============================================================================
-- 18. 插入物资数据
-- ============================================================================
INSERT INTO operational_v2.supplies_v2 (code, name, category, weight_kg, volume_m3, unit, applicable_disasters, required_for_disasters, is_consumable) VALUES
-- 医疗物资
('SP-MED-001', '急救背囊', 'medical', 8.0, 0.03, 'piece', '{earthquake,flood,fire,landslide}', NULL, true),
('SP-MED-002', '便携式AED', 'medical', 1.5, 0.005, 'piece', '{earthquake,flood,fire}', NULL, false),
('SP-MED-003', '医疗氧气瓶', 'medical', 5.0, 0.008, 'piece', '{earthquake,fire,hazmat}', NULL, true),
('SP-MED-004', '止血带', 'medical', 0.1, 0.0001, 'piece', '{earthquake,flood,fire,landslide}', NULL, true),
('SP-MED-005', '脊柱固定板', 'medical', 4.5, 0.02, 'piece', '{earthquake,landslide}', '{earthquake}', false),

-- 防护物资
('SP-PROT-001', '防毒面具', 'protection', 0.5, 0.002, 'piece', '{hazmat,fire}', '{hazmat}', false),
('SP-PROT-002', 'A级防护服', 'protection', 2.5, 0.01, 'piece', '{hazmat}', '{hazmat}', false),
('SP-PROT-003', '抗震头盔', 'protection', 0.8, 0.003, 'piece', '{earthquake,landslide}', '{earthquake}', false),
('SP-PROT-004', '救生衣', 'protection', 1.2, 0.005, 'piece', '{flood}', '{flood}', false),
('SP-PROT-005', '空气呼吸器', 'protection', 11.0, 0.02, 'piece', '{fire,hazmat}', '{fire}', false),

-- 救援工具
('SP-RESC-001', '液压破拆工具', 'rescue', 25.0, 0.08, 'set', '{earthquake,landslide}', '{earthquake}', false),
('SP-RESC-002', '生命探测仪', 'rescue', 8.0, 0.02, 'piece', '{earthquake,landslide}', '{earthquake}', false),
('SP-RESC-003', '救援绳索套装', 'rescue', 15.0, 0.05, 'set', '{earthquake,flood,landslide}', NULL, false),
('SP-RESC-004', '气垫', 'rescue', 12.0, 0.04, 'piece', '{earthquake}', NULL, false),

-- 通信物资
('SP-COMM-001', '卫星电话', 'communication', 0.35, 0.001, 'piece', '{earthquake,flood,landslide}', '{earthquake}', false),
('SP-COMM-002', '数字对讲机', 'communication', 0.35, 0.001, 'piece', '{earthquake,flood,fire,landslide}', NULL, false),
('SP-COMM-003', '便携式中继台', 'communication', 15.0, 0.05, 'piece', '{earthquake,flood}', NULL, false),

-- 生活物资
('SP-LIFE-001', '帐篷', 'life', 15.0, 0.08, 'piece', '{earthquake,flood,landslide}', NULL, false),
('SP-LIFE-002', '睡袋', 'life', 2.0, 0.01, 'piece', '{earthquake,flood,landslide}', NULL, false),
('SP-LIFE-003', '饮用水', 'life', 1.0, 0.001, 'kg', '{earthquake,flood,landslide}', NULL, true),
('SP-LIFE-004', '压缩干粮', 'life', 0.5, 0.0005, 'piece', '{earthquake,flood,landslide}', NULL, true),

-- 工具
('SP-TOOL-001', '强光手电', 'tool', 0.3, 0.0005, 'piece', '{earthquake,flood,fire,landslide}', NULL, false),
('SP-TOOL-002', '便携式发电机', 'tool', 78.0, 0.3, 'piece', '{earthquake,flood}', NULL, false),
('SP-TOOL-003', '多功能工具箱', 'tool', 8.0, 0.02, 'piece', '{earthquake,flood,landslide}', NULL, false);

-- ============================================================================
-- 19. 插入灾害装备配置规则
-- ============================================================================
INSERT INTO operational_v2.disaster_equipment_rules_v2 (disaster_type, response_level, event_subtype, rule_type, target_type, target_code, target_category, min_quantity, recommended_quantity, priority, rule_name, description) VALUES
-- 地震-建筑倒塌 必须配置
('earthquake', NULL, 'building_collapse', 'required', 'module', 'MD-LIFE-001', NULL, 1, 2, 100, '必须携带生命探测模块', '建筑倒塌场景必须配备生命探测能力'),
('earthquake', NULL, 'building_collapse', 'required', 'supply', 'SP-RESC-001', NULL, 1, 2, 95, '必须携带液压破拆工具', '建筑救援必备破拆工具'),
('earthquake', NULL, 'building_collapse', 'required', 'supply', 'SP-MED-005', NULL, 2, 4, 90, '必须携带脊柱固定板', '转运伤员必备'),

-- 地震-通用配置
('earthquake', NULL, NULL, 'required', 'device', NULL, 'drone', 1, 2, 85, '必须配备无人机', '地震侦察必备空中视角'),
('earthquake', NULL, NULL, 'required', 'device', NULL, 'dog', 1, 2, 80, '必须配备机器狗', '废墟搜索必备'),
('earthquake', NULL, NULL, 'recommended', 'module', 'MD-THERMAL-001', NULL, 1, 2, 70, '建议携带热成像模块', '夜间搜索或浓烟环境'),
('earthquake', NULL, NULL, 'recommended', 'supply', 'SP-COMM-001', NULL, 1, 2, 65, '建议携带卫星电话', '通信中断时备用'),

-- 地震-等级配置
('earthquake', 'I', NULL, 'required', 'device', NULL, 'drone', 3, 5, 95, 'I级响应需要大量无人机', '特别重大地震需要大规模侦察'),
('earthquake', 'I', NULL, 'required', 'device', NULL, 'dog', 4, 6, 90, 'I级响应需要大量机器狗', '大范围搜索'),
('earthquake', 'II', NULL, 'required', 'device', NULL, 'drone', 2, 3, 85, 'II级响应无人机配置', NULL),
('earthquake', 'II', NULL, 'required', 'device', NULL, 'dog', 2, 4, 80, 'II级响应机器狗配置', NULL),

-- 洪涝灾害配置
('flood', NULL, NULL, 'required', 'device', NULL, 'ship', 1, 2, 100, '洪涝必须配备无人艇', '水上救援核心装备'),
('flood', NULL, NULL, 'required', 'supply', 'SP-PROT-004', NULL, 10, 20, 95, '必须携带救生衣', '水上救援必备'),
('flood', NULL, NULL, 'required', 'module', 'MD-RESCUE-001', NULL, 1, 2, 90, '必须携带救生设备模块', '无人艇救援配置'),
('flood', NULL, 'people_stranded', 'recommended', 'device', NULL, 'drone', 1, 2, 80, '建议配备无人机', '空中侦察定位被困人员'),

-- 危化品泄漏配置
('hazmat', NULL, NULL, 'required', 'module', 'MD-GAS-001', NULL, 2, 4, 100, '必须携带气体探测模块', '危化品场景核心能力'),
('hazmat', NULL, NULL, 'required', 'supply', 'SP-PROT-001', NULL, 10, 20, 95, '必须携带防毒面具', '人员防护必备'),
('hazmat', NULL, NULL, 'required', 'supply', 'SP-PROT-002', NULL, 4, 8, 90, '必须携带防护服', '进入污染区必备'),
('hazmat', NULL, NULL, 'forbidden', 'device', 'DV-DRONE-003', NULL, NULL, NULL, 100, '禁止使用物资投送无人机', '有爆炸风险'),

-- 火灾配置
('fire', NULL, NULL, 'required', 'module', 'MD-THERMAL-001', NULL, 1, 2, 100, '必须携带热成像模块', '火灾现场必备'),
('fire', NULL, NULL, 'required', 'supply', 'SP-PROT-005', NULL, 4, 8, 95, '必须携带空气呼吸器', '烟雾环境必备'),
('fire', NULL, NULL, 'recommended', 'device', NULL, 'drone', 1, 2, 80, '建议配备无人机', '高空侦察火情'),

-- 滑坡/泥石流配置
('landslide', NULL, NULL, 'required', 'device', NULL, 'drone', 1, 2, 100, '必须配备无人机', '大范围侦察'),
('landslide', NULL, NULL, 'required', 'module', 'MD-LIFE-001', NULL, 1, 2, 95, '必须携带生命探测模块', '掩埋人员搜索'),
('landslide', NULL, NULL, 'recommended', 'module', 'MD-LIDAR-001', NULL, 1, 1, 80, '建议携带激光雷达', '地形变化监测');

-- ============================================================================
-- 20. 创建视图：车辆装载汇总
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.v_vehicle_load_summary_v2 AS
SELECT 
    v.id AS vehicle_id,
    v.code AS vehicle_code,
    v.name AS vehicle_name,
    v.vehicle_type,
    v.max_weight_kg,
    v.current_weight_kg,
    ROUND((v.current_weight_kg / v.max_weight_kg * 100)::numeric, 1) AS weight_usage_percent,
    v.max_volume_m3,
    v.current_volume_m3,
    ROUND((v.current_volume_m3 / v.max_volume_m3 * 100)::numeric, 1) AS volume_usage_percent,
    v.max_device_slots,
    v.current_device_count,
    v.status,
    (SELECT array_agg(d.name) FROM operational_v2.vehicle_device_loads_v2 vdl 
     JOIN operational_v2.devices_v2 d ON vdl.device_id = d.id 
     WHERE vdl.vehicle_id = v.id AND vdl.status = 'loaded') AS loaded_devices,
    (SELECT COUNT(*) FROM operational_v2.vehicle_supply_loads_v2 vsl WHERE vsl.vehicle_id = v.id) AS supply_types_count
FROM operational_v2.vehicles_v2 v;

COMMENT ON VIEW operational_v2.v_vehicle_load_summary_v2 IS '车辆装载汇总视图';

-- ============================================================================
-- 21. 创建视图：设备模块汇总
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.v_device_module_summary_v2 AS
SELECT 
    d.id AS device_id,
    d.code AS device_code,
    d.name AS device_name,
    d.device_type,
    d.module_slots,
    d.current_module_count,
    d.module_slots - d.current_module_count AS available_slots,
    d.in_vehicle_id,
    v.name AS in_vehicle_name,
    d.status,
    (SELECT array_agg(m.name ORDER BY dmm.slot_position) 
     FROM operational_v2.device_module_mounts_v2 dmm 
     JOIN operational_v2.modules_v2 m ON dmm.module_id = m.id 
     WHERE dmm.device_id = d.id AND dmm.status = 'mounted') AS mounted_modules,
    (SELECT array_agg(m.provides_capability ORDER BY dmm.slot_position) 
     FROM operational_v2.device_module_mounts_v2 dmm 
     JOIN operational_v2.modules_v2 m ON dmm.module_id = m.id 
     WHERE dmm.device_id = d.id AND dmm.status = 'mounted') AS capabilities
FROM operational_v2.devices_v2 d
LEFT JOIN operational_v2.vehicles_v2 v ON d.in_vehicle_id = v.id;

COMMENT ON VIEW operational_v2.v_device_module_summary_v2 IS '设备模块汇总视图';

-- ============================================================================
-- 22. 创建函数：获取灾害推荐配置
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.get_disaster_equipment_recommendations(
    p_disaster_type VARCHAR(50),
    p_response_level VARCHAR(10) DEFAULT NULL,
    p_event_subtype VARCHAR(50) DEFAULT NULL
) RETURNS TABLE (
    rule_type VARCHAR(20),
    target_type VARCHAR(20),
    target_code VARCHAR(50),
    target_category VARCHAR(50),
    min_quantity INT,
    recommended_quantity INT,
    priority INT,
    rule_name VARCHAR(200),
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.rule_type,
        r.target_type,
        r.target_code,
        r.target_category,
        r.min_quantity,
        r.recommended_quantity,
        r.priority,
        r.rule_name,
        r.description
    FROM operational_v2.disaster_equipment_rules_v2 r
    WHERE r.disaster_type = p_disaster_type
      AND (r.response_level IS NULL OR r.response_level = p_response_level OR p_response_level IS NULL)
      AND (r.event_subtype IS NULL OR r.event_subtype = p_event_subtype OR p_event_subtype IS NULL)
    ORDER BY r.priority DESC, r.rule_type;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.get_disaster_equipment_recommendations IS '根据灾害类型/等级/子类型获取推荐装备配置';

-- ============================================================================
-- 输出统计信息
-- ============================================================================
DO $$
DECLARE
    v_vehicles INT;
    v_devices INT;
    v_modules INT;
    v_supplies INT;
    v_rules INT;
BEGIN
    SELECT COUNT(*) INTO v_vehicles FROM operational_v2.vehicles_v2;
    SELECT COUNT(*) INTO v_devices FROM operational_v2.devices_v2;
    SELECT COUNT(*) INTO v_modules FROM operational_v2.modules_v2;
    SELECT COUNT(*) INTO v_supplies FROM operational_v2.supplies_v2;
    SELECT COUNT(*) INTO v_rules FROM operational_v2.disaster_equipment_rules_v2;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '车辆-设备-模块 V2模型创建完成';
    RAISE NOTICE '车辆数: %', v_vehicles;
    RAISE NOTICE '设备数: %', v_devices;
    RAISE NOTICE '模块数: %', v_modules;
    RAISE NOTICE '物资种类: %', v_supplies;
    RAISE NOTICE '配置规则数: %', v_rules;
    RAISE NOTICE '========================================';
END $$;
