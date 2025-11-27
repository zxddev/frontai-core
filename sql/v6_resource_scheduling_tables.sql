-- ============================================================================
-- 资源调度扩展表 V6
-- 支持：能力→装备映射、物资需求标准、装备库存
-- ============================================================================

-- ============================================================================
-- 1. 能力→装备映射表 (capability_equipment_v2)
-- 用于：根据能力需求推断所需装备
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.capability_equipment_v2 CASCADE;
CREATE TABLE operational_v2.capability_equipment_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 能力信息
    capability_code VARCHAR(50) NOT NULL,
    capability_name VARCHAR(100),
    
    -- 装备信息
    equipment_type VARCHAR(20) NOT NULL CHECK (equipment_type IN ('device', 'supply')),
    equipment_code VARCHAR(50) NOT NULL,
    equipment_name VARCHAR(200),
    
    -- 数量和优先级
    min_quantity INT DEFAULT 1 CHECK (min_quantity > 0),
    max_quantity INT,
    priority VARCHAR(20) DEFAULT 'required' CHECK (priority IN ('required', 'recommended', 'optional')),
    
    -- 说明
    description TEXT,
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(capability_code, equipment_type, equipment_code)
);

COMMENT ON TABLE operational_v2.capability_equipment_v2 IS '能力-装备映射表：根据能力需求推断所需装备';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.capability_code IS '能力编码，如LIFE_DETECTION/STRUCTURAL_RESCUE';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.equipment_type IS '装备类型：device(无人设备)/supply(物资中的装备)';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.equipment_code IS '装备编码，对应devices_v2.code或supplies_v2.code';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.min_quantity IS '最少需求数量';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.priority IS '优先级：required必须/recommended推荐/optional可选';

CREATE INDEX idx_capability_equipment_cap ON operational_v2.capability_equipment_v2(capability_code);
CREATE INDEX idx_capability_equipment_type ON operational_v2.capability_equipment_v2(equipment_type);

-- ============================================================================
-- 2. 物资需求标准表 (supply_standards_v2)
-- 用于：根据灾害类型和人数计算物资需求量
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.supply_standards_v2 CASCADE;
CREATE TABLE operational_v2.supply_standards_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 灾害类型
    disaster_type VARCHAR(50) NOT NULL,
    disaster_subtype VARCHAR(50),
    
    -- 物资信息
    supply_code VARCHAR(50) NOT NULL,
    supply_name VARCHAR(200),
    supply_category VARCHAR(50),
    
    -- 需求标准
    per_person_per_day DECIMAL(8,3) NOT NULL CHECK (per_person_per_day >= 0),
    unit VARCHAR(20) NOT NULL,
    
    -- 优先级和说明
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    description TEXT,
    
    -- 参考来源
    reference_standard VARCHAR(200),
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(disaster_type, COALESCE(disaster_subtype, ''), supply_code)
);

COMMENT ON TABLE operational_v2.supply_standards_v2 IS '物资需求标准表：人均每天物资需求量';
COMMENT ON COLUMN operational_v2.supply_standards_v2.disaster_type IS '灾害类型：earthquake/fire/flood/hazmat等';
COMMENT ON COLUMN operational_v2.supply_standards_v2.per_person_per_day IS '人均每天需求量';
COMMENT ON COLUMN operational_v2.supply_standards_v2.unit IS '计量单位：liter/pack/piece/set等';
COMMENT ON COLUMN operational_v2.supply_standards_v2.reference_standard IS '参考标准来源，如GB/T xxxx';

CREATE INDEX idx_supply_standards_disaster ON operational_v2.supply_standards_v2(disaster_type);
CREATE INDEX idx_supply_standards_priority ON operational_v2.supply_standards_v2(priority);

-- ============================================================================
-- 3. 装备库存表 (equipment_inventory_v2)
-- 用于：跟踪装备的存放位置和可用状态
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.equipment_inventory_v2 CASCADE;
CREATE TABLE operational_v2.equipment_inventory_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 装备信息
    equipment_type VARCHAR(20) NOT NULL CHECK (equipment_type IN ('device', 'supply')),
    equipment_id UUID NOT NULL,
    equipment_code VARCHAR(50) NOT NULL,
    
    -- 存放位置（关联shelter或team）
    location_type VARCHAR(20) NOT NULL CHECK (location_type IN ('shelter', 'team', 'vehicle', 'warehouse')),
    location_id UUID NOT NULL,
    location_name VARCHAR(200),
    
    -- 数量
    total_quantity INT NOT NULL DEFAULT 0 CHECK (total_quantity >= 0),
    available_quantity INT NOT NULL DEFAULT 0 CHECK (available_quantity >= 0),
    reserved_quantity INT NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
    
    -- 坐标（冗余存储，加速空间查询）
    longitude DECIMAL(10,6),
    latitude DECIMAL(10,6),
    
    -- 时间戳
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    CONSTRAINT chk_quantity CHECK (available_quantity + reserved_quantity <= total_quantity)
);

COMMENT ON TABLE operational_v2.equipment_inventory_v2 IS '装备库存表：跟踪装备存放位置和可用状态';
COMMENT ON COLUMN operational_v2.equipment_inventory_v2.location_type IS '存放位置类型：shelter安置点/team队伍/vehicle车辆/warehouse仓库';
COMMENT ON COLUMN operational_v2.equipment_inventory_v2.available_quantity IS '可用数量（未预留）';
COMMENT ON COLUMN operational_v2.equipment_inventory_v2.reserved_quantity IS '已预留数量（分配给任务但未出发）';

CREATE INDEX idx_equipment_inventory_type ON operational_v2.equipment_inventory_v2(equipment_type);
CREATE INDEX idx_equipment_inventory_location ON operational_v2.equipment_inventory_v2(location_type, location_id);
CREATE INDEX idx_equipment_inventory_code ON operational_v2.equipment_inventory_v2(equipment_code);

-- 空间索引（如果有PostGIS）
-- CREATE INDEX idx_equipment_inventory_geo ON operational_v2.equipment_inventory_v2 
--     USING GIST (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326));

-- ============================================================================
-- 4. 初始数据：能力→装备映射
-- ============================================================================
INSERT INTO operational_v2.capability_equipment_v2 
    (capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, priority, description)
VALUES
    -- 生命探测能力
    ('LIFE_DETECTION', '生命探测', 'supply', 'SP-RESCUE-DETECTOR', '雷达生命探测仪', 1, 'required', '搜索被困人员必备'),
    ('LIFE_DETECTION', '生命探测', 'supply', 'SP-RESCUE-AUDIO', '音频生命探测仪', 1, 'recommended', '配合雷达使用效果更好'),
    ('LIFE_DETECTION', '生命探测', 'device', 'DV-DOG-SEARCH', '搜救机器狗', 1, 'optional', '可替代或补充人工搜索'),
    
    -- 结构救援能力
    ('STRUCTURAL_RESCUE', '结构救援', 'supply', 'SP-RESCUE-BREAKER', '液压破拆工具组', 2, 'required', '破拆建筑结构救人'),
    ('STRUCTURAL_RESCUE', '结构救援', 'supply', 'SP-RESCUE-CUTTER', '液压剪切器', 1, 'required', '剪切钢筋障碍物'),
    ('STRUCTURAL_RESCUE', '结构救援', 'supply', 'SP-RESCUE-SUPPORT', '支撑气垫', 2, 'recommended', '支撑防止二次坍塌'),
    ('STRUCTURAL_RESCUE', '结构救援', 'supply', 'SP-RESCUE-LIGHT', '便携式照明设备', 3, 'required', '废墟内照明'),
    
    -- 医疗救护能力
    ('MEDICAL_TRIAGE', '医疗分诊', 'supply', 'SP-MED-KIT', '急救医药包', 5, 'required', '现场急救'),
    ('MEDICAL_TRIAGE', '医疗分诊', 'supply', 'SP-MED-STRETCHER', '折叠担架', 3, 'required', '伤员转运'),
    ('MEDICAL_TRIAGE', '医疗分诊', 'supply', 'SP-MED-AED', 'AED除颤仪', 1, 'recommended', '心脏骤停急救'),
    
    -- 紧急救治能力
    ('EMERGENCY_TREATMENT', '紧急救治', 'supply', 'SP-MED-KIT', '急救医药包', 10, 'required', '现场急救'),
    ('EMERGENCY_TREATMENT', '紧急救治', 'supply', 'SP-MED-OXYGEN', '便携氧气瓶', 3, 'required', '供氧急救'),
    ('EMERGENCY_TREATMENT', '紧急救治', 'supply', 'SP-MED-IV', '输液器材包', 5, 'recommended', '输液治疗'),
    
    -- 火灾扑救能力
    ('FIRE_SUPPRESSION', '火灾扑救', 'supply', 'SP-FIRE-EXTING', '灭火器', 5, 'required', '初期火灾扑救'),
    ('FIRE_SUPPRESSION', '火灾扑救', 'supply', 'SP-FIRE-HOSE', '消防水带', 3, 'required', '灭火供水'),
    ('FIRE_SUPPRESSION', '火灾扑救', 'supply', 'SP-PROT-SUIT', '防护服', 5, 'required', '人员防护'),
    
    -- 水域救援能力
    ('WATER_RESCUE', '水域救援', 'supply', 'SP-WATER-BOAT', '冲锋舟', 1, 'required', '水上救援'),
    ('WATER_RESCUE', '水域救援', 'supply', 'SP-WATER-VEST', '救生衣', 10, 'required', '人员防护'),
    ('WATER_RESCUE', '水域救援', 'supply', 'SP-WATER-RING', '救生圈', 5, 'required', '抛投救援'),
    ('WATER_RESCUE', '水域救援', 'device', 'DV-SHIP-RESCUE', '救援无人艇', 1, 'optional', '辅助水面搜索'),
    
    -- 危化品处置能力
    ('HAZMAT_RESPONSE', '危化品处置', 'supply', 'SP-HAZMAT-SUIT', '防化服', 5, 'required', '人员防护'),
    ('HAZMAT_RESPONSE', '危化品处置', 'supply', 'SP-HAZMAT-DETECT', '气体检测仪', 2, 'required', '有毒气体检测'),
    ('HAZMAT_RESPONSE', '危化品处置', 'supply', 'SP-HAZMAT-CONTAIN', '堵漏器材', 1, 'required', '泄漏堵漏'),
    
    -- 通信保障能力
    ('COMMUNICATION', '通信保障', 'supply', 'SP-COMM-RADIO', '对讲机', 10, 'required', '现场通信'),
    ('COMMUNICATION', '通信保障', 'supply', 'SP-COMM-RELAY', '通信中继站', 1, 'recommended', '扩展通信范围'),
    ('COMMUNICATION', '通信保障', 'device', 'DV-DRONE-COMM', '通信中继无人机', 1, 'optional', '空中通信中继'),
    
    -- 侦察能力
    ('RECONNAISSANCE', '侦察', 'device', 'DV-DRONE-RECON', '侦察无人机', 2, 'required', '空中侦察'),
    ('RECONNAISSANCE', '侦察', 'device', 'DV-DOG-RECON', '侦察机器狗', 1, 'recommended', '地面侦察'),
    ('RECONNAISSANCE', '侦察', 'supply', 'SP-RECON-THERMAL', '热成像仪', 1, 'required', '热源探测'),
    
    -- 疏散协调能力
    ('EVACUATION_COORDINATION', '疏散协调', 'supply', 'SP-EVAC-SPEAKER', '扩音喊话器', 2, 'required', '人群疏散指挥'),
    ('EVACUATION_COORDINATION', '疏散协调', 'supply', 'SP-EVAC-SIGN', '荧光指示牌', 10, 'required', '疏散路线指示')
ON CONFLICT (capability_code, equipment_type, equipment_code) DO UPDATE SET
    equipment_name = EXCLUDED.equipment_name,
    min_quantity = EXCLUDED.min_quantity,
    priority = EXCLUDED.priority,
    description = EXCLUDED.description,
    updated_at = now();

-- ============================================================================
-- 5. 初始数据：物资需求标准
-- 参考：国家应急物资储备标准、救灾物资储备规划
-- ============================================================================
INSERT INTO operational_v2.supply_standards_v2 
    (disaster_type, supply_code, supply_name, supply_category, per_person_per_day, unit, priority, description, reference_standard)
VALUES
    -- 地震灾害物资标准
    ('earthquake', 'SP-LIFE-WATER', '饮用水', 'life', 2.5, 'liter', 'critical', '每人每天饮用水需求', 'GB/T 29426'),
    ('earthquake', 'SP-LIFE-FOOD', '应急食品', 'life', 0.5, 'kg', 'critical', '每人每天食品需求', 'GB/T 29426'),
    ('earthquake', 'SP-SHELTER-TENT', '救灾帐篷', 'life', 0.2, 'unit', 'high', '每5人1顶帐篷', 'MZ/T 001'),
    ('earthquake', 'SP-SHELTER-BLANKET', '保暖毯', 'life', 1.0, 'piece', 'high', '每人1条毛毯', 'MZ/T 001'),
    ('earthquake', 'SP-MED-KIT', '急救包', 'medical', 0.1, 'set', 'high', '每10人1套急救包', ''),
    ('earthquake', 'SP-PROT-MASK', '防尘口罩', 'protection', 2.0, 'piece', 'medium', '每人每天2个口罩', ''),
    
    -- 洪涝灾害物资标准
    ('flood', 'SP-LIFE-WATER', '饮用水', 'life', 3.0, 'liter', 'critical', '洪涝期间饮水需求增加', 'GB/T 29426'),
    ('flood', 'SP-LIFE-FOOD', '应急食品', 'life', 0.5, 'kg', 'critical', '每人每天食品需求', 'GB/T 29426'),
    ('flood', 'SP-WATER-VEST', '救生衣', 'rescue', 1.0, 'piece', 'critical', '每人1件救生衣', ''),
    ('flood', 'SP-MED-KIT', '急救包', 'medical', 0.15, 'set', 'high', '洪涝伤病风险增加', ''),
    ('flood', 'SP-SHELTER-TENT', '救灾帐篷', 'life', 0.2, 'unit', 'high', '每5人1顶帐篷', 'MZ/T 001'),
    
    -- 火灾灾害物资标准
    ('fire', 'SP-LIFE-WATER', '饮用水', 'life', 3.0, 'liter', 'critical', '火场高温需要更多水分', ''),
    ('fire', 'SP-MED-KIT', '急救包', 'medical', 0.2, 'set', 'critical', '烧伤风险高', ''),
    ('fire', 'SP-MED-BURN', '烧伤药膏', 'medical', 0.5, 'tube', 'critical', '烧伤处理', ''),
    ('fire', 'SP-PROT-MASK', '防烟面罩', 'protection', 1.0, 'piece', 'critical', '防止烟雾吸入', ''),
    
    -- 危化品灾害物资标准
    ('hazmat', 'SP-LIFE-WATER', '饮用水', 'life', 2.5, 'liter', 'critical', '每人每天饮用水需求', ''),
    ('hazmat', 'SP-MED-KIT', '急救包', 'medical', 0.2, 'set', 'critical', '中毒风险', ''),
    ('hazmat', 'SP-PROT-MASK', '防毒面具', 'protection', 1.0, 'piece', 'critical', '防止毒气吸入', ''),
    ('hazmat', 'SP-MED-ANTIDOTE', '解毒药品', 'medical', 0.5, 'dose', 'critical', '中毒急救', ''),
    
    -- 滑坡/泥石流灾害物资标准
    ('landslide', 'SP-LIFE-WATER', '饮用水', 'life', 2.5, 'liter', 'critical', '每人每天饮用水需求', ''),
    ('landslide', 'SP-LIFE-FOOD', '应急食品', 'life', 0.5, 'kg', 'critical', '每人每天食品需求', ''),
    ('landslide', 'SP-MED-KIT', '急救包', 'medical', 0.15, 'set', 'high', '外伤风险', ''),
    ('landslide', 'SP-SHELTER-TENT', '救灾帐篷', 'life', 0.2, 'unit', 'high', '每5人1顶帐篷', '')
ON CONFLICT (disaster_type, COALESCE(disaster_subtype, ''), supply_code) DO UPDATE SET
    supply_name = EXCLUDED.supply_name,
    per_person_per_day = EXCLUDED.per_person_per_day,
    priority = EXCLUDED.priority,
    description = EXCLUDED.description,
    updated_at = now();

-- ============================================================================
-- 6. 创建更新时间触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_capability_equipment_update ON operational_v2.capability_equipment_v2;
CREATE TRIGGER trg_capability_equipment_update
    BEFORE UPDATE ON operational_v2.capability_equipment_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

DROP TRIGGER IF EXISTS trg_supply_standards_update ON operational_v2.supply_standards_v2;
CREATE TRIGGER trg_supply_standards_update
    BEFORE UPDATE ON operational_v2.supply_standards_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

DROP TRIGGER IF EXISTS trg_equipment_inventory_update ON operational_v2.equipment_inventory_v2;
CREATE TRIGGER trg_equipment_inventory_update
    BEFORE UPDATE ON operational_v2.equipment_inventory_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- ============================================================================
-- 验证数据
-- ============================================================================
DO $$
DECLARE
    cap_count INT;
    std_count INT;
BEGIN
    SELECT COUNT(*) INTO cap_count FROM operational_v2.capability_equipment_v2;
    SELECT COUNT(*) INTO std_count FROM operational_v2.supply_standards_v2;
    
    RAISE NOTICE '能力-装备映射: % 条记录', cap_count;
    RAISE NOTICE '物资需求标准: % 条记录', std_count;
END $$;
