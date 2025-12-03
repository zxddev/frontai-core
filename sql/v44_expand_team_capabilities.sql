-- ============================================================================
-- v44_expand_team_capabilities.sql
-- 扩展队伍能力关联
-- 目标: 每队5-10个能力，总计600+条能力记录
-- ============================================================================

-- ============================================================================
-- 一、为新增指挥协调类队伍添加能力
-- ============================================================================

-- 阿坝州应急指挥中心
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 5, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_ABA_001';

-- 成都市应急指挥中心
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 5, 150 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_CD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 5, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_CD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SATELLITE_COMM', '卫星通信', 'communication', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_CD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_CD_001';

-- 绵阳市应急指挥中心
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 5, 120 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_MY_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 4, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_MY_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_MY_001';

-- 德阳市应急指挥中心
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 5, 110 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_DY_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_DY_001';

-- 四川省应急指挥中心
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 5, 200 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_SC_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 5, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_SC_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SATELLITE_COMM', '卫星通信', 'communication', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_SC_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'NETWORK_RECOVERY', '网络恢复', 'communication', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'CMD_SC_001';

-- ============================================================================
-- 二、为新增搜救类队伍添加能力
-- ============================================================================

-- 四川搜救犬中队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_DOG_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_DOG_001';

-- 四川机器人搜救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 5, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_ROBOT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_ROBOT_001';

-- 四川无人机侦察队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_UAV_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_UAV_001';

-- 热成像搜救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_THERMAL_001';

-- 高空救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'ROPE_RESCUE', '绳索救援', 'rescue', 5, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_HIGH_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_HIGH_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_HIGH_001';

-- 狭小空间救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_CONFINED_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_CONFINED_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_CONFINED_001';

-- 山地救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_MOUNTAIN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'ROPE_RESCUE', '绳索救援', 'rescue', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_MOUNTAIN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_MOUNTAIN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LANDSLIDE_RESCUE', '山体滑坡救援', 'rescue', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_MOUNTAIN_001';

-- 城市搜救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_URBAN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 45 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_URBAN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_URBAN_001';

-- 阿坝州搜救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LANDSLIDE_RESCUE', '山体滑坡救援', 'rescue', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_ABA_001';

-- 夜间搜救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_NIGHT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'SAR_NIGHT_001';

-- ============================================================================
-- 三、为新增医疗类队伍添加能力
-- ============================================================================

-- 华西医院ICU转运队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_HUAXI_ICU';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'PATIENT_TRANSPORT', '伤员转运', 'medical', 5, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_HUAXI_ICU';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SURGERY', '手术救治', 'medical', 5, 15 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_HUAXI_ICU';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'TRAUMA_CARE', '创伤护理', 'medical', 5, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_HUAXI_ICU';

-- 野战医疗队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 5, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_FIELD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'MEDICAL_TRIAGE', '医疗分诊', 'medical', 5, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_FIELD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'PATIENT_TRANSPORT', '伤员转运', 'medical', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_FIELD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SURGERY', '手术救治', 'medical', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_FIELD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'TRAUMA_CARE', '创伤护理', 'medical', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_FIELD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CPR_AED', '心肺复苏/AED', 'medical', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_FIELD_001';

-- 烧伤救治队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 5, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_BURN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'TRAUMA_CARE', '创伤护理', 'medical', 5, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_BURN_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SURGERY', '手术救治', 'medical', 5, 15 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_BURN_001';

-- 创伤急救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_TRAUMA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'MEDICAL_TRIAGE', '医疗分诊', 'medical', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_TRAUMA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'TRAUMA_CARE', '创伤护理', 'medical', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_TRAUMA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CPR_AED', '心肺复苏/AED', 'medical', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_TRAUMA_001';

-- 心理援助队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 3, 20 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_PSYCH_001';

-- 儿科急救队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 5, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_PEDIATRIC_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'MEDICAL_TRIAGE', '医疗分诊', 'medical', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_PEDIATRIC_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'PATIENT_TRANSPORT', '伤员转运', 'medical', 4, 20 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_PEDIATRIC_001';

-- 中毒救治队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 5, 20 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_TOXIC_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DECONTAMINATION', '洗消去污', 'hazmat', 4, 15 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_TOXIC_001';

-- 阿坝州医疗救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'MEDICAL_TRIAGE', '医疗分诊', 'medical', 4, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'PATIENT_TRANSPORT', '伤员转运', 'medical', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'TRAUMA_CARE', '创伤护理', 'medical', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_ABA_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CPR_AED', '心肺复苏/AED', 'medical', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'MED_ABA_001';

-- ============================================================================
-- 四、为新增工程类队伍添加能力
-- ============================================================================

-- 重型起吊救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_CRANE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_CRANE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_CRANE_001';

-- 爆破救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_BLAST_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_BLAST_001';

-- 桥梁抢修队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'BRIDGE_REPAIR', '桥梁修复', 'engineering', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_BRIDGE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'ROAD_CLEARANCE', '道路抢通', 'engineering', 4, 45 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_BRIDGE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_BRIDGE_001';

-- 隧道抢险队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 5, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_TUNNEL_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'ROAD_CLEARANCE', '道路抢通', 'engineering', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_TUNNEL_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'BUILDING_SHORING', '建筑支撑加固', 'engineering', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_TUNNEL_001';

-- 破拆作业队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 5, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_DEMOLITION_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_DEMOLITION_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_DEMOLITION_001';

-- 建筑支撑队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'BUILDING_SHORING', '建筑支撑加固', 'engineering', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_SHORING_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_SHORING_001';

-- 电力抢修队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 4, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_POWER_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_POWER_001';

-- 供水抢修队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'ROAD_CLEARANCE', '道路抢通', 'engineering', 3, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'ENG_WATER_001';

-- ============================================================================
-- 五、为新增水域救援类队伍添加能力
-- ============================================================================

-- 潜水救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DIVING_RESCUE', '潜水救援', 'rescue', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_DIVE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'UNDERWATER_SEARCH', '水下搜索', 'search', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_DIVE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_DIVE_001';

-- 急流救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SWIFT_WATER_RESCUE', '急流水域救援', 'rescue', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_SWIFT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_SWIFT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_SWIFT_001';

-- 抗洪抢险队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 4, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_FLOOD_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_FLOOD_001';

-- 舟艇救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_BOAT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_BOAT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'PATIENT_TRANSPORT', '伤员转运', 'medical', 3, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_BOAT_001';

-- 堤防抢险队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_DAM_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 4, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_DAM_001';

-- 排涝抢险队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_PUMP_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'ROAD_CLEARANCE', '道路抢通', 'engineering', 3, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'WATER_PUMP_001';

-- ============================================================================
-- 六、为新增危化品处置类队伍添加能力
-- ============================================================================

-- 危化品检测队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_DETECT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_CONTAINMENT', '危化品围堵', 'hazmat', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_DETECT_001';

-- 洗消处置队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DECONTAMINATION', '洗消去污', 'hazmat', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_DECON_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_DECON_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_CONTAINMENT', '危化品围堵', 'hazmat', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_DECON_001';

-- 核辐射处置队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'RADIATION_PROTECTION', '辐射防护', 'hazmat', 5, 20 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_NUCLEAR_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 5, 20 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_NUCLEAR_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DECONTAMINATION', '洗消去污', 'hazmat', 5, 20 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_NUCLEAR_001';

-- 气体泄漏处置队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 5, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_GAS_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_CONTAINMENT', '危化品围堵', 'hazmat', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_GAS_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_GAS_001';

-- 油品泄漏处置队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_CONTAINMENT', '危化品围堵', 'hazmat', 5, 45 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_OIL_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'FIRE_SUPPRESSION', '火灾扑救', 'fire', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_OIL_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'HAZMAT_OIL_001';

-- ============================================================================
-- 七、为新增通信保障类队伍添加能力
-- ============================================================================

-- 卫星通信保障队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SATELLITE_COMM', '卫星通信', 'communication', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_SAT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_SAT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_SAT_001';

-- 移动通信保障队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 5, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_MOBILE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'NETWORK_RECOVERY', '网络恢复', 'communication', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_MOBILE_001';

-- 网络恢复队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'NETWORK_RECOVERY', '网络恢复', 'communication', 5, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_NETWORK_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_NETWORK_001';

-- 无线电保障队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'COMM_RADIO_001';

-- ============================================================================
-- 八、为新增矿山救援类队伍添加能力
-- ============================================================================

-- 四川省矿山救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 5, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_RESCUE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 5, 70 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_RESCUE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 4, 50 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_RESCUE_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_RESCUE_001';

-- 矿井通风队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 4, 40 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_VENT_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HAZMAT_DETECTION', '危化品检测', 'hazmat', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_VENT_001';

-- 生命通道钻探队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 5, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_DRILL_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 4, 25 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_DRILL_001';

-- 矿井排水队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CONFINED_SPACE_RESCUE', '狭小空间救援', 'rescue', 4, 35 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_PUMP_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 4, 30 FROM operational_v2.rescue_teams_v2 WHERE code = 'MINE_PUMP_001';

-- ============================================================================
-- 九、为新增志愿者类队伍添加能力
-- ============================================================================

-- 蓝天救援队成都分队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'LIFE_DETECTION', '生命探测', 'search', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_BLUESKY_CD';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'STRUCTURAL_RESCUE', '结构救援', 'rescue', 4, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_BLUESKY_CD';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'WATER_RESCUE', '水域救援', 'rescue', 4, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_BLUESKY_CD';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_BLUESKY_CD';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'VOLUNTEER_SUPPORT', '志愿者支持', 'logistics', 5, 150 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_BLUESKY_CD';

-- 绿丝带救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 3, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_GREENRIBBON_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SHELTER_MANAGEMENT', '安置点管理', 'shelter', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_GREENRIBBON_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'VOLUNTEER_SUPPORT', '志愿者支持', 'logistics', 4, 100 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_GREENRIBBON_001';

-- 红十字救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EMERGENCY_TREATMENT', '紧急救治', 'medical', 3, 60 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_REDCROSS_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'CPR_AED', '心肺复苏/AED', 'medical', 4, 70 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_REDCROSS_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'VOLUNTEER_SUPPORT', '志愿者支持', 'logistics', 4, 80 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_REDCROSS_001';

-- 青年志愿者救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 3, 150 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_YOUTH_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'SHELTER_MANAGEMENT', '安置点管理', 'shelter', 3, 200 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_YOUTH_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'VOLUNTEER_SUPPORT', '志愿者支持', 'logistics', 4, 200 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_YOUTH_001';

-- 社区应急志愿队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'EVACUATION_COORDINATION', '疏散协调', 'evacuation', 2, 250 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_COMMUNITY_001';
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'VOLUNTEER_SUPPORT', '志愿者支持', 'logistics', 3, 300 FROM operational_v2.rescue_teams_v2 WHERE code = 'VOL_COMMUNITY_001';

-- ============================================================================
-- 十、为现有队伍补充缺失的关键能力
-- ============================================================================

-- 为所有消防队添加COMMUNICATION_SUPPORT和HEAVY_LIFTING
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT t.id, 'COMMUNICATION_SUPPORT', '通信保障', 'communication', 3, 30 
FROM operational_v2.rescue_teams_v2 t
WHERE t.team_type = 'fire_rescue' 
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = t.id AND tc.capability_code = 'COMMUNICATION_SUPPORT'
  );

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT t.id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 3, 25 
FROM operational_v2.rescue_teams_v2 t
WHERE t.team_type = 'fire_rescue' 
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = t.id AND tc.capability_code = 'HEAVY_LIFTING'
  );

-- 为所有医疗队添加PATIENT_TRANSPORT
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT t.id, 'PATIENT_TRANSPORT', '伤员转运', 'medical', 4, 30 
FROM operational_v2.rescue_teams_v2 t
WHERE t.team_type = 'medical' 
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = t.id AND tc.capability_code = 'PATIENT_TRANSPORT'
  );

-- 为所有工程队添加HEAVY_LIFTING
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT t.id, 'HEAVY_LIFTING', '重物起吊', 'engineering', 4, 35 
FROM operational_v2.rescue_teams_v2 t
WHERE t.team_type = 'engineering' 
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = t.id AND tc.capability_code = 'HEAVY_LIFTING'
  );

-- 为应急管理局队伍添加COMMAND_COORDINATION
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT t.id, 'COMMAND_COORDINATION', '指挥协调', 'command', 4, 50 
FROM operational_v2.rescue_teams_v2 t
WHERE t.name LIKE '%应急管理局%' 
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = t.id AND tc.capability_code = 'COMMAND_COORDINATION'
  );

-- ============================================================================
-- 验证插入结果
-- ============================================================================
SELECT capability_code, COUNT(*) as team_count 
FROM operational_v2.team_capabilities_v2 
GROUP BY capability_code 
ORDER BY team_count DESC;

SELECT COUNT(*) as total_capabilities FROM operational_v2.team_capabilities_v2;

SELECT 
    t.team_type,
    COUNT(DISTINCT t.id) as team_count,
    AVG((SELECT COUNT(*) FROM operational_v2.team_capabilities_v2 tc WHERE tc.team_id = t.id))::numeric(3,1) as avg_capabilities
FROM operational_v2.rescue_teams_v2 t
GROUP BY t.team_type
ORDER BY team_count DESC;
