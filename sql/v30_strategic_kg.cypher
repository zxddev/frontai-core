// =============================================================================
// v30_strategic_kg.cypher - 战略层知识图谱扩展
// 新增节点: TaskDomain, DisasterPhase, RescueModule
// 新增关系: BELONGS_TO, PRIORITY_ORDER, PROVIDES
// 扩展属性: TRRRule.domain, TRRRule.subtask_code
// =============================================================================

// -----------------------------------------------------------------------------
// 1. TaskDomain 节点 - 任务域定义 (5个)
// -----------------------------------------------------------------------------

CREATE (td:TaskDomain {
    domain_id: 'life_rescue',
    name: '生命救护',
    description: '搜救被困人员、现场急救、伤员后送等生命救护任务',
    priority_base: 1
});

CREATE (td:TaskDomain {
    domain_id: 'evacuation',
    name: '群众转移',
    description: '危险区域人员紧急转移、避险安置等任务',
    priority_base: 2
});

CREATE (td:TaskDomain {
    domain_id: 'engineering',
    name: '工程抢险',
    description: '道路抢通、危房排险、堰塞湖处置等工程类任务',
    priority_base: 3
});

CREATE (td:TaskDomain {
    domain_id: 'logistics',
    name: '后勤保障',
    description: '物资投送、通信恢复、医疗保障等后勤支援任务',
    priority_base: 4
});

CREATE (td:TaskDomain {
    domain_id: 'hazard_control',
    name: '次生灾害防控',
    description: '危化品泄漏处置、火灾扑救、疫情防控等次生灾害应对',
    priority_base: 5
});

// -----------------------------------------------------------------------------
// 2. DisasterPhase 节点 - 灾害响应阶段 (4个)
// -----------------------------------------------------------------------------

CREATE (dp:DisasterPhase {
    phase_id: 'initial',
    name: '初期响应',
    description: '灾害发生后0-2小时，快速响应阶段',
    hours_start: 0,
    hours_end: 2
});

CREATE (dp:DisasterPhase {
    phase_id: 'golden',
    name: '黄金救援期',
    description: '灾害发生后2-24小时，生命救援黄金期',
    hours_start: 2,
    hours_end: 24
});

CREATE (dp:DisasterPhase {
    phase_id: 'intensive',
    name: '攻坚作战期',
    description: '灾害发生后24-72小时，持续搜救攻坚阶段',
    hours_start: 24,
    hours_end: 72
});

CREATE (dp:DisasterPhase {
    phase_id: 'recovery',
    name: '恢复重建期',
    description: '灾害发生后72小时以上，转向恢复重建',
    hours_start: 72,
    hours_end: -1
});

// -----------------------------------------------------------------------------
// 3. PRIORITY_ORDER 关系 - 阶段→任务域优先级 (20条)
// -----------------------------------------------------------------------------

// 初期响应阶段 (0-2h): 快速评估，生命优先
MATCH (p:DisasterPhase {phase_id: 'initial'}), (d:TaskDomain {domain_id: 'life_rescue'})
CREATE (p)-[:PRIORITY_ORDER {rank: 1}]->(d);
MATCH (p:DisasterPhase {phase_id: 'initial'}), (d:TaskDomain {domain_id: 'engineering'})
CREATE (p)-[:PRIORITY_ORDER {rank: 2}]->(d);
MATCH (p:DisasterPhase {phase_id: 'initial'}), (d:TaskDomain {domain_id: 'evacuation'})
CREATE (p)-[:PRIORITY_ORDER {rank: 3}]->(d);
MATCH (p:DisasterPhase {phase_id: 'initial'}), (d:TaskDomain {domain_id: 'logistics'})
CREATE (p)-[:PRIORITY_ORDER {rank: 4}]->(d);
MATCH (p:DisasterPhase {phase_id: 'initial'}), (d:TaskDomain {domain_id: 'hazard_control'})
CREATE (p)-[:PRIORITY_ORDER {rank: 5}]->(d);

// 黄金救援期 (2-24h): 全力搜救
MATCH (p:DisasterPhase {phase_id: 'golden'}), (d:TaskDomain {domain_id: 'life_rescue'})
CREATE (p)-[:PRIORITY_ORDER {rank: 1}]->(d);
MATCH (p:DisasterPhase {phase_id: 'golden'}), (d:TaskDomain {domain_id: 'evacuation'})
CREATE (p)-[:PRIORITY_ORDER {rank: 2}]->(d);
MATCH (p:DisasterPhase {phase_id: 'golden'}), (d:TaskDomain {domain_id: 'engineering'})
CREATE (p)-[:PRIORITY_ORDER {rank: 3}]->(d);
MATCH (p:DisasterPhase {phase_id: 'golden'}), (d:TaskDomain {domain_id: 'logistics'})
CREATE (p)-[:PRIORITY_ORDER {rank: 4}]->(d);
MATCH (p:DisasterPhase {phase_id: 'golden'}), (d:TaskDomain {domain_id: 'hazard_control'})
CREATE (p)-[:PRIORITY_ORDER {rank: 5}]->(d);

// 攻坚作战期 (24-72h): 持续搜救+工程抢险
MATCH (p:DisasterPhase {phase_id: 'intensive'}), (d:TaskDomain {domain_id: 'life_rescue'})
CREATE (p)-[:PRIORITY_ORDER {rank: 1}]->(d);
MATCH (p:DisasterPhase {phase_id: 'intensive'}), (d:TaskDomain {domain_id: 'logistics'})
CREATE (p)-[:PRIORITY_ORDER {rank: 2}]->(d);
MATCH (p:DisasterPhase {phase_id: 'intensive'}), (d:TaskDomain {domain_id: 'hazard_control'})
CREATE (p)-[:PRIORITY_ORDER {rank: 3}]->(d);
MATCH (p:DisasterPhase {phase_id: 'intensive'}), (d:TaskDomain {domain_id: 'engineering'})
CREATE (p)-[:PRIORITY_ORDER {rank: 4}]->(d);
MATCH (p:DisasterPhase {phase_id: 'intensive'}), (d:TaskDomain {domain_id: 'evacuation'})
CREATE (p)-[:PRIORITY_ORDER {rank: 5}]->(d);

// 恢复重建期 (72h+): 后勤保障为主
MATCH (p:DisasterPhase {phase_id: 'recovery'}), (d:TaskDomain {domain_id: 'logistics'})
CREATE (p)-[:PRIORITY_ORDER {rank: 1}]->(d);
MATCH (p:DisasterPhase {phase_id: 'recovery'}), (d:TaskDomain {domain_id: 'engineering'})
CREATE (p)-[:PRIORITY_ORDER {rank: 2}]->(d);
MATCH (p:DisasterPhase {phase_id: 'recovery'}), (d:TaskDomain {domain_id: 'hazard_control'})
CREATE (p)-[:PRIORITY_ORDER {rank: 3}]->(d);
MATCH (p:DisasterPhase {phase_id: 'recovery'}), (d:TaskDomain {domain_id: 'life_rescue'})
CREATE (p)-[:PRIORITY_ORDER {rank: 4}]->(d);
MATCH (p:DisasterPhase {phase_id: 'recovery'}), (d:TaskDomain {domain_id: 'evacuation'})
CREATE (p)-[:PRIORITY_ORDER {rank: 5}]->(d);

// -----------------------------------------------------------------------------
// 4. RescueModule 节点 - 预编组救援模块 (~10个)
// -----------------------------------------------------------------------------

CREATE (rm:RescueModule {
    module_id: 'ruins_search',
    name: '废墟搜救模块',
    description: '建筑物废墟搜救专业模块',
    personnel: 15,
    dogs: 4,
    vehicles: 3
});

CREATE (rm:RescueModule {
    module_id: 'heavy_rescue',
    name: '重型破拆模块',
    description: '重型机械破拆作业模块',
    personnel: 12,
    dogs: 0,
    vehicles: 5
});

CREATE (rm:RescueModule {
    module_id: 'medical_forward',
    name: '医疗前突模块',
    description: '现场急救和伤员后送模块',
    personnel: 8,
    dogs: 0,
    vehicles: 2
});

CREATE (rm:RescueModule {
    module_id: 'water_rescue',
    name: '水域救援模块',
    description: '洪水、内涝水域救援模块',
    personnel: 10,
    dogs: 0,
    vehicles: 4
});

CREATE (rm:RescueModule {
    module_id: 'hazmat_response',
    name: '危化品处置模块',
    description: '危险化学品泄漏处置模块',
    personnel: 12,
    dogs: 0,
    vehicles: 4
});

CREATE (rm:RescueModule {
    module_id: 'evacuation_support',
    name: '疏散转移模块',
    description: '群众疏散转移保障模块',
    personnel: 20,
    dogs: 0,
    vehicles: 6
});

CREATE (rm:RescueModule {
    module_id: 'road_clearing',
    name: '道路抢通模块',
    description: '道路清障和抢通作业模块',
    personnel: 15,
    dogs: 0,
    vehicles: 8
});

CREATE (rm:RescueModule {
    module_id: 'communication_restore',
    name: '通信恢复模块',
    description: '应急通信保障和恢复模块',
    personnel: 6,
    dogs: 0,
    vehicles: 2
});

CREATE (rm:RescueModule {
    module_id: 'logistics_support',
    name: '后勤保障模块',
    description: '物资投送和后勤支援模块',
    personnel: 10,
    dogs: 0,
    vehicles: 5
});

CREATE (rm:RescueModule {
    module_id: 'fire_suppression',
    name: '火灾扑救模块',
    description: '建筑火灾和野外火灾扑救模块',
    personnel: 15,
    dogs: 0,
    vehicles: 4
});

// -----------------------------------------------------------------------------
// 5. PROVIDES 关系 - 模块→能力 (每个模块提供多个能力)
// -----------------------------------------------------------------------------

// 废墟搜救模块提供的能力
MATCH (m:RescueModule {module_id: 'ruins_search'}), (c:Capability {code: 'LIFE_DETECTION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 4}]->(c);
MATCH (m:RescueModule {module_id: 'ruins_search'}), (c:Capability {code: 'SEARCH_CANINE'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 4}]->(c);
MATCH (m:RescueModule {module_id: 'ruins_search'}), (c:Capability {code: 'RESCUE_STRUCTURAL'})
CREATE (m)-[:PROVIDES {level: 'intermediate', quantity: 10}]->(c);

// 重型破拆模块提供的能力
MATCH (m:RescueModule {module_id: 'heavy_rescue'}), (c:Capability {code: 'HEAVY_LIFTING'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 3}]->(c);
MATCH (m:RescueModule {module_id: 'heavy_rescue'}), (c:Capability {code: 'DEMOLITION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 2}]->(c);
MATCH (m:RescueModule {module_id: 'heavy_rescue'}), (c:Capability {code: 'EXCAVATION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 3}]->(c);

// 医疗前突模块提供的能力
MATCH (m:RescueModule {module_id: 'medical_forward'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 2}]->(c);
MATCH (m:RescueModule {module_id: 'medical_forward'}), (c:Capability {code: 'MEDICAL_STABILIZATION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 4}]->(c);
MATCH (m:RescueModule {module_id: 'medical_forward'}), (c:Capability {code: 'MEDICAL_EVACUATION'})
CREATE (m)-[:PROVIDES {level: 'intermediate', quantity: 2}]->(c);

// 水域救援模块提供的能力
MATCH (m:RescueModule {module_id: 'water_rescue'}), (c:Capability {code: 'WATER_RESCUE'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 8}]->(c);
MATCH (m:RescueModule {module_id: 'water_rescue'}), (c:Capability {code: 'BOAT_OPERATION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 4}]->(c);

// 危化品处置模块提供的能力
MATCH (m:RescueModule {module_id: 'hazmat_response'}), (c:Capability {code: 'HAZMAT_DETECTION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 3}]->(c);
MATCH (m:RescueModule {module_id: 'hazmat_response'}), (c:Capability {code: 'HAZMAT_CONTAINMENT'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 4}]->(c);
MATCH (m:RescueModule {module_id: 'hazmat_response'}), (c:Capability {code: 'DECONTAMINATION'})
CREATE (m)-[:PROVIDES {level: 'intermediate', quantity: 6}]->(c);

// 疏散转移模块提供的能力
MATCH (m:RescueModule {module_id: 'evacuation_support'}), (c:Capability {code: 'CROWD_MANAGEMENT'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 10}]->(c);
MATCH (m:RescueModule {module_id: 'evacuation_support'}), (c:Capability {code: 'TRANSPORT_PERSONNEL'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 6}]->(c);

// 道路抢通模块提供的能力
MATCH (m:RescueModule {module_id: 'road_clearing'}), (c:Capability {code: 'ROAD_CLEARING'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 5}]->(c);
MATCH (m:RescueModule {module_id: 'road_clearing'}), (c:Capability {code: 'HEAVY_LIFTING'})
CREATE (m)-[:PROVIDES {level: 'intermediate', quantity: 3}]->(c);

// 通信恢复模块提供的能力
MATCH (m:RescueModule {module_id: 'communication_restore'}), (c:Capability {code: 'COMMUNICATION_EMERGENCY'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 4}]->(c);

// 后勤保障模块提供的能力
MATCH (m:RescueModule {module_id: 'logistics_support'}), (c:Capability {code: 'LOGISTICS_SUPPLY'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 5}]->(c);
MATCH (m:RescueModule {module_id: 'logistics_support'}), (c:Capability {code: 'TRANSPORT_CARGO'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 5}]->(c);

// 火灾扑救模块提供的能力
MATCH (m:RescueModule {module_id: 'fire_suppression'}), (c:Capability {code: 'FIRE_SUPPRESSION'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 10}]->(c);
MATCH (m:RescueModule {module_id: 'fire_suppression'}), (c:Capability {code: 'RESCUE_FIRE'})
CREATE (m)-[:PROVIDES {level: 'advanced', quantity: 6}]->(c);

// -----------------------------------------------------------------------------
// 6. 扩展 TRRRule 属性 - 添加 domain 和 subtask_code
// -----------------------------------------------------------------------------

// 生命救护域 (life_rescue) - 人员搜救相关规则
MATCH (r:TRRRule) WHERE r.rule_id IN [
    'TRR-EM-001', 'TRR-EM-002', 'TRR-EM-003', 'TRR-EM-004', 'TRR-EM-005',
    'TRR-EM-040', 'TRR-EM-041', 'TRR-EM-042'
]
SET r.domain = 'life_rescue';

// 群众转移域 (evacuation) - 疏散转移相关规则
MATCH (r:TRRRule) WHERE r.rule_id IN [
    'TRR-EM-006', 'TRR-EM-007', 'TRR-EM-043', 'TRR-EM-044', 'TRR-EM-050',
    'TRR-EM-051', 'TRR-EM-052'
]
SET r.domain = 'evacuation';

// 工程抢险域 (engineering) - 道路抢通、排险相关规则
MATCH (r:TRRRule) WHERE r.rule_id IN [
    'TRR-EM-008', 'TRR-EM-009', 'TRR-EM-045', 'TRR-EM-046', 'TRR-EM-053',
    'TRR-EM-054', 'TRR-EM-055'
]
SET r.domain = 'engineering';

// 后勤保障域 (logistics) - 物资保障、通信恢复相关规则
MATCH (r:TRRRule) WHERE r.rule_id IN [
    'TRR-EM-030', 'TRR-EM-031', 'TRR-EM-032', 'TRR-EM-033', 'TRR-EM-034',
    'TRR-EM-035', 'TRR-EM-056'
]
SET r.domain = 'logistics';

// 次生灾害防控域 (hazard_control) - 火灾、危化品相关规则
MATCH (r:TRRRule) WHERE r.rule_id IN [
    'TRR-EM-010', 'TRR-EM-011', 'TRR-EM-012', 'TRR-EM-020', 'TRR-EM-021',
    'TRR-EM-022', 'TRR-EM-023', 'TRR-EM-024', 'TRR-EM-025'
]
SET r.domain = 'hazard_control';

// 为未分配 domain 的 TRRRule 设置默认值
MATCH (r:TRRRule) WHERE r.domain IS NULL
SET r.domain = 'life_rescue';

// -----------------------------------------------------------------------------
// 7. BELONGS_TO 关系 - TRRRule → TaskDomain
// -----------------------------------------------------------------------------

MATCH (r:TRRRule), (d:TaskDomain)
WHERE r.domain = d.domain_id
CREATE (r)-[:BELONGS_TO]->(d);

// -----------------------------------------------------------------------------
// 8. 创建索引提升查询性能
// -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS FOR (td:TaskDomain) ON (td.domain_id);
CREATE INDEX IF NOT EXISTS FOR (dp:DisasterPhase) ON (dp.phase_id);
CREATE INDEX IF NOT EXISTS FOR (rm:RescueModule) ON (rm.module_id);
CREATE INDEX IF NOT EXISTS FOR (r:TRRRule) ON (r.domain);
