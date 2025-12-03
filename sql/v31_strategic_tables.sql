-- =============================================================================
-- v31_strategic_tables.sql - 战略层配置表
-- 新增表: safety_rules, transport_capacity, report_templates, rescue_module_equipment
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. config.safety_rules - 安全规则表（支持JSON条件）
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS config.safety_rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    rule_type VARCHAR(10) NOT NULL CHECK (rule_type IN ('hard', 'soft')),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    condition JSONB NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('block', 'warn')),
    message TEXT NOT NULL,
    priority INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE config.safety_rules IS '安全规则表，支持JSON条件匹配';
COMMENT ON COLUMN config.safety_rules.rule_type IS '规则类型: hard=硬规则(一票否决), soft=软规则(警告)';
COMMENT ON COLUMN config.safety_rules.condition IS 'JSON条件表达式，如 {"disaster_type": "fire", "has_gas_leak": true}';
COMMENT ON COLUMN config.safety_rules.action IS '动作: block=阻止, warn=警告';

-- 初始数据: 安全规则
INSERT INTO config.safety_rules (rule_id, rule_type, name, description, condition, action, message, priority) VALUES
-- 硬规则 (hard) - 一票否决
('SR-HARD-001', 'hard', '燃气泄漏禁止明火', '火灾现场存在燃气泄漏时，禁止使用明火设备', 
 '{"disaster_type": "fire", "has_gas_leak": true}', 'block', 
 '【严重安全风险】火灾现场检测到燃气泄漏，禁止使用任何明火设备', 100),

('SR-HARD-002', 'hard', '危化品现场防护', '危化品泄漏现场必须配备防护装备', 
 '{"disaster_type": "hazmat", "has_toxic_gas": true}', 'block', 
 '【严重安全风险】危化品现场检测到有毒气体，必须配备A级防护装备', 100),

('SR-HARD-003', 'hard', '建筑坍塌二次风险', '建筑严重受损时禁止进入内部', 
 '{"has_building_collapse": true, "structural_stability": "unstable"}', 'block', 
 '【严重安全风险】建筑结构不稳定，禁止进入内部，需先进行加固', 100),

('SR-HARD-004', 'hard', '余震期间限制进入', '余震频繁时限制进入危险建筑', 
 '{"disaster_type": "earthquake", "aftershock_risk": "high"}', 'block', 
 '【严重安全风险】余震风险较高，暂停进入受损建筑内部搜救', 90),

('SR-HARD-005', 'hard', '洪水水位超限', '水位超过安全线时禁止涉水救援', 
 '{"disaster_type": "flood", "water_level_danger": true}', 'block', 
 '【严重安全风险】洪水水位超过安全线，禁止徒步涉水救援', 90),

-- 软规则 (soft) - 警告但不阻止
('SR-SOFT-001', 'soft', '夜间作业提醒', '夜间作业需加强照明和安全措施', 
 '{"is_night_operation": true}', 'warn', 
 '【安全提醒】夜间作业，请确保充足照明和安全警戒', 50),

('SR-SOFT-002', 'soft', '恶劣天气提醒', '恶劣天气条件下注意安全', 
 '{"weather_condition": "severe"}', 'warn', 
 '【安全提醒】当前天气条件恶劣，请加强安全防护', 50),

('SR-SOFT-003', 'soft', '人员疲劳提醒', '连续作业时间过长', 
 '{"continuous_operation_hours": {"$gt": 8}}', 'warn', 
 '【安全提醒】连续作业超过8小时，建议轮换休息', 40),

('SR-SOFT-004', 'soft', '通信不畅提醒', '通信信号弱时需加强联络', 
 '{"communication_status": "weak"}', 'warn', 
 '【安全提醒】通信信号较弱，请加强联络确认', 40),

('SR-SOFT-005', 'soft', '资源不足警告', '资源配置未达到推荐标准', 
 '{"resource_coverage": {"$lt": 0.8}}', 'warn', 
 '【资源警告】当前资源配置低于推荐标准的80%', 30)
ON CONFLICT (rule_id) DO UPDATE SET
    rule_type = EXCLUDED.rule_type,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    condition = EXCLUDED.condition,
    action = EXCLUDED.action,
    message = EXCLUDED.message,
    priority = EXCLUDED.priority,
    updated_at = NOW();

-- -----------------------------------------------------------------------------
-- 2. config.transport_capacity - 运力参数表
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS config.transport_capacity (
    transport_type VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    capacity_per_unit INT NOT NULL,
    capacity_unit VARCHAR(20) DEFAULT '人',
    speed_kmh INT NOT NULL,
    max_distance_km INT,
    availability_hours VARCHAR(50),
    constraints JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE config.transport_capacity IS '运力参数配置表';
COMMENT ON COLUMN config.transport_capacity.capacity_per_unit IS '单位运力（人数或吨数）';
COMMENT ON COLUMN config.transport_capacity.constraints IS '约束条件，如天气限制、场地要求等';

-- 初始数据: 运力参数
INSERT INTO config.transport_capacity (transport_type, name, description, capacity_per_unit, capacity_unit, speed_kmh, max_distance_km, availability_hours, constraints) VALUES
('helicopter', '直升机', '中型运输直升机', 15, '人', 200, 500, '06:00-18:00', 
 '{"weather_limit": "visibility > 3km", "landing_area": "50m x 50m", "altitude_limit": 4000}'),

('heavy_helicopter', '重型直升机', '重型运输直升机', 30, '人', 180, 400, '06:00-18:00', 
 '{"weather_limit": "visibility > 5km", "landing_area": "80m x 80m", "altitude_limit": 3500}'),

('road_truck', '公路运输车', '重型运输卡车', 25, '人', 60, 1000, '24h', 
 '{"road_condition": "passable", "bridge_limit": "40t"}'),

('road_bus', '大巴车', '大型客运车辆', 45, '人', 80, 500, '24h', 
 '{"road_condition": "good", "tunnel_height": "4m"}'),

('airdrop', '空投', '固定翼飞机空投', 5000, 'kg', 400, 2000, '24h', 
 '{"weather_limit": "wind < 15m/s", "drop_zone": "open_area"}'),

('boat', '冲锋舟', '水上救援艇', 8, '人', 30, 50, '24h', 
 '{"water_depth": "> 0.5m", "current_speed": "< 3m/s"}'),

('amphibious', '两栖车', '水陆两栖车辆', 12, '人', 40, 200, '24h', 
 '{"water_depth": "< 2m", "terrain": "flat"}'
)
ON CONFLICT (transport_type) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    capacity_per_unit = EXCLUDED.capacity_per_unit,
    capacity_unit = EXCLUDED.capacity_unit,
    speed_kmh = EXCLUDED.speed_kmh,
    max_distance_km = EXCLUDED.max_distance_km,
    availability_hours = EXCLUDED.availability_hours,
    constraints = EXCLUDED.constraints,
    updated_at = NOW();

-- -----------------------------------------------------------------------------
-- 3. config.report_templates - 报告模板表
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS config.report_templates (
    template_id VARCHAR(50) PRIMARY KEY,
    report_type VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    template TEXT NOT NULL,
    variables JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE config.report_templates IS '报告模板表';
COMMENT ON COLUMN config.report_templates.report_type IS '报告类型: initial=初报, update=续报, daily=日报';
COMMENT ON COLUMN config.report_templates.variables IS '模板变量定义';

-- 初始数据: 报告模板
INSERT INTO config.report_templates (template_id, report_type, name, description, template, variables) VALUES
('TPL-INITIAL-001', 'initial', '灾情初报模板', '灾害发生后首次上报的标准模板',
'# 灾情初报

## 基本信息
- 灾害类型: {{disaster_type}}
- 发生时间: {{event_time}}
- 发生地点: {{location}}
- 影响范围: {{affected_area}}

## 灾情概况
{{disaster_summary}}

## 人员伤亡情况
- 预估被困人数: {{estimated_trapped}}
- 已确认伤亡: {{confirmed_casualties}}

## 已激活任务域
{{#each active_domains}}
- {{this.name}} (优先级: {{this.priority}})
{{/each}}

## 已调派资源
{{#each recommended_modules}}
- {{this.name}}: {{this.personnel}}人
{{/each}}

## 当前阶段
{{current_phase}}

## 下一步行动
{{next_actions}}

---
报告生成时间: {{report_time}}
', '{"disaster_type": "string", "event_time": "datetime", "location": "string", "affected_area": "string", "disaster_summary": "string", "estimated_trapped": "number", "confirmed_casualties": "number", "active_domains": "array", "recommended_modules": "array", "current_phase": "string", "next_actions": "string", "report_time": "datetime"}'),

('TPL-UPDATE-001', 'update', '灾情续报模板', '灾情进展更新报告模板',
'# 灾情续报 (第{{update_number}}期)

## 更新时间
{{update_time}}

## 态势变化
{{situation_update}}

## 救援进展
- 已搜救人数: {{rescued_count}}
- 仍在搜救: {{ongoing_search}}

## 资源调整
{{resource_changes}}

## 安全提醒
{{#each safety_warnings}}
- {{this}}
{{/each}}

## 下阶段重点
{{next_focus}}

---
报告生成时间: {{report_time}}
', '{"update_number": "number", "update_time": "datetime", "situation_update": "string", "rescued_count": "number", "ongoing_search": "string", "resource_changes": "string", "safety_warnings": "array", "next_focus": "string", "report_time": "datetime"}'),

('TPL-DAILY-001', 'daily', '救援日报模板', '每日救援工作汇总报告',
'# 救援日报

## 报告日期
{{report_date}}

## 今日工作概况
{{daily_summary}}

## 任务完成情况
{{#each task_completion}}
- {{this.domain}}: 完成率 {{this.completion_rate}}%
{{/each}}

## 资源使用情况
{{resource_usage}}

## 明日计划
{{tomorrow_plan}}

## 问题与建议
{{issues_and_suggestions}}

---
报告生成时间: {{report_time}}
', '{"report_date": "date", "daily_summary": "string", "task_completion": "array", "resource_usage": "string", "tomorrow_plan": "string", "issues_and_suggestions": "string", "report_time": "datetime"}'
)
ON CONFLICT (template_id) DO UPDATE SET
    report_type = EXCLUDED.report_type,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    template = EXCLUDED.template,
    variables = EXCLUDED.variables,
    updated_at = NOW();

-- -----------------------------------------------------------------------------
-- 4. config.rescue_module_equipment - 模块装备清单表
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS config.rescue_module_equipment (
    module_id VARCHAR(50) NOT NULL,
    equipment_type VARCHAR(100) NOT NULL,
    equipment_name VARCHAR(200) NOT NULL,
    quantity INT NOT NULL,
    unit VARCHAR(20) DEFAULT '台',
    is_essential BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (module_id, equipment_type)
);

COMMENT ON TABLE config.rescue_module_equipment IS '模块装备清单表';
COMMENT ON COLUMN config.rescue_module_equipment.is_essential IS '是否必备装备';

-- 初始数据: 模块装备清单
INSERT INTO config.rescue_module_equipment (module_id, equipment_type, equipment_name, quantity, unit, is_essential, description) VALUES
-- 废墟搜救模块装备
('ruins_search', 'life_detector', '生命探测仪', 4, '台', TRUE, '雷达/音频生命探测设备'),
('ruins_search', 'search_camera', '蛇眼探测仪', 3, '台', TRUE, '可视化搜索设备'),
('ruins_search', 'cutting_tool', '液压剪切器', 4, '套', TRUE, '液压破拆工具'),
('ruins_search', 'support_kit', '支撑器材', 10, '套', TRUE, '木支撑/气垫等'),
('ruins_search', 'lighting', '照明设备', 6, '套', FALSE, '移动照明灯组'),

-- 重型破拆模块装备
('heavy_rescue', 'excavator', '挖掘机', 2, '台', TRUE, '中型挖掘机'),
('heavy_rescue', 'loader', '装载机', 2, '台', TRUE, '轮式装载机'),
('heavy_rescue', 'crane', '起重机', 1, '台', FALSE, '汽车起重机'),
('heavy_rescue', 'breaker', '破碎锤', 2, '台', TRUE, '液压破碎锤'),
('heavy_rescue', 'generator', '发电机', 2, '台', TRUE, '移动发电机组'),

-- 医疗前突模块装备
('medical_forward', 'ambulance', '救护车', 2, '辆', TRUE, '急救型救护车'),
('medical_forward', 'medical_kit', '急救包', 20, '套', TRUE, '标准急救包'),
('medical_forward', 'stretcher', '担架', 10, '副', TRUE, '折叠担架'),
('medical_forward', 'defibrillator', 'AED除颤仪', 2, '台', TRUE, '自动体外除颤器'),
('medical_forward', 'oxygen', '氧气设备', 5, '套', TRUE, '便携式氧气瓶'),

-- 水域救援模块装备
('water_rescue', 'boat', '冲锋舟', 4, '艘', TRUE, '橡皮冲锋舟'),
('water_rescue', 'life_jacket', '救生衣', 50, '件', TRUE, '专业救生衣'),
('water_rescue', 'throw_bag', '抛投器', 4, '套', TRUE, '救生抛投设备'),
('water_rescue', 'dry_suit', '干式潜水服', 10, '套', TRUE, '水域作业防护服'),

-- 危化品处置模块装备
('hazmat_response', 'detector', '气体检测仪', 6, '台', TRUE, '多参数气体检测'),
('hazmat_response', 'suit_a', 'A级防护服', 12, '套', TRUE, '全封闭防护服'),
('hazmat_response', 'decon_kit', '洗消设备', 2, '套', TRUE, '便携式洗消站'),
('hazmat_response', 'containment', '堵漏器材', 5, '套', TRUE, '各类堵漏工具')
ON CONFLICT (module_id, equipment_type) DO UPDATE SET
    equipment_name = EXCLUDED.equipment_name,
    quantity = EXCLUDED.quantity,
    unit = EXCLUDED.unit,
    is_essential = EXCLUDED.is_essential,
    description = EXCLUDED.description;

-- -----------------------------------------------------------------------------
-- 5. 创建索引
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_safety_rules_type ON config.safety_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_safety_rules_active ON config.safety_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_transport_capacity_active ON config.transport_capacity(is_active);
CREATE INDEX IF NOT EXISTS idx_report_templates_type ON config.report_templates(report_type);
CREATE INDEX IF NOT EXISTS idx_module_equipment_module ON config.rescue_module_equipment(module_id);
