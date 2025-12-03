// ============================================================================
// v32_default_scene_s0.cypher
// 创建S0默认场景（用于HTN兜底）
// ============================================================================

// 检查S0是否存在，如果不存在则创建
MERGE (s:Scene {scene_code: 'S0'})
ON CREATE SET 
    s.scene_name = '通用救援场景',
    s.description = '适用于任何灾害类型的基础搜救链（系统兜底场景）',
    s.disaster_type = 'general',
    s.created_at = datetime()
ON MATCH SET
    s.updated_at = datetime();

// 创建通用任务链
MERGE (tc:TaskChain {chain_id: 'TC-S0'})
ON CREATE SET 
    tc.chain_name = '通用救援任务链',
    tc.scene_code = 'S0',
    tc.description = '基础搜救任务序列：侦察→评估→救援'
ON MATCH SET
    tc.updated_at = datetime();

// 关联场景和任务链
MATCH (s:Scene {scene_code: 'S0'})
MATCH (tc:TaskChain {chain_id: 'TC-S0'})
MERGE (s)-[:HAS_CHAIN]->(tc);

// 关联基础MetaTask（如果存在）
MATCH (tc:TaskChain {chain_id: 'TC-S0'})
OPTIONAL MATCH (em01:MetaTask {task_id: 'EM01'})  // 无人机广域侦察
OPTIONAL MATCH (em04:MetaTask {task_id: 'EM04'})  // 灾情快速评估
OPTIONAL MATCH (em10:MetaTask {task_id: 'EM10'})  // 被困人员救援

FOREACH (_ IN CASE WHEN em01 IS NOT NULL THEN [1] ELSE [] END |
    MERGE (tc)-[:INCLUDES {sequence: 1}]->(em01)
)
FOREACH (_ IN CASE WHEN em04 IS NOT NULL THEN [1] ELSE [] END |
    MERGE (tc)-[:INCLUDES {sequence: 2}]->(em04)
)
FOREACH (_ IN CASE WHEN em10 IS NOT NULL THEN [1] ELSE [] END |
    MERGE (tc)-[:INCLUDES {sequence: 3}]->(em10)
);

// 返回结果
MATCH (s:Scene {scene_code: 'S0'})-[:HAS_CHAIN]->(tc:TaskChain)
OPTIONAL MATCH (tc)-[r:INCLUDES]->(mt:MetaTask)
RETURN s.scene_name, tc.chain_name, count(mt) as task_count;
