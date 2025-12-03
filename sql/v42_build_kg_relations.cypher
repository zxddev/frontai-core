// ============================================================================
// v42_build_kg_relations.cypher
// 建立知识图谱关系
// 目标: 500+条关系
// ============================================================================

// ============================================================================
// 一、Scene -[ACTIVATES]-> TaskChain 关系 (每个场景激活3-6个任务链)
// ============================================================================

// ---------- 地震场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1, description: '首先进行灾情侦察'}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}), (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 5}]->(tc);

MATCH (s:Scene {id: 'S_EQ_URBAN_NIGHT'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_NIGHT'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_NIGHT'}), (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_NIGHT'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);
MATCH (s:Scene {id: 'S_EQ_URBAN_NIGHT'}), (tc:TaskChain {id: 'TC_SUPPORT'}) CREATE (s)-[:ACTIVATES {priority: 5}]->(tc);

MATCH (s:Scene {id: 'S_EQ_MOUNTAIN'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_MOUNTAIN'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_MOUNTAIN'}), (tc:TaskChain {id: 'TC_EQ_HEAVY'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_EQ_MOUNTAIN'}), (tc:TaskChain {id: 'TC_EQ_INFRASTRUCTURE'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_EQ_SECONDARY_FIRE'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SECONDARY_FIRE'}), (tc:TaskChain {id: 'TC_FIRE_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SECONDARY_FIRE'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SECONDARY_FIRE'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_EQ_SECONDARY_HAZMAT'}), (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SECONDARY_HAZMAT'}), (tc:TaskChain {id: 'TC_HAZMAT_CONTAIN'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SECONDARY_HAZMAT'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SECONDARY_HAZMAT'}), (tc:TaskChain {id: 'TC_HAZMAT_DECON'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_EQ_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_EQ_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_EQ_SCHOOL'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SCHOOL'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_SCHOOL'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_EQ_HOSPITAL'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_EQ_HOSPITAL'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_EQ_HOSPITAL'}), (tc:TaskChain {id: 'TC_SUPPORT'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

// ---------- 洪水场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_FLOOD_RIVER'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_RIVER'}), (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_RIVER'}), (tc:TaskChain {id: 'TC_FLOOD_DAM'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_RIVER'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_FLOOD_URBAN'}), (tc:TaskChain {id: 'TC_FLOOD_DRAINAGE'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_URBAN'}), (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_URBAN'}), (tc:TaskChain {id: 'TC_TRAFFIC_CONTROL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_FLOOD_FLASH'}), (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_FLASH'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_FLASH'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_FLOOD_DAM'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_DAM'}), (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_DAM'}), (tc:TaskChain {id: 'TC_FLOOD_DAM'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_FLOOD_TRAPPED_VEHICLE'}), (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_TRAPPED_VEHICLE'}), (tc:TaskChain {id: 'TC_TRAFFIC_EXTRICATE'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_TRAPPED_VEHICLE'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_FLOOD_DEBRIS_FLOW'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_DEBRIS_FLOW'}), (tc:TaskChain {id: 'TC_FLOOD_DEBRIS'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_DEBRIS_FLOW'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_FLOOD_DEBRIS_FLOW'}), (tc:TaskChain {id: 'TC_EQ_INFRASTRUCTURE'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

// ---------- 火灾场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_FIRE_RESIDENTIAL'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_RESIDENTIAL'}), (tc:TaskChain {id: 'TC_FIRE_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_RESIDENTIAL'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_RESIDENTIAL'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_FIRE_HIGHRISE'}), (tc:TaskChain {id: 'TC_FIRE_HIGHRISE'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_HIGHRISE'}), (tc:TaskChain {id: 'TC_FIRE_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_HIGHRISE'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_HIGHRISE'}), (tc:TaskChain {id: 'TC_FIRE_VENT'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_FIRE_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_INDUSTRIAL'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_FIRE_FOREST'}), (tc:TaskChain {id: 'TC_FIRE_FOREST'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_FOREST'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_FOREST'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_FIRE_CHEMICAL'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_CHEMICAL'}), (tc:TaskChain {id: 'TC_HAZMAT_CONTAIN'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_CHEMICAL'}), (tc:TaskChain {id: 'TC_HAZMAT_DECON'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_CHEMICAL'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_FIRE_UNDERGROUND'}), (tc:TaskChain {id: 'TC_FIRE_VENT'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_UNDERGROUND'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_FIRE_UNDERGROUND'}), (tc:TaskChain {id: 'TC_FIRE_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

// ---------- 危化品场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_GAS'}), (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_GAS'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_GAS'}), (tc:TaskChain {id: 'TC_HAZMAT_CONTAIN'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_GAS'}), (tc:TaskChain {id: 'TC_HAZMAT_DECON'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_HAZMAT_LEAK_LIQUID'}), (tc:TaskChain {id: 'TC_HAZMAT_CONTAIN'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_LIQUID'}), (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_LIQUID'}), (tc:TaskChain {id: 'TC_HAZMAT_TRANSFER'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_HAZMAT_EXPLOSION'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_EXPLOSION'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_EXPLOSION'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_EXPLOSION'}), (tc:TaskChain {id: 'TC_HAZMAT_DECON'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_HAZMAT_RADIATION'}), (tc:TaskChain {id: 'TC_HAZMAT_RADIATION'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_RADIATION'}), (tc:TaskChain {id: 'TC_EVAC'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_HAZMAT_RADIATION'}), (tc:TaskChain {id: 'TC_HAZMAT_DECON'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

// ---------- 地质灾害场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_GEO_LANDSLIDE'}), (tc:TaskChain {id: 'TC_RECON'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_GEO_LANDSLIDE'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_GEO_LANDSLIDE'}), (tc:TaskChain {id: 'TC_EQ_HEAVY'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_GEO_LANDSLIDE'}), (tc:TaskChain {id: 'TC_EQ_INFRASTRUCTURE'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_GEO_MINE_COLLAPSE'}), (tc:TaskChain {id: 'TC_MINE_VENTILATION'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_COLLAPSE'}), (tc:TaskChain {id: 'TC_MINE_DRILLING'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_COLLAPSE'}), (tc:TaskChain {id: 'TC_MINE_SUPPORT'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_COLLAPSE'}), (tc:TaskChain {id: 'TC_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_GEO_MINE_GAS'}), (tc:TaskChain {id: 'TC_MINE_VENTILATION'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_GAS'}), (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_GAS'}), (tc:TaskChain {id: 'TC_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_GEO_MINE_FLOOD'}), (tc:TaskChain {id: 'TC_MINE_PUMP'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_FLOOD'}), (tc:TaskChain {id: 'TC_MINE_DRILLING'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_GEO_MINE_FLOOD'}), (tc:TaskChain {id: 'TC_RESCUE'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

// ---------- 交通事故场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}), (tc:TaskChain {id: 'TC_TRAFFIC_CONTROL'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}), (tc:TaskChain {id: 'TC_TRAFFIC_EXTRICATE'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}), (tc:TaskChain {id: 'TC_TRAFFIC_CLEARANCE'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_TRAFFIC_TUNNEL'}), (tc:TaskChain {id: 'TC_TRAFFIC_TUNNEL'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_TUNNEL'}), (tc:TaskChain {id: 'TC_FIRE_VENT'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_TUNNEL'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

MATCH (s:Scene {id: 'S_TRAFFIC_BUS'}), (tc:TaskChain {id: 'TC_TRAFFIC_EXTRICATE'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_BUS'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_TRAFFIC_BUS'}), (tc:TaskChain {id: 'TC_TRAFFIC_CONTROL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

// ---------- 建筑事故场景激活的任务链 ----------
MATCH (s:Scene {id: 'S_BUILDING_COLLAPSE'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_BUILDING_COLLAPSE'}), (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_BUILDING_COLLAPSE'}), (tc:TaskChain {id: 'TC_EQ_HEAVY'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);
MATCH (s:Scene {id: 'S_BUILDING_COLLAPSE'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 4}]->(tc);

MATCH (s:Scene {id: 'S_BUILDING_EXPLOSION'}), (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}) CREATE (s)-[:ACTIVATES {priority: 1}]->(tc);
MATCH (s:Scene {id: 'S_BUILDING_EXPLOSION'}), (tc:TaskChain {id: 'TC_SEARCH'}) CREATE (s)-[:ACTIVATES {priority: 2}]->(tc);
MATCH (s:Scene {id: 'S_BUILDING_EXPLOSION'}), (tc:TaskChain {id: 'TC_MEDICAL'}) CREATE (s)-[:ACTIVATES {priority: 3}]->(tc);

// ============================================================================
// 二、TaskChain -[INCLUDES]-> MetaTask 关系 (每个任务链包含3-8个元任务)
// ============================================================================

// ---------- 侦察评估链 ----------
MATCH (tc:TaskChain {id: 'TC_RECON'}), (mt:MetaTask {id: 'EM01'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_RECON'}), (mt:MetaTask {id: 'EM03'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_RECON'}), (mt:MetaTask {id: 'EM04'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_RECON'}), (mt:MetaTask {id: 'EM05'}) CREATE (tc)-[:INCLUDES {order: 4, mandatory: false}]->(mt);

// ---------- 搜索定位链 ----------
MATCH (tc:TaskChain {id: 'TC_SEARCH'}), (mt:MetaTask {id: 'EM06'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_SEARCH'}), (mt:MetaTask {id: 'EM12'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: false}]->(mt);
MATCH (tc:TaskChain {id: 'TC_SEARCH'}), (mt:MetaTask {id: 'EM13'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: false}]->(mt);

// ---------- 救援实施链 ----------
MATCH (tc:TaskChain {id: 'TC_RESCUE'}), (mt:MetaTask {id: 'EM10'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_RESCUE'}), (mt:MetaTask {id: 'EM11'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: false}]->(mt);
MATCH (tc:TaskChain {id: 'TC_RESCUE'}), (mt:MetaTask {id: 'EM07'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: true}]->(mt);

// ---------- 医疗救治链 ----------
MATCH (tc:TaskChain {id: 'TC_MEDICAL'}), (mt:MetaTask {id: 'EM14'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_MEDICAL'}), (mt:MetaTask {id: 'EM15'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);

// ---------- 疏散安置链 ----------
MATCH (tc:TaskChain {id: 'TC_EVAC'}), (mt:MetaTask {id: 'EM08'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EVAC'}), (mt:MetaTask {id: 'EM09'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);

// ---------- 结构救援链 ----------
MATCH (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}), (mt:MetaTask {id: 'EM06'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}), (mt:MetaTask {id: 'EM10'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}), (mt:MetaTask {id: 'EM11'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: false}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_STRUCTURAL'}), (mt:MetaTask {id: 'EM14'}) CREATE (tc)-[:INCLUDES {order: 4, mandatory: true}]->(mt);

// ---------- 重型救援链 ----------
MATCH (tc:TaskChain {id: 'TC_EQ_HEAVY'}), (mt:MetaTask {id: 'EM11'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_HEAVY'}), (mt:MetaTask {id: 'EM10'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_HEAVY'}), (mt:MetaTask {id: 'EM16'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: false}]->(mt);

// ---------- 基础设施抢修链 ----------
MATCH (tc:TaskChain {id: 'TC_EQ_INFRASTRUCTURE'}), (mt:MetaTask {id: 'EM16'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_INFRASTRUCTURE'}), (mt:MetaTask {id: 'EM17'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: false}]->(mt);
MATCH (tc:TaskChain {id: 'TC_EQ_INFRASTRUCTURE'}), (mt:MetaTask {id: 'EM18'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: false}]->(mt);

// ---------- 火灾扑救链 ----------
MATCH (tc:TaskChain {id: 'TC_FIRE_SUPPRESS'}), (mt:MetaTask {id: 'EM19'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);

// ---------- 火场搜救链 ----------
MATCH (tc:TaskChain {id: 'TC_FIRE_SEARCH'}), (mt:MetaTask {id: 'EM06'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_FIRE_SEARCH'}), (mt:MetaTask {id: 'EM10'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_FIRE_SEARCH'}), (mt:MetaTask {id: 'EM14'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: true}]->(mt);

// ---------- 水域救援链 ----------
MATCH (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}), (mt:MetaTask {id: 'EM06'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}), (mt:MetaTask {id: 'EM10'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}), (mt:MetaTask {id: 'EM14'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_FLOOD_WATER_RESCUE'}), (mt:MetaTask {id: 'EM15'}) CREATE (tc)-[:INCLUDES {order: 4, mandatory: true}]->(mt);

// ---------- 危化品检测链 ----------
MATCH (tc:TaskChain {id: 'TC_HAZMAT_DETECT'}), (mt:MetaTask {id: 'EM05'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);

// ---------- 危化品围堵链 ----------
// (需要先创建对应的MetaTask节点，这里暂时跳过没有对应MetaTask的任务链)

// ---------- 交通救援链 ----------
MATCH (tc:TaskChain {id: 'TC_TRAFFIC_EXTRICATE'}), (mt:MetaTask {id: 'EM10'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_TRAFFIC_EXTRICATE'}), (mt:MetaTask {id: 'EM14'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_TRAFFIC_EXTRICATE'}), (mt:MetaTask {id: 'EM15'}) CREATE (tc)-[:INCLUDES {order: 3, mandatory: true}]->(mt);

// ---------- 指挥协调链 ----------
MATCH (tc:TaskChain {id: 'TC_COMMAND'}), (mt:MetaTask {id: 'EM02'}) CREATE (tc)-[:INCLUDES {order: 1, mandatory: true}]->(mt);
MATCH (tc:TaskChain {id: 'TC_COMMAND'}), (mt:MetaTask {id: 'EM07'}) CREATE (tc)-[:INCLUDES {order: 2, mandatory: true}]->(mt);

// ============================================================================
// 三、MetaTask -[PRECEDES]-> MetaTask 关系 (任务依赖关系)
// ============================================================================

// 侦察 -> 搜索
MATCH (m1:MetaTask {id: 'EM01'}), (m2:MetaTask {id: 'EM06'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);
MATCH (m1:MetaTask {id: 'EM03'}), (m2:MetaTask {id: 'EM06'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);
MATCH (m1:MetaTask {id: 'EM04'}), (m2:MetaTask {id: 'EM07'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);

// 搜索 -> 救援
MATCH (m1:MetaTask {id: 'EM06'}), (m2:MetaTask {id: 'EM10'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);
MATCH (m1:MetaTask {id: 'EM12'}), (m2:MetaTask {id: 'EM10'}) CREATE (m1)-[:PRECEDES {dependency_type: 'parallel'}]->(m2);
MATCH (m1:MetaTask {id: 'EM13'}), (m2:MetaTask {id: 'EM10'}) CREATE (m1)-[:PRECEDES {dependency_type: 'parallel'}]->(m2);

// 救援 -> 医疗
MATCH (m1:MetaTask {id: 'EM10'}), (m2:MetaTask {id: 'EM14'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);
MATCH (m1:MetaTask {id: 'EM11'}), (m2:MetaTask {id: 'EM14'}) CREATE (m1)-[:PRECEDES {dependency_type: 'parallel'}]->(m2);

// 医疗 -> 转运
MATCH (m1:MetaTask {id: 'EM14'}), (m2:MetaTask {id: 'EM15'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);

// 疏散路线 -> 疏散转移
MATCH (m1:MetaTask {id: 'EM08'}), (m2:MetaTask {id: 'EM09'}) CREATE (m1)-[:PRECEDES {dependency_type: 'sequential'}]->(m2);

// 道路抢通 -> 转运
MATCH (m1:MetaTask {id: 'EM16'}), (m2:MetaTask {id: 'EM15'}) CREATE (m1)-[:PRECEDES {dependency_type: 'enables'}]->(m2);

// 风险评估 -> 救援
MATCH (m1:MetaTask {id: 'EM05'}), (m2:MetaTask {id: 'EM10'}) CREATE (m1)-[:PRECEDES {dependency_type: 'informs'}]->(m2);

// 灭火 -> 搜救
MATCH (m1:MetaTask {id: 'EM19'}), (m2:MetaTask {id: 'EM06'}) CREATE (m1)-[:PRECEDES {dependency_type: 'enables'}]->(m2);

// 燃气关阀 -> 灭火
MATCH (m1:MetaTask {id: 'EM17'}), (m2:MetaTask {id: 'EM19'}) CREATE (m1)-[:PRECEDES {dependency_type: 'safety'}]->(m2);

// 电力切断 -> 救援
MATCH (m1:MetaTask {id: 'EM18'}), (m2:MetaTask {id: 'EM10'}) CREATE (m1)-[:PRECEDES {dependency_type: 'safety'}]->(m2);

// ============================================================================
// 四、Scene -[REQUIRES]-> Capability 关系 (场景能力需求)
// ============================================================================

// 地震场景需要的能力
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'LIFE_DETECTION', name: '生命探测'});
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'STRUCTURAL_RESCUE', name: '结构救援'});
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'EMERGENCY_TREATMENT', name: '紧急救治'});
MATCH (s:Scene {id: 'S_EQ_URBAN_DAY'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'HEAVY_LIFTING', name: '重物起吊'});

MATCH (s:Scene {id: 'S_EQ_SECONDARY_FIRE'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'FIRE_SUPPRESSION', name: '火灾扑救'});
MATCH (s:Scene {id: 'S_EQ_SECONDARY_FIRE'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'LIFE_DETECTION', name: '生命探测'});

MATCH (s:Scene {id: 'S_EQ_SECONDARY_HAZMAT'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'HAZMAT_DETECTION', name: '危化品检测'});
MATCH (s:Scene {id: 'S_EQ_SECONDARY_HAZMAT'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'HAZMAT_CONTAINMENT', name: '危化品围堵'});

// 洪水场景需要的能力
MATCH (s:Scene {id: 'S_FLOOD_RIVER'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'WATER_RESCUE', name: '水域救援'});
MATCH (s:Scene {id: 'S_FLOOD_RIVER'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'SWIFT_WATER_RESCUE', name: '急流水域救援'});

MATCH (s:Scene {id: 'S_FLOOD_URBAN'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'PUMP_DRAINAGE', name: '排水泵送'});
MATCH (s:Scene {id: 'S_FLOOD_URBAN'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'EVACUATION_COORDINATION', name: '疏散协调'});

// 火灾场景需要的能力
MATCH (s:Scene {id: 'S_FIRE_RESIDENTIAL'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'FIRE_SUPPRESSION', name: '火灾扑救'});
MATCH (s:Scene {id: 'S_FIRE_RESIDENTIAL'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'FIRE_SEARCH_RESCUE', name: '火场搜救'});

MATCH (s:Scene {id: 'S_FIRE_HIGHRISE'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'FIRE_SUPPRESSION', name: '火灾扑救'});
MATCH (s:Scene {id: 'S_FIRE_HIGHRISE'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'ROPE_RESCUE', name: '绳索救援'});

MATCH (s:Scene {id: 'S_FIRE_FOREST'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'FIRE_FOREST', name: '森林火灾扑救'});

// 危化品场景需要的能力
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_GAS'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'HAZMAT_DETECTION', name: '危化品检测'});
MATCH (s:Scene {id: 'S_HAZMAT_LEAK_GAS'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'DECONTAMINATION', name: '洗消去污'});

MATCH (s:Scene {id: 'S_HAZMAT_RADIATION'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'RADIATION_PROTECTION', name: '辐射防护'});

// 矿山场景需要的能力
MATCH (s:Scene {id: 'S_GEO_MINE_COLLAPSE'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'CONFINED_SPACE_RESCUE', name: '狭小空间救援'});
MATCH (s:Scene {id: 'S_GEO_MINE_COLLAPSE'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'LIFE_DETECTION', name: '生命探测'});

// 交通事故场景需要的能力
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}) 
CREATE (s)-[:REQUIRES {priority: 'critical'}]->(:Capability {code: 'STRUCTURAL_RESCUE', name: '结构救援'});
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'EMERGENCY_TREATMENT', name: '紧急救治'});
MATCH (s:Scene {id: 'S_TRAFFIC_HIGHWAY'}) 
CREATE (s)-[:REQUIRES {priority: 'high'}]->(:Capability {code: 'ROAD_CLEARANCE', name: '道路抢通'});

// ============================================================================
// 五、验证关系创建结果
// ============================================================================
MATCH ()-[r:ACTIVATES]->() RETURN 'ACTIVATES' as type, count(r) as count
UNION ALL
MATCH ()-[r:INCLUDES]->() RETURN 'INCLUDES' as type, count(r) as count
UNION ALL
MATCH ()-[r:PRECEDES]->() RETURN 'PRECEDES' as type, count(r) as count
UNION ALL
MATCH ()-[r:REQUIRES]->() RETURN 'REQUIRES' as type, count(r) as count;
