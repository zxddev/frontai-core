-- 应急救灾协同决策系统数据库
-- 支持场景：地震主灾、次生火灾、危化品泄漏、山洪泥石流、暴雨内涝

-- CREATE DATABASE emergency_planner;
-- \c emergency_planner

CREATE SCHEMA IF NOT EXISTS planning;

-- ========================================
-- 1. 元任务表（MT）
-- ========================================
CREATE TABLE planning.tasks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,                    -- sensing/search_rescue/medical/hazmat/firefighting/drainage/coordination等
  precondition TEXT NOT NULL,
  effect TEXT NOT NULL,
  outputs TEXT[] DEFAULT '{}'::TEXT[],       -- 任务产出物
  typical_scenes TEXT[] NOT NULL,
  phase TEXT NOT NULL,                       -- detect/assess/plan/execute/monitor/recover
  duration_min INT NOT NULL DEFAULT 30,      -- 最短时长(分钟)
  duration_max INT NOT NULL DEFAULT 120,     -- 最长时长(分钟)
  required_capabilities TEXT[] DEFAULT '{}'::TEXT[],
  risk_level TEXT NOT NULL DEFAULT 'medium', -- low/medium/high
  requires_approval BOOLEAN DEFAULT FALSE,   -- 是否需要人工审批
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.tasks IS '应急救灾元任务库';
COMMENT ON COLUMN planning.tasks.category IS '任务类别：sensing感知/search_rescue搜救/medical医疗/hazmat危化品/firefighting消防/drainage排涝/coordination协调等';
COMMENT ON COLUMN planning.tasks.risk_level IS '任务风险等级：low低/medium中/high高';
COMMENT ON COLUMN planning.tasks.requires_approval IS '高风险任务是否需要指挥员审批';

-- ========================================
-- 2. 场景定义表
-- ========================================
CREATE TABLE planning.scenes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  triggers TEXT[] NOT NULL,                  -- 触发条件
  typical_tasks TEXT[] NOT NULL,             -- 典型任务列表
  priority_objectives TEXT[] NOT NULL,       -- 优先目标
  response_level TEXT NOT NULL DEFAULT 'III',-- 响应级别 I/II/III/IV
  max_response_time INT,                     -- 最大响应时间(分钟)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.scenes IS '应急场景定义';
COMMENT ON COLUMN planning.scenes.response_level IS '响应级别：I特别重大/II重大/III较大/IV一般';

-- ========================================
-- 3. 资源/力量表
-- ========================================
CREATE TABLE planning.resources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,                        -- 资源类型
  category TEXT NOT NULL,                    -- fire/rescue/medical/police/utility/uav/robot等
  org TEXT NOT NULL,                         -- 所属单位
  capabilities TEXT[] NOT NULL,
  location POINT NOT NULL,                   -- 使用PostGIS点类型
  location_text TEXT NOT NULL,               -- "lon,lat" 文本格式备用
  status TEXT NOT NULL DEFAULT 'available',  -- available/dispatched/busy/maintenance/offline
  capacity JSONB DEFAULT '{}'::JSONB,        -- 容量信息(人员数、载重等)
  constraints JSONB DEFAULT '{}'::JSONB,     -- 约束条件(行驶距离、道路等级等)
  properties JSONB DEFAULT '{}'::JSONB,      -- 其他属性
  last_heartbeat TIMESTAMPTZ,                -- 最后心跳时间
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.resources IS '应急救援资源/力量';
COMMENT ON COLUMN planning.resources.category IS '资源类别：fire消防/rescue救援/medical医疗/police公安/utility市政/uav无人机/robot机器人等';
COMMENT ON COLUMN planning.resources.status IS '资源状态：available可用/dispatched已调度/busy执行中/maintenance维护/offline离线';

CREATE INDEX idx_resources_location ON planning.resources USING GIST(location);
CREATE INDEX idx_resources_status ON planning.resources(status);
CREATE INDEX idx_resources_category ON planning.resources(category);

-- ========================================
-- 4. 能力本体表
-- ========================================
CREATE TABLE planning.capabilities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,                    -- sensing/mobility/operation/communication/support
  description TEXT NOT NULL,
  metrics JSONB NOT NULL,                    -- 度量指标
  parent_id TEXT REFERENCES planning.capabilities(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.capabilities IS '能力本体定义';

-- ========================================
-- 5. 任务依赖链表
-- ========================================
CREATE TABLE planning.task_chains (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scene_id TEXT REFERENCES planning.scenes(id),
  description TEXT,
  tasks TEXT[] NOT NULL,                     -- 任务序列
  dependencies JSONB NOT NULL,               -- 任务依赖关系 {"EM03": ["EM01"]}
  parallel_groups JSONB DEFAULT '[]'::JSONB, -- 可并行任务组
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.task_chains IS '任务依赖链定义';

-- ========================================
-- 6. 规则主表
-- ========================================
CREATE TABLE planning.rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,                    -- safety/resource/coordination/decision
  rule_type TEXT NOT NULL,                   -- hard硬约束/soft软约束/preference偏好
  description TEXT,
  priority INT NOT NULL DEFAULT 100,         -- 优先级，越大越优先
  scenes TEXT[] NULL,                        -- 适用场景，NULL表示全局
  active BOOLEAN NOT NULL DEFAULT TRUE,
  version INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.rules IS '应急规则主表';
COMMENT ON COLUMN planning.rules.rule_type IS '规则类型：hard硬约束(一票否决)/soft软约束(扣分)/preference偏好(加分)';

-- ========================================
-- 7. 规则触发条件表
-- ========================================
CREATE TABLE planning.rule_triggers (
  id SERIAL PRIMARY KEY,
  rule_id TEXT REFERENCES planning.rules(id) ON DELETE CASCADE,
  condition JSONB NOT NULL,                  -- 触发条件
  condition_expr TEXT,                       -- 条件表达式(可选)
  scope TEXT DEFAULT 'scene'                 -- scene/task/resource/global
);

-- ========================================
-- 8. 规则动作表
-- ========================================
CREATE TABLE planning.rule_actions (
  id SERIAL PRIMARY KEY,
  rule_id TEXT REFERENCES planning.rules(id) ON DELETE CASCADE,
  action_type TEXT NOT NULL,                 -- veto否决/penalty扣分/bonus加分/inject_task注入任务/require_approval需审批
  action JSONB NOT NULL,
  explanation_template TEXT                  -- 解释模板
);

-- ========================================
-- 9. 硬约束规则表（生命安全等一票否决）
-- ========================================
CREATE TABLE planning.hard_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,                    -- life_safety/personnel_safety/legal/technical
  condition TEXT NOT NULL,
  decision TEXT NOT NULL,                    -- reject/require_approval/escalate
  explanation TEXT NOT NULL,
  priority INT NOT NULL DEFAULT 1000,        -- 硬约束优先级最高
  scenes TEXT[] NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.hard_rules IS '硬约束规则（一票否决）';
COMMENT ON COLUMN planning.hard_rules.category IS 'life_safety生命安全/personnel_safety人员安全/legal法规/technical技术';

-- ========================================
-- 10. 决策权重配置表
-- ========================================
CREATE TABLE planning.decision_weights (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  -- 目标权重
  weight_life_safety NUMERIC NOT NULL DEFAULT 0.35,    -- 生命安全
  weight_time NUMERIC NOT NULL DEFAULT 0.25,           -- 时效性
  weight_resource NUMERIC NOT NULL DEFAULT 0.15,       -- 资源效率
  weight_risk NUMERIC NOT NULL DEFAULT 0.15,           -- 风险控制
  weight_coverage NUMERIC NOT NULL DEFAULT 0.10,       -- 覆盖完整性
  -- 权重解释
  interpretation JSONB NOT NULL DEFAULT '{}'::JSONB,
  -- 适用场景
  scenes TEXT[] NULL,
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.decision_weights IS '决策偏好权重配置';

-- ========================================
-- 11. 方案评分表
-- ========================================
CREATE TABLE planning.plan_scores (
  id SERIAL PRIMARY KEY,
  plan_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  weight_profile_id TEXT REFERENCES planning.decision_weights(id),
  -- 各维度得分
  life_safety_score NUMERIC,
  time_score NUMERIC,
  resource_score NUMERIC,
  risk_score NUMERIC,
  coverage_score NUMERIC,
  -- 总分
  total_score NUMERIC,
  -- 是否通过硬约束
  passed_hard_rules BOOLEAN DEFAULT TRUE,
  failed_hard_rules TEXT[] DEFAULT '{}'::TEXT[],
  -- 追溯
  trace_id TEXT,
  explanation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_plan_scores_scene ON planning.plan_scores(scene_id);
CREATE INDEX idx_plan_scores_best ON planning.plan_scores(total_score DESC);

-- ========================================
-- 12. 调度记录表
-- ========================================
CREATE TABLE planning.dispatch_records (
  id SERIAL PRIMARY KEY,
  plan_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  dispatch_time TIMESTAMPTZ NOT NULL DEFAULT now(),
  eta_minutes INT,
  actual_arrival TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'dispatched',  -- dispatched/en_route/arrived/executing/completed/cancelled
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dispatch_records_plan ON planning.dispatch_records(plan_id);
CREATE INDEX idx_dispatch_records_resource ON planning.dispatch_records(resource_id);

-- ========================================
-- 13. 事件/灾情记录表
-- ========================================
CREATE TABLE planning.incidents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scene_id TEXT REFERENCES planning.scenes(id),
  level TEXT NOT NULL,                        -- I/II/III/IV
  location POINT NOT NULL,
  location_text TEXT NOT NULL,
  affected_area NUMERIC,                      -- 影响面积(km2)
  estimated_casualties INT,
  status TEXT NOT NULL DEFAULT 'active',      -- active/contained/resolved
  start_time TIMESTAMPTZ NOT NULL DEFAULT now(),
  end_time TIMESTAMPTZ,
  properties JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incidents_location ON planning.incidents USING GIST(location);
CREATE INDEX idx_incidents_status ON planning.incidents(status);

-- ========================================
-- 14. 审批记录表（人在回路）
-- ========================================
CREATE TABLE planning.approvals (
  id SERIAL PRIMARY KEY,
  plan_id TEXT NOT NULL,
  task_id TEXT,
  approval_type TEXT NOT NULL,               -- plan_approval/task_approval/resource_override
  status TEXT NOT NULL DEFAULT 'pending',    -- pending/approved/rejected/timeout
  requested_by TEXT,
  approved_by TEXT,
  reason TEXT,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  responded_at TIMESTAMPTZ,
  timeout_minutes INT DEFAULT 5
);

CREATE INDEX idx_approvals_status ON planning.approvals(status);

-- ========================================
-- 基础数据：场景定义
-- ========================================
INSERT INTO planning.scenes (id, name, description, triggers, typical_tasks, priority_objectives, response_level, max_response_time) VALUES
  ('S1', '地震主灾', '地震导致建筑倒塌、人员被埋压、基础设施损毁', 
   ARRAY['earthquake_alert', 'seismic_intensity>=6'], 
   ARRAY['EM01','EM02','EM03','EM04','EM05','EM06','EM07','EM08','EM09','EM10','EM11','EM12','EM13','EM14','EM15','EM16','EM24','EM25','EM26','EM27','EM28','EM29','EM30'],
   ARRAY['life_safety', 'search_rescue', 'medical_support'], 'I', 30),
  
  ('S2', '地震次生火灾', '地震引发燃气泄漏、电气短路导致火灾',
   ARRAY['fire_detected', 'gas_leak_alert'],
   ARRAY['EM01','EM04','EM05','EM07','EM08','EM17','EM18','EM19','EM14','EM15','EM16','EM26','EM27'],
   ARRAY['fire_control', 'gas_shutoff', 'evacuation'], 'II', 15),
  
  ('S3', '地震次生危化品泄漏', '地震导致化工设施、储罐破损泄漏',
   ARRAY['hazmat_leak_detected', 'chemical_alarm'],
   ARRAY['EM01','EM04','EM05','EM07','EM08','EM20','EM21','EM22','EM14','EM15','EM16','EM26','EM27'],
   ARRAY['leak_containment', 'evacuation', 'decontamination'], 'II', 20),
  
  ('S4', '山洪泥石流', '暴雨或地震引发山洪、泥石流、滑坡',
   ARRAY['flash_flood_warning', 'debris_flow_alert', 'heavy_rain_alert'],
   ARRAY['EM01','EM02','EM04','EM05','EM07','EM08','EM09','EM23','EM10','EM14','EM15','EM16','EM26','EM27','EM28'],
   ARRAY['early_warning', 'evacuation', 'road_clearance'], 'II', 30),
  
  ('S5', '暴雨内涝', '强降雨导致城区积水、交通瘫痪、人员被困',
   ARRAY['heavy_rain_alert', 'waterlogging_report'],
   ARRAY['EM01','EM02','EM04','EM07','EM08','EM09','EM31','EM32','EM10','EM14','EM15','EM16','EM26','EM27'],
   ARRAY['life_safety', 'drainage', 'traffic_restoration'], 'III', 60);

-- ========================================
-- 基础数据：元任务
-- ========================================
INSERT INTO planning.tasks (id, name, category, precondition, effect, outputs, typical_scenes, phase, duration_min, duration_max, required_capabilities, risk_level, requires_approval) VALUES
  ('EM01', '无人机广域侦察', 'sensing', '无人机可用且天气条件允许', '获取灾区宏观态势图像', ARRAY['area_overview','damage_map','road_status'], ARRAY['S1','S2','S3','S4','S5'], 'detect', 10, 30, ARRAY['aerial_perception','image_transmission'], 'low', FALSE),
  ('EM02', '地震监测数据分析', 'sensing', '地震台网数据可用', '确定震中、震级、烈度分布', ARRAY['epicenter','magnitude','intensity_map','aftershock_forecast'], ARRAY['S1','S4','S5'], 'detect', 2, 10, ARRAY['seismic_analysis','data_fusion'], 'low', FALSE),
  ('EM03', '建筑倒塌区域识别', 'sensing', '已获取灾区图像或现场报告', '标定倒塌建筑位置和范围', ARRAY['collapse_zones','building_damage_level'], ARRAY['S1'], 'detect', 10, 30, ARRAY['image_analysis','structural_assessment'], 'low', FALSE),
  ('EM04', '灾情快速评估', 'assessment', '已获取态势数据', '形成灾情等级和影响范围评估', ARRAY['disaster_level','affected_area','estimated_casualties','priority_zones'], ARRAY['S1','S2','S3','S4','S5'], 'assess', 5, 15, ARRAY['situation_analysis','gis_processing'], 'low', FALSE),
  ('EM05', '次生灾害风险研判', 'assessment', '灾情评估完成', '识别次生灾害风险点和演化趋势', ARRAY['secondary_hazard_list','risk_zones','evolution_forecast'], ARRAY['S1','S2','S3','S4'], 'assess', 10, 30, ARRAY['hazard_analysis','risk_modeling'], 'low', FALSE),
  ('EM06', '埋压人员生命探测', 'search_rescue', '已标定倒塌区域', '发现并定位埋压人员', ARRAY['victim_locations','victim_count_estimate','vital_signs'], ARRAY['S1'], 'detect', 15, 60, ARRAY['life_detection','acoustic_detection','thermal_imaging'], 'medium', FALSE),
  ('EM07', '救援力量调度', 'coordination', '灾情评估完成且资源可用', '救援力量到达指定位置', ARRAY['dispatch_orders','eta_list','resource_allocation'], ARRAY['S1','S2','S3','S4','S5'], 'plan', 5, 20, ARRAY['resource_scheduling','communication'], 'low', FALSE),
  ('EM08', '疏散路线规划', 'planning', '已识别危险区域和道路状况', '生成安全疏散路径', ARRAY['evacuation_routes','assembly_points','shelter_locations'], ARRAY['S1','S2','S3','S4','S5'], 'plan', 5, 15, ARRAY['route_planning','traffic_analysis'], 'low', FALSE),
  ('EM09', '群众疏散转移', 'evacuation', '疏散路线已规划且引导力量就位', '群众有序撤离危险区域', ARRAY['evacuation_progress','evacuee_count','shelter_status'], ARRAY['S1','S4','S5'], 'execute', 30, 180, ARRAY['crowd_guidance','public_announcement','transport'], 'medium', FALSE),
  ('EM10', '被困人员救援', 'search_rescue', '已定位被困人员且救援力量就位', '被困人员脱困', ARRAY['rescued_count','rescue_status'], ARRAY['S1','S4','S5'], 'execute', 30, 240, ARRAY['rescue_operation','heavy_equipment','medical_support'], 'high', TRUE),
  ('EM11', '废墟挖掘与破拆', 'search_rescue', '倒塌区域已确认安全或可控', '开辟救援通道接近埋压人员', ARRAY['access_path','debris_removed'], ARRAY['S1'], 'execute', 60, 480, ARRAY['demolition','heavy_machinery','structural_shoring'], 'high', TRUE),
  ('EM12', '搜救犬搜索', 'search_rescue', '搜救犬队到位', '扩大生命探测覆盖范围', ARRAY['search_coverage','alert_locations'], ARRAY['S1'], 'detect', 30, 120, ARRAY['canine_search'], 'medium', FALSE),
  ('EM13', '机器人狭小空间探测', 'search_rescue', '机器人可用且有狭小空间需探测', '获取人员无法进入区域的信息', ARRAY['interior_imagery','victim_detection'], ARRAY['S1'], 'detect', 15, 60, ARRAY['robot_operation','confined_space_sensing'], 'low', FALSE),
  ('EM14', '伤员现场急救', 'medical', '医疗力量到位', '伤员得到初步救治和分诊', ARRAY['treated_count','triage_results'], ARRAY['S1','S2','S3','S4','S5'], 'execute', 5, 30, ARRAY['emergency_medical','triage'], 'medium', FALSE),
  ('EM15', '伤员转运后送', 'medical', '伤员已分诊且转运通道畅通', '伤员送达医疗机构', ARRAY['transport_count','hospital_assignments'], ARRAY['S1','S2','S3','S4','S5'], 'execute', 15, 90, ARRAY['medical_transport','route_coordination'], 'medium', FALSE),
  ('EM16', '交通管制与道路抢通', 'traffic', '道路损毁情况已评估', '保障应急通道畅通', ARRAY['traffic_status','cleared_routes','detour_routes'], ARRAY['S1','S2','S3','S4','S5'], 'execute', 30, 180, ARRAY['traffic_control','road_repair','debris_clearance'], 'medium', FALSE),
  ('EM17', '燃气管网关阀', 'utility', '燃气泄漏风险已识别', '切断泄漏区域燃气供应', ARRAY['shutoff_status','isolated_area'], ARRAY['S1','S2'], 'execute', 10, 60, ARRAY['gas_operation','valve_control'], 'high', TRUE),
  ('EM18', '电力切断与恢复', 'utility', '电力设施损毁情况已评估', '消除电击风险或恢复关键区域供电', ARRAY['power_status','outage_area','restoration_progress'], ARRAY['S1','S2'], 'execute', 30, 240, ARRAY['power_operation','electrical_safety'], 'high', TRUE),
  ('EM19', '消防灭火作业', 'firefighting', '消防力量到位且水源可用', '控制或扑灭火势', ARRAY['fire_status','water_usage','controlled_area'], ARRAY['S2'], 'execute', 30, 240, ARRAY['fire_suppression','water_supply'], 'high', FALSE),
  ('EM20', '危化品泄漏侦检', 'hazmat', '危化品泄漏报警或疑似泄漏', '确定泄漏物质种类、浓度和扩散范围', ARRAY['chemical_type','concentration_map','spread_forecast'], ARRAY['S3'], 'detect', 15, 60, ARRAY['chemical_detection','hazmat_identification'], 'high', FALSE),
  ('EM21', '危化品堵漏处置', 'hazmat', '专业处置队到位且防护到位', '泄漏源封堵或控制', ARRAY['leak_status','containment_result'], ARRAY['S3'], 'execute', 30, 180, ARRAY['hazmat_handling','leak_sealing'], 'high', TRUE),
  ('EM22', '洗消去污作业', 'hazmat', '污染区域已界定', '人员和装备去除污染', ARRAY['decon_count','area_clearance'], ARRAY['S3'], 'execute', 30, 120, ARRAY['decontamination','hazmat_disposal'], 'medium', FALSE),
  ('EM23', '山洪泥石流预警监测', 'monitoring', '监测设备在线或人工观测就位', '实时掌握山洪泥石流发展态势', ARRAY['water_level','debris_flow_status','warning_level'], ARRAY['S4'], 'detect', 5, 30, ARRAY['hydrological_monitoring','geological_monitoring'], 'medium', FALSE),
  ('EM24', '危险建筑排查加固', 'structure', '余震风险评估完成', '识别和处置危险建筑', ARRAY['unsafe_buildings','reinforcement_status'], ARRAY['S1'], 'execute', 60, 480, ARRAY['structural_assessment','temporary_shoring'], 'high', TRUE),
  ('EM25', '临时安置点设置', 'shelter', '安置需求已评估', '受灾群众得到临时安置', ARRAY['shelter_capacity','settled_count','supply_status'], ARRAY['S1'], 'recover', 60, 240, ARRAY['shelter_management','logistics_support'], 'low', FALSE),
  ('EM26', '信息发布与预警广播', 'communication', '信息审核完成', '公众获知灾情和应对指引', ARRAY['broadcast_coverage','public_awareness'], ARRAY['S1','S2','S3','S4','S5'], 'execute', 5, 15, ARRAY['public_notification','emergency_broadcast'], 'low', FALSE),
  ('EM27', '多部门协同指挥', 'coordination', '指挥体系建立', '各部门行动协调一致', ARRAY['coordination_status','task_assignments'], ARRAY['S1','S2','S3','S4','S5'], 'plan', 10, 30, ARRAY['command_control','inter_agency_coordination'], 'low', FALSE),
  ('EM28', '应急物资调配', 'logistics', '物资需求已明确', '救援物资送达指定地点', ARRAY['delivery_status','inventory_update'], ARRAY['S1','S4','S5'], 'execute', 30, 120, ARRAY['logistics_management','transport'], 'low', FALSE),
  ('EM29', '通信保障与恢复', 'infrastructure', '通信中断或不足', '保障现场通信畅通', ARRAY['comm_status','coverage_area'], ARRAY['S1'], 'execute', 30, 120, ARRAY['comm_support','network_deployment'], 'low', FALSE),
  ('EM30', '灾后评估与总结', 'assessment', '应急响应基本结束', '形成灾害损失和响应效果评估', ARRAY['damage_report','response_evaluation','lessons_learned'], ARRAY['S1'], 'recover', 120, 480, ARRAY['damage_assessment','report_generation'], 'low', FALSE),
  ('EM31', '排涝抽水作业', 'drainage', '排涝设备到位且积水点已确认', '降低积水水位', ARRAY['water_level_change','drainage_rate'], ARRAY['S5'], 'execute', 60, 480, ARRAY['water_pumping','drainage_management'], 'medium', FALSE),
  ('EM32', '积水点监测与预警', 'monitoring', '降雨持续或积水未消退', '实时掌握积水动态变化', ARRAY['waterlogging_map','depth_readings','trend_forecast'], ARRAY['S5'], 'monitor', 5, 30, ARRAY['water_level_monitoring','urban_drainage_analysis'], 'low', FALSE);

-- ========================================
-- 基础数据：能力本体
-- ========================================
INSERT INTO planning.capabilities (id, name, category, description, metrics) VALUES
  ('aerial_perception', '空中感知', 'sensing', '通过无人机等平台获取空中视角态势', '{"coverage_km2": "number", "resolution_m": "number", "update_interval_s": "number"}'),
  ('life_detection', '生命探测', 'sensing', '探测埋压或被困人员生命迹象', '{"detection_depth_m": "number", "accuracy": "number"}'),
  ('thermal_imaging', '热成像', 'sensing', '红外热成像探测', '{"resolution": "number", "range_m": "number"}'),
  ('seismic_analysis', '地震分析', 'sensing', '地震数据分析与余震预测', '{"accuracy": "number", "forecast_hours": "number"}'),
  ('situation_analysis', '态势分析', 'sensing', '综合态势研判', '{"update_interval_min": "number"}'),
  ('rescue_operation', '救援作业', 'operation', '实施人员救援', '{"capacity_person": "number", "speed": "number"}'),
  ('fire_suppression', '灭火作业', 'operation', '消防灭火能力', '{"water_flow_lpm": "number", "range_m": "number"}'),
  ('hazmat_handling', '危化品处置', 'operation', '危险化学品处置能力', '{"protection_level": "string", "chemicals": "array"}'),
  ('water_pumping', '排涝抽水', 'operation', '抽水排涝能力', '{"flow_rate_m3h": "number"}'),
  ('emergency_medical', '现场急救', 'operation', '紧急医疗救护', '{"capacity_patient": "number", "level": "string"}'),
  ('medical_transport', '医疗转运', 'mobility', '伤员转运能力', '{"capacity_patient": "number", "speed_kmh": "number"}'),
  ('traffic_control', '交通管制', 'operation', '道路交通管控', '{"coverage_km": "number"}'),
  ('command_control', '指挥控制', 'communication', '指挥协调能力', '{"channels": "number", "range_km": "number"}'),
  ('public_notification', '公众告知', 'communication', '公众信息发布', '{"coverage_population": "number", "channels": "array"}'),
  ('logistics_management', '物资管理', 'support', '应急物资调配', '{"capacity_ton": "number", "categories": "array"}');

-- ========================================
-- 基础数据：任务链
-- ========================================
INSERT INTO planning.task_chains (id, name, scene_id, description, tasks, dependencies, parallel_groups) VALUES
  ('CHAIN-EQ-MAIN', '地震搜救主链', 'S1', '地震发生后的标准搜救流程',
   ARRAY['EM02','EM01','EM03','EM04','EM05','EM06','EM07','EM11','EM10','EM14','EM15'],
   '{"EM01":["EM02"],"EM03":["EM01"],"EM04":["EM03"],"EM05":["EM04"],"EM06":["EM03"],"EM07":["EM04"],"EM11":["EM06"],"EM10":["EM11"],"EM14":["EM10"],"EM15":["EM14"]}',
   '[["EM06","EM12","EM13"],["EM17","EM18"]]'),
  
  ('CHAIN-FIRE', '次生火灾处置链', 'S2', '地震引发火灾的处置流程',
   ARRAY['EM01','EM04','EM05','EM17','EM18','EM19','EM08','EM09'],
   '{"EM04":["EM01"],"EM05":["EM04"],"EM17":["EM05"],"EM18":["EM05"],"EM19":["EM17"],"EM08":["EM05"],"EM09":["EM08"]}',
   '[]'),
  
  ('CHAIN-HAZMAT', '危化品泄漏处置链', 'S3', '地震引发危化品泄漏的处置流程',
   ARRAY['EM01','EM04','EM20','EM08','EM09','EM21','EM22'],
   '{"EM04":["EM01"],"EM20":["EM04"],"EM08":["EM20"],"EM09":["EM08"],"EM21":["EM20"],"EM22":["EM21"]}',
   '[]'),
  
  ('CHAIN-FLOOD', '山洪泥石流处置链', 'S4', '山洪泥石流灾害的处置流程',
   ARRAY['EM23','EM01','EM04','EM08','EM09','EM10','EM16'],
   '{"EM01":["EM23"],"EM04":["EM01"],"EM08":["EM04"],"EM09":["EM08"],"EM10":["EM04"],"EM16":["EM04"]}',
   '[]'),
  
  ('CHAIN-WATERLOG', '暴雨内涝处置链', 'S5', '城市暴雨内涝的处置流程',
   ARRAY['EM02','EM01','EM04','EM32','EM31','EM08','EM09','EM10','EM16'],
   '{"EM01":["EM02"],"EM04":["EM01"],"EM32":["EM04"],"EM31":["EM32"],"EM08":["EM04"],"EM09":["EM08"],"EM10":["EM04"],"EM16":["EM04"]}',
   '[]');

-- ========================================
-- 基础数据：硬约束规则（生命安全优先）
-- ========================================
INSERT INTO planning.hard_rules (id, name, category, condition, decision, explanation, priority, scenes) VALUES
  ('HR-001', '生命安全第一', 'life_safety', '任何方案必须优先保障生命安全', 'reject', '方案未将生命安全作为首要目标，违反生命至上原则', 1000, NULL),
  ('HR-002', '救援人员安全', 'personnel_safety', '救援人员进入高危区域前必须完成风险评估', 'require_approval', '高危区域作业需指挥员审批确认安全措施', 950, ARRAY['S1','S3']),
  ('HR-003', '危化品防护要求', 'personnel_safety', '进入危化品污染区必须佩戴规定防护装备', 'reject', '未满足防护要求，不得进入污染区', 980, ARRAY['S3']),
  ('HR-004', '余震风险管控', 'personnel_safety', '强余震预警期间暂停废墟内部救援', 'reject', '余震风险过高，暂停内部作业保护救援人员', 960, ARRAY['S1']),
  ('HR-005', '燃气泄漏区禁火', 'technical', '燃气泄漏区域禁止明火作业和电气操作', 'reject', '存在爆炸风险，禁止明火和电气操作', 990, ARRAY['S2']),
  ('HR-006', '疏散优先原则', 'life_safety', '危险区域群众疏散优先于财产保护', 'reject', '生命优先，必须先完成人员疏散', 970, NULL),
  ('HR-007', '医疗转运通道', 'life_safety', '重伤员转运通道必须保持畅通', 'escalate', '转运通道受阻需立即上报协调', 940, NULL),
  ('HR-008', '次生灾害监控', 'technical', '主灾处置期间必须持续监控次生灾害风险', 'require_approval', '未部署次生灾害监控的方案需审批', 920, ARRAY['S1']);

-- ========================================
-- 基础数据：决策权重配置
-- ========================================
INSERT INTO planning.decision_weights (id, name, description, weight_life_safety, weight_time, weight_resource, weight_risk, weight_coverage, interpretation, scenes, is_default) VALUES
  ('DW-DEFAULT', '默认均衡', '均衡考虑各项目标', 0.35, 0.25, 0.15, 0.15, 0.10, 
   '{"life_safety": "生命安全始终最高权重", "time": "时效性较重要", "resource": "资源效率适中", "risk": "风险控制适中", "coverage": "覆盖完整性兜底"}',
   NULL, TRUE),
  
  ('DW-EARTHQUAKE', '地震救援', '地震场景：生命搜救优先，时间紧迫', 0.40, 0.30, 0.10, 0.12, 0.08,
   '{"life_safety": "黄金72小时内生命搜救最优先", "time": "时间极其紧迫", "resource": "资源效率适度让步", "risk": "接受较高风险换取救援速度", "coverage": "聚焦重点区域"}',
   ARRAY['S1'], FALSE),
  
  ('DW-HAZMAT', '危化品处置', '危化品场景：风险控制和人员安全并重', 0.35, 0.20, 0.10, 0.25, 0.10,
   '{"life_safety": "生命安全优先", "time": "允许适当延长处置时间", "resource": "专业资源优先", "risk": "风险控制权重提升", "coverage": "确保污染区全覆盖"}',
   ARRAY['S3'], FALSE),
  
  ('DW-FLOOD', '洪涝应急', '洪涝场景：疏散转移优先', 0.38, 0.28, 0.12, 0.14, 0.08,
   '{"life_safety": "人员转移最优先", "time": "抢在水位上涨前", "resource": "舟艇资源关键", "risk": "水情变化风险", "coverage": "低洼区域优先"}',
   ARRAY['S4', 'S5'], FALSE);

-- ========================================
-- 基础数据：示例资源
-- ========================================
INSERT INTO planning.resources (id, name, type, category, org, capabilities, location, location_text, status, capacity, constraints, properties) VALUES
  ('UAV-001', '侦察无人机1号', 'reconnaissance_uav', 'uav', '应急管理局', ARRAY['aerial_perception','image_transmission'], POINT(121.47, 31.23), '121.47,31.23', 'available', '{"endurance_min": 60, "payload_kg": 2}', '{"max_wind_ms": 10, "min_visibility_m": 1000}', '{"model": "DJI M300"}'),
  ('UAV-002', '侦察无人机2号', 'reconnaissance_uav', 'uav', '应急管理局', ARRAY['aerial_perception','thermal_imaging'], POINT(121.50, 31.25), '121.50,31.25', 'available', '{"endurance_min": 45, "payload_kg": 1.5}', '{"max_wind_ms": 8}', '{"model": "DJI M30T"}'),
  ('FIRE-001', '消防车1号', 'fire_truck', 'fire', '消防救援支队', ARRAY['fire_suppression','water_supply'], POINT(121.45, 31.22), '121.45,31.22', 'available', '{"water_ton": 8, "crew": 6}', '{"road_class": ["main","secondary"]}', '{"type": "水罐车"}'),
  ('FIRE-002', '登高消防车', 'ladder_truck', 'fire', '消防救援支队', ARRAY['fire_suppression','aerial_rescue'], POINT(121.46, 31.21), '121.46,31.21', 'available', '{"max_height_m": 53, "crew": 4}', '{"road_class": ["main"]}', '{"type": "53米登高车"}'),
  ('RESCUE-001', '重型救援队', 'rescue_team', 'rescue', '消防救援支队', ARRAY['rescue_operation','demolition','heavy_machinery'], POINT(121.48, 31.24), '121.48,31.24', 'available', '{"personnel": 20, "equipment_ton": 15}', '{}', '{"specialty": "建筑坍塌救援"}'),
  ('RESCUE-002', '轻型救援队', 'rescue_team', 'rescue', '消防救援支队', ARRAY['rescue_operation','confined_space_sensing'], POINT(121.49, 31.23), '121.49,31.23', 'available', '{"personnel": 12}', '{}', '{"specialty": "狭小空间救援"}'),
  ('K9-001', '搜救犬队', 'search_dog_team', 'rescue', '消防救援支队', ARRAY['canine_search','life_detection'], POINT(121.47, 31.22), '121.47,31.22', 'available', '{"dogs": 4, "handlers": 4}', '{}', '{}'),
  ('MED-001', '急救车1号', 'ambulance', 'medical', '急救中心', ARRAY['emergency_medical','medical_transport'], POINT(121.44, 31.20), '121.44,31.20', 'available', '{"capacity_patient": 2, "crew": 3}', '{}', '{"type": "监护型"}'),
  ('MED-002', '急救车2号', 'ambulance', 'medical', '急救中心', ARRAY['emergency_medical','medical_transport'], POINT(121.52, 31.26), '121.52,31.26', 'available', '{"capacity_patient": 2, "crew": 3}', '{}', '{"type": "监护型"}'),
  ('MED-003', '移动医疗站', 'mobile_hospital', 'medical', '卫健委', ARRAY['emergency_medical','triage'], POINT(121.50, 31.24), '121.50,31.24', 'available', '{"capacity_patient": 20, "crew": 15}', '{}', '{"type": "方舱医院"}'),
  ('HAZMAT-001', '危化品处置车', 'hazmat_vehicle', 'hazmat', '消防救援支队', ARRAY['chemical_detection','hazmat_handling','decontamination'], POINT(121.55, 31.28), '121.55,31.28', 'available', '{"crew": 8}', '{}', '{"chemicals": ["acid","alkali","organic"]}'),
  ('PUMP-001', '排涝泵车1号', 'pump_truck', 'utility', '市政管理局', ARRAY['water_pumping','drainage_management'], POINT(121.43, 31.19), '121.43,31.19', 'available', '{"flow_rate_m3h": 500, "crew": 3}', '{}', '{}'),
  ('PUMP-002', '排涝泵车2号', 'pump_truck', 'utility', '市政管理局', ARRAY['water_pumping','drainage_management'], POINT(121.51, 31.27), '121.51,31.27', 'available', '{"flow_rate_m3h": 300, "crew": 2}', '{}', '{}'),
  ('ROBOT-001', '搜救机器人', 'rescue_robot', 'robot', '应急管理局', ARRAY['robot_operation','confined_space_sensing','life_detection'], POINT(121.48, 31.23), '121.48,31.23', 'available', '{"endurance_min": 120}', '{}', '{"type": "履带式"}'),
  ('COMM-001', '应急通信车', 'comm_vehicle', 'communication', '应急管理局', ARRAY['comm_support','network_deployment','command_control'], POINT(121.47, 31.22), '121.47,31.22', 'available', '{"coverage_km": 10, "channels": 20}', '{}', '{}');

-- ========================================
-- 15. 能力约束表（用于CSP求解）
-- ========================================
CREATE TABLE planning.capability_constraints (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,                    -- weather/terrain/time/resource/safety
  description TEXT NOT NULL,
  constraint_type TEXT NOT NULL,             -- hard/soft
  condition_expr TEXT NOT NULL,              -- 约束表达式
  penalty_score NUMERIC DEFAULT 0,           -- 软约束违反时的扣分
  applicable_capabilities TEXT[],            -- 适用的能力
  applicable_scenes TEXT[],
  priority INT NOT NULL DEFAULT 100,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.capability_constraints IS '能力约束条件（用于CSP求解）';

-- ========================================
-- 16. 资源-能力映射表（用于能力匹配）
-- ========================================
CREATE TABLE planning.resource_capability_map (
  id SERIAL PRIMARY KEY,
  resource_type TEXT NOT NULL,
  capability_id TEXT REFERENCES planning.capabilities(id),
  proficiency NUMERIC NOT NULL DEFAULT 1.0,  -- 能力熟练度 0-1
  capacity_factor NUMERIC NOT NULL DEFAULT 1.0, -- 容量系数
  constraints JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================
-- 17. 任务-能力需求表（用于能力提取）
-- ========================================
CREATE TABLE planning.task_capability_requirements (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES planning.tasks(id),
  capability_id TEXT REFERENCES planning.capabilities(id),
  min_level NUMERIC NOT NULL DEFAULT 1,      -- 最低能力等级要求
  importance TEXT NOT NULL DEFAULT 'required', -- required/preferred/optional
  quantity INT DEFAULT 1,                    -- 需要的能力数量
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================
-- 18. 软规则表（用于方案评分）
-- ========================================
CREATE TABLE planning.soft_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,                    -- efficiency/coordination/quality/timing
  description TEXT NOT NULL,
  condition_expr TEXT NOT NULL,              -- 触发条件表达式
  score_impact NUMERIC NOT NULL,             -- 分值影响（正为加分，负为扣分）
  impact_dimension TEXT NOT NULL,            -- 影响的评分维度
  scenes TEXT[],
  priority INT NOT NULL DEFAULT 100,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.soft_rules IS '软规则（方案评分调整）';

-- ========================================
-- 19. 优化算法参数表
-- ========================================
CREATE TABLE planning.optimization_params (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  algorithm TEXT NOT NULL,                   -- nsga2/mcts/ga/greedy
  description TEXT,
  params JSONB NOT NULL,                     -- 算法参数
  scenes TEXT[],
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.optimization_params IS '优化算法参数配置';

-- ========================================
-- 20. 仿真评估参数表
-- ========================================
CREATE TABLE planning.simulation_params (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scene_id TEXT REFERENCES planning.scenes(id),
  -- 时间相关参数
  golden_time_hours NUMERIC,                 -- 黄金救援时间
  response_deadline_min INT,                 -- 响应时限
  -- 成功率相关参数
  base_success_rate NUMERIC,                 -- 基础成功率
  time_decay_factor NUMERIC,                 -- 时间衰减因子
  resource_bonus_factor NUMERIC,             -- 资源充足加成
  -- 风险相关参数
  base_risk NUMERIC,                         -- 基础风险
  secondary_disaster_prob NUMERIC,           -- 次生灾害概率
  -- 覆盖率相关参数
  min_coverage_rate NUMERIC,                 -- 最小覆盖率要求
  -- 其他参数
  params JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.simulation_params IS '仿真评估参数';

-- ========================================
-- 21. 资源调度约束表
-- ========================================
CREATE TABLE planning.dispatch_constraints (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  constraint_type TEXT NOT NULL,             -- distance/time/capacity/exclusion/dependency
  description TEXT NOT NULL,
  condition_expr TEXT NOT NULL,
  penalty_weight NUMERIC DEFAULT 1.0,
  is_hard BOOLEAN DEFAULT FALSE,
  scenes TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.dispatch_constraints IS '资源调度约束';

-- ========================================
-- 22. 历史案例表（用于案例推理）
-- ========================================
CREATE TABLE planning.historical_cases (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scene_id TEXT REFERENCES planning.scenes(id),
  incident_level TEXT NOT NULL,
  location_text TEXT NOT NULL,
  affected_population INT,
  -- 方案信息
  task_sequence TEXT[] NOT NULL,
  resource_allocation JSONB NOT NULL,
  -- 结果信息
  success_rate NUMERIC,
  response_time_min INT,
  casualties INT,
  rescued_count INT,
  -- 评价
  evaluation_score NUMERIC,
  lessons_learned TEXT,
  -- 元数据
  occurred_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE planning.historical_cases IS '历史案例库（用于案例推理）';

-- ========================================
-- 补充数据：完整能力本体（约40项）
-- ========================================
INSERT INTO planning.capabilities (id, name, category, description, metrics) VALUES
  -- 感知类能力
  ('image_transmission', '图像传输', 'sensing', '实时图像/视频传输能力', '{"bandwidth_mbps": "number", "latency_ms": "number", "resolution": "string"}'),
  ('acoustic_detection', '声波探测', 'sensing', '通过声波探测生命迹象', '{"sensitivity_db": "number", "range_m": "number"}'),
  ('chemical_detection', '化学探测', 'sensing', '危险化学物质探测识别', '{"chemicals": "array", "sensitivity_ppm": "number", "response_time_s": "number"}'),
  ('hydrological_monitoring', '水文监测', 'sensing', '水位、流速等水文数据监测', '{"accuracy_cm": "number", "update_interval_s": "number"}'),
  ('geological_monitoring', '地质监测', 'sensing', '地质灾害监测预警', '{"sensors": "array", "accuracy": "number"}'),
  ('structural_assessment', '结构评估', 'sensing', '建筑结构安全评估', '{"assessment_time_min": "number", "accuracy": "number"}'),
  ('image_analysis', '图像分析', 'sensing', 'AI图像识别分析', '{"accuracy": "number", "processing_time_s": "number"}'),
  ('data_fusion', '数据融合', 'sensing', '多源数据融合处理', '{"sources": "array", "latency_ms": "number"}'),
  ('hazmat_identification', '危化品识别', 'sensing', '危险化学品种类识别', '{"database_size": "number", "accuracy": "number"}'),
  ('water_level_monitoring', '水位监测', 'sensing', '积水水位实时监测', '{"accuracy_cm": "number", "range_m": "number"}'),
  ('urban_drainage_analysis', '排水分析', 'sensing', '城市排水系统分析', '{"coverage_km2": "number"}'),
  ('gis_processing', 'GIS处理', 'sensing', '地理信息系统数据处理', '{"layers": "array", "update_interval_min": "number"}'),
  ('hazard_analysis', '灾害分析', 'sensing', '灾害风险分析研判', '{"models": "array"}'),
  ('risk_modeling', '风险建模', 'sensing', '灾害风险演化建模', '{"forecast_hours": "number", "accuracy": "number"}'),
  
  -- 机动类能力
  ('ground_mobility', '地面机动', 'mobility', '地面车辆机动能力', '{"speed_kmh": "number", "terrain": "array"}'),
  ('aerial_mobility', '空中机动', 'mobility', '空中平台机动能力', '{"speed_kmh": "number", "altitude_m": "number", "endurance_min": "number"}'),
  ('water_mobility', '水上机动', 'mobility', '水上/水下机动能力', '{"speed_knot": "number", "draft_m": "number"}'),
  ('all_terrain', '全地形通过', 'mobility', '复杂地形通过能力', '{"terrain_types": "array", "grade_percent": "number"}'),
  
  -- 作业类能力
  ('demolition', '破拆作业', 'operation', '建筑物破拆能力', '{"concrete_thickness_cm": "number", "steel_diameter_mm": "number"}'),
  ('heavy_machinery', '重型机械', 'operation', '重型工程机械操作', '{"lift_capacity_ton": "number", "reach_m": "number"}'),
  ('structural_shoring', '结构支撑', 'operation', '临时结构支撑加固', '{"load_capacity_ton": "number"}'),
  ('confined_space_sensing', '狭小空间探测', 'operation', '狭小空间内部探测', '{"diameter_cm": "number", "length_m": "number"}'),
  ('robot_operation', '机器人操作', 'operation', '救援机器人遥控操作', '{"control_range_m": "number", "dof": "number"}'),
  ('canine_search', '搜救犬搜索', 'operation', '搜救犬生命搜索', '{"coverage_m2_per_hour": "number", "accuracy": "number"}'),
  ('water_supply', '供水保障', 'operation', '消防供水能力', '{"flow_rate_lpm": "number", "pressure_mpa": "number"}'),
  ('aerial_rescue', '高空救援', 'operation', '高层建筑人员救援', '{"max_height_m": "number", "capacity_person": "number"}'),
  ('leak_sealing', '堵漏作业', 'operation', '泄漏封堵能力', '{"pressure_mpa": "number", "materials": "array"}'),
  ('decontamination', '洗消去污', 'operation', '人员装备洗消', '{"capacity_person_per_hour": "number", "chemicals": "array"}'),
  ('hazmat_disposal', '危废处置', 'operation', '危险废物处置', '{"categories": "array", "capacity_ton": "number"}'),
  ('gas_operation', '燃气操作', 'operation', '燃气管网操作', '{"valve_types": "array", "pressure_range": "string"}'),
  ('power_operation', '电力操作', 'operation', '电力设施操作', '{"voltage_kv": "number", "capacity_kva": "number"}'),
  ('electrical_safety', '电气安全', 'operation', '电气安全作业', '{"voltage_max_kv": "number"}'),
  ('road_repair', '道路抢修', 'operation', '道路快速修复', '{"area_m2_per_hour": "number"}'),
  ('debris_clearance', '清障作业', 'operation', '道路障碍清除', '{"capacity_ton_per_hour": "number"}'),
  ('drainage_management', '排水管理', 'operation', '排水系统调度管理', '{"capacity_m3h": "number"}'),
  ('triage', '检伤分类', 'operation', '伤员检伤分类', '{"capacity_person_per_hour": "number", "accuracy": "number"}'),
  ('shelter_management', '安置管理', 'support', '临时安置点管理', '{"capacity_person": "number", "services": "array"}'),
  ('transport', '运输保障', 'support', '人员物资运输', '{"capacity_ton": "number", "capacity_person": "number"}'),
  
  -- 通信类能力
  ('emergency_broadcast', '应急广播', 'communication', '应急信息广播发布', '{"coverage_km2": "number", "channels": "array"}'),
  ('inter_agency_coordination', '跨部门协调', 'communication', '多部门协同指挥', '{"agencies": "array", "protocols": "array"}'),
  ('comm_support', '通信保障', 'communication', '现场通信保障', '{"bandwidth_mbps": "number", "coverage_km": "number"}'),
  ('network_deployment', '网络部署', 'communication', '临时通信网络搭建', '{"deployment_time_min": "number", "capacity": "number"}'),
  ('resource_scheduling', '资源调度', 'communication', '资源调配管理', '{"max_resources": "number"}'),
  ('route_planning', '路线规划', 'communication', '疏散/救援路线规划', '{"algorithm": "string", "factors": "array"}'),
  ('traffic_analysis', '交通分析', 'communication', '交通态势分析', '{"coverage_km": "number", "update_interval_s": "number"}'),
  ('route_coordination', '路线协调', 'communication', '多车辆路线协调', '{"vehicles": "number"}'),
  ('crowd_guidance', '人群引导', 'communication', '人群疏散引导', '{"capacity_person": "number", "methods": "array"}'),
  ('damage_assessment', '损失评估', 'support', '灾害损失评估', '{"categories": "array"}'),
  ('report_generation', '报告生成', 'support', '评估报告自动生成', '{"templates": "array"}');

-- ========================================
-- 补充数据：能力约束（约30条）
-- ========================================
INSERT INTO planning.capability_constraints (id, name, category, condition_expr, constraint_type, penalty_score, description, applicable_capabilities, applicable_scenes, priority) VALUES
  -- 天气约束
  ('CON-W01', '风速限制-无人机', 'weather', 'wind_speed_ms <= 10', 'hard', 0, '风速超过10m/s时无人机禁止起飞', ARRAY['aerial_perception','aerial_mobility'], NULL, 100),
  ('CON-W02', '风速限制-登高作业', 'weather', 'wind_speed_ms <= 8', 'hard', 0, '风速超过8m/s时禁止高空作业', ARRAY['aerial_rescue'], NULL, 100),
  ('CON-W03', '能见度要求-航空侦察', 'weather', 'visibility_m >= 1000', 'soft', -0.1, '能见度低于1km影响航空侦察效果', ARRAY['aerial_perception'], NULL, 80),
  ('CON-W04', '降雨限制-电气作业', 'weather', 'rainfall_mm_h <= 10', 'hard', 0, '强降雨时禁止带电作业', ARRAY['power_operation','electrical_safety'], NULL, 100),
  ('CON-W05', '温度限制-危化品', 'weather', 'temperature_c BETWEEN -10 AND 40', 'soft', -0.15, '极端温度影响危化品处置安全', ARRAY['hazmat_handling','chemical_detection'], ARRAY['S3'], 90),
  
  -- 地形约束
  ('CON-T01', '道路等级-重型车辆', 'terrain', 'road_class IN ("main","secondary")', 'hard', 0, '重型车辆只能在主干道和次干道行驶', ARRAY['heavy_machinery','ground_mobility'], NULL, 100),
  ('CON-T02', '坡度限制-轮式车辆', 'terrain', 'slope_percent <= 15', 'soft', -0.05, '坡度超过15%影响轮式车辆通行', ARRAY['ground_mobility'], ARRAY['S4'], 70),
  ('CON-T03', '积水深度-车辆涉水', 'terrain', 'water_depth_cm <= 40', 'hard', 0, '积水超过40cm普通车辆禁止通行', ARRAY['ground_mobility'], ARRAY['S5'], 100),
  ('CON-T04', '建筑稳定性-进入作业', 'terrain', 'building_stability >= 0.6', 'hard', 0, '建筑稳定性评分低于0.6禁止进入', ARRAY['rescue_operation','demolition'], ARRAY['S1'], 100),
  ('CON-T05', '地质稳定-山区作业', 'terrain', 'geological_risk <= 0.3', 'soft', -0.2, '地质风险高的区域需加强监测', ARRAY['rescue_operation'], ARRAY['S4'], 85),
  
  -- 时间约束
  ('CON-TM01', '黄金72小时', 'time', 'elapsed_hours <= 72', 'soft', -0.3, '超过72小时生存率大幅下降', ARRAY['life_detection','rescue_operation'], ARRAY['S1'], 95),
  ('CON-TM02', '夜间作业限制', 'time', 'is_daytime OR has_lighting', 'soft', -0.1, '夜间无照明影响搜救效率', ARRAY['canine_search','aerial_perception'], NULL, 75),
  ('CON-TM03', '危化品扩散时效', 'time', 'elapsed_min <= 60', 'soft', -0.25, '泄漏后60分钟内为最佳处置窗口', ARRAY['hazmat_handling','leak_sealing'], ARRAY['S3'], 90),
  ('CON-TM04', '洪水预警响应时间', 'time', 'warning_lead_time_min >= 30', 'hard', 0, '预警提前量不足30分钟需立即疏散', ARRAY['crowd_guidance'], ARRAY['S4','S5'], 100),
  
  -- 资源约束
  ('CON-R01', '人员轮换要求', 'resource', 'continuous_work_hours <= 4', 'soft', -0.1, '连续作业超过4小时需轮换', ARRAY['rescue_operation','demolition'], NULL, 80),
  ('CON-R02', '设备续航要求', 'resource', 'battery_percent >= 20', 'hard', 0, '电量低于20%必须返航/充电', ARRAY['aerial_mobility','robot_operation'], NULL, 100),
  ('CON-R03', '水源距离限制', 'resource', 'water_source_distance_m <= 500', 'soft', -0.15, '水源距离超过500m影响灭火效率', ARRAY['fire_suppression','water_supply'], ARRAY['S2'], 85),
  ('CON-R04', '医疗资源配比', 'resource', 'medic_per_100_affected >= 1', 'soft', -0.2, '每百人至少配置1名医护', ARRAY['emergency_medical','triage'], NULL, 90),
  ('CON-R05', '通信覆盖要求', 'resource', 'comm_coverage >= 0.9', 'soft', -0.15, '通信覆盖率低于90%影响协调', ARRAY['command_control','inter_agency_coordination'], NULL, 85),
  
  -- 安全约束
  ('CON-S01', '防护等级要求-危化品', 'safety', 'protection_level >= required_level', 'hard', 0, '防护等级必须达到要求', ARRAY['hazmat_handling','chemical_detection'], ARRAY['S3'], 100),
  ('CON-S02', '余震监测要求', 'safety', 'aftershock_monitoring_active', 'hard', 0, '废墟作业期间必须持续监测余震', ARRAY['rescue_operation','demolition'], ARRAY['S1'], 100),
  ('CON-S03', '燃气浓度监测', 'safety', 'gas_concentration_ppm <= safe_threshold', 'hard', 0, '燃气浓度超标时禁止作业', ARRAY['rescue_operation','fire_suppression'], ARRAY['S2'], 100),
  ('CON-S04', '安全员配置', 'safety', 'safety_officer_present', 'soft', -0.1, '高危作业需配置安全员', ARRAY['demolition','heavy_machinery','hazmat_handling'], NULL, 90),
  ('CON-S05', '撤离通道保持', 'safety', 'evacuation_route_clear', 'hard', 0, '作业区域必须保持撤离通道畅通', ARRAY['rescue_operation','hazmat_handling'], NULL, 100);

-- ========================================
-- 补充数据：软规则（约25条）
-- ========================================
INSERT INTO planning.soft_rules (id, name, category, description, condition_expr, score_impact, impact_dimension, scenes, priority) VALUES
  -- 效率类
  ('SR-E01', '就近调度优先', 'efficiency', '优先调度距离最近的资源', 'resource_distance <= avg_distance * 0.7', 0.05, 'time_score', NULL, 80),
  ('SR-E02', '专业队伍优先', 'efficiency', '专业任务优先使用专业队伍', 'resource_specialty MATCHES task_category', 0.08, 'resource_score', NULL, 85),
  ('SR-E03', '多任务复用', 'efficiency', '单次出动完成多项任务加分', 'tasks_per_dispatch >= 2', 0.06, 'resource_score', NULL, 75),
  ('SR-E04', '并行任务执行', 'efficiency', '可并行任务同时执行加分', 'parallel_execution_rate >= 0.3', 0.07, 'time_score', NULL, 80),
  ('SR-E05', '资源利用率优化', 'efficiency', '资源利用率高于80%加分', 'resource_utilization >= 0.8', 0.05, 'resource_score', NULL, 70),
  
  -- 协调类
  ('SR-C01', '跨部门协同', 'coordination', '多部门联合作业加分', 'agencies_involved >= 3', 0.06, 'coverage_score', NULL, 85),
  ('SR-C02', '信息共享及时', 'coordination', '态势信息更新间隔短加分', 'info_update_interval_min <= 5', 0.04, 'coverage_score', NULL, 75),
  ('SR-C03', '指挥链路清晰', 'coordination', '指挥层级不超过3级', 'command_levels <= 3', 0.05, 'time_score', NULL, 80),
  ('SR-C04', '资源冲突少', 'coordination', '资源调度冲突率低加分', 'resource_conflict_rate <= 0.1', 0.06, 'resource_score', NULL, 85),
  
  -- 质量类
  ('SR-Q01', '搜索覆盖完整', 'quality', '搜索覆盖率超过95%加分', 'search_coverage >= 0.95', 0.08, 'coverage_score', ARRAY['S1'], 90),
  ('SR-Q02', '伤员分诊规范', 'quality', '所有伤员完成规范分诊', 'triage_completion_rate >= 0.98', 0.05, 'life_safety_score', NULL, 85),
  ('SR-Q03', '危险源全覆盖', 'quality', '所有识别的危险源都有处置措施', 'hazard_coverage >= 1.0', 0.07, 'risk_score', ARRAY['S1','S2','S3'], 90),
  ('SR-Q04', '疏散无遗漏', 'quality', '疏散区域人员全部转移', 'evacuation_completion >= 0.99', 0.1, 'life_safety_score', NULL, 95),
  ('SR-Q05', '医疗救治及时', 'quality', '重伤员30分钟内得到救治', 'critical_treatment_time_min <= 30', 0.08, 'life_safety_score', NULL, 90),
  
  -- 时效类
  ('SR-T01', '快速响应', 'timing', '首批力量15分钟内到达', 'first_response_time_min <= 15', 0.1, 'time_score', NULL, 90),
  ('SR-T02', '黄金时间内完成', 'timing', '主要搜救在黄金时间内完成', 'main_rescue_within_golden_time', 0.15, 'life_safety_score', ARRAY['S1'], 95),
  ('SR-T03', '预警提前发布', 'timing', '预警信息提前30分钟发布', 'warning_lead_time_min >= 30', 0.08, 'life_safety_score', ARRAY['S4','S5'], 90),
  ('SR-T04', '道路抢通及时', 'timing', '主要道路2小时内抢通', 'main_road_clear_time_hours <= 2', 0.06, 'time_score', NULL, 80),
  ('SR-T05', '转运无延误', 'timing', '伤员转运无等待延误', 'transport_delay_min <= 5', 0.05, 'time_score', NULL, 85),
  
  -- 风险控制类
  ('SR-R01', '冗余力量配置', 'risk', '关键任务配置备用力量', 'backup_resource_ratio >= 0.2', 0.05, 'risk_score', NULL, 80),
  ('SR-R02', '次生灾害预防', 'risk', '部署次生灾害监测预警', 'secondary_monitoring_active', 0.07, 'risk_score', ARRAY['S1'], 85),
  ('SR-R03', '撤离预案准备', 'risk', '所有作业点有撤离预案', 'evacuation_plan_coverage >= 1.0', 0.04, 'risk_score', NULL, 80),
  ('SR-R04', '安全间距保持', 'risk', '危险源周边保持安全距离', 'safety_distance_compliance >= 0.95', 0.06, 'risk_score', ARRAY['S2','S3'], 85),
  ('SR-R05', '通信备份', 'risk', '通信系统有备份', 'comm_redundancy >= 1', 0.03, 'risk_score', NULL, 75);

-- ========================================
-- 补充数据：优化算法参数
-- ========================================
INSERT INTO planning.optimization_params (id, name, algorithm, description, params, scenes, is_default) VALUES
  ('OPT-NSGA2-DEFAULT', 'NSGA-II默认配置', 'nsga2', '多目标优化默认参数',
   '{"population_size": 100, "generations": 200, "crossover_prob": 0.9, "mutation_prob": 0.1, "objectives": ["life_safety", "time", "resource", "risk", "coverage"]}',
   NULL, TRUE),
  
  ('OPT-NSGA2-EARTHQUAKE', 'NSGA-II地震专用', 'nsga2', '地震场景优化参数，强调生命搜救',
   '{"population_size": 150, "generations": 300, "crossover_prob": 0.85, "mutation_prob": 0.15, "objectives": ["life_safety", "time", "coverage"], "objective_weights": {"life_safety": 0.5, "time": 0.35, "coverage": 0.15}}',
   ARRAY['S1'], FALSE),
  
  ('OPT-MCTS-DEFAULT', 'MCTS默认配置', 'mcts', '蒙特卡洛树搜索默认参数',
   '{"max_iterations": 10000, "exploration_constant": 1.414, "max_depth": 20, "simulation_count": 100, "time_limit_sec": 30}',
   NULL, FALSE),
  
  ('OPT-MCTS-REALTIME', 'MCTS实时决策', 'mcts', '快速决策场景参数',
   '{"max_iterations": 3000, "exploration_constant": 2.0, "max_depth": 10, "simulation_count": 50, "time_limit_sec": 10}',
   ARRAY['S2','S4','S5'], FALSE),
  
  ('OPT-GA-DEFAULT', '遗传算法默认配置', 'ga', '单目标遗传算法参数',
   '{"population_size": 80, "generations": 150, "crossover_prob": 0.8, "mutation_prob": 0.05, "selection": "tournament", "tournament_size": 3, "elitism": 0.1}',
   NULL, FALSE),
  
  ('OPT-GREEDY-FAST', '贪心快速配置', 'greedy', '贪心算法快速求解',
   '{"strategy": "nearest_first", "lookahead": 3, "time_limit_sec": 5}',
   NULL, FALSE),
  
  ('OPT-CSP-DEFAULT', 'CSP约束求解配置', 'csp', '约束满足问题求解参数',
   '{"solver": "or-tools", "time_limit_sec": 60, "num_search_workers": 4, "optimization_mode": "satisfaction_first"}',
   NULL, FALSE);

-- ========================================
-- 补充数据：仿真评估参数
-- ========================================
INSERT INTO planning.simulation_params (id, name, scene_id, golden_time_hours, response_deadline_min, base_success_rate, time_decay_factor, resource_bonus_factor, base_risk, secondary_disaster_prob, min_coverage_rate, params) VALUES
  ('SIM-S1', '地震仿真参数', 'S1', 72, 30, 0.7, 0.02, 0.15, 0.3, 0.25, 0.9,
   '{"survival_decay_model": "exponential", "aftershock_impact": 0.1, "building_collapse_rate": 0.15, "infrastructure_damage_rate": 0.4, "casualty_estimation_model": "usgs_pager"}'),
  
  ('SIM-S2', '次生火灾仿真参数', 'S2', NULL, 15, 0.8, 0.05, 0.1, 0.25, 0.15, 0.95,
   '{"fire_spread_model": "cellular_automaton", "gas_leak_probability": 0.3, "explosion_risk_threshold": 0.4, "wind_spread_factor": 1.5}'),
  
  ('SIM-S3', '危化品泄漏仿真参数', 'S3', NULL, 20, 0.75, 0.03, 0.12, 0.35, 0.2, 0.98,
   '{"dispersion_model": "gaussian_plume", "toxicity_threshold_ppm": 50, "evacuation_radius_factor": 2.0, "decontamination_effectiveness": 0.9}'),
  
  ('SIM-S4', '山洪泥石流仿真参数', 'S4', NULL, 30, 0.65, 0.04, 0.1, 0.4, 0.3, 0.85,
   '{"flow_model": "flo2d", "warning_effectiveness": 0.8, "road_damage_probability": 0.5, "evacuation_compliance_rate": 0.75}'),
  
  ('SIM-S5', '暴雨内涝仿真参数', 'S5', NULL, 60, 0.85, 0.01, 0.08, 0.2, 0.1, 0.9,
   '{"drainage_model": "swmm", "waterlogging_threshold_cm": 30, "traffic_impact_factor": 0.6, "pump_efficiency": 0.85}');

-- ========================================
-- 补充数据：资源调度约束
-- ========================================
INSERT INTO planning.dispatch_constraints (id, name, constraint_type, description, condition_expr, penalty_weight, is_hard, scenes) VALUES
  ('DC-D01', '最大响应距离', 'distance', '资源响应距离不超过50km', 'distance_km <= 50', 1.0, TRUE, NULL),
  ('DC-D02', '优选近距离资源', 'distance', '距离超过20km扣分', 'distance_km <= 20', 0.5, FALSE, NULL),
  ('DC-T01', '响应时限硬约束', 'time', '必须在响应时限内到达', 'eta_min <= response_deadline', 1.0, TRUE, NULL),
  ('DC-T02', '快速响应偏好', 'time', 'ETA超过30分钟扣分', 'eta_min <= 30', 0.3, FALSE, NULL),
  ('DC-C01', '单资源单任务', 'capacity', '同一资源同一时间只能执行一个任务', 'concurrent_tasks <= 1', 1.0, TRUE, NULL),
  ('DC-C02', '人员容量限制', 'capacity', '不超过资源人员容量', 'assigned_personnel <= capacity_personnel', 1.0, TRUE, NULL),
  ('DC-E01', '同类资源互斥', 'exclusion', '同一地点不需要多个同类资源', 'same_type_at_location <= 1', 0.4, FALSE, NULL),
  ('DC-E02', '危险区域人员限制', 'exclusion', '危险区域同时作业人数限制', 'personnel_in_danger_zone <= max_allowed', 1.0, TRUE, ARRAY['S1','S3']),
  ('DC-DEP01', '生命探测先于救援', 'dependency', '必须先完成生命探测再实施救援', 'life_detection_completed BEFORE rescue_operation', 1.0, TRUE, ARRAY['S1']),
  ('DC-DEP02', '灾情评估先于调度', 'dependency', '必须先完成灾情评估再大规模调度', 'assessment_completed BEFORE mass_dispatch', 1.0, TRUE, NULL),
  ('DC-DEP03', '危化品侦检先于处置', 'dependency', '必须先完成侦检再进行堵漏', 'hazmat_detection_completed BEFORE hazmat_handling', 1.0, TRUE, ARRAY['S3']),
  ('DC-DEP04', '路线规划先于疏散', 'dependency', '必须先完成路线规划再开始疏散', 'route_planning_completed BEFORE evacuation', 1.0, TRUE, NULL);

-- ========================================
-- 补充数据：任务-能力需求映射
-- ========================================
INSERT INTO planning.task_capability_requirements (task_id, capability_id, min_level, importance, quantity) VALUES
  -- EM01 无人机广域侦察
  ('EM01', 'aerial_perception', 0.8, 'required', 1),
  ('EM01', 'image_transmission', 0.7, 'required', 1),
  ('EM01', 'aerial_mobility', 0.6, 'required', 1),
  
  -- EM06 埋压人员生命探测
  ('EM06', 'life_detection', 0.8, 'required', 1),
  ('EM06', 'acoustic_detection', 0.7, 'preferred', 1),
  ('EM06', 'thermal_imaging', 0.7, 'preferred', 1),
  
  -- EM10 被困人员救援
  ('EM10', 'rescue_operation', 0.9, 'required', 1),
  ('EM10', 'emergency_medical', 0.6, 'required', 1),
  ('EM10', 'heavy_machinery', 0.5, 'preferred', 1),
  
  -- EM11 废墟挖掘与破拆
  ('EM11', 'demolition', 0.8, 'required', 1),
  ('EM11', 'heavy_machinery', 0.8, 'required', 1),
  ('EM11', 'structural_shoring', 0.7, 'required', 1),
  
  -- EM19 消防灭火作业
  ('EM19', 'fire_suppression', 0.9, 'required', 2),
  ('EM19', 'water_supply', 0.8, 'required', 1),
  
  -- EM20 危化品泄漏侦检
  ('EM20', 'chemical_detection', 0.9, 'required', 1),
  ('EM20', 'hazmat_identification', 0.8, 'required', 1),
  
  -- EM21 危化品堵漏处置
  ('EM21', 'hazmat_handling', 0.9, 'required', 1),
  ('EM21', 'leak_sealing', 0.8, 'required', 1),
  
  -- EM31 排涝抽水作业
  ('EM31', 'water_pumping', 0.8, 'required', 2),
  ('EM31', 'drainage_management', 0.7, 'preferred', 1);

-- ========================================
-- 补充数据：更多资源（约50个）
-- ========================================
INSERT INTO planning.resources (id, name, type, category, org, capabilities, location, location_text, status, capacity, constraints, properties) VALUES
  -- 无人机
  ('UAV-003', '侦察无人机3号', 'reconnaissance_uav', 'uav', '应急管理局', ARRAY['aerial_perception','image_transmission'], POINT(121.42, 31.18), '121.42,31.18', 'available', '{"endurance_min": 55, "payload_kg": 2.5}', '{"max_wind_ms": 12, "min_visibility_m": 800}', '{"model": "DJI M350"}'),
  ('UAV-004', '热成像无人机', 'thermal_uav', 'uav', '消防救援支队', ARRAY['aerial_perception','thermal_imaging','life_detection'], POINT(121.48, 31.22), '121.48,31.22', 'available', '{"endurance_min": 40, "thermal_resolution": "640x512"}', '{"max_wind_ms": 8}', '{"model": "DJI H20T"}'),
  ('UAV-005', '应急通信无人机', 'comm_uav', 'uav', '应急管理局', ARRAY['aerial_mobility','comm_support','network_deployment'], POINT(121.50, 31.20), '121.50,31.20', 'available', '{"endurance_min": 50, "coverage_km": 5}', '{"max_wind_ms": 10}', '{"model": "系留无人机"}'),
  
  -- 消防车辆
  ('FIRE-003', '水罐消防车2号', 'fire_truck', 'fire', '消防救援支队', ARRAY['fire_suppression','water_supply'], POINT(121.52, 31.24), '121.52,31.24', 'available', '{"water_ton": 10, "crew": 6, "pump_flow_lpm": 4000}', '{"road_class": ["main","secondary"]}', '{"type": "重型水罐车"}'),
  ('FIRE-004', '泡沫消防车', 'foam_truck', 'fire', '消防救援支队', ARRAY['fire_suppression','water_supply'], POINT(121.48, 31.26), '121.48,31.26', 'available', '{"foam_ton": 3, "water_ton": 6, "crew": 5}', '{"road_class": ["main","secondary"]}', '{"type": "泡沫消防车"}'),
  ('FIRE-005', '抢险救援消防车', 'rescue_fire_truck', 'fire', '消防救援支队', ARRAY['rescue_operation','demolition','fire_suppression'], POINT(121.44, 31.23), '121.44,31.23', 'available', '{"crew": 8, "equipment_categories": ["破拆","支撑","照明"]}', '{"road_class": ["main","secondary"]}', '{"type": "抢险救援车"}'),
  ('FIRE-006', '32米登高车', 'ladder_truck', 'fire', '消防救援支队', ARRAY['fire_suppression','aerial_rescue'], POINT(121.50, 31.21), '121.50,31.21', 'available', '{"max_height_m": 32, "crew": 4}', '{"road_class": ["main"]}', '{"type": "32米登高车"}'),
  ('FIRE-007', '供水消防车', 'water_supply_truck', 'fire', '消防救援支队', ARRAY['water_supply','ground_mobility'], POINT(121.46, 31.25), '121.46,31.25', 'available', '{"water_ton": 15, "crew": 3}', '{"road_class": ["main","secondary"]}', '{"type": "大型供水车"}'),
  
  -- 救援队伍
  ('RESCUE-003', '地震救援队', 'earthquake_rescue', 'rescue', '国家救援队', ARRAY['rescue_operation','demolition','heavy_machinery','life_detection','structural_shoring'], POINT(121.55, 31.30), '121.55,31.30', 'available', '{"personnel": 50, "equipment_ton": 30}', '{}', '{"level": "国家级", "specialty": "地震救援"}'),
  ('RESCUE-004', '矿山救援队', 'mine_rescue', 'rescue', '矿山救护队', ARRAY['rescue_operation','confined_space_sensing','life_detection'], POINT(121.60, 31.35), '121.60,31.35', 'available', '{"personnel": 30}', '{}', '{"specialty": "矿山坍塌救援"}'),
  ('RESCUE-005', '水上救援队', 'water_rescue', 'rescue', '消防救援支队', ARRAY['rescue_operation','water_mobility'], POINT(121.47, 31.21), '121.47,31.21', 'available', '{"personnel": 15, "boats": 3}', '{}', '{"specialty": "水域救援"}'),
  ('RESCUE-006', '高空救援队', 'height_rescue', 'rescue', '消防救援支队', ARRAY['rescue_operation','aerial_rescue'], POINT(121.49, 31.24), '121.49,31.24', 'available', '{"personnel": 12}', '{}', '{"specialty": "高空绳索救援"}'),
  
  -- 搜救犬
  ('K9-002', '搜救犬队2组', 'search_dog_team', 'rescue', '消防救援支队', ARRAY['canine_search','life_detection'], POINT(121.51, 31.23), '121.51,31.23', 'available', '{"dogs": 6, "handlers": 6}', '{}', '{}'),
  
  -- 医疗资源
  ('MED-004', '急救车3号', 'ambulance', 'medical', '急救中心', ARRAY['emergency_medical','medical_transport'], POINT(121.43, 31.18), '121.43,31.18', 'available', '{"capacity_patient": 2, "crew": 3}', '{}', '{"type": "监护型"}'),
  ('MED-005', '急救车4号', 'ambulance', 'medical', '急救中心', ARRAY['emergency_medical','medical_transport'], POINT(121.55, 31.28), '121.55,31.28', 'available', '{"capacity_patient": 2, "crew": 3}', '{}', '{"type": "监护型"}'),
  ('MED-006', '负压急救车', 'ambulance', 'medical', '急救中心', ARRAY['emergency_medical','medical_transport'], POINT(121.48, 31.25), '121.48,31.25', 'available', '{"capacity_patient": 1, "crew": 4}', '{}', '{"type": "负压型"}'),
  ('MED-007', '移动手术车', 'surgery_vehicle', 'medical', '卫健委', ARRAY['emergency_medical'], POINT(121.52, 31.22), '121.52,31.22', 'available', '{"surgery_capacity": 2, "crew": 8}', '{"road_class": ["main"]}', '{"type": "野战手术车"}'),
  ('MED-008', '医疗物资车', 'medical_supply', 'medical', '卫健委', ARRAY['logistics_management','transport'], POINT(121.46, 31.20), '121.46,31.20', 'available', '{"capacity_ton": 5}', '{}', '{"supplies": ["药品","器械","血液"]}'),
  
  -- 危化品处置
  ('HAZMAT-002', '危化品侦检车', 'hazmat_detection', 'hazmat', '消防救援支队', ARRAY['chemical_detection','hazmat_identification'], POINT(121.58, 31.32), '121.58,31.32', 'available', '{"crew": 6, "detection_range_m": 500}', '{}', '{"chemicals": ["gas","liquid","solid"]}'),
  ('HAZMAT-003', '洗消车', 'decon_vehicle', 'hazmat', '消防救援支队', ARRAY['decontamination'], POINT(121.53, 31.27), '121.53,31.27', 'available', '{"crew": 5, "capacity_person_per_hour": 60}', '{}', '{}'),
  
  -- 市政资源
  ('PUMP-003', '大型排涝车', 'pump_truck', 'utility', '市政管理局', ARRAY['water_pumping','drainage_management'], POINT(121.40, 31.15), '121.40,31.15', 'available', '{"flow_rate_m3h": 800, "crew": 4}', '{}', '{"type": "龙吸水"}'),
  ('PUMP-004', '移动泵站', 'mobile_pump', 'utility', '市政管理局', ARRAY['water_pumping'], POINT(121.45, 31.17), '121.45,31.17', 'available', '{"flow_rate_m3h": 1200, "crew": 2}', '{}', '{}'),
  ('UTIL-001', '电力抢修车', 'power_repair', 'utility', '供电公司', ARRAY['power_operation','electrical_safety'], POINT(121.48, 31.19), '121.48,31.19', 'available', '{"crew": 6}', '{}', '{"voltage_kv": 10}'),
  ('UTIL-002', '燃气抢修车', 'gas_repair', 'utility', '燃气公司', ARRAY['gas_operation','leak_sealing'], POINT(121.50, 31.22), '121.50,31.22', 'available', '{"crew": 5}', '{}', '{}'),
  ('UTIL-003', '路政抢修车', 'road_repair', 'utility', '交通局', ARRAY['road_repair','debris_clearance'], POINT(121.44, 31.21), '121.44,31.21', 'available', '{"crew": 8}', '{}', '{}'),
  
  -- 工程机械
  ('MACH-001', '挖掘机', 'excavator', 'machinery', '应急管理局', ARRAY['heavy_machinery','demolition','debris_clearance'], POINT(121.55, 31.25), '121.55,31.25', 'available', '{"bucket_capacity_m3": 1.2, "reach_m": 10}', '{"road_class": ["main"]}', '{"type": "履带式挖掘机"}'),
  ('MACH-002', '装载机', 'loader', 'machinery', '应急管理局', ARRAY['heavy_machinery','debris_clearance'], POINT(121.53, 31.23), '121.53,31.23', 'available', '{"bucket_capacity_m3": 3, "lift_capacity_ton": 5}', '{"road_class": ["main","secondary"]}', '{"type": "轮式装载机"}'),
  ('MACH-003', '起重机', 'crane', 'machinery', '应急管理局', ARRAY['heavy_machinery'], POINT(121.57, 31.28), '121.57,31.28', 'available', '{"lift_capacity_ton": 50, "reach_m": 40}', '{"road_class": ["main"]}', '{"type": "汽车起重机"}'),
  ('MACH-004', '破碎锤', 'breaker', 'machinery', '消防救援支队', ARRAY['demolition'], POINT(121.49, 31.22), '121.49,31.22', 'available', '{}', '{}', '{"type": "液压破碎锤"}'),
  
  -- 机器人
  ('ROBOT-002', '排爆机器人', 'eod_robot', 'robot', '公安局', ARRAY['robot_operation'], POINT(121.52, 31.24), '121.52,31.24', 'available', '{"endurance_min": 90, "payload_kg": 30}', '{}', '{"type": "轮式排爆机器人"}'),
  ('ROBOT-003', '消防机器人', 'fire_robot', 'robot', '消防救援支队', ARRAY['robot_operation','fire_suppression'], POINT(121.47, 31.23), '121.47,31.23', 'available', '{"endurance_min": 60, "water_flow_lpm": 80}', '{}', '{"type": "灭火侦察机器人"}'),
  ('ROBOT-004', '蛇形搜救机器人', 'snake_robot', 'robot', '应急管理局', ARRAY['robot_operation','confined_space_sensing','life_detection'], POINT(121.50, 31.25), '121.50,31.25', 'available', '{"endurance_min": 45, "diameter_cm": 8, "length_m": 20}', '{}', '{"type": "蛇形机器人"}'),
  
  -- 舟艇
  ('BOAT-001', '冲锋舟1号', 'assault_boat', 'water', '消防救援支队', ARRAY['water_mobility','rescue_operation'], POINT(121.45, 31.20), '121.45,31.20', 'available', '{"capacity_person": 8, "speed_kmh": 40}', '{}', '{}'),
  ('BOAT-002', '冲锋舟2号', 'assault_boat', 'water', '消防救援支队', ARRAY['water_mobility','rescue_operation'], POINT(121.48, 31.18), '121.48,31.18', 'available', '{"capacity_person": 8, "speed_kmh": 40}', '{}', '{}'),
  ('BOAT-003', '橡皮艇', 'rubber_boat', 'water', '消防救援支队', ARRAY['water_mobility'], POINT(121.46, 31.19), '121.46,31.19', 'available', '{"capacity_person": 6, "speed_kmh": 25}', '{}', '{}'),
  
  -- 通信指挥
  ('COMM-002', '卫星通信车', 'satcom_vehicle', 'communication', '应急管理局', ARRAY['comm_support','network_deployment'], POINT(121.49, 31.21), '121.49,31.21', 'available', '{"bandwidth_mbps": 100, "coverage_km": 50}', '{}', '{"type": "卫星通信"}'),
  ('COMM-003', '现场指挥车', 'command_vehicle', 'communication', '应急管理局', ARRAY['command_control','inter_agency_coordination','comm_support'], POINT(121.47, 31.24), '121.47,31.24', 'available', '{"stations": 10, "screens": 6}', '{}', '{}'),
  
  -- 物资保障
  ('LOG-001', '物资运输车1号', 'cargo_truck', 'logistics', '应急管理局', ARRAY['logistics_management','transport'], POINT(121.42, 31.16), '121.42,31.16', 'available', '{"capacity_ton": 10}', '{}', '{}'),
  ('LOG-002', '物资运输车2号', 'cargo_truck', 'logistics', '应急管理局', ARRAY['logistics_management','transport'], POINT(121.54, 31.29), '121.54,31.29', 'available', '{"capacity_ton": 10}', '{}', '{}'),
  ('LOG-003', '帐篷车', 'shelter_truck', 'logistics', '民政局', ARRAY['shelter_management','transport'], POINT(121.51, 31.26), '121.51,31.26', 'available', '{"tents": 50, "capacity_person": 250}', '{}', '{}'),
  ('LOG-004', '供水车', 'water_truck', 'logistics', '卫健委', ARRAY['logistics_management','transport'], POINT(121.48, 31.20), '121.48,31.20', 'available', '{"water_ton": 8}', '{}', '{"type": "饮用水"}'),
  ('LOG-005', '发电车', 'generator_truck', 'logistics', '供电公司', ARRAY['power_operation'], POINT(121.46, 31.22), '121.46,31.22', 'available', '{"capacity_kva": 500}', '{}', '{}'),
  
  -- 公安交警
  ('POLICE-001', '交警巡逻车1', 'patrol_car', 'police', '公安局', ARRAY['traffic_control'], POINT(121.45, 31.23), '121.45,31.23', 'available', '{"crew": 2}', '{}', '{}'),
  ('POLICE-002', '交警巡逻车2', 'patrol_car', 'police', '公安局', ARRAY['traffic_control'], POINT(121.50, 31.27), '121.50,31.27', 'available', '{"crew": 2}', '{}', '{}'),
  ('POLICE-003', '清障车', 'tow_truck', 'police', '公安局', ARRAY['debris_clearance','traffic_control'], POINT(121.48, 31.25), '121.48,31.25', 'available', '{"tow_capacity_ton": 20}', '{}', '{}');

-- ========================================
-- 补充数据：历史案例
-- ========================================
INSERT INTO planning.historical_cases (id, name, scene_id, incident_level, location_text, affected_population, task_sequence, resource_allocation, success_rate, response_time_min, casualties, rescued_count, evaluation_score, lessons_learned, occurred_at) VALUES
  ('CASE-EQ-001', '某市6.5级地震救援', 'S1', 'I', '121.50,31.25', 50000,
   ARRAY['EM02','EM01','EM03','EM04','EM06','EM07','EM11','EM10','EM14','EM15','EM25'],
   '{"UAV": 4, "rescue_team": 6, "ambulance": 12, "excavator": 3, "k9_team": 2}',
   0.85, 25, 120, 450, 0.82,
   '1.无人机快速响应对初期态势掌握至关重要；2.搜救犬与生命探测仪配合使用效果最佳；3.重型装备需提前预置',
   '2024-05-12 14:28:00+08'),
  
  ('CASE-FIRE-001', '某化工园区火灾处置', 'S2', 'II', '121.55,31.30', 5000,
   ARRAY['EM01','EM04','EM17','EM18','EM19','EM08','EM09'],
   '{"fire_truck": 8, "foam_truck": 3, "ambulance": 4, "gas_repair": 2}',
   0.92, 12, 3, 0, 0.88,
   '1.燃气关阀必须在灭火前完成；2.泡沫车对化学品火灾效果显著',
   '2024-08-15 09:45:00+08'),
  
  ('CASE-HAZMAT-001', '某企业氨气泄漏事故', 'S3', 'II', '121.48,31.22', 2000,
   ARRAY['EM01','EM04','EM20','EM08','EM09','EM21','EM22'],
   '{"hazmat_vehicle": 2, "decon_vehicle": 1, "ambulance": 3, "uav": 2}',
   0.95, 18, 5, 0, 0.90,
   '1.风向判断对疏散方向选择关键；2.洗消站设置位置需在上风向',
   '2024-06-20 16:30:00+08'),
  
  ('CASE-FLOOD-001', '某县山洪泥石流救援', 'S4', 'II', '121.35,31.40', 8000,
   ARRAY['EM23','EM01','EM04','EM08','EM09','EM10','EM16'],
   '{"uav": 3, "rescue_team": 4, "excavator": 2, "boat": 4, "ambulance": 6}',
   0.78, 35, 25, 180, 0.75,
   '1.预警系统提前量不足是主要教训；2.道路抢通是救援展开的前提',
   '2024-07-08 03:20:00+08'),
  
  ('CASE-WATERLOG-001', '某市暴雨内涝处置', 'S5', 'III', '121.47,31.23', 15000,
   ARRAY['EM01','EM04','EM32','EM31','EM08','EM09','EM10','EM16'],
   '{"pump_truck": 6, "uav": 2, "boat": 5, "ambulance": 4, "traffic_police": 8}',
   0.90, 45, 2, 35, 0.85,
   '1.积水点实时监测对排涝调度很重要；2.低洼区域需提前预警',
   '2024-09-01 18:00:00+08');

-- ========================================
-- 索引优化
-- ========================================
CREATE INDEX idx_tasks_phase ON planning.tasks(phase);
CREATE INDEX idx_tasks_category ON planning.tasks(category);
CREATE INDEX idx_rules_category ON planning.rules(category, active, priority);
CREATE INDEX idx_hard_rules_category ON planning.hard_rules(category, active);
CREATE INDEX idx_soft_rules_category ON planning.soft_rules(category, active);
CREATE INDEX idx_capability_constraints_category ON planning.capability_constraints(category);
CREATE INDEX idx_dispatch_constraints_type ON planning.dispatch_constraints(constraint_type);
CREATE INDEX idx_historical_cases_scene ON planning.historical_cases(scene_id);
CREATE INDEX idx_task_capability_requirements_task ON planning.task_capability_requirements(task_id);

-- ========================================
-- 注释
-- ========================================
COMMENT ON SCHEMA planning IS '应急救灾协同决策系统';
