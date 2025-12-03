// =============================================================================
// TRR规则导入脚本 - 将trr_emergency.yaml的45条规则导入Neo4j
// 执行方式: 在Neo4j Browser中执行
// =============================================================================

// 先删除旧的TRR-EM规则（如果存在）
MATCH (r:TRRRule) WHERE r.rule_id STARTS WITH 'TRR-EM-' DETACH DELETE r;

// =============================================================================
// 地震相关规则 (TRR-EM-001 ~ TRR-EM-009)
// =============================================================================

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-001',
    name: '地震人员搜救规则',
    description: '地震导致建筑倒塌且有被困人员时触发搜救任务',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type IN [earthquake, building_collapse]', 'has_trapped = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['search_rescue', 'medical_emergency'],
    resource_types: ['rescue_team', 'medical_team'],
    grouping_pattern: '1搜救队 + 1医疗队',
    tactical_notes: '优先使用生命探测仪定位被困人员，72小时黄金救援期'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-002',
    name: '地震重型破拆规则',
    description: '大面积建筑倒塌需要重型机械支援',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type IN [earthquake, building_collapse]', 'collapse_area_sqm >= 500'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.85,
    is_active: true,
    task_types: ['heavy_rescue', 'debris_clearing'],
    resource_types: ['engineering_team', 'heavy_equipment'],
    grouping_pattern: '1工程队 + 挖掘机/吊车',
    tactical_notes: '协调交通管制，确保大型设备进场通道'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-003',
    name: '地震次生灾害监测规则',
    description: '地震后启动次生灾害监测',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'magnitude >= 5.0'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.80,
    is_active: true,
    task_types: ['hazard_monitoring', 'reconnaissance'],
    resource_types: ['monitoring_team', 'uav_team'],
    grouping_pattern: '监测组 + 无人机侦察',
    tactical_notes: '重点监测滑坡、堰塞湖、火灾等次生灾害风险点'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-004',
    name: '学校地震救援规则',
    description: '学校建筑倒塌时启动针对性搜救',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'building_type = school'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['search_rescue', 'medical_emergency', 'psychological_aid'],
    resource_types: ['rescue_team', 'medical_team', 'psychological_team'],
    grouping_pattern: '2搜救队 + 儿童医疗组 + 心理援助组',
    tactical_notes: '优先搜救，注意儿童伤员特殊处置，启动家属联络'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-005',
    name: '医院地震救援规则',
    description: '医院建筑受损时启动医疗系统应急',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'building_type = hospital'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['patient_transfer', 'medical_emergency', 'power_restoration'],
    resource_types: ['ambulance_team', 'power_team'],
    grouping_pattern: '急救转运组 + 应急电力组',
    tactical_notes: '优先转运危重病人，确保医疗设备供电'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-006',
    name: '地震大规模疏散规则',
    description: '强烈地震后启动大规模人员疏散',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'magnitude >= 6.0'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.85,
    is_active: true,
    task_types: ['mass_evacuation', 'shelter_setup', 'traffic_control'],
    resource_types: ['police_team', 'logistics_team'],
    grouping_pattern: '疏散引导组 + 安置点开设组 + 交通管制组',
    tactical_notes: '开放所有避难场所，启用应急广播系统'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-007',
    name: '地震供水保障规则',
    description: '地震导致供水中断时启动应急供水',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'water_supply_disrupted = true'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.75,
    is_active: true,
    task_types: ['water_supply', 'pipe_repair'],
    resource_types: ['water_supply_team', 'repair_team'],
    grouping_pattern: '供水保障组 + 管道抢修组',
    tactical_notes: '优先保障医院、安置点供水'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-008',
    name: '地震电力抢修规则',
    description: '地震导致大面积停电时启动电力抢修',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'power_outage_area_sqkm >= 1'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.80,
    is_active: true,
    task_types: ['power_restoration', 'generator_deployment'],
    resource_types: ['power_team', 'generator_vehicle'],
    grouping_pattern: '电力抢修组 + 发电车组',
    tactical_notes: '优先恢复医院、通信基站、指挥中心供电'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-009',
    name: '地震燃气泄漏处置规则',
    description: '地震导致燃气管道破裂时启动处置',
    disaster_type: 'earthquake',
    trigger_conditions: ['disaster_type = earthquake', 'gas_leak_detected = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['gas_shutoff', 'evacuation', 'fire_prevention'],
    resource_types: ['gas_team', 'fire_team'],
    grouping_pattern: '燃气处置组 + 消防警戒组',
    tactical_notes: '立即关闭总阀，疏散周边群众，禁止明火'
});

// =============================================================================
// 火灾相关规则 (TRR-EM-010 ~ TRR-EM-019)
// =============================================================================

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-010',
    name: '建筑火灾扑救规则',
    description: '建筑火灾时启动消防扑救',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_type IN [building, residential, commercial]'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['fire_suppression', 'search_rescue'],
    resource_types: ['fire_team', 'fire_engine'],
    grouping_pattern: '2消防中队 + 云梯车',
    tactical_notes: '优先控制火势蔓延，确保人员疏散通道'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-011',
    name: '高层建筑火灾规则',
    description: '高层建筑火灾需要特种装备',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'building_height_m >= 30'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.90,
    is_active: true,
    task_types: ['high_rise_rescue', 'fire_suppression'],
    resource_types: ['special_rescue_team', 'aerial_ladder'],
    grouping_pattern: '特勤队 + 举高车 + 排烟车',
    tactical_notes: '启用消防电梯，协调直升机待命，注意烟囱效应'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-012',
    name: '森林火灾扑救规则',
    description: '森林火灾启动专业扑救',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_type = forest'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['forest_fire_suppression', 'firebreak_construction'],
    resource_types: ['forest_fire_team', 'uav_team', 'bulldozer'],
    grouping_pattern: '森林消防队 + 无人机侦察组 + 开辟隔离带组',
    tactical_notes: '监测火势蔓延方向，注意风向变化，保护扑火人员安全'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-013',
    name: '工厂火灾处置规则',
    description: '工厂火灾需要考虑危险品',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_type = industrial'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['fire_suppression', 'hazmat_standby', 'evacuation'],
    resource_types: ['fire_team', 'hazmat_team', 'foam_truck'],
    grouping_pattern: '消防主力 + 危化品侦检组 + 泡沫车',
    tactical_notes: '了解工厂储存物品，防止有毒烟气扩散'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-014',
    name: '地下空间火灾规则',
    description: '地下商场/车库火灾特殊处置',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_location = underground'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['underground_fire_suppression', 'smoke_control', 'rescue'],
    resource_types: ['special_fire_team', 'smoke_exhaust_vehicle'],
    grouping_pattern: '地下灭火攻坚组 + 排烟组',
    tactical_notes: '控制所有出入口，采用正压送风，内攻人员必须佩戴空呼'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-015',
    name: '加油站火灾规则',
    description: '加油站/油库火灾处置',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_location IN [gas_station, oil_depot]'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['oil_fire_suppression', 'cooling', 'evacuation'],
    resource_types: ['foam_truck', 'water_tank', 'police_team'],
    grouping_pattern: '泡沫灭火组 + 冷却保护组 + 警戒疏散组',
    tactical_notes: '严禁使用直流水，划定500米警戒区，切断电源'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-016',
    name: '电气火灾规则',
    description: '电气设备火灾特殊处置',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_cause = electrical'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.90,
    is_active: true,
    task_types: ['electrical_fire_suppression', 'power_cutoff'],
    resource_types: ['fire_team', 'power_team'],
    grouping_pattern: '消防队 + 电力抢修组',
    tactical_notes: '确认断电后再灭火，使用干粉或二氧化碳灭火器'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-017',
    name: '车辆火灾规则',
    description: '车辆火灾处置',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_type = vehicle'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.80,
    is_active: true,
    task_types: ['vehicle_fire_suppression', 'traffic_control'],
    resource_types: ['fire_team', 'police_team'],
    grouping_pattern: '消防车 + 交警',
    tactical_notes: '注意油箱爆炸风险，新能源车注意电池热失控'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-018',
    name: '人员密集场所火灾规则',
    description: '商场、影院等人员密集场所火灾',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'crowd_density >= 100'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['fire_suppression', 'mass_evacuation', 'crowd_control'],
    resource_types: ['fire_team', 'police_team', 'medical_team'],
    grouping_pattern: '消防主力 + 疏散组 + 医疗待命组',
    tactical_notes: '启用所有安全出口，防止踩踏，安排医疗力量待命'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-019',
    name: '仓库火灾规则',
    description: '大型仓库火灾处置',
    disaster_type: 'fire',
    trigger_conditions: ['disaster_type = fire', 'fire_type = warehouse'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.85,
    is_active: true,
    task_types: ['fire_suppression', 'property_protection'],
    resource_types: ['fire_team', 'water_tanker'],
    grouping_pattern: '多中队联合 + 供水编队',
    tactical_notes: '了解仓储物品，考虑塌落风险，保护相邻建筑'
});

// =============================================================================
// 危化品相关规则 (TRR-EM-020 ~ TRR-EM-026)
// =============================================================================

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-020',
    name: '危化品泄漏处置规则',
    description: '危化品泄漏时启动专业处置',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'has_leak = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['hazmat_containment', 'evacuation'],
    resource_types: ['hazmat_team', 'decon_unit'],
    grouping_pattern: '危化品处置队 + 洗消车',
    tactical_notes: '划定警戒区，上风向集结，穿戴防护装备'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-021',
    name: '危化品人员防护规则',
    description: '危化品现场有人员暴露时启动医疗救护',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'exposed_population >= 1'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['medical_decon', 'medical_emergency'],
    resource_types: ['medical_team', 'decon_unit'],
    grouping_pattern: '医疗队 + 洗消组',
    tactical_notes: '先洗消后救治，防止二次污染'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-022',
    name: '毒气泄漏规则',
    description: '有毒气体泄漏处置',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'hazmat_type IN [toxic_gas, chlorine, ammonia, hydrogen_sulfide]'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['gas_leak_control', 'mass_evacuation', 'air_monitoring'],
    resource_types: ['hazmat_team', 'police_team', 'medical_team'],
    grouping_pattern: '气体侦检组 + 堵漏组 + 疏散组',
    tactical_notes: '根据气体密度判断扩散方向，低洼处重点警戒'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-023',
    name: '危化品爆炸规则',
    description: '危化品爆炸后处置',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'has_explosion = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['search_rescue', 'fire_suppression', 'hazmat_containment'],
    resource_types: ['rescue_team', 'fire_team', 'hazmat_team'],
    grouping_pattern: '搜救组 + 灭火组 + 侦检组',
    tactical_notes: '注意二次爆炸风险，确认无爆炸风险后再进入'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-024',
    name: '放射性物质泄漏规则',
    description: '放射性物质泄漏处置',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'hazmat_type = radioactive'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.99,
    is_active: true,
    task_types: ['radiation_control', 'evacuation', 'decontamination'],
    resource_types: ['nuclear_team', 'decon_unit'],
    grouping_pattern: '核应急队 + 洗消组',
    tactical_notes: '划定辐射警戒区，限制暴露时间，碘片预防'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-025',
    name: '危化品运输事故规则',
    description: '危化品运输车辆事故处置',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'incident_type = transport_accident'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['hazmat_containment', 'traffic_control', 'transfer'],
    resource_types: ['hazmat_team', 'police_team', 'tanker'],
    grouping_pattern: '堵漏组 + 交通管制组 + 倒罐组',
    tactical_notes: '核实运输货物，查看安全技术说明书'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-026',
    name: '腐蚀性物质泄漏规则',
    description: '强酸强碱泄漏处置',
    disaster_type: 'hazmat',
    trigger_conditions: ['disaster_type = hazmat', 'hazmat_type IN [acid, alkali, corrosive]'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.90,
    is_active: true,
    task_types: ['hazmat_containment', 'neutralization'],
    resource_types: ['hazmat_team'],
    grouping_pattern: '危化品处置队',
    tactical_notes: '防止泄漏扩散到下水道，中和处理后收集'
});

// =============================================================================
// 洪涝相关规则 (TRR-EM-030 ~ TRR-EM-035)
// =============================================================================

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-030',
    name: '洪水人员转移规则',
    description: '洪水淹没区域有被困人员时启动水域救援',
    disaster_type: 'flood',
    trigger_conditions: ['disaster_type = flood', 'has_trapped = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['water_rescue', 'evacuation'],
    resource_types: ['water_rescue_team', 'boat'],
    grouping_pattern: '水域救援队 + 冲锋舟',
    tactical_notes: '注意水流速度，配备救生设备'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-031',
    name: '内涝排水规则',
    description: '城市内涝时启动排水作业',
    disaster_type: 'flood',
    trigger_conditions: ['disaster_type = flood', 'flood_type = urban_waterlogging'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.80,
    is_active: true,
    task_types: ['drainage', 'traffic_control'],
    resource_types: ['drainage_team', 'pump_vehicle'],
    grouping_pattern: '排涝组 + 排水泵车',
    tactical_notes: '优先保障交通要道和重点区域'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-032',
    name: '堤坝险情处置规则',
    description: '堤坝出现险情时启动抢险',
    disaster_type: 'flood',
    trigger_conditions: ['disaster_type = flood', 'dam_emergency = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['dam_reinforcement', 'evacuation'],
    resource_types: ['armed_police', 'militia', 'engineering_team'],
    grouping_pattern: '抢险突击队 + 疏散组',
    tactical_notes: '监测险情发展，提前转移下游群众'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-033',
    name: '山洪预警转移规则',
    description: '山洪预警时启动预防性转移',
    disaster_type: 'flood',
    trigger_conditions: ['disaster_type = flood', 'flood_type = flash_flood'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['preventive_evacuation', 'monitoring'],
    resource_types: ['village_cadre', 'monitoring_team'],
    grouping_pattern: '转移组 + 监测预警组',
    tactical_notes: '提前转移危险区域群众，不漏一户一人'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-034',
    name: '地下空间积水规则',
    description: '地下车库/地铁等积水处置',
    disaster_type: 'flood',
    trigger_conditions: ['disaster_type = flood', 'flood_location = underground'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['underwater_rescue', 'drainage', 'power_cutoff'],
    resource_types: ['water_rescue_team', 'drainage_team', 'power_team'],
    grouping_pattern: '水域救援组 + 排水组 + 电力保障组',
    tactical_notes: '先断电再救援，注意漂浮车辆'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-035',
    name: '洪水物资保障规则',
    description: '洪灾期间启动物资保障',
    disaster_type: 'flood',
    trigger_conditions: ['disaster_type = flood', 'affected_population >= 1000'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.80,
    is_active: true,
    task_types: ['supply_distribution', 'shelter_management'],
    resource_types: ['logistics_team', 'volunteer'],
    grouping_pattern: '物资保障组 + 安置点管理组',
    tactical_notes: '确保食品、饮水、药品等基本生活物资供应'
});

// =============================================================================
// 滑坡/泥石流相关规则 (TRR-EM-040 ~ TRR-EM-043)
// =============================================================================

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-040',
    name: '滑坡搜救规则',
    description: '滑坡掩埋人员时启动搜救',
    disaster_type: 'landslide',
    trigger_conditions: ['disaster_type = landslide', 'has_buried = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['search_rescue', 'debris_clearing'],
    resource_types: ['rescue_team', 'engineering_team'],
    grouping_pattern: '搜救队 + 工程机械组',
    tactical_notes: '注意二次滑坡风险，设置监测预警'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-041',
    name: '滑坡监测预警规则',
    description: '滑坡区域持续监测',
    disaster_type: 'landslide',
    trigger_conditions: ['disaster_type = landslide'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.75,
    is_active: true,
    task_types: ['hazard_monitoring'],
    resource_types: ['monitoring_team'],
    grouping_pattern: '地质监测组',
    tactical_notes: '监测位移、裂缝、降雨量等指标'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-042',
    name: '泥石流预警转移规则',
    description: '泥石流预警时启动转移',
    disaster_type: 'debris_flow',
    trigger_conditions: ['disaster_type = debris_flow'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.95,
    is_active: true,
    task_types: ['preventive_evacuation', 'road_closure'],
    resource_types: ['police_team', 'village_cadre'],
    grouping_pattern: '转移组 + 交通管制组',
    tactical_notes: '封闭危险路段，转移沟口居民'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-043',
    name: '堰塞湖处置规则',
    description: '滑坡形成堰塞湖时启动处置',
    disaster_type: 'landslide',
    trigger_conditions: ['disaster_type IN [landslide, earthquake]', 'barrier_lake_formed = true'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.98,
    is_active: true,
    task_types: ['barrier_lake_discharge', 'evacuation', 'monitoring'],
    resource_types: ['engineering_team', 'armed_police', 'monitoring_team'],
    grouping_pattern: '工程抢险组 + 下游疏散组 + 监测组',
    tactical_notes: '监测水位变化，制定应急泄流方案'
});

// =============================================================================
// 通用规则 (TRR-EM-090 ~ TRR-EM-098)
// =============================================================================

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-090',
    name: '大规模伤亡事件医疗规则',
    description: '伤亡人数超过阈值时启动批量伤员救治',
    disaster_type: 'general',
    trigger_conditions: ['estimated_casualties >= 10'],
    trigger_logic: 'AND',
    priority: 'critical',
    weight: 0.90,
    is_active: true,
    task_types: ['mass_casualty_incident', 'medical_emergency'],
    resource_types: ['medical_team', 'ambulance'],
    grouping_pattern: '医疗指挥组 + 多个急救单元',
    tactical_notes: '建立现场分诊站，协调医院收治'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-091',
    name: '夜间作业照明规则',
    description: '夜间救援作业需要照明支持',
    disaster_type: 'general',
    trigger_conditions: ['is_night_operation = true'],
    trigger_logic: 'AND',
    priority: 'medium',
    weight: 0.60,
    is_active: true,
    task_types: ['logistics_support'],
    resource_types: ['support_team', 'lighting_vehicle'],
    grouping_pattern: '照明保障组',
    tactical_notes: '确保作业面充足照明'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-092',
    name: '通信中断保障规则',
    description: '通信中断时启动应急通信保障',
    disaster_type: 'general',
    trigger_conditions: ['communication_status = disrupted'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.85,
    is_active: true,
    task_types: ['communication_support'],
    resource_types: ['communication_team'],
    grouping_pattern: '通信保障组',
    tactical_notes: '部署卫星通信和自组网设备'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-093',
    name: '现场指挥部设立规则',
    description: '重大事件设立现场指挥部',
    disaster_type: 'general',
    trigger_conditions: ['incident_level IN [I, II]'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.85,
    is_active: true,
    task_types: ['command_setup'],
    resource_types: ['command_vehicle'],
    grouping_pattern: '现场指挥组',
    tactical_notes: '设立在安全位置，确保通信畅通'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-095',
    name: '后勤保障规则',
    description: '长时间救援启动后勤保障',
    disaster_type: 'general',
    trigger_conditions: ['expected_duration_hours >= 6'],
    trigger_logic: 'AND',
    priority: 'medium',
    weight: 0.70,
    is_active: true,
    task_types: ['logistics_support'],
    resource_types: ['logistics_team', 'catering_vehicle'],
    grouping_pattern: '后勤保障组',
    tactical_notes: '保障救援人员饮食休息'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-096',
    name: '心理援助规则',
    description: '重大事件启动心理援助',
    disaster_type: 'general',
    trigger_conditions: ['casualties >= 5'],
    trigger_logic: 'AND',
    priority: 'medium',
    weight: 0.65,
    is_active: true,
    task_types: ['psychological_aid'],
    resource_types: ['psychological_team'],
    grouping_pattern: '心理援助组',
    tactical_notes: '关注受害者家属和救援人员心理状态'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-097',
    name: '现场警戒规则',
    description: '事故现场启动警戒管控',
    disaster_type: 'general',
    trigger_conditions: ['scene_control_required = true'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.75,
    is_active: true,
    task_types: ['scene_control'],
    resource_types: ['police_team'],
    grouping_pattern: '警戒组',
    tactical_notes: '划定警戒线，禁止无关人员进入'
});

CREATE (r:TRRRule {
    rule_id: 'TRR-EM-098',
    name: '无人机侦察规则',
    description: '复杂现场启动无人机侦察',
    disaster_type: 'general',
    trigger_conditions: ['scene_complexity = high'],
    trigger_logic: 'AND',
    priority: 'high',
    weight: 0.75,
    is_active: true,
    task_types: ['aerial_reconnaissance'],
    resource_types: ['uav_team'],
    grouping_pattern: '无人机侦察组',
    tactical_notes: '获取现场全貌，辅助决策'
});

// =============================================================================
// 验证导入结果
// =============================================================================
// MATCH (r:TRRRule) WHERE r.rule_id STARTS WITH 'TRR-EM-' 
// RETURN r.rule_id, r.name, r.disaster_type 
// ORDER BY r.rule_id;
