-- ============================================================================
-- 能力→装备映射表
-- 
-- 定义每种救援能力所需的装备清单，用于装备调度器自动推断装备需求
-- ============================================================================

-- 创建装备类型枚举（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'equipment_type_enum') THEN
        CREATE TYPE operational_v2.equipment_type_enum AS ENUM ('device', 'supply');
    END IF;
END $$;

-- 创建优先级枚举（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'equipment_priority_enum') THEN
        CREATE TYPE operational_v2.equipment_priority_enum AS ENUM ('required', 'recommended', 'optional');
    END IF;
END $$;

-- 创建能力→装备映射表
CREATE TABLE IF NOT EXISTS operational_v2.capability_equipment_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 能力信息
    capability_code VARCHAR(100) NOT NULL,
    capability_name VARCHAR(200),
    
    -- 装备信息
    equipment_type VARCHAR(20) NOT NULL DEFAULT 'device',
    equipment_code VARCHAR(100) NOT NULL,
    equipment_name VARCHAR(200),
    
    -- 数量需求
    min_quantity INT NOT NULL DEFAULT 1,
    max_quantity INT,
    
    -- 优先级
    priority VARCHAR(20) NOT NULL DEFAULT 'required',
    
    -- 描述
    description TEXT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 唯一约束：同一能力不能有重复的装备编码
    CONSTRAINT uq_capability_equipment UNIQUE (capability_code, equipment_code)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_capability_equipment_code 
ON operational_v2.capability_equipment_v2(capability_code);

CREATE INDEX IF NOT EXISTS idx_capability_equipment_type 
ON operational_v2.capability_equipment_v2(equipment_type);

CREATE INDEX IF NOT EXISTS idx_capability_equipment_priority 
ON operational_v2.capability_equipment_v2(priority);

-- 添加注释
COMMENT ON TABLE operational_v2.capability_equipment_v2 IS '能力→装备映射表，定义每种能力所需的装备';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.capability_code IS '能力编码，如STRUCTURAL_RESCUE';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.equipment_type IS '装备类型：device(设备)/supply(物资)';
COMMENT ON COLUMN operational_v2.capability_equipment_v2.priority IS '优先级：required(必须)/recommended(推荐)/optional(可选)';

-- ============================================================================
-- 插入基础映射数据
-- ============================================================================

-- 清空旧数据（如果有）
TRUNCATE operational_v2.capability_equipment_v2;

-- 结构救援（STRUCTURAL_RESCUE）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('STRUCTURAL_RESCUE', '结构救援', 'device', 'EQ-HYD-CUTTER', '液压剪切器', 2, 5, 'required', '切割钢筋混凝土'),
('STRUCTURAL_RESCUE', '结构救援', 'device', 'EQ-HYD-SPREADER', '液压扩张器', 2, 5, 'required', '扩张变形空间'),
('STRUCTURAL_RESCUE', '结构救援', 'device', 'EQ-JACK', '救援千斤顶', 2, 4, 'required', '顶升重物'),
('STRUCTURAL_RESCUE', '结构救援', 'supply', 'EQ-BREAKER', '破拆工具组', 3, 6, 'recommended', '手动破拆工具'),
('STRUCTURAL_RESCUE', '结构救援', 'device', 'EQ-CRANE-MINI', '小型起重机', 1, 2, 'optional', '大型构件吊装');

-- 生命探测（LIFE_DETECTION）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('LIFE_DETECTION', '生命探测', 'device', 'EQ-DETECTOR-AUDIO', '音频生命探测仪', 2, 5, 'required', '探测被困者声音'),
('LIFE_DETECTION', '生命探测', 'device', 'EQ-DETECTOR-RADAR', '雷达生命探测仪', 1, 3, 'required', '穿透废墟探测'),
('LIFE_DETECTION', '生命探测', 'device', 'EQ-CAMERA-SNAKE', '蛇眼探测仪', 2, 4, 'recommended', '狭小空间可视化探测'),
('LIFE_DETECTION', '生命探测', 'device', 'EQ-DOG-SEARCH', '搜救犬', 1, 3, 'recommended', '生物嗅觉探测');

-- 医疗急救（MEDICAL_EMERGENCY）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('MEDICAL_EMERGENCY', '医疗急救', 'supply', 'EQ-MED-KIT', '急救医疗包', 10, 50, 'required', '基础急救药品和器材'),
('MEDICAL_EMERGENCY', '医疗急救', 'supply', 'EQ-STRETCHER', '担架', 5, 20, 'required', '伤员转运'),
('MEDICAL_EMERGENCY', '医疗急救', 'device', 'EQ-DEFIBRILLATOR', 'AED除颤仪', 2, 5, 'required', '心脏复苏'),
('MEDICAL_EMERGENCY', '医疗急救', 'supply', 'EQ-OXYGEN', '便携氧气瓶', 5, 20, 'recommended', '呼吸支持'),
('MEDICAL_EMERGENCY', '医疗急救', 'device', 'EQ-MONITOR-VITAL', '生命体征监护仪', 2, 5, 'recommended', '实时监护');

-- 医疗分检（MEDICAL_TRIAGE）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('MEDICAL_TRIAGE', '医疗分检', 'supply', 'EQ-TRIAGE-TAG', '伤员分检标签', 100, 500, 'required', '伤情分级标识'),
('MEDICAL_TRIAGE', '医疗分检', 'supply', 'EQ-MED-KIT', '急救医疗包', 5, 20, 'required', '基础急救'),
('MEDICAL_TRIAGE', '医疗分检', 'device', 'EQ-TENT-MEDICAL', '医疗帐篷', 1, 3, 'recommended', '临时医疗站');

-- 紧急救治（EMERGENCY_TREATMENT）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('EMERGENCY_TREATMENT', '紧急救治', 'supply', 'EQ-MED-KIT-ADV', '高级急救包', 5, 20, 'required', '高级急救器材'),
('EMERGENCY_TREATMENT', '紧急救治', 'device', 'EQ-DEFIBRILLATOR', 'AED除颤仪', 2, 5, 'required', '心脏复苏'),
('EMERGENCY_TREATMENT', '紧急救治', 'supply', 'EQ-IV-SET', '静脉输液套装', 20, 100, 'required', '液体复苏'),
('EMERGENCY_TREATMENT', '紧急救治', 'device', 'EQ-VENTILATOR-PORT', '便携呼吸机', 1, 3, 'recommended', '呼吸支持');

-- 灭火（FIRE_SUPPRESSION）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('FIRE_SUPPRESSION', '灭火', 'supply', 'EQ-EXTINGUISHER', '灭火器', 10, 50, 'required', '初期火灾扑灭'),
('FIRE_SUPPRESSION', '灭火', 'supply', 'EQ-HOSE', '消防水带', 5, 20, 'required', '水源输送'),
('FIRE_SUPPRESSION', '灭火', 'device', 'EQ-PUMP', '消防水泵', 2, 5, 'required', '加压供水'),
('FIRE_SUPPRESSION', '灭火', 'supply', 'EQ-FOAM', '泡沫灭火剂', 5, 20, 'recommended', '油类火灾');

-- 道路清障（ROAD_CLEARANCE）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('ROAD_CLEARANCE', '道路清障', 'device', 'EQ-EXCAVATOR', '挖掘机', 1, 3, 'required', '大型障碍清除'),
('ROAD_CLEARANCE', '道路清障', 'device', 'EQ-LOADER', '装载机', 1, 2, 'required', '土石方清运'),
('ROAD_CLEARANCE', '道路清障', 'device', 'EQ-CRANE', '吊车', 1, 2, 'recommended', '重型障碍吊装'),
('ROAD_CLEARANCE', '道路清障', 'supply', 'EQ-CHAINSAW', '油锯', 3, 10, 'recommended', '树木障碍清除');

-- 人员疏散（EVACUATION_COORDINATION）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('EVACUATION_COORDINATION', '人员疏散', 'device', 'EQ-SPEAKER', '扩音器', 5, 20, 'required', '疏散指挥广播'),
('EVACUATION_COORDINATION', '人员疏散', 'supply', 'EQ-FLASHLIGHT', '强光手电', 20, 100, 'required', '夜间照明引导'),
('EVACUATION_COORDINATION', '人员疏散', 'supply', 'EQ-SIGN-EVAC', '疏散指示牌', 20, 50, 'recommended', '路线指示');

-- 无人机侦察（UAV_RECONNAISSANCE）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('UAV_RECONNAISSANCE', '无人机侦察', 'device', 'EQ-UAV-SURVEY', '侦察无人机', 2, 5, 'required', '空中侦察'),
('UAV_RECONNAISSANCE', '无人机侦察', 'device', 'EQ-UAV-THERMAL', '热成像无人机', 1, 3, 'recommended', '夜间/烟雾侦察'),
('UAV_RECONNAISSANCE', '无人机侦察', 'supply', 'EQ-BATTERY-UAV', '无人机电池', 10, 30, 'required', '续航保障');

-- 危化品处置（HAZMAT_HANDLING）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('HAZMAT_HANDLING', '危化品处置', 'supply', 'EQ-SUIT-HAZMAT', '防化服', 10, 30, 'required', '人员防护'),
('HAZMAT_HANDLING', '危化品处置', 'device', 'EQ-DETECTOR-GAS', '气体检测仪', 3, 10, 'required', '有毒气体检测'),
('HAZMAT_HANDLING', '危化品处置', 'supply', 'EQ-ABSORBENT', '吸附材料', 50, 200, 'required', '泄漏液体吸收'),
('HAZMAT_HANDLING', '危化品处置', 'device', 'EQ-PUMP-CHEM', '防爆泵', 1, 3, 'recommended', '危险液体转移');

-- 水上救援（WATER_RESCUE）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('WATER_RESCUE', '水上救援', 'device', 'EQ-BOAT-INFLATABLE', '冲锋舟', 2, 5, 'required', '水上搜救'),
('WATER_RESCUE', '水上救援', 'supply', 'EQ-LIFEJACKET', '救生衣', 20, 100, 'required', '人员漂浮'),
('WATER_RESCUE', '水上救援', 'supply', 'EQ-LIFEBUOY', '救生圈', 10, 50, 'required', '抛投救援'),
('WATER_RESCUE', '水上救援', 'device', 'EQ-USV', '无人救援艇', 1, 3, 'recommended', '远程水上救援');

-- 通信保障（COMMUNICATION_SUPPORT）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('COMMUNICATION_SUPPORT', '通信保障', 'device', 'EQ-RADIO', '对讲机', 20, 100, 'required', '现场通信'),
('COMMUNICATION_SUPPORT', '通信保障', 'device', 'EQ-SATELLITE', '卫星电话', 2, 5, 'required', '远程通信'),
('COMMUNICATION_SUPPORT', '通信保障', 'device', 'EQ-REPEATER', '中继台', 1, 3, 'recommended', '信号覆盖扩展');

-- 照明保障（LIGHTING_SUPPORT）
INSERT INTO operational_v2.capability_equipment_v2 
(capability_code, capability_name, equipment_type, equipment_code, equipment_name, min_quantity, max_quantity, priority, description) 
VALUES
('LIGHTING_SUPPORT', '照明保障', 'device', 'EQ-LIGHT-TOWER', '移动照明灯塔', 2, 5, 'required', '大范围照明'),
('LIGHTING_SUPPORT', '照明保障', 'device', 'EQ-GENERATOR', '发电机', 2, 5, 'required', '供电保障'),
('LIGHTING_SUPPORT', '照明保障', 'supply', 'EQ-FLASHLIGHT', '强光手电', 30, 100, 'recommended', '个人照明');

-- 验证插入结果
SELECT 
    capability_code,
    COUNT(*) as equipment_count,
    SUM(CASE WHEN priority = 'required' THEN 1 ELSE 0 END) as required_count,
    SUM(CASE WHEN priority = 'recommended' THEN 1 ELSE 0 END) as recommended_count
FROM operational_v2.capability_equipment_v2
GROUP BY capability_code
ORDER BY capability_code;
