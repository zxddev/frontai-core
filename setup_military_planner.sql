-- 可选：手工先创建并连接到 military_planner 数据库
-- 示例：
--   CREATE DATABASE military_planner;
--   \c military_planner

-- 创建模式
CREATE SCHEMA IF NOT EXISTS planning;

-- 任务表（MT）
CREATE TABLE planning.tasks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  precondition TEXT NOT NULL,
  effect TEXT NOT NULL,
  typical_scenes TEXT[] NOT NULL,
  phase TEXT NOT NULL,
  required_capabilities TEXT[] DEFAULT '{}'::TEXT[]
);

-- 资源表
CREATE TABLE planning.resources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  capabilities TEXT[] NOT NULL,
  location TEXT NOT NULL, -- "lon,lat"
  status TEXT NOT NULL DEFAULT 'ready',
  properties JSONB DEFAULT '{}'::JSONB
);

-- 场景中心表
CREATE TABLE planning.scene_centers (
  scene_id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  rcs TEXT NOT NULL,
  radiation TEXT NOT NULL,
  location TEXT NOT NULL,
  speed TEXT NOT NULL,
  base_score NUMERIC DEFAULT 0.8
);

-- 编组规则
CREATE TABLE planning.grouping_rules (
  id TEXT PRIMARY KEY,
  pattern TEXT NOT NULL,
  definition TEXT NOT NULL,
  roles JSONB NOT NULL,
  features TEXT NOT NULL,
  scenes TEXT[] NOT NULL
);

-- 能力指标
CREATE TABLE planning.capability_metrics (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  target TEXT NOT NULL,
  unit TEXT NOT NULL,
  constraints TEXT[] NOT NULL
);

-- 能力约束
CREATE TABLE planning.capability_constraints (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  priority TEXT NOT NULL
);

-- 规则主表
CREATE TABLE planning.rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT,
  version INT NOT NULL DEFAULT 1,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  priority INT NOT NULL DEFAULT 100,
  scenes TEXT[] NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 规则触发表
CREATE TABLE planning.rule_triggers (
  id SERIAL PRIMARY KEY,
  rule_id TEXT REFERENCES planning.rules(id) ON DELETE CASCADE,
  condition JSONB NOT NULL,
  cooldown_sec INT DEFAULT 0,
  scope TEXT
);

-- 规则动作表
CREATE TABLE planning.rule_actions (
  id SERIAL PRIMARY KEY,
  rule_id TEXT REFERENCES planning.rules(id) ON DELETE CASCADE,
  action JSONB NOT NULL,
  action_type TEXT NOT NULL
);

-- 基础数据：MT01~MT15
INSERT INTO planning.tasks (id, name, precondition, effect, typical_scenes, phase, required_capabilities) VALUES
  ('MT01', '无人诱饵前出', '无人机可用', '诱使雷达开机', ARRAY['S1','S4'], 'detect', ARRAY['S1-M1']),
  ('MT02', '无源电磁侦收', '敌雷达开机', '获得辐射源方位', ARRAY['S1','S4'], 'detect', ARRAY['S1-M2']),
  ('MT03', '多平台交叉定位', '获取不少于两条方位', '获得精确坐标', ARRAY['S1','S4'], 'locate', ARRAY['S1-M22']),
  ('MT04', '红外搜索与跟踪', '已获取精确坐标且在探测范围', '维持目标航迹', ARRAY['S1'], 'track', ARRAY['S1-M22']),
  ('MT05', '预警机雷达搜索', '无', '发现潜在目标列表', ARRAY['S1','S2','S3'], 'detect', ARRAY['S1-M2']),
  ('MT06', '目标数据链分发', '已有目标列表', '全单元共享目标数据', ARRAY['S1','S2','S3'], 'share', ARRAY['S1-M2']),
  ('MT07', '接收目标数据', '目标数据已分发', '后方平台获得目标数据', ARRAY['S1'], 'aim', ARRAY['S1-M2']),
  ('MT08', '导弹发射', '完成接收与瞄准', '导弹脱离平台', ARRAY['S1','S3','S4'], 'engage', ARRAY['S1-M1']),
  ('MT09', '远程武器发射', '发射决策完成', '武器脱离平台', ARRAY['S1','S3'], 'engage', ARRAY['S1-M1']),
  ('MT10', '海上目标搜索识别', '广域监视完成', '目标类型确认', ARRAY['S3'], 'detect', ARRAY['S1-M2']),
  ('MT11', '电子压制', '目标识别完成', '敌雷达效能降低', ARRAY['S3','S4'], 'aim', ARRAY['S1-M1']),
  ('MT12', '多平台协同攻击', '电子压制完成', '饱和火力投放', ARRAY['S3'], 'engage', ARRAY['S1-M1']),
  ('MT13', '导弹中段制导', '武器发射', '导弹轨迹修正', ARRAY['S3'], 'engage', ARRAY['S1-M2']),
  ('MT14', '协同电子压制', '辐射源定位完成', '敌系统受干扰', ARRAY['S4'], 'aim', ARRAY['S1-M1']),
  ('MT15', '战果评估', '攻击行动完成', '目标状态确认', ARRAY['S1','S2','S3','S4'], 'assess', ARRAY['S1-M22']);

-- DEMO 追加任务：S2/S3/S4 差异化
INSERT INTO planning.tasks (id, name, precondition, effect, typical_scenes, phase, required_capabilities) VALUES
  ('MT21', '预警机引导拦截', '预警机可用', '目标被持续跟踪', ARRAY['S2'], 'detect', ARRAY['S1-M2']),
  ('MT22', '双机拦截交战', '预警机分配目标', '驱离或击落来袭', ARRAY['S2'], 'engage', ARRAY['S1-M1']),
  ('MT31', '对海目标识别', '广域监视完成', '确认舰艇类型', ARRAY['S3'], 'detect', ARRAY['S1-M2']),
  ('MT32', '多轴向饱和攻击', '电子压制完成', '对海目标重创', ARRAY['S3'], 'engage', ARRAY['S1-M1']),
  ('MT41', '前沿电磁侦收', '目标雷达活跃', '精确定位辐射源', ARRAY['S4'], 'detect', ARRAY['S1-M2']),
  ('MT42', '反辐射打击', '定位完成', '摧毁防空节点', ARRAY['S4'], 'engage', ARRAY['S1-M1']);

-- 资源种子数据
INSERT INTO planning.resources (id, name, type, capabilities, location, properties) VALUES
  ('J-20_01', '歼-20长机', 'J-20_LIKE', ARRAY['S1-M1', 'S1-M2'], '121.0,31.0', '{"risk": 0.1, "fuel": 100}'),
  ('J-20_02', '歼-20僚机', 'J-20_LIKE', ARRAY['S1-M1', 'S1-M2'], '121.05,31.05', '{"risk": 0.1, "fuel": 100}'),
  ('UAV_01', '攻击-11无人机', 'UAV_F_8', ARRAY['S1-M22'], '121.2,31.2', '{"risk": 0.05, "endurance": 120}'),
  ('UAV_02', '攻击-11无人机', 'UAV_F_8', ARRAY['S1-M22'], '121.3,31.3', '{"risk": 0.05, "endurance": 120}'),
  ('PL-15_01', 'PL-15导弹', 'PL-15_LIKE', ARRAY['S1-M1'], '121.0,31.0', '{"p_hit": 0.9}');

-- DEMO 追加资源：S2/S3/S4
INSERT INTO planning.resources (id, name, type, capabilities, location, properties) VALUES
  ('J-11_01', 'S2 拦截机1', 'S2_FIGHTER', ARRAY['S1-M1','S1-M2'], '122.0,32.0', '{"risk":0.2,"p_hit":0.7,"cost":200}'),
  ('J-11_02', 'S2 拦截机2', 'S2_FIGHTER', ARRAY['S1-M1','S1-M2'], '122.1,32.1', '{"risk":0.25,"p_hit":0.65,"cost":220}'),
  ('J-15K_01', 'S3 载机1', 'S3_STRIKE', ARRAY['S1-M1'], '123.0,30.5', '{"risk":0.35,"p_hit":0.7,"cost":300}'),
  ('J-15K_02', 'S3 载机2', 'S3_STRIKE', ARRAY['S1-M1'], '123.1,30.6', '{"risk":0.4,"p_hit":0.68,"cost":320}'),
  ('EW_UAV_01', 'S4 侦收无人机', 'S4_EW_UAV', ARRAY['S1-M2'], '124.0,30.0', '{"risk":0.25,"p_hit":0.5,"cost":150}'),
  ('HARM_01', 'S4 反辐射导弹', 'S4_HARM', ARRAY['S1-M1'], '124.0,30.0', '{"risk":0.2,"p_hit":0.75,"cost":180}');

-- 场景中心
INSERT INTO planning.scene_centers (scene_id, target_type, rcs, radiation, location, speed, base_score) VALUES
  ('S1', '空中目标', '极低', '间歇/静默', '空中', '高', 0.8),
  ('S2', '空中目标', '中/高', '持续', '空中', '中/高', 0.8),
  ('S3', '水面目标', '极高', '持续', '海上', '低', 0.8),
  ('S4', '地面辐射源', '不适用', '搜索/跟踪', '陆地', '静止', 0.8);

-- 编组规则
INSERT INTO planning.grouping_rules (id, pattern, definition, roles, features, scenes) VALUES
  ('GROUP-001', '1+2', '1有人+2无人（隐身猎杀小组）', '{"manned":"决策核心/静默接敌/致命一击","uav1":"前出侦察/诱骗","uav2":"侧翼掩护/中继制导"}', '高隐蔽性、强突防能力', ARRAY['S1']),
  ('GROUP-003', '1+2', '1有人+2无人（电子战指挥小组）', '{"manned":"电子战指挥","uav1":"前沿侦收","uav2":"诱骗/干扰"}', '电磁优势、风险分散', ARRAY['S1','S4']),
  ('GROUP-006', '2+4', '2有人+4无人（联合猎杀小组）', '{"manned1":"主攻手","manned2":"支援策应","uav1":"侦察定位","uav2":"侦察定位","uav3":"电磁压制","uav4":"电磁压制"}', '决策冗余、火力增强、抗毁性强', ARRAY['S1']);

-- S1 能力指标（现有抄录 M1, M2, M22，其余待补充）
INSERT INTO planning.capability_metrics (id, name, type, target, unit, constraints) VALUES
  ('S1-M1', '雷达信号模拟逼真度', 'KPP', '>=90%', '%', ARRAY['S1-CON1','S1-CON2']),
  ('S1-M2', '频段覆盖范围', 'KPP', '2-18', 'GHz', ARRAY['S1-CON1']),
  ('S1-M22', '抵近侦察安全距离', 'KPP', '>=10', 'km', ARRAY['S1-CON16']);

-- S1 约束（CON1-CON16）
INSERT INTO planning.capability_constraints (id, name, category, description, priority) VALUES
  ('S1-CON1', '频谱管理约束', '战术', '需在指定频段时段发射', '高'),
  ('S1-CON2', '反制规避约束', '环境', '避开敌电子战范围', '高'),
  ('S1-CON3', '航线安全约束', '环境', '规避敌防空雷达区', '高'),
  ('S1-CON4', '任务周期约束', '时间', '控制高危区域停留时间', '中'),
  ('S1-CON5', '阵位几何约束', '几何', '目标侧后向接收位', '高'),
  ('S1-CON6', '时统可靠性约束', '资源', '需多源时统备份', '高'),
  ('S1-CON7', '网络联通约束', '协同', '保持视距通信链路', '高'),
  ('S1-CON8', '跟踪前出约束', '战术', '前出至目标航路侧方', '高'),
  ('S1-CON9', '辐射管控约束', '战术', '优先保持雷达静默', '高'),
  ('S1-CON10', '抗干扰约束', '电磁', '复杂电磁环境启用抗干扰模式', '中'),
  ('S1-CON11', '发射阵位约束', '战术', '需占据有效射程内攻击阵位', '高'),
  ('S1-CON12', '静默优先约束', '战术', '未被发现时保持静默', '高'),
  ('S1-CON13', '中继生存约束', '环境', '避免过近接敌', '中'),
  ('S1-CON14', '平台导弹匹配约束', '协同', '制导平台与导弹型号兼容', '高'),
  ('S1-CON15', '气象能见度约束', '环境', '恶劣气象影响光学侦察', '中'),
  ('S1-CON16', '抵近时机约束', '战术', '需在威胁清除后实施', '高');

-- 基础规则集 R-001 ~ R-006（示例）
INSERT INTO planning.rules (id, name, category, description, priority, scenes) VALUES
  ('R-001', '反隐身空战', '体系支援', '空中隐身目标优先诱敌开机+远程打击', 120, ARRAY['S1']),
  ('R-002', '电子诱骗', '电子战', '无人诱饵前出引导雷达暴露', 110, ARRAY['S1','S4']),
  ('R-003', '常规空战拦截', '制空', '非隐身来袭时预警机引导中距拦射', 100, ARRAY['S2']),
  ('R-004', '对海饱和攻击', '打击', '多轴向防区外饱和攻击', 105, ARRAY['S3']),
  ('R-005', '防空压制', '电子战', '诱骗+反辐射压制地面防空', 115, ARRAY['S4']),
  ('R-006', '预警机引导', '体系支援', '预警机远程搜索与分发', 90, ARRAY['S1','S2']);

INSERT INTO planning.rule_triggers (rule_id, condition, cooldown_sec, scope) VALUES
  ('R-001', '{"target":"stealth","threat":"high"}', 0, 'scene'),
  ('R-002', '{"ew":"needed","uav":"available"}', 0, 'scene'),
  ('R-003', '{"target":"non_stealth","heading":"hostile"}', 0, 'scene'),
  ('R-004', '{"target":"ship","defense":"strong"}', 0, 'scene'),
  ('R-005', '{"radar":"active"}', 0, 'scene'),
  ('R-006', '{"mission":"air_defense"}', 0, 'scene');

INSERT INTO planning.rule_actions (rule_id, action, action_type) VALUES
  ('R-001', '{"inject_task":"MT01","adjust_weight":{"success":0.05}}', 'adjust_weight'),
  ('R-002', '{"inject_task":"MT01","position":"pre_detect"}', 'inject_task'),
  ('R-003', '{"route_change":"bvr_intercept"}', 'route_change'),
  ('R-004', '{"inject_task":"MT12","position":"strike"}', 'inject_task'),
  ('R-005', '{"inject_task":"MT11","position":"aim"}', 'inject_task'),
  ('R-006', '{"adjust_weight":{"success":0.03}}', 'adjust_weight');

-- 注释
COMMENT ON TABLE planning.rules IS '规则主表：存储规则基础信息';
COMMENT ON COLUMN planning.rules.scenes IS '规则适用场景数组';
COMMENT ON TABLE planning.rule_triggers IS '规则触发表：存储触发条件';
COMMENT ON TABLE planning.rule_actions IS '规则动作表：存储动作定义';

-- 规则扩展（docx TRR/HR/决策权重/场景议程）
CREATE TABLE IF NOT EXISTS planning.trr_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  conditions TEXT[] NOT NULL,
  actions TEXT[] NOT NULL,
  description TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT 'docx-2025-11-24',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE planning.trr_rules IS 'docx 抄录的 TRR-001-001~012 规则库';

CREATE TABLE IF NOT EXISTS planning.hard_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  condition TEXT NOT NULL,
  decision TEXT NOT NULL,
  description TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT 'docx-2025-11-24',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE planning.hard_rules IS 'docx 抄录的硬约束规则，一票否决';

CREATE TABLE IF NOT EXISTS planning.decision_weights (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  weight_success NUMERIC NOT NULL,
  weight_time NUMERIC NOT NULL,
  weight_cost NUMERIC NOT NULL,
  weight_risk NUMERIC NOT NULL,
  weight_redundancy NUMERIC NOT NULL,
  interpretation JSONB NOT NULL,
  version TEXT NOT NULL DEFAULT 'docx-2025-11-24',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE planning.decision_weights IS 'docx 决策偏好权重库（如快速夺取主动权）';

CREATE TABLE IF NOT EXISTS planning.scene_task_agendas (
  scene_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  initial_tasks TEXT[] NOT NULL,
  tactical_preferences TEXT[] NOT NULL,
  evidence TEXT,
  version TEXT NOT NULL DEFAULT 'docx-2025-11-24',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE planning.scene_task_agendas IS 'docx 命中 TRR 后的初始任务议程与战术偏好';

-- 方案打分与仿真审计
CREATE TABLE IF NOT EXISTS planning.plan_scores (
  id SERIAL PRIMARY KEY,
  plan_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  weight_profile_id TEXT REFERENCES planning.decision_weights(id),
  success NUMERIC,
  time_cost NUMERIC,
  cost NUMERIC,
  risk NUMERIC,
  redundancy NUMERIC,
  score NUMERIC,
  trace_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE planning.plan_scores IS '方案评分：软规则加权后的指标与总分';

CREATE INDEX IF NOT EXISTS idx_plan_scores_scene ON planning.plan_scores(scene_id);
CREATE INDEX IF NOT EXISTS idx_plan_scores_best ON planning.plan_scores(score DESC);

CREATE TABLE IF NOT EXISTS planning.simulation_runs (
  id SERIAL PRIMARY KEY,
  plan_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  weight_profile_id TEXT REFERENCES planning.decision_weights(id),
  input JSONB NOT NULL,
  output JSONB NOT NULL,
  trace_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE planning.simulation_runs IS '仿真/退化评分运行记录，含输入输出与 trace_id';

-- 索引增强
CREATE INDEX IF NOT EXISTS idx_rules_cat_active_pri ON planning.rules(category, active, priority);
CREATE INDEX IF NOT EXISTS idx_resources_location ON planning.resources(location);
