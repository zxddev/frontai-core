-- ============================================================================
-- v20_extend_capability_codes.sql
-- 扩展应急响应能力代码库
-- 将PostgreSQL能力代码从34种扩展到110种(34现有 + 76新增)
-- ============================================================================

-- 创建能力代码参考表（如果不存在）
CREATE TABLE IF NOT EXISTS operational_v2.capability_codes (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE operational_v2.capability_codes IS '应急响应能力代码参考表';

-- 清空并重新插入所有能力代码（现有34个 + 新增76个）
TRUNCATE TABLE operational_v2.capability_codes;

INSERT INTO operational_v2.capability_codes (code, name, category) VALUES
-- ========== 现有34个能力代码（PostgreSQL team_capabilities_v2中已使用）==========
('BRIDGE_REPAIR', '桥梁修复', 'engineering'),
('BUILDING_SHORING', '建筑支撑加固', 'engineering'),
('CHEMICAL_FIRE', '化学火灾扑救', 'fire'),
('COMMAND_COORDINATION', '指挥协调', 'command'),
('COMMUNICATION_SUPPORT', '通信保障', 'communication'),
('CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue'),
('CPR_AED', '心肺复苏/AED', 'medical'),
('DECONTAMINATION', '洗消去污', 'hazmat'),
('DEMOLITION', '破拆作业', 'engineering'),
('DIVING_RESCUE', '潜水救援', 'rescue'),
('EMERGENCY_TREATMENT', '紧急救治', 'medical'),
('EVACUATION_COORDINATION', '疏散协调', 'evacuation'),
('FIRE_SEARCH_RESCUE', '火场搜救', 'fire'),
('FIRE_SUPPRESSION', '火灾扑救', 'fire'),
('HAZMAT_CONTAINMENT', '危化品围堵', 'hazmat'),
('HAZMAT_DETECTION', '危化品检测', 'hazmat'),
('HEAVY_LIFTING', '重物起吊', 'engineering'),
('LANDSLIDE_RESCUE', '山体滑坡救援', 'rescue'),
('LIFE_DETECTION', '生命探测', 'search'),
('MEDICAL_TRIAGE', '医疗分诊', 'medical'),
('NETWORK_RECOVERY', '网络恢复', 'communication'),
('PATIENT_TRANSPORT', '伤员转运', 'medical'),
('RADIATION_PROTECTION', '辐射防护', 'hazmat'),
('ROAD_CLEARANCE', '道路抢通', 'engineering'),
('ROPE_RESCUE', '绳索救援', 'rescue'),
('SATELLITE_COMM', '卫星通信', 'communication'),
('SHELTER_MANAGEMENT', '安置点管理', 'shelter'),
('STRUCTURAL_RESCUE', '结构救援', 'rescue'),
('SURGERY', '手术救治', 'medical'),
('SWIFT_WATER_RESCUE', '急流水域救援', 'rescue'),
('TRAUMA_CARE', '创伤护理', 'medical'),
('UNDERWATER_SEARCH', '水下搜索', 'search'),
('VOLUNTEER_SUPPORT', '志愿者支持', 'logistics'),
('WATER_RESCUE', '水域救援', 'rescue'),

-- ========== 新增76个能力代码（来自YAML TRR规则）==========
-- 呼吸/安全装备
('BREATHING_APPARATUS', '呼吸器装备', 'equipment'),

-- 后勤保障
('CATERING_FIELD', '野外餐饮保障', 'logistics'),
('SUPPLY_TRANSPORT', '物资运输', 'logistics'),

-- 指挥通信
('COMMAND_VEHICLE', '指挥车辆', 'command'),
('COMM_COMMAND', '指挥通信', 'communication'),
('COMM_MESH', '网状通信', 'communication'),
('COMM_SATELLITE', '卫星通信能力', 'communication'),

-- 消防灭火
('COOLING_SPRAY', '冷却喷淋', 'fire'),
('FIRE_AERIAL', '空中灭火', 'fire'),
('FIRE_ELECTRICAL', '电气火灾扑救', 'fire'),
('FIRE_FOREST', '森林火灾扑救', 'fire'),
('FIRE_STANDBY', '消防待命', 'fire'),
('FIRE_SUPPLY_WATER', '消防供水', 'fire'),
('FIRE_SUPPRESS', '火灾扑救能力', 'fire'),
('FIRE_UNDERGROUND', '地下火灾扑救', 'fire'),
('FIREBREAK_BUILD', '防火隔离带构建', 'fire'),
('FOAM_SUPPRESS', '泡沫灭火', 'fire'),
('SMOKE_EXHAUST', '排烟作业', 'fire'),

-- 人群疏散
('CROWD_CONTROL', '人群控制', 'evacuation'),
('EVAC_GUIDANCE', '疏散引导', 'evacuation'),
('WARNING_BROADCAST', '预警广播', 'evacuation'),

-- 评估监测
('DAMAGE_ASSESS', '损失评估', 'assessment'),
('FLOOD_MONITOR', '洪水监测', 'monitoring'),
('GEO_MONITOR', '地质监测', 'monitoring'),
('GAS_MONITOR', '气体监测', 'monitoring'),

-- 水利工程
('DAM_REPAIR', '大坝修复', 'engineering'),
('PUMP_DRAINAGE', '排水泵送', 'engineering'),
('PUMP_HIGH_CAPACITY', '大流量泵送', 'engineering'),
('SANDBAG_FILL', '沙袋填装', 'engineering'),
('PIPE_REPAIR', '管道修复', 'engineering'),

-- 工程作业
('ENG_BLASTING', '工程爆破', 'engineering'),
('ENG_DEMOLITION', '工程破拆', 'engineering'),
('ENG_HEAVY_MACHINE', '重型机械作业', 'engineering'),
('TREE_CLEARANCE', '树木清理', 'engineering'),

-- 专家支持
('EXPERT_CONSULT', '专家咨询', 'support'),
('MEDIA_LIAISON', '媒体联络', 'support'),

-- 设施安全
('FACILITY_SECURE', '设施安全加固', 'engineering'),

-- 危化品处置
('GAS_DETECT', '气体检测', 'hazmat'),
('GAS_SHUTOFF', '气体关断', 'hazmat'),
('HAZMAT_CONTAIN', '危化品围堵能力', 'hazmat'),
('HAZMAT_DECON', '危化品洗消', 'hazmat'),
('HAZMAT_DETECT', '危化品探测', 'hazmat'),
('HAZMAT_GAS_DETECT', '危化品气体检测', 'hazmat'),
('HAZMAT_NEUTRALIZE', '危化品中和', 'hazmat'),
('HAZMAT_TRANSFER', '危化品转移', 'hazmat'),

-- 生命支持
('LIFE_SUPPORT_DRILL', '生命支持钻探', 'rescue'),

-- 照明设备
('LIGHTING_MOBILE', '移动照明', 'equipment'),

-- 医疗救护
('MEDICAL_FIRST_AID', '现场急救', 'medical'),
('MEDICAL_ICU', '重症监护', 'medical'),
('MEDICAL_PEDIATRIC', '儿科救治', 'medical'),
('MEDICAL_TOXICOLOGY', '中毒救治', 'medical'),
('MEDICAL_TRANSPORT', '医疗转运', 'medical'),

-- 特种救援
('MINE_RESCUE', '矿山救援', 'rescue'),
('RESCUE_CONFINED', '受限空间救援', 'rescue'),
('RESCUE_HIGH_ANGLE', '高空救援', 'rescue'),
('RESCUE_STRUCTURAL', '建筑结构救援', 'rescue'),
('RESCUE_VEHICLE', '车辆救援', 'rescue'),
('RESCUE_WATER_FLOOD', '洪水水域救援', 'rescue'),
('RESCUE_WATER_SWIFT', '急流救援', 'rescue'),

-- 电力保障
('POWER_CUTOFF', '电力切断', 'power'),
('POWER_EMERGENCY', '应急供电', 'power'),
('POWER_LINE_REPAIR', '电力线路修复', 'power'),

-- 心理援助
('PSYCH_CRISIS', '心理危机干预', 'medical'),

-- 核辐射
('RADIATION_DETECT', '辐射检测', 'hazmat'),
('RADIATION_SHIELD', '辐射屏蔽', 'hazmat'),

-- 现场安保
('SCENE_GUARD', '现场警戒', 'security'),
('TRAFFIC_CONTROL', '交通管制', 'security'),

-- 搜索探测
('SEARCH_LIFE_DETECT', '生命搜索探测', 'search'),
('UAV_RECONNAISSANCE', '无人机侦察', 'search'),
('UAV_THERMAL', '热成像无人机', 'search'),

-- 安置管理
('SHELTER_MANAGE', '安置管理能力', 'shelter'),
('SHELTER_SETUP', '安置点搭建', 'shelter'),

-- 通风作业
('VENTILATION_CONTROL', '通风控制', 'engineering'),
('VENTILATION_RESTORE', '通风恢复', 'engineering'),

-- 供水保障
('WATER_PURIFY', '水质净化', 'logistics'),
('WATER_TRANSPORT', '供水运输', 'logistics');

-- 验证插入结果
SELECT 
    category,
    COUNT(*) as count
FROM operational_v2.capability_codes
GROUP BY category
ORDER BY count DESC;

-- 输出总数
SELECT COUNT(*) as total_capabilities FROM operational_v2.capability_codes;
