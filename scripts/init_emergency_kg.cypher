// ============================================================================
// 应急救灾知识图谱初始化脚本
// 包含：TRR触发规则、能力映射、任务依赖关系
// 执行方式：在Neo4j Browser中执行，或使用 cypher-shell
// ============================================================================

// 清理已有应急救灾相关节点（可选，谨慎使用）
// MATCH (n) WHERE n:TRRRule OR n:Capability OR n:TaskType OR n:ResourceType DETACH DELETE n;

// ============================================================================
// 1. 创建约束和索引
// ============================================================================

CREATE CONSTRAINT trr_rule_id IF NOT EXISTS FOR (r:TRRRule) REQUIRE r.rule_id IS UNIQUE;
CREATE CONSTRAINT capability_code IF NOT EXISTS FOR (c:Capability) REQUIRE c.code IS UNIQUE;
CREATE CONSTRAINT task_type_code IF NOT EXISTS FOR (t:TaskType) REQUIRE t.code IS UNIQUE;
CREATE CONSTRAINT resource_type_code IF NOT EXISTS FOR (rt:ResourceType) REQUIRE rt.code IS UNIQUE;

CREATE INDEX trr_rule_disaster_type IF NOT EXISTS FOR (r:TRRRule) ON (r.disaster_type);
CREATE INDEX capability_category IF NOT EXISTS FOR (c:Capability) ON (c.category);

// ============================================================================
// 2. 创建能力节点 (Capability)
// ============================================================================

// 搜救能力
CREATE (c:Capability {
    code: 'LIFE_DETECTION',
    name: '生命探测',
    category: 'search_rescue',
    description: '使用生命探测仪探测废墟下被困人员',
    equipment_required: ['生命探测仪', '蛇眼探测器', '雷达探测仪']
});

CREATE (c:Capability {
    code: 'STRUCTURAL_RESCUE',
    name: '结构救援',
    category: 'search_rescue',
    description: '从倒塌建筑中营救被困人员',
    equipment_required: ['液压剪切器', '千斤顶', '气垫', '破拆工具']
});

CREATE (c:Capability {
    code: 'CONFINED_SPACE_RESCUE',
    name: '狭小空间救援',
    category: 'search_rescue',
    description: '在狭小空间中实施救援',
    equipment_required: ['狭小空间救援设备', '通风设备', '照明设备']
});

// 医疗能力
CREATE (c:Capability {
    code: 'MEDICAL_TRIAGE',
    name: '医疗分诊',
    category: 'medical',
    description: '对伤员进行快速分诊分类',
    equipment_required: ['分诊标签', '急救包', '担架']
});

CREATE (c:Capability {
    code: 'EMERGENCY_TREATMENT',
    name: '紧急救治',
    category: 'medical',
    description: '现场紧急医疗救治',
    equipment_required: ['急救药品', '除颤仪', '呼吸机', '止血带']
});

CREATE (c:Capability {
    code: 'PATIENT_TRANSPORT',
    name: '伤员转运',
    category: 'medical',
    description: '将伤员安全转运至医疗机构',
    equipment_required: ['救护车', '担架', '转运监护设备']
});

// 消防能力
CREATE (c:Capability {
    code: 'FIRE_SUPPRESSION',
    name: '火灾扑救',
    category: 'fire',
    description: '扑灭各类火灾',
    equipment_required: ['消防车', '水带', '灭火器', '消防服']
});

CREATE (c:Capability {
    code: 'FIRE_SEARCH_RESCUE',
    name: '火场搜救',
    category: 'fire',
    description: '在火灾现场搜救被困人员',
    equipment_required: ['空气呼吸器', '热成像仪', '破拆工具']
});

// 危化品处置能力
CREATE (c:Capability {
    code: 'HAZMAT_DETECTION',
    name: '危化品检测',
    category: 'hazmat',
    description: '检测识别危险化学品种类和浓度',
    equipment_required: ['气体检测仪', '化学试剂', '采样设备']
});

CREATE (c:Capability {
    code: 'HAZMAT_CONTAINMENT',
    name: '危化品围堵',
    category: 'hazmat',
    description: '对泄漏危化品进行围堵控制',
    equipment_required: ['围堵材料', '吸附材料', '防护服', '洗消设备']
});

CREATE (c:Capability {
    code: 'DECONTAMINATION',
    name: '洗消去污',
    category: 'hazmat',
    description: '对人员和设备进行洗消去污',
    equipment_required: ['洗消车', '洗消剂', '防护服']
});

// 疏散能力
CREATE (c:Capability {
    code: 'EVACUATION_COORDINATION',
    name: '疏散协调',
    category: 'evacuation',
    description: '组织协调人员安全疏散',
    equipment_required: ['扩音设备', '警戒带', '指示牌', '通信设备']
});

CREATE (c:Capability {
    code: 'SHELTER_MANAGEMENT',
    name: '安置点管理',
    category: 'evacuation',
    description: '管理临时安置点',
    equipment_required: ['帐篷', '床铺', '生活物资', '登记系统']
});

// 通信保障能力
CREATE (c:Capability {
    code: 'EMERGENCY_COMMUNICATION',
    name: '应急通信',
    category: 'communication',
    description: '建立应急通信网络',
    equipment_required: ['卫星电话', '对讲机', '移动基站', '无人机中继']
});

// 工程抢险能力
CREATE (c:Capability {
    code: 'ROAD_CLEARANCE',
    name: '道路抢通',
    category: 'engineering',
    description: '清除道路障碍恢复通行',
    equipment_required: ['挖掘机', '装载机', '破碎锤', '吊车']
});

CREATE (c:Capability {
    code: 'STRUCTURAL_ASSESSMENT',
    name: '结构评估',
    category: 'engineering',
    description: '评估建筑结构安全性',
    equipment_required: ['检测仪器', '测量设备', '标识材料']
});

// ============================================================================
// 3. 创建任务类型节点 (TaskType)
// ============================================================================

CREATE (t:TaskType {
    code: 'SEARCH_RESCUE',
    name: '搜索救援',
    category: 'rescue',
    priority_default: 'critical',
    golden_hour: 72,
    description: '搜索并营救被困人员'
});

CREATE (t:TaskType {
    code: 'MEDICAL_EMERGENCY',
    name: '医疗急救',
    category: 'medical',
    priority_default: 'critical',
    golden_hour: 1,
    description: '对伤员进行紧急医疗救治'
});

CREATE (t:TaskType {
    code: 'FIRE_SUPPRESSION',
    name: '火灾扑救',
    category: 'fire',
    priority_default: 'critical',
    golden_hour: 0.5,
    description: '扑灭火灾控制火势蔓延'
});

CREATE (t:TaskType {
    code: 'HAZMAT_RESPONSE',
    name: '危化品处置',
    category: 'hazmat',
    priority_default: 'critical',
    golden_hour: 2,
    description: '处置危险化学品泄漏'
});

CREATE (t:TaskType {
    code: 'EVACUATION',
    name: '人员疏散',
    category: 'evacuation',
    priority_default: 'high',
    golden_hour: 4,
    description: '组织危险区域人员疏散'
});

CREATE (t:TaskType {
    code: 'ROAD_CLEARANCE',
    name: '道路抢通',
    category: 'engineering',
    priority_default: 'high',
    golden_hour: 12,
    description: '清除道路障碍恢复交通'
});

CREATE (t:TaskType {
    code: 'STRUCTURAL_ASSESSMENT',
    name: '建筑评估',
    category: 'engineering',
    priority_default: 'medium',
    golden_hour: 24,
    description: '评估建筑结构安全性'
});

CREATE (t:TaskType {
    code: 'SHELTER_SETUP',
    name: '安置点设立',
    category: 'evacuation',
    priority_default: 'high',
    golden_hour: 6,
    description: '设立临时安置点'
});

CREATE (t:TaskType {
    code: 'COMMUNICATION_RESTORE',
    name: '通信恢复',
    category: 'infrastructure',
    priority_default: 'high',
    golden_hour: 4,
    description: '恢复应急通信能力'
});

// ============================================================================
// 4. 创建资源类型节点 (ResourceType)
// ============================================================================

CREATE (rt:ResourceType {
    code: 'RESCUE_TEAM',
    name: '救援队',
    category: 'team',
    typical_size: 12,
    description: '专业救援队伍'
});

CREATE (rt:ResourceType {
    code: 'MEDICAL_TEAM',
    name: '医疗队',
    category: 'team',
    typical_size: 8,
    description: '医疗救护队伍'
});

CREATE (rt:ResourceType {
    code: 'FIRE_TEAM',
    name: '消防队',
    category: 'team',
    typical_size: 10,
    description: '消防救援队伍'
});

CREATE (rt:ResourceType {
    code: 'HAZMAT_TEAM',
    name: '危化品处置队',
    category: 'team',
    typical_size: 8,
    description: '危险化学品处置队伍'
});

CREATE (rt:ResourceType {
    code: 'ENGINEERING_TEAM',
    name: '工程抢险队',
    category: 'team',
    typical_size: 15,
    description: '工程抢险队伍'
});

CREATE (rt:ResourceType {
    code: 'EVACUATION_TEAM',
    name: '疏散引导队',
    category: 'team',
    typical_size: 6,
    description: '人员疏散引导队伍'
});

CREATE (rt:ResourceType {
    code: 'AMBULANCE',
    name: '救护车',
    category: 'vehicle',
    description: '医疗转运车辆'
});

CREATE (rt:ResourceType {
    code: 'FIRE_ENGINE',
    name: '消防车',
    category: 'vehicle',
    description: '消防救援车辆'
});

CREATE (rt:ResourceType {
    code: 'EXCAVATOR',
    name: '挖掘机',
    category: 'equipment',
    description: '工程机械设备'
});

// ============================================================================
// 5. 创建TRR触发规则节点 (TRRRule)
// ============================================================================

// 地震-建筑倒塌搜救规则
CREATE (r:TRRRule {
    rule_id: 'TRR-EQ-001',
    name: '地震建筑搜救规则',
    description: '地震导致建筑倒塌且有被困人员时触发搜救任务',
    disaster_type: 'earthquake',
    priority: 'critical',
    weight: 0.95,
    trigger_conditions: [
        'has_building_collapse = true',
        'has_trapped_persons = true'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 地震-次生火灾规则
CREATE (r:TRRRule {
    rule_id: 'TRR-EQ-002',
    name: '地震次生火灾规则',
    description: '地震引发火灾时触发消防任务',
    disaster_type: 'earthquake',
    priority: 'critical',
    weight: 0.90,
    trigger_conditions: [
        'has_secondary_fire = true'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 地震-危化品泄漏规则
CREATE (r:TRRRule {
    rule_id: 'TRR-EQ-003',
    name: '地震危化品泄漏规则',
    description: '地震导致危化品泄漏时触发应急处置',
    disaster_type: 'earthquake',
    priority: 'critical',
    weight: 0.92,
    trigger_conditions: [
        'has_hazmat_leak = true'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 地震-人员伤亡规则
CREATE (r:TRRRule {
    rule_id: 'TRR-EQ-004',
    name: '地震伤员救治规则',
    description: '地震造成人员伤亡时触发医疗救治',
    disaster_type: 'earthquake',
    priority: 'critical',
    weight: 0.88,
    trigger_conditions: [
        'estimated_casualties > 0'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 地震-人员疏散规则
CREATE (r:TRRRule {
    rule_id: 'TRR-EQ-005',
    name: '地震人员疏散规则',
    description: '地震影响区域需要疏散时触发疏散任务',
    disaster_type: 'earthquake',
    priority: 'high',
    weight: 0.85,
    trigger_conditions: [
        'affected_population > 100',
        'building_damage_level >= medium'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 地震-道路抢通规则
CREATE (r:TRRRule {
    rule_id: 'TRR-EQ-006',
    name: '地震道路抢通规则',
    description: '地震导致道路中断时触发抢通任务',
    disaster_type: 'earthquake',
    priority: 'high',
    weight: 0.80,
    trigger_conditions: [
        'has_road_damage = true'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 次生灾害-余震应对规则
CREATE (r:TRRRule {
    rule_id: 'TRR-SD-001',
    name: '余震应对规则',
    description: '发生余震时调整救援策略',
    disaster_type: 'aftershock',
    priority: 'high',
    weight: 0.75,
    trigger_conditions: [
        'aftershock_magnitude >= 4.0'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 次生灾害-滑坡泥石流规则
CREATE (r:TRRRule {
    rule_id: 'TRR-SD-002',
    name: '滑坡泥石流规则',
    description: '发生滑坡泥石流时触发搜救和疏散',
    disaster_type: 'landslide',
    priority: 'critical',
    weight: 0.90,
    trigger_conditions: [
        'has_landslide = true'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// 次生灾害-堰塞湖规则
CREATE (r:TRRRule {
    rule_id: 'TRR-SD-003',
    name: '堰塞湖规则',
    description: '形成堰塞湖时触发疏散和监测',
    disaster_type: 'dammed_lake',
    priority: 'critical',
    weight: 0.93,
    trigger_conditions: [
        'has_dammed_lake = true'
    ],
    trigger_logic: 'AND',
    is_active: true
});

// ============================================================================
// 6. 创建规则-任务关系 (TRIGGERS)
// ============================================================================

// TRR-EQ-001 触发搜救和医疗任务
MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (t:TaskType {code: 'SEARCH_RESCUE'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (t:TaskType {code: 'MEDICAL_EMERGENCY'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 2}]->(t);

// TRR-EQ-002 触发消防任务
MATCH (r:TRRRule {rule_id: 'TRR-EQ-002'}), (t:TaskType {code: 'FIRE_SUPPRESSION'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t);

// TRR-EQ-003 触发危化品处置和疏散
MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (t:TaskType {code: 'HAZMAT_RESPONSE'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (t:TaskType {code: 'EVACUATION'})
CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 2}]->(t);

// TRR-EQ-004 触发医疗任务
MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (t:TaskType {code: 'MEDICAL_EMERGENCY'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t);

// TRR-EQ-005 触发疏散和安置任务
MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (t:TaskType {code: 'EVACUATION'})
CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 1}]->(t);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (t:TaskType {code: 'SHELTER_SETUP'})
CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 2}]->(t);

// TRR-EQ-006 触发道路抢通
MATCH (r:TRRRule {rule_id: 'TRR-EQ-006'}), (t:TaskType {code: 'ROAD_CLEARANCE'})
CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 1}]->(t);

// TRR-SD-002 触发搜救和疏散
MATCH (r:TRRRule {rule_id: 'TRR-SD-002'}), (t:TaskType {code: 'SEARCH_RESCUE'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t);

MATCH (r:TRRRule {rule_id: 'TRR-SD-002'}), (t:TaskType {code: 'EVACUATION'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 2}]->(t);

// TRR-SD-003 触发疏散
MATCH (r:TRRRule {rule_id: 'TRR-SD-003'}), (t:TaskType {code: 'EVACUATION'})
CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t);

// ============================================================================
// 7. 创建规则-能力关系 (REQUIRES_CAPABILITY)
// ============================================================================

// TRR-EQ-001 需要的能力
MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (c:Capability {code: 'LIFE_DETECTION'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (c:Capability {code: 'STRUCTURAL_RESCUE'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

// TRR-EQ-002 需要的能力
MATCH (r:TRRRule {rule_id: 'TRR-EQ-002'}), (c:Capability {code: 'FIRE_SUPPRESSION'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-002'}), (c:Capability {code: 'FIRE_SEARCH_RESCUE'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

// TRR-EQ-003 需要的能力
MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (c:Capability {code: 'HAZMAT_DETECTION'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (c:Capability {code: 'HAZMAT_CONTAINMENT'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (c:Capability {code: 'EVACUATION_COORDINATION'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

// TRR-EQ-004 需要的能力
MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (c:Capability {code: 'EMERGENCY_TREATMENT'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (c:Capability {code: 'PATIENT_TRANSPORT'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

// TRR-EQ-005 需要的能力
MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (c:Capability {code: 'EVACUATION_COORDINATION'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (c:Capability {code: 'SHELTER_MANAGEMENT'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

// TRR-EQ-006 需要的能力
MATCH (r:TRRRule {rule_id: 'TRR-EQ-006'}), (c:Capability {code: 'ROAD_CLEARANCE'})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c);

// ============================================================================
// 8. 创建任务-能力关系 (REQUIRES)
// ============================================================================

MATCH (t:TaskType {code: 'SEARCH_RESCUE'}), (c:Capability {code: 'LIFE_DETECTION'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'SEARCH_RESCUE'}), (c:Capability {code: 'STRUCTURAL_RESCUE'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'MEDICAL_EMERGENCY'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'MEDICAL_EMERGENCY'}), (c:Capability {code: 'EMERGENCY_TREATMENT'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'FIRE_SUPPRESSION'}), (c:Capability {code: 'FIRE_SUPPRESSION'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'HAZMAT_RESPONSE'}), (c:Capability {code: 'HAZMAT_DETECTION'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'HAZMAT_RESPONSE'}), (c:Capability {code: 'HAZMAT_CONTAINMENT'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'EVACUATION'}), (c:Capability {code: 'EVACUATION_COORDINATION'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

MATCH (t:TaskType {code: 'ROAD_CLEARANCE'}), (c:Capability {code: 'ROAD_CLEARANCE'})
CREATE (t)-[:REQUIRES {is_critical: true}]->(c);

// ============================================================================
// 9. 创建能力-资源关系 (PROVIDED_BY)
// ============================================================================

MATCH (c:Capability {code: 'LIFE_DETECTION'}), (rt:ResourceType {code: 'RESCUE_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'STRUCTURAL_RESCUE'}), (rt:ResourceType {code: 'RESCUE_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'MEDICAL_TRIAGE'}), (rt:ResourceType {code: 'MEDICAL_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'EMERGENCY_TREATMENT'}), (rt:ResourceType {code: 'MEDICAL_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'PATIENT_TRANSPORT'}), (rt:ResourceType {code: 'AMBULANCE'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'FIRE_SUPPRESSION'}), (rt:ResourceType {code: 'FIRE_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'FIRE_SEARCH_RESCUE'}), (rt:ResourceType {code: 'FIRE_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'HAZMAT_DETECTION'}), (rt:ResourceType {code: 'HAZMAT_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'HAZMAT_CONTAINMENT'}), (rt:ResourceType {code: 'HAZMAT_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'EVACUATION_COORDINATION'}), (rt:ResourceType {code: 'EVACUATION_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

MATCH (c:Capability {code: 'ROAD_CLEARANCE'}), (rt:ResourceType {code: 'ENGINEERING_TEAM'})
CREATE (c)-[:PROVIDED_BY]->(rt);

// ============================================================================
// 10. 创建任务依赖关系 (DEPENDS_ON)
// ============================================================================

// 医疗急救依赖搜救（先救出才能治疗）
MATCH (t1:TaskType {code: 'MEDICAL_EMERGENCY'}), (t2:TaskType {code: 'SEARCH_RESCUE'})
CREATE (t1)-[:DEPENDS_ON {is_strict: false, description: '救出伤员后进行医疗救治'}]->(t2);

// 安置点设立依赖疏散（先疏散才需要安置）
MATCH (t1:TaskType {code: 'SHELTER_SETUP'}), (t2:TaskType {code: 'EVACUATION'})
CREATE (t1)-[:DEPENDS_ON {is_strict: true, description: '疏散人员后设立安置点'}]->(t2);

// 搜救可能依赖道路抢通（如果道路中断）
MATCH (t1:TaskType {code: 'SEARCH_RESCUE'}), (t2:TaskType {code: 'ROAD_CLEARANCE'})
CREATE (t1)-[:DEPENDS_ON {is_strict: false, description: '道路抢通后便于救援队进入'}]->(t2);

// ============================================================================
// 11. 验证查询
// ============================================================================

// 查询所有TRR规则及其触发的任务
// MATCH (r:TRRRule)-[:TRIGGERS]->(t:TaskType)
// RETURN r.rule_id, r.name, r.disaster_type, collect(t.name) as tasks
// ORDER BY r.weight DESC;

// 查询地震规则及其需要的能力
// MATCH (r:TRRRule {disaster_type: 'earthquake'})-[:REQUIRES_CAPABILITY]->(c:Capability)
// RETURN r.rule_id, r.name, collect(c.name) as capabilities;
