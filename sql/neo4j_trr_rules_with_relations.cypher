// ============================================================================
// neo4j_trr_rules_with_relations.cypher
// 创建TRR-EM规则节点并建立TRIGGERS和REQUIRES_CAPABILITY关系
// 总规则数: 56条
// ============================================================================

// 先删除现有的TRR-EM规则（保留TRR-EQ和TRR-SD规则）
MATCH (r:TRRRule) WHERE r.rule_id STARTS WITH 'TRR-EM'
DETACH DELETE r;

// === TRR-EM-001: 地震人员搜救规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-001",
  name: "地震人员搜救规则",
  description: "地震导致建筑倒塌且有被困人员时触发搜救任务",
  disaster_type: "earthquake",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (c:Capability {code: "SEARCH_LIFE_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (c:Capability {code: "RESCUE_STRUCTURAL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (c:Capability {code: "RESCUE_CONFINED"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (c:Capability {code: "MEDICAL_TRIAGE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-001"}), (c:Capability {code: "MEDICAL_FIRST_AID"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-002: 地震重型破拆规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-002",
  name: "地震重型破拆规则",
  description: "大面积建筑倒塌需要重型机械支援",
  disaster_type: "earthquake",
  priority: "high",
  weight: 0.85,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-002"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-002"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-002"}), (c:Capability {code: "ENG_HEAVY_MACHINE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-002"}), (c:Capability {code: "ENG_DEMOLITION"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-003: 地震次生灾害监测规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-003",
  name: "地震次生灾害监测规则",
  description: "地震后启动次生灾害监测",
  disaster_type: "earthquake",
  priority: "high",
  weight: 0.8,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-003"}), (t:TaskType {code: "STRUCTURAL_ASSESSMENT"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-003"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-003"}), (c:Capability {code: "GEO_MONITOR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-003"}), (c:Capability {code: "UAV_RECONNAISSANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-004: 学校地震救援规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-004",
  name: "学校地震救援规则",
  description: "学校建筑倒塌时启动针对性搜救",
  disaster_type: "earthquake",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-004"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-004"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-004"}), (c:Capability {code: "SEARCH_LIFE_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-004"}), (c:Capability {code: "RESCUE_CONFINED"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-004"}), (c:Capability {code: "MEDICAL_PEDIATRIC"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-004"}), (c:Capability {code: "PSYCH_CRISIS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-005: 医院地震救援规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-005",
  name: "医院地震救援规则",
  description: "医院建筑受损时启动医疗系统应急",
  disaster_type: "earthquake",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-005"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-005"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-005"}), (c:Capability {code: "MEDICAL_TRANSPORT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-005"}), (c:Capability {code: "MEDICAL_ICU"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-005"}), (c:Capability {code: "POWER_EMERGENCY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-006: 地震大规模疏散规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-006",
  name: "地震大规模疏散规则",
  description: "强烈地震后启动大规模人员疏散",
  disaster_type: "earthquake",
  priority: "high",
  weight: 0.85,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-006"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-006"}), (t:TaskType {code: "SHELTER_SETUP"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-006"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-006"}), (c:Capability {code: "SHELTER_SETUP"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-006"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-007: 地震供水保障规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-007",
  name: "地震供水保障规则",
  description: "地震导致供水中断时启动应急供水",
  disaster_type: "earthquake",
  priority: "high",
  weight: 0.75,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-007"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-007"}), (c:Capability {code: "WATER_PURIFY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-007"}), (c:Capability {code: "WATER_TRANSPORT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-007"}), (c:Capability {code: "PIPE_REPAIR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "medium"}]->(c);

// === TRR-EM-008: 地震电力抢修规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-008",
  name: "地震电力抢修规则",
  description: "地震导致大面积停电时启动电力抢修",
  disaster_type: "earthquake",
  priority: "high",
  weight: 0.8,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-008"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-008"}), (c:Capability {code: "POWER_LINE_REPAIR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-008"}), (c:Capability {code: "POWER_EMERGENCY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-009: 地震燃气泄漏处置规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-009",
  name: "地震燃气泄漏处置规则",
  description: "地震导致燃气管道破裂时启动处置",
  disaster_type: "earthquake",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-009"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-009"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-009"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-009"}), (c:Capability {code: "GAS_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-009"}), (c:Capability {code: "GAS_SHUTOFF"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-009"}), (c:Capability {code: "FIRE_STANDBY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-010: 建筑火灾扑救规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-010",
  name: "建筑火灾扑救规则",
  description: "建筑火灾时启动消防扑救",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-010"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-010"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-010"}), (c:Capability {code: "FIRE_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-010"}), (c:Capability {code: "FIRE_SUPPLY_WATER"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-010"}), (c:Capability {code: "RESCUE_HIGH_ANGLE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-011: 高层建筑火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-011",
  name: "高层建筑火灾规则",
  description: "高层建筑火灾需要特种装备",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.9,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-011"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-011"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-011"}), (c:Capability {code: "RESCUE_HIGH_ANGLE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-011"}), (c:Capability {code: "FIRE_AERIAL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-011"}), (c:Capability {code: "SMOKE_EXHAUST"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-012: 森林火灾扑救规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-012",
  name: "森林火灾扑救规则",
  description: "森林火灾启动专业扑救",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-012"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-012"}), (c:Capability {code: "FIRE_FOREST"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-012"}), (c:Capability {code: "UAV_RECONNAISSANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-012"}), (c:Capability {code: "FIREBREAK_BUILD"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-013: 工厂火灾处置规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-013",
  name: "工厂火灾处置规则",
  description: "工厂火灾需要考虑危险品",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-013"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-013"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-013"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-013"}), (c:Capability {code: "FIRE_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-013"}), (c:Capability {code: "HAZMAT_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-013"}), (c:Capability {code: "FOAM_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-014: 地下空间火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-014",
  name: "地下空间火灾规则",
  description: "地下商场/车库火灾特殊处置",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-014"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-014"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-014"}), (c:Capability {code: "FIRE_UNDERGROUND"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-014"}), (c:Capability {code: "SMOKE_EXHAUST"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-014"}), (c:Capability {code: "BREATHING_APPARATUS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-015: 加油站火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-015",
  name: "加油站火灾规则",
  description: "加油站/油库火灾处置",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-015"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-015"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-015"}), (c:Capability {code: "FOAM_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-015"}), (c:Capability {code: "COOLING_SPRAY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-015"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-016: 电气火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-016",
  name: "电气火灾规则",
  description: "电气设备火灾特殊处置",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.9,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-016"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-016"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-016"}), (c:Capability {code: "FIRE_ELECTRICAL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-016"}), (c:Capability {code: "POWER_CUTOFF"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-017: 车辆火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-017",
  name: "车辆火灾规则",
  description: "车辆火灾处置",
  disaster_type: "fire",
  priority: "high",
  weight: 0.8,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-017"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-017"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-017"}), (c:Capability {code: "FIRE_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-017"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-018: 人员密集场所火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-018",
  name: "人员密集场所火灾规则",
  description: "商场、影院等人员密集场所火灾",
  disaster_type: "fire",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-018"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-018"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-018"}), (c:Capability {code: "FIRE_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-018"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-018"}), (c:Capability {code: "CROWD_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-019: 仓库火灾规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-019",
  name: "仓库火灾规则",
  description: "大型仓库火灾处置",
  disaster_type: "fire",
  priority: "high",
  weight: 0.85,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-019"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-019"}), (c:Capability {code: "FIRE_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-019"}), (c:Capability {code: "FIRE_SUPPLY_WATER"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-020: 危化品泄漏处置规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-020",
  name: "危化品泄漏处置规则",
  description: "危化品泄漏时启动专业处置",
  disaster_type: "hazmat",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-020"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-020"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-020"}), (c:Capability {code: "HAZMAT_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-020"}), (c:Capability {code: "HAZMAT_CONTAIN"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-020"}), (c:Capability {code: "HAZMAT_DECON"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-021: 危化品人员防护规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-021",
  name: "危化品人员防护规则",
  description: "危化品现场有人员暴露时启动医疗救护",
  disaster_type: "hazmat",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-021"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-021"}), (c:Capability {code: "MEDICAL_TOXICOLOGY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-021"}), (c:Capability {code: "HAZMAT_DECON"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-022: 毒气泄漏规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-022",
  name: "毒气泄漏规则",
  description: "有毒气体泄漏处置",
  disaster_type: "hazmat",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-022"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-022"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-022"}), (c:Capability {code: "HAZMAT_GAS_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-022"}), (c:Capability {code: "HAZMAT_NEUTRALIZE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-022"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-023: 危化品爆炸规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-023",
  name: "危化品爆炸规则",
  description: "危化品爆炸后处置",
  disaster_type: "hazmat",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-023"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-023"}), (t:TaskType {code: "FIRE_SUPPRESSION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-023"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-023"}), (c:Capability {code: "SEARCH_LIFE_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-023"}), (c:Capability {code: "FIRE_SUPPRESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-023"}), (c:Capability {code: "HAZMAT_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-024: 放射性物质泄漏规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-024",
  name: "放射性物质泄漏规则",
  description: "放射性物质泄漏处置",
  disaster_type: "hazmat",
  priority: "critical",
  weight: 0.99,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-024"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-024"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-024"}), (c:Capability {code: "RADIATION_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-024"}), (c:Capability {code: "RADIATION_SHIELD"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-024"}), (c:Capability {code: "HAZMAT_DECON"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-025: 危化品运输事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-025",
  name: "危化品运输事故规则",
  description: "危化品运输车辆事故处置",
  disaster_type: "hazmat",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-025"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-025"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-025"}), (c:Capability {code: "HAZMAT_CONTAIN"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-025"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-025"}), (c:Capability {code: "HAZMAT_TRANSFER"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-026: 腐蚀性物质泄漏规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-026",
  name: "腐蚀性物质泄漏规则",
  description: "强酸强碱泄漏处置",
  disaster_type: "hazmat",
  priority: "high",
  weight: 0.9,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-026"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-026"}), (c:Capability {code: "HAZMAT_CONTAIN"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-026"}), (c:Capability {code: "HAZMAT_NEUTRALIZE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-030: 洪水人员转移规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-030",
  name: "洪水人员转移规则",
  description: "洪水淹没区域有被困人员时启动水域救援",
  disaster_type: "flood",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-030"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-030"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-030"}), (c:Capability {code: "RESCUE_WATER_FLOOD"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-030"}), (c:Capability {code: "RESCUE_WATER_SWIFT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-031: 内涝排水规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-031",
  name: "内涝排水规则",
  description: "城市内涝时启动排水作业",
  disaster_type: "flood",
  priority: "high",
  weight: 0.8,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-031"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-031"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-031"}), (c:Capability {code: "PUMP_DRAINAGE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-032: 堤坝险情处置规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-032",
  name: "堤坝险情处置规则",
  description: "堤坝出现险情时启动抢险",
  disaster_type: "flood",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-032"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-032"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-032"}), (c:Capability {code: "DAM_REPAIR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-032"}), (c:Capability {code: "SANDBAG_FILL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-032"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-033: 山洪预警转移规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-033",
  name: "山洪预警转移规则",
  description: "山洪预警时启动预防性转移",
  disaster_type: "flood",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-033"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-033"}), (t:TaskType {code: "STRUCTURAL_ASSESSMENT"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-033"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-033"}), (c:Capability {code: "FLOOD_MONITOR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-034: 地下空间积水规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-034",
  name: "地下空间积水规则",
  description: "地下车库/地铁等积水处置",
  disaster_type: "flood",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-034"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-034"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-034"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-034"}), (c:Capability {code: "RESCUE_WATER_FLOOD"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-034"}), (c:Capability {code: "PUMP_DRAINAGE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-034"}), (c:Capability {code: "POWER_CUTOFF"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-035: 洪水物资保障规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-035",
  name: "洪水物资保障规则",
  description: "洪灾期间启动物资保障",
  disaster_type: "flood",
  priority: "high",
  weight: 0.8,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-035"}), (t:TaskType {code: "SHELTER_SETUP"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-035"}), (c:Capability {code: "SUPPLY_TRANSPORT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-035"}), (c:Capability {code: "SHELTER_MANAGE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-040: 滑坡搜救规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-040",
  name: "滑坡搜救规则",
  description: "滑坡掩埋人员时启动搜救",
  disaster_type: "landslide",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-040"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-040"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-040"}), (c:Capability {code: "SEARCH_LIFE_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-040"}), (c:Capability {code: "ENG_HEAVY_MACHINE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-040"}), (c:Capability {code: "RESCUE_STRUCTURAL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-041: 滑坡监测预警规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-041",
  name: "滑坡监测预警规则",
  description: "滑坡区域持续监测",
  disaster_type: "landslide",
  priority: "high",
  weight: 0.75,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-041"}), (t:TaskType {code: "STRUCTURAL_ASSESSMENT"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-041"}), (c:Capability {code: "GEO_MONITOR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-041"}), (c:Capability {code: "UAV_RECONNAISSANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "medium"}]->(c);

// === TRR-EM-042: 泥石流预警转移规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-042",
  name: "泥石流预警转移规则",
  description: "泥石流预警时启动转移",
  disaster_type: "debris_flow",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-042"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-042"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-042"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-043: 堰塞湖处置规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-043",
  name: "堰塞湖处置规则",
  description: "滑坡形成堰塞湖时启动处置",
  disaster_type: "landslide",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-043"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-043"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-043"}), (t:TaskType {code: "STRUCTURAL_ASSESSMENT"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-043"}), (c:Capability {code: "ENG_BLASTING"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-043"}), (c:Capability {code: "ENG_HEAVY_MACHINE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-043"}), (c:Capability {code: "FLOOD_MONITOR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-050: 台风预警响应规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-050",
  name: "台风预警响应规则",
  description: "台风预警时启动预防措施",
  disaster_type: "typhoon",
  priority: "high",
  weight: 0.85,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-050"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-050"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-050"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-050"}), (c:Capability {code: "FACILITY_SECURE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-051: 台风登陆响应规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-051",
  name: "台风登陆响应规则",
  description: "台风登陆后启动应急响应",
  disaster_type: "typhoon",
  priority: "critical",
  weight: 0.9,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-051"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-051"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-051"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-051"}), (c:Capability {code: "TREE_CLEARANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-051"}), (c:Capability {code: "POWER_LINE_REPAIR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-051"}), (c:Capability {code: "RESCUE_STRUCTURAL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-052: 雷电预警规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-052",
  name: "雷电预警规则",
  description: "雷电预警时启动防护措施",
  disaster_type: "thunderstorm",
  priority: "medium",
  weight: 0.7,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-052"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "medium"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-052"}), (c:Capability {code: "WARNING_BROADCAST"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-053: 冰雹灾害规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-053",
  name: "冰雹灾害规则",
  description: "冰雹灾害时启动响应",
  disaster_type: "hail",
  priority: "medium",
  weight: 0.7,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-053"}), (t:TaskType {code: "SHELTER_SETUP"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "medium"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-053"}), (t:TaskType {code: "STRUCTURAL_ASSESSMENT"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "medium"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-053"}), (c:Capability {code: "EVAC_GUIDANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-053"}), (c:Capability {code: "DAMAGE_ASSESS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "medium"}]->(c);

// === TRR-EM-060: 重大交通事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-060",
  name: "重大交通事故规则",
  description: "重大交通事故时启动救援",
  disaster_type: "traffic_accident",
  priority: "critical",
  weight: 0.9,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-060"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-060"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-060"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 3, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-060"}), (c:Capability {code: "RESCUE_VEHICLE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-060"}), (c:Capability {code: "MEDICAL_FIRST_AID"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-060"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-061: 客车事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-061",
  name: "客车事故规则",
  description: "客车事故时启动批量救援",
  disaster_type: "traffic_accident",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-061"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-061"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-061"}), (c:Capability {code: "RESCUE_VEHICLE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-061"}), (c:Capability {code: "MEDICAL_TRIAGE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-061"}), (c:Capability {code: "MEDICAL_FIRST_AID"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-062: 隧道事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-062",
  name: "隧道事故规则",
  description: "隧道内事故特殊处置",
  disaster_type: "traffic_accident",
  priority: "critical",
  weight: 0.95,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-062"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-062"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-062"}), (c:Capability {code: "RESCUE_CONFINED"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-062"}), (c:Capability {code: "VENTILATION_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-062"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-070: 矿山透水事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-070",
  name: "矿山透水事故规则",
  description: "矿山透水时启动救援",
  disaster_type: "mine_accident",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-070"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-070"}), (t:TaskType {code: "ROAD_CLEARANCE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-070"}), (c:Capability {code: "MINE_RESCUE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-070"}), (c:Capability {code: "PUMP_HIGH_CAPACITY"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-071: 矿山塌方事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-071",
  name: "矿山塌方事故规则",
  description: "矿山塌方时启动救援",
  disaster_type: "mine_accident",
  priority: "critical",
  weight: 0.98,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-071"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-071"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-071"}), (c:Capability {code: "MINE_RESCUE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-071"}), (c:Capability {code: "LIFE_SUPPORT_DRILL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-071"}), (c:Capability {code: "SEARCH_LIFE_DETECT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-072: 矿山瓦斯事故规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-072",
  name: "矿山瓦斯事故规则",
  description: "矿山瓦斯爆炸/突出时启动救援",
  disaster_type: "mine_accident",
  priority: "critical",
  weight: 0.99,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-072"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-072"}), (t:TaskType {code: "HAZMAT_RESPONSE"})
CREATE (r)-[:TRIGGERS {sequence: 2, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-072"}), (c:Capability {code: "MINE_RESCUE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-072"}), (c:Capability {code: "GAS_MONITOR"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-072"}), (c:Capability {code: "VENTILATION_RESTORE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-090: 大规模伤亡事件医疗规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-090",
  name: "大规模伤亡事件医疗规则",
  description: "伤亡人数超过阈值时启动批量伤员救治",
  disaster_type: "",
  priority: "critical",
  weight: 0.9,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-090"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "critical"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-090"}), (c:Capability {code: "MEDICAL_TRIAGE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-090"}), (c:Capability {code: "MEDICAL_FIRST_AID"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-090"}), (c:Capability {code: "MEDICAL_TRANSPORT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-091: 夜间作业照明规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-091",
  name: "夜间作业照明规则",
  description: "夜间救援作业需要照明支持",
  disaster_type: "",
  priority: "medium",
  weight: 0.6,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-091"}), (t:TaskType {code: "SHELTER_SETUP"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "medium"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-091"}), (c:Capability {code: "LIGHTING_MOBILE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-092: 通信中断保障规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-092",
  name: "通信中断保障规则",
  description: "通信中断时启动应急通信保障",
  disaster_type: "",
  priority: "high",
  weight: 0.85,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-092"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-092"}), (c:Capability {code: "COMM_SATELLITE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-092"}), (c:Capability {code: "COMM_MESH"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-093: 现场指挥部设立规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-093",
  name: "现场指挥部设立规则",
  description: "重大事件设立现场指挥部",
  disaster_type: "",
  priority: "high",
  weight: 0.85,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-093"}), (t:TaskType {code: "COMMUNICATION_RESTORE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-093"}), (c:Capability {code: "COMMAND_VEHICLE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-093"}), (c:Capability {code: "COMM_COMMAND"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "critical"}]->(c);

// === TRR-EM-094: 新闻媒体应对规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-094",
  name: "新闻媒体应对规则",
  description: "重大事件启动新闻发布",
  disaster_type: "",
  priority: "medium",
  weight: 0.6,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-094"}), (c:Capability {code: "MEDIA_LIAISON"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "medium"}]->(c);

// === TRR-EM-095: 后勤保障规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-095",
  name: "后勤保障规则",
  description: "长时间救援启动后勤保障",
  disaster_type: "",
  priority: "medium",
  weight: 0.7,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-095"}), (t:TaskType {code: "SHELTER_SETUP"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "medium"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-095"}), (c:Capability {code: "CATERING_FIELD"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-095"}), (c:Capability {code: "SUPPLY_TRANSPORT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-096: 心理援助规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-096",
  name: "心理援助规则",
  description: "重大事件启动心理援助",
  disaster_type: "",
  priority: "medium",
  weight: 0.65,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-096"}), (t:TaskType {code: "MEDICAL_EMERGENCY"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "medium"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-096"}), (c:Capability {code: "PSYCH_CRISIS"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "medium"}]->(c);

// === TRR-EM-097: 现场警戒规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-097",
  name: "现场警戒规则",
  description: "事故现场启动警戒管控",
  disaster_type: "",
  priority: "high",
  weight: 0.75,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-097"}), (t:TaskType {code: "EVACUATION"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-097"}), (c:Capability {code: "SCENE_GUARD"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-097"}), (c:Capability {code: "TRAFFIC_CONTROL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// === TRR-EM-098: 无人机侦察规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-098",
  name: "无人机侦察规则",
  description: "复杂现场启动无人机侦察",
  disaster_type: "",
  priority: "high",
  weight: 0.75,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-098"}), (t:TaskType {code: "SEARCH_RESCUE"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-098"}), (c:Capability {code: "UAV_RECONNAISSANCE"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);
MATCH (r:TRRRule {rule_id: "TRR-EM-098"}), (c:Capability {code: "UAV_THERMAL"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "medium"}]->(c);

// === TRR-EM-099: 专家会商规则 ===
CREATE (r:TRRRule {
  rule_id: "TRR-EM-099",
  name: "专家会商规则",
  description: "复杂事件启动专家会商",
  disaster_type: "",
  priority: "high",
  weight: 0.7,
  trigger_logic: "AND",
  is_active: true
});

MATCH (r:TRRRule {rule_id: "TRR-EM-099"}), (t:TaskType {code: "STRUCTURAL_ASSESSMENT"})
CREATE (r)-[:TRIGGERS {sequence: 1, priority: "high"}]->(t);
MATCH (r:TRRRule {rule_id: "TRR-EM-099"}), (c:Capability {code: "EXPERT_CONSULT"})
CREATE (r)-[:REQUIRES_CAPABILITY {priority: "high"}]->(c);

// ========== 验证统计 ==========
MATCH (r:TRRRule) WHERE r.rule_id STARTS WITH 'TRR-EM'
RETURN count(r) AS total_rules;

MATCH (r:TRRRule)-[:TRIGGERS]->(t:TaskType) WHERE r.rule_id STARTS WITH 'TRR-EM'
RETURN count(*) AS total_triggers_relations;

MATCH (r:TRRRule)-[:REQUIRES_CAPABILITY]->(c:Capability) WHERE r.rule_id STARTS WITH 'TRR-EM'
RETURN count(*) AS total_capability_relations;
