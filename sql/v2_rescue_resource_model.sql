-- ============================================================================
-- 应急救灾资源数据模型 V2
-- 包含：想定、救援队伍、队员、装备、能力等完整数据结构
-- ============================================================================

-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 创建新schema
CREATE SCHEMA IF NOT EXISTS operational_v2;

-- ============================================================================
-- 1. 想定表 (scenarios_v2) - 顶层业务对象
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.scenarios_v2 CASCADE;
CREATE TABLE operational_v2.scenarios_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,                    -- "四川茂县6.8级地震想定"
    scenario_type VARCHAR(50) NOT NULL,            -- earthquake/flood/fire/hazmat/landslide
    response_level VARCHAR(10),                    -- I/II/III/IV 响应等级
    status VARCHAR(20) DEFAULT 'active',           -- draft/active/resolved/archived
    location GEOGRAPHY(POINT),                     -- 事发中心点
    affected_area GEOGRAPHY(POLYGON),              -- 影响范围
    started_at TIMESTAMPTZ,                        -- 事件发生时间
    ended_at TIMESTAMPTZ,                          -- 事件结束时间
    
    -- 想定参数
    parameters JSONB DEFAULT '{}',                 -- 震级、降雨量、风速等
    affected_population INT,                       -- 影响人口估计
    affected_area_km2 DECIMAL(10,2),              -- 影响面积(平方公里)
    
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.scenarios_v2 IS '想定表 - 应急事件的顶层容器，如"四川茂县地震想定"';
COMMENT ON COLUMN operational_v2.scenarios_v2.id IS '想定唯一标识符';
COMMENT ON COLUMN operational_v2.scenarios_v2.name IS '想定名称，如"四川茂县6.8级地震想定"';
COMMENT ON COLUMN operational_v2.scenarios_v2.scenario_type IS '想定类型: earthquake地震/flood洪涝/fire火灾/hazmat危化品/landslide滑坡';
COMMENT ON COLUMN operational_v2.scenarios_v2.response_level IS '响应等级: I特别重大/II重大/III较大/IV一般';
COMMENT ON COLUMN operational_v2.scenarios_v2.status IS '想定状态: draft草稿/active进行中/resolved已解决/archived已归档';
COMMENT ON COLUMN operational_v2.scenarios_v2.location IS '事发中心点地理坐标';
COMMENT ON COLUMN operational_v2.scenarios_v2.affected_area IS '影响范围多边形';
COMMENT ON COLUMN operational_v2.scenarios_v2.started_at IS '事件发生时间';
COMMENT ON COLUMN operational_v2.scenarios_v2.ended_at IS '事件结束时间';
COMMENT ON COLUMN operational_v2.scenarios_v2.parameters IS '想定参数JSON: {magnitude震级, depth_km震源深度, rainfall_mm降雨量, wind_speed_ms风速等}';
COMMENT ON COLUMN operational_v2.scenarios_v2.affected_population IS '预估影响人口数量';
COMMENT ON COLUMN operational_v2.scenarios_v2.affected_area_km2 IS '影响面积（平方公里）';
COMMENT ON COLUMN operational_v2.scenarios_v2.created_by IS '创建人';
COMMENT ON COLUMN operational_v2.scenarios_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.scenarios_v2.updated_at IS '更新时间';

-- ============================================================================
-- 2. 救援队伍类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.team_type_v2 CASCADE;
CREATE TYPE operational_v2.team_type_v2 AS ENUM (
    'fire_rescue',           -- 消防救援队
    'medical',               -- 医疗救护队
    'search_rescue',         -- 搜救队
    'hazmat',                -- 危化品处置队
    'engineering',           -- 工程抢险队
    'communication',         -- 通信保障队
    'logistics',             -- 后勤保障队
    'evacuation',            -- 疏散转移队
    'water_rescue',          -- 水上救援队
    'mountain_rescue',       -- 山地救援队
    'mine_rescue',           -- 矿山救护队
    'armed_police',          -- 武警部队
    'militia',               -- 民兵预备役
    'volunteer'              -- 志愿者队伍
);

-- ============================================================================
-- 3. 救援队伍主表 (rescue_teams_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.rescue_teams_v2 CASCADE;
CREATE TABLE operational_v2.rescue_teams_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,              -- 队伍编号 RT-001
    name VARCHAR(200) NOT NULL,                    -- 茂县消防救援大队
    team_type operational_v2.team_type_v2 NOT NULL,
    
    -- 组织信息
    parent_org VARCHAR(200),                       -- 上级单位
    contact_person VARCHAR(100),                   -- 联系人
    contact_phone VARCHAR(20),                     -- 联系电话
    
    -- 位置信息
    base_location GEOGRAPHY(POINT),                -- 驻地位置
    base_address VARCHAR(300),                     -- 驻地地址
    jurisdiction_area GEOGRAPHY(POLYGON),          -- 管辖区域
    
    -- 人员配置
    total_personnel INT DEFAULT 0,                 -- 总人数
    available_personnel INT DEFAULT 0,             -- 可用人数
    
    -- 能力等级
    capability_level INT DEFAULT 3 CHECK (capability_level BETWEEN 1 AND 5),  -- 1-5级，5最高
    certification_level VARCHAR(50),               -- 资质等级
    
    -- 响应能力
    response_time_minutes INT,                     -- 响应时间(分钟)
    max_deployment_hours INT DEFAULT 72,           -- 最大部署时长(小时)
    
    -- 状态
    status VARCHAR(20) DEFAULT 'standby',          -- standby/deployed/resting/unavailable
    current_task_id UUID,                          -- 当前执行的任务
    
    -- 扩展属性
    properties JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rescue_teams_v2_type ON operational_v2.rescue_teams_v2(team_type);
CREATE INDEX idx_rescue_teams_v2_status ON operational_v2.rescue_teams_v2(status);
CREATE INDEX idx_rescue_teams_v2_location ON operational_v2.rescue_teams_v2 USING GIST(base_location);

COMMENT ON TABLE operational_v2.rescue_teams_v2 IS '救援队伍主表 - 存储各类救援队伍信息';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.id IS '队伍唯一标识符';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.code IS '队伍编号，如RT-FR-001';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.name IS '队伍名称，如"茂县消防救援大队"';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.team_type IS '队伍类型枚举';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.parent_org IS '上级单位名称';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.contact_person IS '联系人姓名';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.contact_phone IS '联系电话';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.base_location IS '驻地地理坐标';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.base_address IS '驻地详细地址';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.jurisdiction_area IS '管辖区域多边形';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.total_personnel IS '队伍总人数';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.available_personnel IS '当前可用人数';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.capability_level IS '能力等级1-5，5为最高（国家级）';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.certification_level IS '资质等级，如"一级消防站"';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.response_time_minutes IS '平均响应时间（分钟）';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.max_deployment_hours IS '最大连续部署时长（小时）';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.status IS '队伍状态: standby待命/deployed已部署/resting休整/unavailable不可用';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.current_task_id IS '当前执行的任务ID';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.updated_at IS '更新时间';

-- ============================================================================
-- 4. 队伍能力表 (team_capabilities_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.team_capabilities_v2 CASCADE;
CREATE TABLE operational_v2.team_capabilities_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    
    capability_code VARCHAR(50) NOT NULL,          -- 能力编码
    capability_name VARCHAR(100) NOT NULL,         -- 能力名称
    capability_category VARCHAR(50),               -- 能力类别
    
    proficiency_level INT DEFAULT 3 CHECK (proficiency_level BETWEEN 1 AND 5),  -- 熟练度1-5
    
    -- 适用灾害类型
    applicable_disasters TEXT[],                   -- {earthquake, flood, fire, ...}
    
    -- 能力参数
    max_capacity INT,                              -- 最大处置能力（如最多救援人数）
    typical_duration_minutes INT,                  -- 典型作业时长
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_team_capabilities_v2_team ON operational_v2.team_capabilities_v2(team_id);
CREATE INDEX idx_team_capabilities_v2_code ON operational_v2.team_capabilities_v2(capability_code);

COMMENT ON TABLE operational_v2.team_capabilities_v2 IS '队伍能力表 - 描述队伍具备的专业能力';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.team_id IS '所属队伍ID，关联rescue_teams_v2表';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.capability_code IS '能力编码，关联capability_codes_v2表';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.capability_name IS '能力名称，如"生命探测"';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.capability_category IS '能力类别: search搜索/rescue救援/medical医疗/hazmat危化/logistics保障';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.proficiency_level IS '熟练度等级1-5，5为最熟练';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.applicable_disasters IS '适用灾害类型数组，如{earthquake,flood}';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.max_capacity IS '最大处置能力，如最多可同时救援人数';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.typical_duration_minutes IS '典型作业时长（分钟）';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.team_capabilities_v2.created_at IS '创建时间';

-- ============================================================================
-- 5. 队员表 (team_members_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.team_members_v2 CASCADE;
CREATE TABLE operational_v2.team_members_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    
    employee_id VARCHAR(50),                       -- 工号
    name VARCHAR(100) NOT NULL,
    gender VARCHAR(10),
    age INT,
    
    -- 职务信息
    position VARCHAR(100),                         -- 职务：队长/副队长/队员
    rank VARCHAR(50),                              -- 职级
    
    -- 资质证书
    certifications TEXT[],                         -- {一级消防员, 急救员, ...}
    
    -- 技能
    skills TEXT[],                                 -- {高空救援, 水域救援, 破拆, ...}
    skill_levels JSONB DEFAULT '{}',               -- {"高空救援": 5, "水域救援": 3}
    
    -- 状态
    status VARCHAR(20) DEFAULT 'available',        -- available/on_duty/resting/injured/leave
    health_status VARCHAR(20) DEFAULT 'fit',       -- fit/minor_issue/unfit
    
    contact_phone VARCHAR(20),
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_team_members_v2_team ON operational_v2.team_members_v2(team_id);
CREATE INDEX idx_team_members_v2_status ON operational_v2.team_members_v2(status);

COMMENT ON TABLE operational_v2.team_members_v2 IS '队员表 - 存储救援队伍成员信息';
COMMENT ON COLUMN operational_v2.team_members_v2.id IS '队员唯一标识符';
COMMENT ON COLUMN operational_v2.team_members_v2.team_id IS '所属队伍ID，关联rescue_teams_v2表';
COMMENT ON COLUMN operational_v2.team_members_v2.employee_id IS '工号/编号';
COMMENT ON COLUMN operational_v2.team_members_v2.name IS '队员姓名';
COMMENT ON COLUMN operational_v2.team_members_v2.gender IS '性别: male男/female女';
COMMENT ON COLUMN operational_v2.team_members_v2.age IS '年龄';
COMMENT ON COLUMN operational_v2.team_members_v2.position IS '职务，如队长/副队长/队员';
COMMENT ON COLUMN operational_v2.team_members_v2.rank IS '职级';
COMMENT ON COLUMN operational_v2.team_members_v2.certifications IS '资质证书数组，如{一级消防员,急救员}';
COMMENT ON COLUMN operational_v2.team_members_v2.skills IS '技能数组，如{高空救援,水域救援,破拆}';
COMMENT ON COLUMN operational_v2.team_members_v2.skill_levels IS '技能等级JSON，如{"高空救援":5,"水域救援":3}';
COMMENT ON COLUMN operational_v2.team_members_v2.status IS '状态: available可用/on_duty执勤/resting休息/injured受伤/leave请假';
COMMENT ON COLUMN operational_v2.team_members_v2.health_status IS '健康状态: fit健康/minor_issue小问题/unfit不适';
COMMENT ON COLUMN operational_v2.team_members_v2.contact_phone IS '联系电话';
COMMENT ON COLUMN operational_v2.team_members_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.team_members_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.team_members_v2.updated_at IS '更新时间';

-- ============================================================================
-- 6. 装备类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.equipment_category_v2 CASCADE;
CREATE TYPE operational_v2.equipment_category_v2 AS ENUM (
    'search_detect',         -- 搜索探测类（生命探测仪、热成像仪）
    'rescue_tool',           -- 救援工具类（破拆工具、液压剪）
    'medical',               -- 医疗类（急救包、担架、AED）
    'protection',            -- 防护类（防护服、呼吸器）
    'communication',         -- 通信类（对讲机、卫星电话）
    'lighting',              -- 照明类（应急灯、探照灯）
    'power',                 -- 电力类（发电机、电池组）
    'transport',             -- 运输类（担架车、物资车）
    'hazmat',                -- 危化类（气体检测、洗消设备）
    'water_rescue',          -- 水上救援类（救生衣、冲锋舟）
    'rope_rescue',           -- 绳索救援类（绳索、安全带）
    'other'                  -- 其他
);

-- ============================================================================
-- 7. 装备主表 (equipment_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.equipment_v2 CASCADE;
CREATE TABLE operational_v2.equipment_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,              -- 装备编号 EQ-001
    name VARCHAR(200) NOT NULL,                    -- 生命探测仪
    category operational_v2.equipment_category_v2 NOT NULL,
    
    -- 规格信息
    model VARCHAR(100),                            -- 型号
    manufacturer VARCHAR(100),                     -- 厂商
    specifications JSONB DEFAULT '{}',             -- 详细规格参数
    
    -- 使用信息
    weight_kg DECIMAL(10,2),                       -- 重量(kg)
    volume_m3 DECIMAL(10,4),                       -- 体积(m³)
    power_requirement VARCHAR(50),                 -- 电源需求
    
    -- 适用场景
    applicable_scenarios TEXT[],                   -- {earthquake, flood, fire}
    terrain_restrictions TEXT[],                   -- 地形限制 {steep_slope, water}
    weather_restrictions TEXT[],                   -- 天气限制 {heavy_rain, strong_wind}
    
    -- 操作要求
    operator_certification VARCHAR(100),           -- 操作资质要求
    min_operators INT DEFAULT 1,                   -- 最少操作人数
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_equipment_v2_category ON operational_v2.equipment_v2(category);

COMMENT ON TABLE operational_v2.equipment_v2 IS '装备主表 - 可携带/消耗的装备定义';
COMMENT ON COLUMN operational_v2.equipment_v2.id IS '装备唯一标识符';
COMMENT ON COLUMN operational_v2.equipment_v2.code IS '装备编号，如EQ-SD-001';
COMMENT ON COLUMN operational_v2.equipment_v2.name IS '装备名称，如"雷达生命探测仪"';
COMMENT ON COLUMN operational_v2.equipment_v2.category IS '装备类别枚举';
COMMENT ON COLUMN operational_v2.equipment_v2.model IS '装备型号';
COMMENT ON COLUMN operational_v2.equipment_v2.manufacturer IS '生产厂商';
COMMENT ON COLUMN operational_v2.equipment_v2.specifications IS '详细规格参数JSON';
COMMENT ON COLUMN operational_v2.equipment_v2.weight_kg IS '重量（公斤）';
COMMENT ON COLUMN operational_v2.equipment_v2.volume_m3 IS '体积（立方米）';
COMMENT ON COLUMN operational_v2.equipment_v2.power_requirement IS '电源需求描述';
COMMENT ON COLUMN operational_v2.equipment_v2.applicable_scenarios IS '适用场景数组，如{earthquake,flood}';
COMMENT ON COLUMN operational_v2.equipment_v2.terrain_restrictions IS '地形限制数组，如{steep_slope,water}';
COMMENT ON COLUMN operational_v2.equipment_v2.weather_restrictions IS '天气限制数组，如{heavy_rain,strong_wind}';
COMMENT ON COLUMN operational_v2.equipment_v2.operator_certification IS '操作资质要求';
COMMENT ON COLUMN operational_v2.equipment_v2.min_operators IS '最少操作人数';
COMMENT ON COLUMN operational_v2.equipment_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.equipment_v2.created_at IS '创建时间';

-- ============================================================================
-- 8. 装备能力表 (equipment_capabilities_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.equipment_capabilities_v2 CASCADE;
CREATE TABLE operational_v2.equipment_capabilities_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID NOT NULL REFERENCES operational_v2.equipment_v2(id) ON DELETE CASCADE,
    
    capability_code VARCHAR(50) NOT NULL,          -- 能力编码
    capability_name VARCHAR(100) NOT NULL,         -- 生命探测/破拆/医疗救治
    
    -- 能力参数
    detection_range_m INT,                         -- 探测范围(米)
    detection_depth_m DECIMAL(5,2),                -- 探测深度(米)
    accuracy_percent DECIMAL(5,2),                 -- 准确率
    processing_capacity INT,                       -- 处理能力(人/小时)
    
    -- 适用条件
    min_temperature_c INT,                         -- 最低工作温度
    max_temperature_c INT,                         -- 最高工作温度
    
    effectiveness_score DECIMAL(3,2) DEFAULT 1.0, -- 效能系数0-1
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_equipment_capabilities_v2_equip ON operational_v2.equipment_capabilities_v2(equipment_id);

COMMENT ON TABLE operational_v2.equipment_capabilities_v2 IS '装备能力表 - 描述装备具备的专业能力及参数';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.equipment_id IS '所属装备ID，关联equipment_v2表';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.capability_code IS '能力编码';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.capability_name IS '能力名称，如"生命探测"';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.detection_range_m IS '探测范围（米）';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.detection_depth_m IS '探测深度（米）';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.accuracy_percent IS '准确率百分比';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.processing_capacity IS '处理能力（人/小时）';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.min_temperature_c IS '最低工作温度（摄氏度）';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.max_temperature_c IS '最高工作温度（摄氏度）';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.effectiveness_score IS '效能系数0-1，1为最高';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.equipment_capabilities_v2.created_at IS '创建时间';

-- ============================================================================
-- 9. 队伍-装备关联表 (team_equipment_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.team_equipment_v2 CASCADE;
CREATE TABLE operational_v2.team_equipment_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    equipment_id UUID NOT NULL REFERENCES operational_v2.equipment_v2(id) ON DELETE CASCADE,
    
    quantity INT NOT NULL DEFAULT 1,               -- 数量
    available_quantity INT NOT NULL DEFAULT 1,     -- 可用数量
    
    -- 装备状态
    status VARCHAR(20) DEFAULT 'ready',            -- ready/in_use/maintenance/damaged
    
    -- 位置（可能不在驻地）
    current_location GEOGRAPHY(POINT),
    location_description VARCHAR(200),
    
    last_maintenance_at TIMESTAMPTZ,
    next_maintenance_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(team_id, equipment_id)
);

CREATE INDEX idx_team_equipment_v2_team ON operational_v2.team_equipment_v2(team_id);
CREATE INDEX idx_team_equipment_v2_equipment ON operational_v2.team_equipment_v2(equipment_id);

COMMENT ON TABLE operational_v2.team_equipment_v2 IS '队伍装备关联表 - 记录队伍拥有的装备';
COMMENT ON COLUMN operational_v2.team_equipment_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.team_equipment_v2.team_id IS '队伍ID，关联rescue_teams_v2表';
COMMENT ON COLUMN operational_v2.team_equipment_v2.equipment_id IS '装备ID，关联equipment_v2表';
COMMENT ON COLUMN operational_v2.team_equipment_v2.quantity IS '装备总数量';
COMMENT ON COLUMN operational_v2.team_equipment_v2.available_quantity IS '当前可用数量';
COMMENT ON COLUMN operational_v2.team_equipment_v2.status IS '装备状态: ready就绪/in_use使用中/maintenance维护中/damaged损坏';
COMMENT ON COLUMN operational_v2.team_equipment_v2.current_location IS '当前位置坐标（可能不在驻地）';
COMMENT ON COLUMN operational_v2.team_equipment_v2.location_description IS '位置描述';
COMMENT ON COLUMN operational_v2.team_equipment_v2.last_maintenance_at IS '上次维护时间';
COMMENT ON COLUMN operational_v2.team_equipment_v2.next_maintenance_at IS '下次计划维护时间';
COMMENT ON COLUMN operational_v2.team_equipment_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.team_equipment_v2.updated_at IS '更新时间';

-- ============================================================================
-- 10. 能力需求映射表 (capability_requirements_v2)
--     定义：什么灾害类型需要什么能力
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.capability_requirements_v2 CASCADE;
CREATE TABLE operational_v2.capability_requirements_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    disaster_type VARCHAR(50) NOT NULL,            -- earthquake/flood/fire/hazmat
    event_subtype VARCHAR(50),                     -- building_collapse/people_trapped/...
    severity_level VARCHAR(20),                    -- critical/high/medium/low
    
    -- 需要的能力
    required_capability_code VARCHAR(50) NOT NULL,
    required_capability_name VARCHAR(100) NOT NULL,
    
    -- 优先级和数量
    priority INT DEFAULT 50,                       -- 0-100
    min_teams INT DEFAULT 1,                       -- 最少需要队伍数
    recommended_teams INT DEFAULT 1,               -- 建议队伍数
    
    -- 时间要求
    response_time_max_minutes INT,                 -- 最大响应时间
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_capability_requirements_v2_disaster ON operational_v2.capability_requirements_v2(disaster_type);

COMMENT ON TABLE operational_v2.capability_requirements_v2 IS '能力需求映射表 - 定义灾害类型与所需能力的映射关系';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.disaster_type IS '灾害类型: earthquake地震/flood洪涝/fire火灾/hazmat危化品';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.event_subtype IS '事件子类型: building_collapse建筑倒塌/people_trapped人员被困等';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.severity_level IS '严重程度: critical紧急/high高/medium中/low低';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.required_capability_code IS '所需能力编码';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.required_capability_name IS '所需能力名称';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.priority IS '优先级0-100，100为最高';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.min_teams IS '最少需要队伍数';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.recommended_teams IS '建议队伍数';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.response_time_max_minutes IS '最大允许响应时间（分钟）';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.capability_requirements_v2.created_at IS '创建时间';

-- ============================================================================
-- 11. 资源调度记录表 (resource_dispatches_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.resource_dispatches_v2 CASCADE;
CREATE TABLE operational_v2.resource_dispatches_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    scenario_id UUID REFERENCES operational_v2.scenarios_v2(id),
    event_id UUID,                                 -- 关联events表
    scheme_id UUID,                                -- 关联scheme表
    task_id UUID,                                  -- 关联tasks表
    
    -- 调度的资源
    team_id UUID REFERENCES operational_v2.rescue_teams_v2(id),
    equipment_ids UUID[],                          -- 携带的装备
    personnel_count INT,                           -- 出动人数
    
    -- 调度信息
    dispatch_type VARCHAR(50),                     -- initial/reinforcement/replacement
    dispatched_at TIMESTAMPTZ DEFAULT now(),
    estimated_arrival_at TIMESTAMPTZ,
    actual_arrival_at TIMESTAMPTZ,
    
    -- 目的地
    destination GEOGRAPHY(POINT),
    destination_address VARCHAR(300),
    
    -- 任务
    mission_description TEXT,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'dispatched',       -- dispatched/en_route/arrived/completed/cancelled
    
    completed_at TIMESTAMPTZ,
    result JSONB DEFAULT '{}',
    
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_resource_dispatches_v2_scenario ON operational_v2.resource_dispatches_v2(scenario_id);
CREATE INDEX idx_resource_dispatches_v2_team ON operational_v2.resource_dispatches_v2(team_id);
CREATE INDEX idx_resource_dispatches_v2_status ON operational_v2.resource_dispatches_v2(status);

COMMENT ON TABLE operational_v2.resource_dispatches_v2 IS '资源调度记录表 - 记录救援资源的调度历史';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.scenario_id IS '关联想定ID';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.event_id IS '关联事件ID';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.scheme_id IS '关联方案ID';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.task_id IS '关联任务ID';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.team_id IS '调度的队伍ID';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.equipment_ids IS '携带的装备ID数组';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.personnel_count IS '出动人数';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.dispatch_type IS '调度类型: initial首次/reinforcement增援/replacement替换';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.dispatched_at IS '调度时间';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.estimated_arrival_at IS '预计到达时间';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.actual_arrival_at IS '实际到达时间';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.destination IS '目的地坐标';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.destination_address IS '目的地地址';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.mission_description IS '任务描述';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.status IS '状态: dispatched已调度/en_route途中/arrived已到达/completed已完成/cancelled已取消';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.completed_at IS '完成时间';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.result IS '执行结果JSON';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.created_by IS '创建人';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.resource_dispatches_v2.updated_at IS '更新时间';

-- ============================================================================
-- 12. 能力编码字典表 (capability_codes_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.capability_codes_v2 CASCADE;
CREATE TABLE operational_v2.capability_codes_v2 (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),                          -- search/rescue/medical/hazmat/logistics/...
    description TEXT,
    
    -- 关联的装备类型
    related_equipment_categories operational_v2.equipment_category_v2[],
    
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.capability_codes_v2 IS '能力编码字典 - 定义所有标准化的能力类型';
COMMENT ON COLUMN operational_v2.capability_codes_v2.code IS '能力编码，主键，如SEARCH_LIFE_DETECT';
COMMENT ON COLUMN operational_v2.capability_codes_v2.name IS '能力名称，如"生命探测"';
COMMENT ON COLUMN operational_v2.capability_codes_v2.category IS '能力类别: search搜索/rescue救援/medical医疗/hazmat危化/fire消防/engineering工程/logistics保障';
COMMENT ON COLUMN operational_v2.capability_codes_v2.description IS '能力描述';
COMMENT ON COLUMN operational_v2.capability_codes_v2.related_equipment_categories IS '关联的装备类型数组';
COMMENT ON COLUMN operational_v2.capability_codes_v2.created_at IS '创建时间';

-- ============================================================================
-- 插入能力编码字典数据
-- ============================================================================
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories) VALUES
-- 搜索类能力
('SEARCH_LIFE_DETECT', '生命探测', 'search', '使用设备探测被困人员生命迹象', '{search_detect}'),
('SEARCH_THERMAL', '热成像搜索', 'search', '使用热成像仪搜索人员', '{search_detect}'),
('SEARCH_CANINE', '搜救犬搜索', 'search', '使用搜救犬定位被困人员', NULL),
('SEARCH_SONAR', '声纳探测', 'search', '水下声纳探测', '{search_detect,water_rescue}'),

-- 救援类能力
('RESCUE_STRUCTURAL', '建筑物救援', 'rescue', '倒塌建筑物中救援被困人员', '{rescue_tool}'),
('RESCUE_CONFINED', '狭小空间救援', 'rescue', '狭小空间救援', '{rescue_tool,protection}'),
('RESCUE_TRENCH', '沟渠救援', 'rescue', '沟渠/坑道救援', '{rescue_tool,rope_rescue}'),
('RESCUE_ROPE', '绳索救援', 'rescue', '高空/悬崖绳索救援', '{rope_rescue}'),
('RESCUE_WATER_SWIFT', '急流水域救援', 'rescue', '急流水域救援', '{water_rescue}'),
('RESCUE_WATER_FLOOD', '洪水救援', 'rescue', '洪涝灾害救援', '{water_rescue}'),
('RESCUE_VEHICLE', '车辆救援', 'rescue', '车祸/车辆困人救援', '{rescue_tool}'),

-- 医疗类能力
('MEDICAL_TRIAGE', '伤员分诊', 'medical', '现场伤员分类分级', '{medical}'),
('MEDICAL_FIRST_AID', '现场急救', 'medical', '紧急医疗救治', '{medical}'),
('MEDICAL_TRAUMA', '创伤处理', 'medical', '创伤/骨折处理', '{medical}'),
('MEDICAL_CPR', '心肺复苏', 'medical', 'CPR和AED使用', '{medical}'),
('MEDICAL_TRANSPORT', '伤员转运', 'medical', '安全转运伤员', '{medical,transport}'),

-- 危化类能力
('HAZMAT_DETECT', '危化品检测', 'hazmat', '有毒有害物质检测', '{hazmat}'),
('HAZMAT_CONTAIN', '泄漏控制', 'hazmat', '危化品泄漏控制', '{hazmat,protection}'),
('HAZMAT_DECON', '洗消', 'hazmat', '人员/设备洗消', '{hazmat}'),
('HAZMAT_FIRE', '化学火灾扑救', 'hazmat', '危化品火灾扑救', '{hazmat,protection}'),

-- 消防类能力
('FIRE_SUPPRESS', '火灾扑救', 'fire', '常规火灾扑救', '{protection}'),
('FIRE_FOREST', '森林灭火', 'fire', '森林/草原火灾扑救', '{protection}'),
('FIRE_HIGH_RISE', '高层灭火', 'fire', '高层建筑火灾扑救', '{protection,rope_rescue}'),

-- 工程类能力
('ENG_SHORING', '支撑加固', 'engineering', '建筑支撑加固', '{rescue_tool}'),
('ENG_DEMOLITION', '破拆清障', 'engineering', '障碍物破拆清除', '{rescue_tool}'),
('ENG_LIFTING', '重物起吊', 'engineering', '重物起吊搬移', '{rescue_tool}'),

-- 保障类能力
('LOG_POWER', '电力保障', 'logistics', '应急供电', '{power}'),
('LOG_LIGHTING', '照明保障', 'logistics', '现场照明', '{lighting}'),
('LOG_COMM', '通信保障', 'logistics', '应急通信', '{communication}'),
('LOG_SHELTER', '安置保障', 'logistics', '临时安置点搭建', '{other}'),
('LOG_SUPPLY', '物资保障', 'logistics', '救援物资调配', '{transport}');

-- ============================================================================
-- 插入装备数据
-- ============================================================================
INSERT INTO operational_v2.equipment_v2 (code, name, category, model, manufacturer, weight_kg, applicable_scenarios, specifications) VALUES
-- 搜索探测类
('EQ-SD-001', '雷达生命探测仪', 'search_detect', 'LD-100', '中科院', 8.5, '{earthquake,building_collapse}', 
 '{"detection_depth_m": 30, "detection_range_m": 50, "battery_hours": 8}'),
('EQ-SD-002', '蛇眼生命探测仪', 'search_detect', 'SE-200', '消防科技', 3.2, '{earthquake,building_collapse,confined_space}',
 '{"probe_length_m": 3, "camera_resolution": "1080p", "led_light": true}'),
('EQ-SD-003', '热成像仪', 'search_detect', 'FLIR-E8', 'FLIR', 0.8, '{earthquake,fire,search}',
 '{"resolution": "320x240", "temperature_range": "-20~650", "accuracy": 2}'),
('EQ-SD-004', '声波探测仪', 'search_detect', 'DKL-3000', '德国DKL', 2.1, '{earthquake,building_collapse}',
 '{"sensitivity": "heartbeat", "range_m": 20}'),

-- 救援工具类
('EQ-RT-001', '液压剪切器', 'rescue_tool', 'HYD-350', '鲁普', 18.0, '{vehicle_rescue,earthquake}',
 '{"cutting_force_kn": 350, "opening_mm": 180}'),
('EQ-RT-002', '液压扩张器', 'rescue_tool', 'HYD-400', '鲁普', 16.5, '{vehicle_rescue,earthquake}',
 '{"spreading_force_kn": 400, "opening_mm": 720}'),
('EQ-RT-003', '液压顶杆', 'rescue_tool', 'HYD-200', '鲁普', 12.0, '{earthquake,building_collapse}',
 '{"lifting_force_kn": 200, "stroke_mm": 500}'),
('EQ-RT-004', '机动链锯', 'rescue_tool', 'MS-661', '斯蒂尔', 7.4, '{earthquake,forestry}',
 '{"bar_length_cm": 63, "power_kw": 5.4}'),
('EQ-RT-005', '无齿锯', 'rescue_tool', 'K-770', '富世华', 9.6, '{fire,earthquake}',
 '{"blade_diameter_mm": 350, "cutting_depth_mm": 125}'),
('EQ-RT-006', '气垫', 'rescue_tool', 'AIR-30', '威特', 4.2, '{earthquake,vehicle_rescue}',
 '{"lifting_capacity_ton": 30, "height_mm": 400}'),

-- 医疗类
('EQ-MD-001', '急救背囊', 'medical', 'MED-A1', '急救中心', 8.0, '{all}',
 '{"contents": ["bandages", "splints", "tourniquets", "medications"]}'),
('EQ-MD-002', '便携式AED', 'medical', 'HS-1', '飞利浦', 1.5, '{all}',
 '{"battery_shocks": 200, "voice_guidance": true}'),
('EQ-MD-003', '铲式担架', 'medical', 'SC-100', '医疗器械', 6.8, '{all}',
 '{"load_capacity_kg": 170, "material": "aluminum"}'),
('EQ-MD-004', '脊柱固定板', 'medical', 'SP-200', '医疗器械', 4.5, '{all}',
 '{"length_cm": 183, "with_straps": true}'),
('EQ-MD-005', '便携式呼吸机', 'medical', 'LTV-1200', '卡迈特', 5.4, '{all}',
 '{"modes": ["AC", "SIMV", "CPAP"], "battery_hours": 6}'),

-- 防护类
('EQ-PT-001', '空气呼吸器', 'protection', 'SCBA-6.8', '梅思安', 11.2, '{fire,hazmat}',
 '{"cylinder_volume_l": 6.8, "working_time_min": 45}'),
('EQ-PT-002', 'A级防护服', 'protection', 'LEVEL-A', '杜邦', 2.5, '{hazmat}',
 '{"protection_level": "A", "material": "Tychem"}'),
('EQ-PT-003', '防毒面具', 'protection', 'FM-3000', '3M', 0.5, '{hazmat,fire}',
 '{"filter_types": ["organic", "acid", "particulate"]}'),

-- 通信类
('EQ-CM-001', '数字对讲机', 'communication', 'DP-4800', '摩托罗拉', 0.35, '{all}',
 '{"frequency_range": "400-470MHz", "channels": 32, "battery_hours": 12}'),
('EQ-CM-002', '卫星电话', 'communication', 'IsatPhone2', '海事卫星', 0.32, '{all,remote_area}',
 '{"coverage": "global", "battery_hours": 8}'),
('EQ-CM-003', '便携式中继台', 'communication', 'REP-100', '海能达', 15.0, '{all}',
 '{"coverage_km": 30, "channels": 16}'),

-- 照明类
('EQ-LT-001', '移动照明灯组', 'lighting', 'ML-4000', '华荣', 45.0, '{all,night}',
 '{"power_w": 4000, "height_m": 4.5, "coverage_m2": 2000}'),
('EQ-LT-002', '防爆手电', 'lighting', 'RJW-7101', '海洋王', 0.25, '{all,hazmat}',
 '{"lumens": 300, "battery_hours": 10, "explosion_proof": true}'),

-- 电力类
('EQ-PW-001', '汽油发电机', 'power', 'EU-7000', '本田', 78.0, '{all}',
 '{"power_kw": 7.0, "fuel_capacity_l": 25, "runtime_hours": 8}'),
('EQ-PW-002', '便携式电源', 'power', 'PS-2000', '正浩', 25.0, '{all}',
 '{"capacity_wh": 2016, "output_w": 2400}'),

-- 水上救援类
('EQ-WR-001', '救生衣', 'water_rescue', 'LJ-150', '救生设备', 1.2, '{flood,water_rescue}',
 '{"buoyancy_n": 150, "size": "universal"}'),
('EQ-WR-002', '救生圈', 'water_rescue', 'LR-720', '救生设备', 2.5, '{flood,water_rescue}',
 '{"diameter_mm": 720, "material": "polyethylene"}'),
('EQ-WR-003', '橡皮艇', 'water_rescue', 'RB-380', '天海', 65.0, '{flood,water_rescue}',
 '{"length_m": 3.8, "capacity_persons": 6, "motor_compatible": true}'),
('EQ-WR-004', '冲锋舟', 'water_rescue', 'AS-450', '宏帆', 120.0, '{flood,water_rescue}',
 '{"length_m": 4.5, "capacity_persons": 8, "motor_hp": 40}'),

-- 绳索救援类
('EQ-RR-001', '静力绳', 'rope_rescue', 'SR-11', 'BEAL', 0.07, '{rope_rescue,mountain}',
 '{"diameter_mm": 11, "length_m": 50, "breaking_strength_kn": 32}'),
('EQ-RR-002', '全身安全带', 'rope_rescue', 'HB-FULL', 'Petzl', 1.8, '{rope_rescue,high_altitude}',
 '{"load_kg": 150, "fall_arrest": true}'),
('EQ-RR-003', '下降器', 'rope_rescue', 'ID-S', 'Petzl', 0.53, '{rope_rescue}',
 '{"rope_diameter_mm": "10-11.5", "max_load_kg": 150}'),
('EQ-RR-004', '三脚架', 'rope_rescue', 'TR-200', '救援装备', 35.0, '{rope_rescue,confined_space}',
 '{"height_m": 2.2, "load_capacity_kg": 500}');

-- ============================================================================
-- 插入装备能力数据
-- ============================================================================
INSERT INTO operational_v2.equipment_capabilities_v2 (equipment_id, capability_code, capability_name, detection_range_m, detection_depth_m, effectiveness_score) 
SELECT e.id, 'SEARCH_LIFE_DETECT', '生命探测', 50, 30, 0.95
FROM operational_v2.equipment_v2 e WHERE e.code = 'EQ-SD-001';

INSERT INTO operational_v2.equipment_capabilities_v2 (equipment_id, capability_code, capability_name, detection_range_m, effectiveness_score) 
SELECT e.id, 'SEARCH_LIFE_DETECT', '生命探测(蛇眼)', 3, 0.85
FROM operational_v2.equipment_v2 e WHERE e.code = 'EQ-SD-002';

INSERT INTO operational_v2.equipment_capabilities_v2 (equipment_id, capability_code, capability_name, detection_range_m, effectiveness_score) 
SELECT e.id, 'SEARCH_THERMAL', '热成像搜索', 100, 0.90
FROM operational_v2.equipment_v2 e WHERE e.code = 'EQ-SD-003';

INSERT INTO operational_v2.equipment_capabilities_v2 (equipment_id, capability_code, capability_name, effectiveness_score, processing_capacity) 
SELECT e.id, 'RESCUE_STRUCTURAL', '建筑救援(液压剪)', 0.85, 5
FROM operational_v2.equipment_v2 e WHERE e.code = 'EQ-RT-001';

INSERT INTO operational_v2.equipment_capabilities_v2 (equipment_id, capability_code, capability_name, effectiveness_score, processing_capacity) 
SELECT e.id, 'MEDICAL_CPR', 'AED除颤', 0.92, 10
FROM operational_v2.equipment_v2 e WHERE e.code = 'EQ-MD-002';

-- ============================================================================
-- 插入救援队伍数据
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (code, name, team_type, parent_org, contact_person, contact_phone, 
    base_location, base_address, total_personnel, available_personnel, capability_level, response_time_minutes, status)
VALUES
-- 消防救援队伍
('RT-FR-001', '茂县消防救援大队', 'fire_rescue', '阿坝州消防救援支队', '张明', '13800001001',
 ST_GeogFromText('POINT(103.85 31.68)'), '四川省阿坝州茂县凤仪镇', 45, 40, 4, 15, 'standby'),
('RT-FR-002', '汶川消防救援大队', 'fire_rescue', '阿坝州消防救援支队', '李强', '13800001002',
 ST_GeogFromText('POINT(103.58 31.47)'), '四川省阿坝州汶川县威州镇', 50, 45, 4, 20, 'standby'),
('RT-FR-003', '成都特勤消防救援站', 'fire_rescue', '成都市消防救援支队', '王刚', '13800001003',
 ST_GeogFromText('POINT(104.06 30.67)'), '四川省成都市金牛区', 80, 70, 5, 90, 'standby'),

-- 医疗救护队伍
('RT-MD-001', '茂县人民医院急救队', 'medical', '茂县卫健局', '刘芳', '13800002001',
 ST_GeogFromText('POINT(103.85 31.68)'), '四川省阿坝州茂县凤仪镇', 20, 18, 3, 10, 'standby'),
('RT-MD-002', '阿坝州急救中心', 'medical', '阿坝州卫健委', '陈丽', '13800002002',
 ST_GeogFromText('POINT(102.22 31.90)'), '四川省阿坝州马尔康市', 35, 30, 4, 60, 'standby'),
('RT-MD-003', '华西医院应急医疗队', 'medical', '四川大学华西医院', '赵医生', '13800002003',
 ST_GeogFromText('POINT(104.04 30.64)'), '四川省成都市武侯区', 50, 45, 5, 120, 'standby'),

-- 搜救队伍
('RT-SR-001', '阿坝州应急救援队', 'search_rescue', '阿坝州应急管理局', '黄勇', '13800003001',
 ST_GeogFromText('POINT(102.22 31.90)'), '四川省阿坝州马尔康市', 30, 25, 4, 45, 'standby'),
('RT-SR-002', '四川省矿山救护队', 'mine_rescue', '四川煤监局', '周平', '13800003002',
 ST_GeogFromText('POINT(104.10 30.65)'), '四川省成都市龙泉驿区', 60, 50, 5, 90, 'standby'),
('RT-SR-003', '蓝天救援队茂县分队', 'volunteer', '蓝天救援队', '孙涛', '13800003003',
 ST_GeogFromText('POINT(103.85 31.68)'), '四川省阿坝州茂县凤仪镇', 25, 20, 3, 30, 'standby'),

-- 工程抢险队伍
('RT-EN-001', '茂县住建局抢险队', 'engineering', '茂县住建局', '吴建', '13800004001',
 ST_GeogFromText('POINT(103.85 31.68)'), '四川省阿坝州茂县凤仪镇', 40, 35, 3, 20, 'standby'),
('RT-EN-002', '四川路桥抢险队', 'engineering', '四川路桥集团', '郑工', '13800004002',
 ST_GeogFromText('POINT(104.08 30.66)'), '四川省成都市成华区', 100, 80, 4, 120, 'standby'),

-- 通信保障队伍
('RT-CM-001', '阿坝移动应急通信队', 'communication', '中国移动阿坝分公司', '钱通', '13800005001',
 ST_GeogFromText('POINT(102.22 31.90)'), '四川省阿坝州马尔康市', 15, 12, 4, 60, 'standby'),

-- 武警部队
('RT-AP-001', '武警阿坝支队', 'armed_police', '武警四川总队', '林指', '13800006001',
 ST_GeogFromText('POINT(102.22 31.90)'), '四川省阿坝州马尔康市', 200, 180, 5, 30, 'standby'),

-- 水上救援
('RT-WR-001', '都江堰水上救援队', 'water_rescue', '成都市应急局', '何波', '13800007001',
 ST_GeogFromText('POINT(103.62 30.99)'), '四川省成都市都江堰市', 25, 22, 4, 60, 'standby');

-- ============================================================================
-- 插入队伍能力数据
-- ============================================================================
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'RESCUE_STRUCTURAL', '建筑物救援', 'rescue', 5, '{earthquake,building_collapse}', 20
FROM operational_v2.rescue_teams_v2 t WHERE t.code = 'RT-FR-001';

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'SEARCH_LIFE_DETECT', '生命探测', 'search', 4, '{earthquake,building_collapse}', 50
FROM operational_v2.rescue_teams_v2 t WHERE t.code = 'RT-FR-001';

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'FIRE_SUPPRESS', '火灾扑救', 'fire', 5, '{fire,earthquake_fire}', 1
FROM operational_v2.rescue_teams_v2 t WHERE t.code IN ('RT-FR-001', 'RT-FR-002', 'RT-FR-003');

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'MEDICAL_TRIAGE', '伤员分诊', 'medical', 5, '{all}', 100
FROM operational_v2.rescue_teams_v2 t WHERE t.code = 'RT-MD-001';

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'MEDICAL_FIRST_AID', '现场急救', 'medical', 5, '{all}', 50
FROM operational_v2.rescue_teams_v2 t WHERE t.code IN ('RT-MD-001', 'RT-MD-002', 'RT-MD-003');

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'RESCUE_CONFINED', '狭小空间救援', 'rescue', 5, '{earthquake,mine_accident}', 10
FROM operational_v2.rescue_teams_v2 t WHERE t.code = 'RT-SR-002';

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'LOG_COMM', '通信保障', 'logistics', 5, '{all}', 1
FROM operational_v2.rescue_teams_v2 t WHERE t.code = 'RT-CM-001';

INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, applicable_disasters, max_capacity)
SELECT t.id, 'RESCUE_WATER_FLOOD', '洪水救援', 'rescue', 5, '{flood}', 30
FROM operational_v2.rescue_teams_v2 t WHERE t.code = 'RT-WR-001';

-- ============================================================================
-- 插入队伍装备关联数据
-- ============================================================================
-- 茂县消防大队的装备
INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 2, 2, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-FR-001' AND e.code = 'EQ-SD-001';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 4, 4, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-FR-001' AND e.code = 'EQ-SD-002';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 2, 2, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-FR-001' AND e.code = 'EQ-RT-001';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 2, 2, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-FR-001' AND e.code = 'EQ-RT-002';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 20, 20, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-FR-001' AND e.code = 'EQ-PT-001';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 30, 30, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-FR-001' AND e.code = 'EQ-CM-001';

-- 医疗队的装备
INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 10, 10, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-MD-001' AND e.code = 'EQ-MD-001';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 5, 5, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-MD-001' AND e.code = 'EQ-MD-002';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 10, 10, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-MD-001' AND e.code = 'EQ-MD-003';

-- 水上救援队的装备
INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 30, 30, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-WR-001' AND e.code = 'EQ-WR-001';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 4, 4, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-WR-001' AND e.code = 'EQ-WR-003';

INSERT INTO operational_v2.team_equipment_v2 (team_id, equipment_id, quantity, available_quantity, status)
SELECT t.id, e.id, 2, 2, 'ready'
FROM operational_v2.rescue_teams_v2 t, operational_v2.equipment_v2 e
WHERE t.code = 'RT-WR-001' AND e.code = 'EQ-WR-004';

-- ============================================================================
-- 插入能力需求映射数据
-- ============================================================================
INSERT INTO operational_v2.capability_requirements_v2 (disaster_type, event_subtype, severity_level, required_capability_code, required_capability_name, priority, min_teams, recommended_teams, response_time_max_minutes)
VALUES
-- 地震相关
('earthquake', 'building_collapse', 'critical', 'SEARCH_LIFE_DETECT', '生命探测', 100, 1, 3, 30),
('earthquake', 'building_collapse', 'critical', 'RESCUE_STRUCTURAL', '建筑物救援', 95, 2, 5, 30),
('earthquake', 'building_collapse', 'critical', 'MEDICAL_TRIAGE', '伤员分诊', 90, 1, 2, 30),
('earthquake', 'building_collapse', 'critical', 'MEDICAL_FIRST_AID', '现场急救', 90, 1, 3, 30),
('earthquake', 'people_trapped', 'high', 'SEARCH_LIFE_DETECT', '生命探测', 100, 1, 2, 45),
('earthquake', 'people_trapped', 'high', 'RESCUE_CONFINED', '狭小空间救援', 90, 1, 2, 45),
('earthquake', 'road_blocked', 'medium', 'ENG_DEMOLITION', '破拆清障', 70, 1, 2, 60),
('earthquake', 'secondary_fire', 'high', 'FIRE_SUPPRESS', '火灾扑救', 95, 1, 3, 20),

-- 洪涝相关
('flood', 'people_stranded', 'critical', 'RESCUE_WATER_FLOOD', '洪水救援', 100, 1, 3, 30),
('flood', 'people_stranded', 'critical', 'MEDICAL_FIRST_AID', '现场急救', 85, 1, 2, 45),
('flood', 'dam_breach', 'critical', 'RESCUE_WATER_FLOOD', '洪水救援', 100, 2, 5, 20),

-- 火灾相关
('fire', 'building_fire', 'high', 'FIRE_SUPPRESS', '火灾扑救', 100, 1, 3, 15),
('fire', 'building_fire', 'high', 'MEDICAL_FIRST_AID', '现场急救', 80, 1, 2, 20),
('fire', 'forest_fire', 'high', 'FIRE_FOREST', '森林灭火', 100, 3, 10, 60),

-- 危化品相关
('hazmat', 'chemical_leak', 'critical', 'HAZMAT_DETECT', '危化品检测', 100, 1, 2, 30),
('hazmat', 'chemical_leak', 'critical', 'HAZMAT_CONTAIN', '泄漏控制', 95, 1, 2, 30),
('hazmat', 'chemical_leak', 'critical', 'HAZMAT_DECON', '洗消', 80, 1, 1, 45);

-- ============================================================================
-- 插入示例想定数据
-- ============================================================================
INSERT INTO operational_v2.scenarios_v2 (name, scenario_type, response_level, status, location, started_at, parameters, affected_population, affected_area_km2, created_by)
VALUES
('四川茂县6.8级地震想定', 'earthquake', 'II', 'active', 
 ST_GeogFromText('POINT(103.85 31.68)'), 
 '2024-01-15 14:30:00+08',
 '{"magnitude": 6.8, "depth_km": 10, "intensity_max": "IX", "aftershock_count": 45}',
 85000, 450.5, 'system'),

('阿坝州山洪泥石流想定', 'flood', 'III', 'draft',
 ST_GeogFromText('POINT(102.50 31.85)'),
 '2024-07-20 03:00:00+08',
 '{"rainfall_24h_mm": 180, "flood_level": "major", "landslide_risk": "high"}',
 12000, 80.0, 'system'),

('汶川县暴雨内涝想定', 'flood', 'IV', 'draft',
 ST_GeogFromText('POINT(103.58 31.47)'),
 '2024-08-01 18:00:00+08',
 '{"rainfall_1h_mm": 80, "waterlogging_depth_m": 1.2, "affected_roads": 15}',
 25000, 35.0, 'system');

-- ============================================================================
-- 创建常用视图
-- ============================================================================

-- 队伍能力汇总视图
CREATE OR REPLACE VIEW operational_v2.v_team_capability_summary_v2 AS
SELECT 
    t.id AS team_id,
    t.code AS team_code,
    t.name AS team_name,
    t.team_type,
    t.total_personnel,
    t.available_personnel,
    t.capability_level,
    t.status,
    t.base_address,
    array_agg(DISTINCT tc.capability_code) AS capabilities,
    COUNT(DISTINCT te.equipment_id) AS equipment_types,
    SUM(te.quantity) AS total_equipment
FROM operational_v2.rescue_teams_v2 t
LEFT JOIN operational_v2.team_capabilities_v2 tc ON t.id = tc.team_id
LEFT JOIN operational_v2.team_equipment_v2 te ON t.id = te.team_id
GROUP BY t.id, t.code, t.name, t.team_type, t.total_personnel, t.available_personnel, t.capability_level, t.status, t.base_address;

-- 装备能力汇总视图
CREATE OR REPLACE VIEW operational_v2.v_equipment_capability_summary_v2 AS
SELECT 
    e.id AS equipment_id,
    e.code AS equipment_code,
    e.name AS equipment_name,
    e.category,
    e.model,
    e.applicable_scenarios,
    array_agg(ec.capability_code) AS capabilities,
    AVG(ec.effectiveness_score) AS avg_effectiveness
FROM operational_v2.equipment_v2 e
LEFT JOIN operational_v2.equipment_capabilities_v2 ec ON e.id = ec.equipment_id
GROUP BY e.id, e.code, e.name, e.category, e.model, e.applicable_scenarios;

-- ============================================================================
-- 输出统计信息
-- ============================================================================
DO $$
DECLARE
    v_scenarios INT;
    v_teams INT;
    v_equipment INT;
    v_capabilities INT;
BEGIN
    SELECT COUNT(*) INTO v_scenarios FROM operational_v2.scenarios_v2;
    SELECT COUNT(*) INTO v_teams FROM operational_v2.rescue_teams_v2;
    SELECT COUNT(*) INTO v_equipment FROM operational_v2.equipment_v2;
    SELECT COUNT(*) INTO v_capabilities FROM operational_v2.capability_codes_v2;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'V2 资源模型创建完成';
    RAISE NOTICE '想定数: %', v_scenarios;
    RAISE NOTICE '救援队伍数: %', v_teams;
    RAISE NOTICE '装备类型数: %', v_equipment;
    RAISE NOTICE '能力编码数: %', v_capabilities;
    RAISE NOTICE '========================================';
END $$;
