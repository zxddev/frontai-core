// ============================================================================
// 统一MetaTask能力代码与PostgreSQL队伍能力代码
// 
// 问题：Neo4j MetaTask使用小写蛇形命名（如life_detection），
//      PostgreSQL队伍使用大写下划线命名（如LIFE_DETECTION），
//      导致任务-资源匹配失效。
//
// 解决：更新Neo4j中MetaTask的required_capabilities为PostgreSQL能力代码
// ============================================================================

// EM01: 无人机广域侦察 - 需要生命探测和通信支持
MATCH (m:MetaTask {id: 'EM01'}) 
SET m.required_capabilities = ['LIFE_DETECTION', 'COMMUNICATION_SUPPORT'];

// EM02: 地震监测数据分析 - 需要指挥协调
MATCH (m:MetaTask {id: 'EM02'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

// EM03: 建筑倒塌区域识别 - 需要结构救援和建筑支撑
MATCH (m:MetaTask {id: 'EM03'}) 
SET m.required_capabilities = ['STRUCTURAL_RESCUE', 'BUILDING_SHORING'];

// EM04: 灾情快速评估 - 需要指挥协调
MATCH (m:MetaTask {id: 'EM04'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

// EM05: 次生灾害风险研判 - 需要危化品检测
MATCH (m:MetaTask {id: 'EM05'}) 
SET m.required_capabilities = ['HAZMAT_DETECTION'];

// EM06: 埋压人员生命探测 - 需要生命探测
MATCH (m:MetaTask {id: 'EM06'}) 
SET m.required_capabilities = ['LIFE_DETECTION'];

// EM07: 救援力量调度 - 需要指挥协调和通信支持
MATCH (m:MetaTask {id: 'EM07'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION', 'COMMUNICATION_SUPPORT'];

// EM08: 疏散路线规划 - 需要指挥协调
MATCH (m:MetaTask {id: 'EM08'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

// EM09: 群众疏散转移 - 需要疏散协调和安置管理
MATCH (m:MetaTask {id: 'EM09'}) 
SET m.required_capabilities = ['EVACUATION_COORDINATION', 'SHELTER_MANAGEMENT'];

// EM10: 被困人员救援 - 需要结构救援、重型起吊、急救
MATCH (m:MetaTask {id: 'EM10'}) 
SET m.required_capabilities = ['STRUCTURAL_RESCUE', 'HEAVY_LIFTING', 'EMERGENCY_TREATMENT'];

// EM11: 废墟挖掘与破拆 - 需要拆除、重型起吊、建筑支撑
MATCH (m:MetaTask {id: 'EM11'}) 
SET m.required_capabilities = ['DEMOLITION', 'HEAVY_LIFTING', 'BUILDING_SHORING'];

// EM12: 搜救犬搜索 - 需要生命探测
MATCH (m:MetaTask {id: 'EM12'}) 
SET m.required_capabilities = ['LIFE_DETECTION'];

// EM13: 机器人狭小空间探测 - 需要狭小空间救援和生命探测
MATCH (m:MetaTask {id: 'EM13'}) 
SET m.required_capabilities = ['CONFINED_SPACE_RESCUE', 'LIFE_DETECTION'];

// EM14: 伤员现场急救 - 需要急救和分诊
MATCH (m:MetaTask {id: 'EM14'}) 
SET m.required_capabilities = ['EMERGENCY_TREATMENT', 'MEDICAL_TRIAGE'];

// EM15: 伤员转运后送 - 需要伤员转运
MATCH (m:MetaTask {id: 'EM15'}) 
SET m.required_capabilities = ['PATIENT_TRANSPORT'];

// EM16: 交通管制与道路抢通 - 需要道路清障
MATCH (m:MetaTask {id: 'EM16'}) 
SET m.required_capabilities = ['ROAD_CLEARANCE'];

// EM17: 燃气管网关阀 - 需要危化品封堵
MATCH (m:MetaTask {id: 'EM17'}) 
SET m.required_capabilities = ['HAZMAT_CONTAINMENT'];

// EM18: 电力切断与恢复 - 需要指挥协调
MATCH (m:MetaTask {id: 'EM18'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

// EM19: 消防灭火作业 - 需要灭火
MATCH (m:MetaTask {id: 'EM19'}) 
SET m.required_capabilities = ['FIRE_SUPPRESSION'];

// EM20-EM32: 其他任务（如果存在）
MATCH (m:MetaTask {id: 'EM20'}) 
SET m.required_capabilities = ['FIRE_SUPPRESSION', 'FIRE_SEARCH_RESCUE'];

MATCH (m:MetaTask {id: 'EM21'}) 
SET m.required_capabilities = ['WATER_RESCUE', 'SWIFT_WATER_RESCUE'];

MATCH (m:MetaTask {id: 'EM22'}) 
SET m.required_capabilities = ['WATER_RESCUE'];

MATCH (m:MetaTask {id: 'EM23'}) 
SET m.required_capabilities = ['HAZMAT_DETECTION', 'HAZMAT_CONTAINMENT'];

MATCH (m:MetaTask {id: 'EM24'}) 
SET m.required_capabilities = ['DECONTAMINATION'];

MATCH (m:MetaTask {id: 'EM25'}) 
SET m.required_capabilities = ['SHELTER_MANAGEMENT'];

MATCH (m:MetaTask {id: 'EM26'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

MATCH (m:MetaTask {id: 'EM27'}) 
SET m.required_capabilities = ['COMMUNICATION_SUPPORT', 'SATELLITE_COMM'];

MATCH (m:MetaTask {id: 'EM28'}) 
SET m.required_capabilities = ['VOLUNTEER_SUPPORT'];

MATCH (m:MetaTask {id: 'EM29'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

MATCH (m:MetaTask {id: 'EM30'}) 
SET m.required_capabilities = ['COMMAND_COORDINATION'];

MATCH (m:MetaTask {id: 'EM31'}) 
SET m.required_capabilities = ['TRAUMA_CARE', 'SURGERY'];

MATCH (m:MetaTask {id: 'EM32'}) 
SET m.required_capabilities = ['EMERGENCY_TREATMENT'];
