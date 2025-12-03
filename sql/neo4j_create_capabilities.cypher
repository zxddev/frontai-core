// ============================================================================
// neo4j_create_capabilities.cypher
// 创建统一格式的Capability节点（110个）
// 与PostgreSQL capability_codes表保持一致
// ============================================================================

// 先删除现有的混合格式Capability节点（保留关系会自动删除）
MATCH (c:Capability)
DETACH DELETE c;

// ========== 创建110个统一格式的Capability节点 ==========

// ---------- 现有34个（PostgreSQL team_capabilities_v2中已使用）----------
CREATE (c:Capability {code: 'BRIDGE_REPAIR', name: '桥梁修复', category: 'engineering'});
CREATE (c:Capability {code: 'BUILDING_SHORING', name: '建筑支撑加固', category: 'engineering'});
CREATE (c:Capability {code: 'CHEMICAL_FIRE', name: '化学火灾扑救', category: 'fire'});
CREATE (c:Capability {code: 'COMMAND_COORDINATION', name: '指挥协调', category: 'command'});
CREATE (c:Capability {code: 'COMMUNICATION_SUPPORT', name: '通信保障', category: 'communication'});
CREATE (c:Capability {code: 'CONFINED_SPACE_RESCUE', name: '狭小空间救援', category: 'rescue'});
CREATE (c:Capability {code: 'CPR_AED', name: '心肺复苏/AED', category: 'medical'});
CREATE (c:Capability {code: 'DECONTAMINATION', name: '洗消去污', category: 'hazmat'});
CREATE (c:Capability {code: 'DEMOLITION', name: '破拆作业', category: 'engineering'});
CREATE (c:Capability {code: 'DIVING_RESCUE', name: '潜水救援', category: 'rescue'});
CREATE (c:Capability {code: 'EMERGENCY_TREATMENT', name: '紧急救治', category: 'medical'});
CREATE (c:Capability {code: 'EVACUATION_COORDINATION', name: '疏散协调', category: 'evacuation'});
CREATE (c:Capability {code: 'FIRE_SEARCH_RESCUE', name: '火场搜救', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_SUPPRESSION', name: '火灾扑救', category: 'fire'});
CREATE (c:Capability {code: 'HAZMAT_CONTAINMENT', name: '危化品围堵', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_DETECTION', name: '危化品检测', category: 'hazmat'});
CREATE (c:Capability {code: 'HEAVY_LIFTING', name: '重物起吊', category: 'engineering'});
CREATE (c:Capability {code: 'LANDSLIDE_RESCUE', name: '山体滑坡救援', category: 'rescue'});
CREATE (c:Capability {code: 'LIFE_DETECTION', name: '生命探测', category: 'search'});
CREATE (c:Capability {code: 'MEDICAL_TRIAGE', name: '医疗分诊', category: 'medical'});
CREATE (c:Capability {code: 'NETWORK_RECOVERY', name: '网络恢复', category: 'communication'});
CREATE (c:Capability {code: 'PATIENT_TRANSPORT', name: '伤员转运', category: 'medical'});
CREATE (c:Capability {code: 'RADIATION_PROTECTION', name: '辐射防护', category: 'hazmat'});
CREATE (c:Capability {code: 'ROAD_CLEARANCE', name: '道路抢通', category: 'engineering'});
CREATE (c:Capability {code: 'ROPE_RESCUE', name: '绳索救援', category: 'rescue'});
CREATE (c:Capability {code: 'SATELLITE_COMM', name: '卫星通信', category: 'communication'});
CREATE (c:Capability {code: 'SHELTER_MANAGEMENT', name: '安置点管理', category: 'shelter'});
CREATE (c:Capability {code: 'STRUCTURAL_RESCUE', name: '结构救援', category: 'rescue'});
CREATE (c:Capability {code: 'SURGERY', name: '手术救治', category: 'medical'});
CREATE (c:Capability {code: 'SWIFT_WATER_RESCUE', name: '急流水域救援', category: 'rescue'});
CREATE (c:Capability {code: 'TRAUMA_CARE', name: '创伤护理', category: 'medical'});
CREATE (c:Capability {code: 'UNDERWATER_SEARCH', name: '水下搜索', category: 'search'});
CREATE (c:Capability {code: 'VOLUNTEER_SUPPORT', name: '志愿者支持', category: 'logistics'});
CREATE (c:Capability {code: 'WATER_RESCUE', name: '水域救援', category: 'rescue'});

// ---------- 新增76个（来自YAML TRR规则）----------
// 呼吸/安全装备
CREATE (c:Capability {code: 'BREATHING_APPARATUS', name: '呼吸器装备', category: 'equipment'});

// 后勤保障
CREATE (c:Capability {code: 'CATERING_FIELD', name: '野外餐饮保障', category: 'logistics'});
CREATE (c:Capability {code: 'SUPPLY_TRANSPORT', name: '物资运输', category: 'logistics'});

// 指挥通信
CREATE (c:Capability {code: 'COMMAND_VEHICLE', name: '指挥车辆', category: 'command'});
CREATE (c:Capability {code: 'COMM_COMMAND', name: '指挥通信', category: 'communication'});
CREATE (c:Capability {code: 'COMM_MESH', name: '网状通信', category: 'communication'});
CREATE (c:Capability {code: 'COMM_SATELLITE', name: '卫星通信能力', category: 'communication'});

// 消防灭火
CREATE (c:Capability {code: 'COOLING_SPRAY', name: '冷却喷淋', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_AERIAL', name: '空中灭火', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_ELECTRICAL', name: '电气火灾扑救', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_FOREST', name: '森林火灾扑救', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_STANDBY', name: '消防待命', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_SUPPLY_WATER', name: '消防供水', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_SUPPRESS', name: '火灾扑救能力', category: 'fire'});
CREATE (c:Capability {code: 'FIRE_UNDERGROUND', name: '地下火灾扑救', category: 'fire'});
CREATE (c:Capability {code: 'FIREBREAK_BUILD', name: '防火隔离带构建', category: 'fire'});
CREATE (c:Capability {code: 'FOAM_SUPPRESS', name: '泡沫灭火', category: 'fire'});
CREATE (c:Capability {code: 'SMOKE_EXHAUST', name: '排烟作业', category: 'fire'});

// 人群疏散
CREATE (c:Capability {code: 'CROWD_CONTROL', name: '人群控制', category: 'evacuation'});
CREATE (c:Capability {code: 'EVAC_GUIDANCE', name: '疏散引导', category: 'evacuation'});
CREATE (c:Capability {code: 'WARNING_BROADCAST', name: '预警广播', category: 'evacuation'});

// 评估监测
CREATE (c:Capability {code: 'DAMAGE_ASSESS', name: '损失评估', category: 'assessment'});
CREATE (c:Capability {code: 'FLOOD_MONITOR', name: '洪水监测', category: 'monitoring'});
CREATE (c:Capability {code: 'GEO_MONITOR', name: '地质监测', category: 'monitoring'});
CREATE (c:Capability {code: 'GAS_MONITOR', name: '气体监测', category: 'monitoring'});

// 水利工程
CREATE (c:Capability {code: 'DAM_REPAIR', name: '大坝修复', category: 'engineering'});
CREATE (c:Capability {code: 'PUMP_DRAINAGE', name: '排水泵送', category: 'engineering'});
CREATE (c:Capability {code: 'PUMP_HIGH_CAPACITY', name: '大流量泵送', category: 'engineering'});
CREATE (c:Capability {code: 'SANDBAG_FILL', name: '沙袋填装', category: 'engineering'});
CREATE (c:Capability {code: 'PIPE_REPAIR', name: '管道修复', category: 'engineering'});

// 工程作业
CREATE (c:Capability {code: 'ENG_BLASTING', name: '工程爆破', category: 'engineering'});
CREATE (c:Capability {code: 'ENG_DEMOLITION', name: '工程破拆', category: 'engineering'});
CREATE (c:Capability {code: 'ENG_HEAVY_MACHINE', name: '重型机械作业', category: 'engineering'});
CREATE (c:Capability {code: 'TREE_CLEARANCE', name: '树木清理', category: 'engineering'});

// 专家支持
CREATE (c:Capability {code: 'EXPERT_CONSULT', name: '专家咨询', category: 'support'});
CREATE (c:Capability {code: 'MEDIA_LIAISON', name: '媒体联络', category: 'support'});

// 设施安全
CREATE (c:Capability {code: 'FACILITY_SECURE', name: '设施安全加固', category: 'engineering'});

// 危化品处置
CREATE (c:Capability {code: 'GAS_DETECT', name: '气体检测', category: 'hazmat'});
CREATE (c:Capability {code: 'GAS_SHUTOFF', name: '气体关断', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_CONTAIN', name: '危化品围堵能力', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_DECON', name: '危化品洗消', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_DETECT', name: '危化品探测', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_GAS_DETECT', name: '危化品气体检测', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_NEUTRALIZE', name: '危化品中和', category: 'hazmat'});
CREATE (c:Capability {code: 'HAZMAT_TRANSFER', name: '危化品转移', category: 'hazmat'});

// 生命支持
CREATE (c:Capability {code: 'LIFE_SUPPORT_DRILL', name: '生命支持钻探', category: 'rescue'});

// 照明设备
CREATE (c:Capability {code: 'LIGHTING_MOBILE', name: '移动照明', category: 'equipment'});

// 医疗救护
CREATE (c:Capability {code: 'MEDICAL_FIRST_AID', name: '现场急救', category: 'medical'});
CREATE (c:Capability {code: 'MEDICAL_ICU', name: '重症监护', category: 'medical'});
CREATE (c:Capability {code: 'MEDICAL_PEDIATRIC', name: '儿科救治', category: 'medical'});
CREATE (c:Capability {code: 'MEDICAL_TOXICOLOGY', name: '中毒救治', category: 'medical'});
CREATE (c:Capability {code: 'MEDICAL_TRANSPORT', name: '医疗转运', category: 'medical'});

// 特种救援
CREATE (c:Capability {code: 'MINE_RESCUE', name: '矿山救援', category: 'rescue'});
CREATE (c:Capability {code: 'RESCUE_CONFINED', name: '受限空间救援', category: 'rescue'});
CREATE (c:Capability {code: 'RESCUE_HIGH_ANGLE', name: '高空救援', category: 'rescue'});
CREATE (c:Capability {code: 'RESCUE_STRUCTURAL', name: '建筑结构救援', category: 'rescue'});
CREATE (c:Capability {code: 'RESCUE_VEHICLE', name: '车辆救援', category: 'rescue'});
CREATE (c:Capability {code: 'RESCUE_WATER_FLOOD', name: '洪水水域救援', category: 'rescue'});
CREATE (c:Capability {code: 'RESCUE_WATER_SWIFT', name: '急流救援', category: 'rescue'});

// 电力保障
CREATE (c:Capability {code: 'POWER_CUTOFF', name: '电力切断', category: 'power'});
CREATE (c:Capability {code: 'POWER_EMERGENCY', name: '应急供电', category: 'power'});
CREATE (c:Capability {code: 'POWER_LINE_REPAIR', name: '电力线路修复', category: 'power'});

// 心理援助
CREATE (c:Capability {code: 'PSYCH_CRISIS', name: '心理危机干预', category: 'medical'});

// 核辐射
CREATE (c:Capability {code: 'RADIATION_DETECT', name: '辐射检测', category: 'hazmat'});
CREATE (c:Capability {code: 'RADIATION_SHIELD', name: '辐射屏蔽', category: 'hazmat'});

// 现场安保
CREATE (c:Capability {code: 'SCENE_GUARD', name: '现场警戒', category: 'security'});
CREATE (c:Capability {code: 'TRAFFIC_CONTROL', name: '交通管制', category: 'security'});

// 搜索探测
CREATE (c:Capability {code: 'SEARCH_LIFE_DETECT', name: '生命搜索探测', category: 'search'});
CREATE (c:Capability {code: 'UAV_RECONNAISSANCE', name: '无人机侦察', category: 'search'});
CREATE (c:Capability {code: 'UAV_THERMAL', name: '热成像无人机', category: 'search'});

// 安置管理
CREATE (c:Capability {code: 'SHELTER_MANAGE', name: '安置管理能力', category: 'shelter'});
CREATE (c:Capability {code: 'SHELTER_SETUP', name: '安置点搭建', category: 'shelter'});

// 通风作业
CREATE (c:Capability {code: 'VENTILATION_CONTROL', name: '通风控制', category: 'engineering'});
CREATE (c:Capability {code: 'VENTILATION_RESTORE', name: '通风恢复', category: 'engineering'});

// 供水保障
CREATE (c:Capability {code: 'WATER_PURIFY', name: '水质净化', category: 'logistics'});
CREATE (c:Capability {code: 'WATER_TRANSPORT', name: '供水运输', category: 'logistics'});

// ========== 创建索引 ==========
CREATE INDEX capability_code_idx IF NOT EXISTS FOR (c:Capability) ON (c.code);
CREATE INDEX capability_category_idx IF NOT EXISTS FOR (c:Capability) ON (c.category);

// ========== 验证 ==========
MATCH (c:Capability)
RETURN c.category AS category, count(*) AS count
ORDER BY count DESC;
