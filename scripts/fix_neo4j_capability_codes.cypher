// ============================================
// 修复 Neo4j 能力代码以匹配 PostgreSQL 标准
// 执行时间: 2025-12-09
// ============================================

// 1. 更新 Capability 节点：PATIENT_TRANSPORT -> MEDICAL_TRANSPORT
MATCH (c:Capability {code: 'PATIENT_TRANSPORT'})
SET c.code = 'MEDICAL_TRANSPORT'
RETURN c.code as updated_code;

// 2. 更新 MetaTask 节点的 required_capabilities 数组
MATCH (m:MetaTask)
WHERE 'PATIENT_TRANSPORT' IN m.required_capabilities
SET m.required_capabilities = [x IN m.required_capabilities | 
    CASE WHEN x = 'PATIENT_TRANSPORT' THEN 'MEDICAL_TRANSPORT' ELSE x END]
RETURN m.id, m.required_capabilities;

MATCH (m:MetaTask)
WHERE 'DEMOLITION' IN m.required_capabilities
SET m.required_capabilities = [x IN m.required_capabilities | 
    CASE WHEN x = 'DEMOLITION' THEN 'ENG_DEMOLITION' ELSE x END]
RETURN m.id, m.required_capabilities;

// 3. 验证修复结果
MATCH (c:Capability)
WHERE c.code IN ['PATIENT_TRANSPORT', 'DEMOLITION']
RETURN c.code as remaining_old_codes;

MATCH (m:MetaTask)
WHERE ANY(cap IN m.required_capabilities WHERE cap IN ['PATIENT_TRANSPORT', 'DEMOLITION'])
RETURN m.id as task_with_old_codes;
