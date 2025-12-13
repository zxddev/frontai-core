// ============================================================================
// SOP (标准作业程序) 知识图谱初始化脚本
//
// 用途：为 task_coordinator agent 提供步骤级救援流程知识
// 执行：cypher-shell -u neo4j -p <password> < scripts/init_sop_kg.cypher
// ============================================================================

// 清理旧数据（可选，生产环境慎用）
// MATCH (n:SOPTemplate) DETACH DELETE n;
// MATCH (n:SOPStep) DETACH DELETE n;

// ============================================================================
// 1. 地震建筑倒塌救援 SOP
// ============================================================================

CREATE (sop1:SOPTemplate {
  id: "SOP-EARTHQUAKE-BUILDING-COLLAPSE",
  name: "地震建筑倒塌救援SOP",
  disaster_type: "earthquake",
  scene_code: "building_collapse",
  description: "适用于地震导致的建筑物倒塌救援场景",
  version: "1.0",
  total_steps: 4,
  estimated_duration_minutes: 165,
  created_at: datetime()
})

CREATE (eq_step1:SOPStep {
  id: "SOP-EQ-BC-001",
  name: "生命探测",
  sequence: 1,
  duration_minutes: 30,
  roles: ["主攻"],
  required_capabilities: ["LIFE_DETECTION"],
  required_equipment: ["生命探测仪", "蛇眼探测器", "音频探测器", "标记旗"],
  parallel_allowed: false,
  completion_criteria: "完成所有区域探测，标记至少1个救援点位",
  safety_notes: "注意余震风险，保持通讯畅通"
})

CREATE (eq_step2:SOPStep {
  id: "SOP-EQ-BC-002",
  name: "破拆通道",
  sequence: 2,
  duration_minutes: 60,
  roles: ["主攻", "配合"],
  required_capabilities: ["HEAVY_RESCUE", "STRUCTURAL_SUPPORT"],
  required_equipment: ["液压剪", "破拆锤", "切割机", "液压支撑杆", "木方"],
  parallel_allowed: true,
  completion_criteria: "开辟至少1条可通行救援通道",
  safety_notes: "破拆前确认结构稳定性，配合队伍同步支撑"
})

CREATE (eq_step3:SOPStep {
  id: "SOP-EQ-BC-003",
  name: "伤员救出",
  sequence: 3,
  duration_minutes: 45,
  roles: ["主攻", "配合"],
  required_capabilities: ["RESCUE", "MEDICAL_FIRST_AID"],
  required_equipment: ["担架", "医疗包", "颈托", "夹板", "氧气袋"],
  parallel_allowed: true,
  completion_criteria: "所有标记点位伤员救出",
  safety_notes: "注意伤员脊椎保护，避免二次伤害"
})

CREATE (eq_step4:SOPStep {
  id: "SOP-EQ-BC-004",
  name: "现场急救转运",
  sequence: 4,
  duration_minutes: 30,
  roles: ["主攻"],
  required_capabilities: ["MEDICAL_EMERGENCY"],
  required_equipment: ["急救设备", "救护车", "心电监护仪"],
  parallel_allowed: false,
  completion_criteria: "伤员转运至医疗点或医院",
  safety_notes: "转运途中持续监护生命体征"
})

// 建立 SOP 模板与步骤的关系
CREATE (sop1)-[:HAS_STEP {sequence: 1}]->(eq_step1)
CREATE (sop1)-[:HAS_STEP {sequence: 2}]->(eq_step2)
CREATE (sop1)-[:HAS_STEP {sequence: 3}]->(eq_step3)
CREATE (sop1)-[:HAS_STEP {sequence: 4}]->(eq_step4)

// 建立步骤之间的依赖关系
CREATE (eq_step2)-[:DEPENDS_ON]->(eq_step1)
CREATE (eq_step3)-[:DEPENDS_ON]->(eq_step2)
CREATE (eq_step4)-[:DEPENDS_ON]->(eq_step3);

// ============================================================================
// 2. 危化品泄漏处置 SOP
// ============================================================================

CREATE (sop2:SOPTemplate {
  id: "SOP-HAZMAT-LEAK",
  name: "危化品泄漏处置SOP",
  disaster_type: "hazmat",
  scene_code: "chemical_leak",
  description: "适用于危险化学品泄漏事故的处置",
  version: "1.0",
  total_steps: 5,
  estimated_duration_minutes: 210,
  created_at: datetime()
})

CREATE (hz_step1:SOPStep {
  id: "SOP-HZ-LK-001",
  name: "侦检识别",
  sequence: 1,
  duration_minutes: 20,
  roles: ["主攻"],
  required_capabilities: ["HAZMAT_DETECTION"],
  required_equipment: ["气体检测仪", "PH试纸", "防化服", "空气呼吸器"],
  parallel_allowed: false,
  completion_criteria: "确定泄漏物质种类、浓度、扩散范围",
  safety_notes: "必须穿戴防护装备，上风向接近"
})

CREATE (hz_step2:SOPStep {
  id: "SOP-HZ-LK-002",
  name: "警戒隔离",
  sequence: 2,
  duration_minutes: 30,
  roles: ["主攻", "配合"],
  required_capabilities: ["CROWD_CONTROL", "EVACUATION"],
  required_equipment: ["警戒带", "扩音器", "警示牌", "疏散指示牌"],
  parallel_allowed: true,
  completion_criteria: "建立警戒区，疏散危险区域人员",
  safety_notes: "根据风向确定警戒范围，至少300米"
})

CREATE (hz_step3:SOPStep {
  id: "SOP-HZ-LK-003",
  name: "洗消准备",
  sequence: 3,
  duration_minutes: 40,
  roles: ["主攻"],
  required_capabilities: ["DECONTAMINATION"],
  required_equipment: ["洗消车", "洗消帐篷", "洗消液", "收集容器"],
  parallel_allowed: true,
  completion_criteria: "洗消站搭建完成，可接收污染人员",
  safety_notes: "洗消站设置在热区与温区交界处"
})

CREATE (hz_step4:SOPStep {
  id: "SOP-HZ-LK-004",
  name: "堵漏封堵",
  sequence: 4,
  duration_minutes: 90,
  roles: ["主攻", "配合"],
  required_capabilities: ["HAZMAT_CONTAINMENT"],
  required_equipment: ["堵漏器材", "围堰材料", "吸附材料", "收集桶"],
  parallel_allowed: false,
  completion_criteria: "泄漏源封堵，扩散得到控制",
  safety_notes: "堵漏人员必须穿戴A级防护，限时作业"
})

CREATE (hz_step5:SOPStep {
  id: "SOP-HZ-LK-005",
  name: "环境监测",
  sequence: 5,
  duration_minutes: 30,
  roles: ["主攻"],
  required_capabilities: ["ENVIRONMENTAL_MONITORING"],
  required_equipment: ["便携式检测仪", "采样器", "记录本"],
  parallel_allowed: false,
  completion_criteria: "环境指标恢复安全阈值",
  safety_notes: "持续监测直至确认安全"
})

// 建立关系
CREATE (sop2)-[:HAS_STEP {sequence: 1}]->(hz_step1)
CREATE (sop2)-[:HAS_STEP {sequence: 2}]->(hz_step2)
CREATE (sop2)-[:HAS_STEP {sequence: 3}]->(hz_step3)
CREATE (sop2)-[:HAS_STEP {sequence: 4}]->(hz_step4)
CREATE (sop2)-[:HAS_STEP {sequence: 5}]->(hz_step5)

CREATE (hz_step2)-[:DEPENDS_ON]->(hz_step1)
CREATE (hz_step3)-[:DEPENDS_ON]->(hz_step1)
CREATE (hz_step4)-[:DEPENDS_ON]->(hz_step2)
CREATE (hz_step4)-[:DEPENDS_ON]->(hz_step3)
CREATE (hz_step5)-[:DEPENDS_ON]->(hz_step4);

// ============================================================================
// 3. 火灾扑救 SOP
// ============================================================================

CREATE (sop3:SOPTemplate {
  id: "SOP-FIRE-SUPPRESSION",
  name: "火灾扑救SOP",
  disaster_type: "fire",
  scene_code: "building_fire",
  description: "适用于建筑物火灾的扑救",
  version: "1.0",
  total_steps: 4,
  estimated_duration_minutes: 150,
  created_at: datetime()
})

CREATE (fr_step1:SOPStep {
  id: "SOP-FR-SP-001",
  name: "火情侦察",
  sequence: 1,
  duration_minutes: 15,
  roles: ["主攻"],
  required_capabilities: ["FIRE_RECONNAISSANCE"],
  required_equipment: ["热成像仪", "测温仪", "对讲机"],
  parallel_allowed: false,
  completion_criteria: "确定火点位置、蔓延方向、被困人员情况",
  safety_notes: "保持安全距离，注意建筑结构稳定性"
})

CREATE (fr_step2:SOPStep {
  id: "SOP-FR-SP-002",
  name: "人员搜救",
  sequence: 2,
  duration_minutes: 45,
  roles: ["主攻", "配合"],
  required_capabilities: ["FIRE_RESCUE", "SEARCH_RESCUE"],
  required_equipment: ["空气呼吸器", "救生绳", "破拆工具", "担架"],
  parallel_allowed: true,
  completion_criteria: "所有被困人员救出",
  safety_notes: "两人一组进入，保持通讯，限时撤离"
})

CREATE (fr_step3:SOPStep {
  id: "SOP-FR-SP-003",
  name: "火势控制",
  sequence: 3,
  duration_minutes: 60,
  roles: ["主攻", "配合", "保障"],
  required_capabilities: ["FIRE_SUPPRESSION"],
  required_equipment: ["消防水带", "水枪", "泡沫枪", "云梯车"],
  parallel_allowed: true,
  completion_criteria: "明火扑灭，无复燃风险",
  safety_notes: "注意水源供应，防止建筑坍塌"
})

CREATE (fr_step4:SOPStep {
  id: "SOP-FR-SP-004",
  name: "现场清理",
  sequence: 4,
  duration_minutes: 30,
  roles: ["主攻"],
  required_capabilities: ["FIRE_OVERHAUL"],
  required_equipment: ["热成像仪", "铁锹", "水枪"],
  parallel_allowed: false,
  completion_criteria: "无暗火，现场移交",
  safety_notes: "彻底检查隐蔽部位"
})

// 建立关系
CREATE (sop3)-[:HAS_STEP {sequence: 1}]->(fr_step1)
CREATE (sop3)-[:HAS_STEP {sequence: 2}]->(fr_step2)
CREATE (sop3)-[:HAS_STEP {sequence: 3}]->(fr_step3)
CREATE (sop3)-[:HAS_STEP {sequence: 4}]->(fr_step4)

CREATE (fr_step2)-[:DEPENDS_ON]->(fr_step1)
CREATE (fr_step3)-[:DEPENDS_ON]->(fr_step1)
CREATE (fr_step4)-[:DEPENDS_ON]->(fr_step3);

// ============================================================================
// 4. 洪水救援 SOP
// ============================================================================

CREATE (sop4:SOPTemplate {
  id: "SOP-FLOOD-RESCUE",
  name: "洪水救援SOP",
  disaster_type: "flood",
  scene_code: "flood_rescue",
  description: "适用于洪涝灾害的人员救援",
  version: "1.0",
  total_steps: 4,
  estimated_duration_minutes: 180,
  created_at: datetime()
})

CREATE (fl_step1:SOPStep {
  id: "SOP-FL-RS-001",
  name: "水情侦察",
  sequence: 1,
  duration_minutes: 20,
  roles: ["主攻"],
  required_capabilities: ["WATER_RECONNAISSANCE"],
  required_equipment: ["无人机", "测深仪", "对讲机", "地图"],
  parallel_allowed: false,
  completion_criteria: "确定水深、流速、被困人员位置",
  safety_notes: "注意水流变化，确认安全通道"
})

CREATE (fl_step2:SOPStep {
  id: "SOP-FL-RS-002",
  name: "水上救援",
  sequence: 2,
  duration_minutes: 90,
  roles: ["主攻", "配合"],
  required_capabilities: ["WATER_RESCUE"],
  required_equipment: ["冲锋舟", "救生衣", "救生圈", "抛绳器"],
  parallel_allowed: true,
  completion_criteria: "所有被困人员转移至安全地带",
  safety_notes: "救援人员必须穿戴救生衣，注意水下障碍物"
})

CREATE (fl_step3:SOPStep {
  id: "SOP-FL-RS-003",
  name: "群众安置",
  sequence: 3,
  duration_minutes: 60,
  roles: ["主攻", "配合"],
  required_capabilities: ["EVACUATION", "LOGISTICS"],
  required_equipment: ["大巴车", "帐篷", "饮用水", "食品"],
  parallel_allowed: true,
  completion_criteria: "群众转移至安置点，基本生活保障到位",
  safety_notes: "统计人数，关注老弱病残"
})

CREATE (fl_step4:SOPStep {
  id: "SOP-FL-RS-004",
  name: "卫生防疫",
  sequence: 4,
  duration_minutes: 30,
  roles: ["主攻"],
  required_capabilities: ["MEDICAL_SUPPORT"],
  required_equipment: ["消毒液", "防疫药品", "医疗包"],
  parallel_allowed: false,
  completion_criteria: "完成消毒和防疫宣传",
  safety_notes: "注意饮水安全和传染病预防"
})

// 建立关系
CREATE (sop4)-[:HAS_STEP {sequence: 1}]->(fl_step1)
CREATE (sop4)-[:HAS_STEP {sequence: 2}]->(fl_step2)
CREATE (sop4)-[:HAS_STEP {sequence: 3}]->(fl_step3)
CREATE (sop4)-[:HAS_STEP {sequence: 4}]->(fl_step4)

CREATE (fl_step2)-[:DEPENDS_ON]->(fl_step1)
CREATE (fl_step3)-[:DEPENDS_ON]->(fl_step2)
CREATE (fl_step4)-[:DEPENDS_ON]->(fl_step3);

// ============================================================================
// 创建索引以提高查询性能
// ============================================================================

CREATE INDEX sop_template_id IF NOT EXISTS FOR (s:SOPTemplate) ON (s.id);
CREATE INDEX sop_template_disaster_type IF NOT EXISTS FOR (s:SOPTemplate) ON (s.disaster_type);
CREATE INDEX sop_template_scene_code IF NOT EXISTS FOR (s:SOPTemplate) ON (s.scene_code);
CREATE INDEX sop_step_id IF NOT EXISTS FOR (s:SOPStep) ON (s.id);
