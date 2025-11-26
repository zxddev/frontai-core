-- ============================================================================
-- V2 事件与方案模型 (v2_event_scheme_model.sql)
-- 核心业务流程: 事件 → 方案 → 任务 → 分配
-- ============================================================================

-- ============================================================================
-- 枚举类型定义
-- ============================================================================

-- 事件类型
CREATE TYPE event_type_v2 AS ENUM (
    'trapped_person',      -- 被困人员
    'fire',                -- 火灾
    'flood',               -- 洪水
    'landslide',           -- 滑坡
    'building_collapse',   -- 建筑倒塌
    'road_damage',         -- 道路损毁
    'power_outage',        -- 电力中断
    'communication_lost',  -- 通信中断
    'hazmat_leak',         -- 危化品泄漏
    'epidemic',            -- 疫情
    'earthquake_secondary',-- 地震次生灾害
    'other'                -- 其他
);

-- 事件来源
CREATE TYPE event_source_type_v2 AS ENUM (
    'manual_report',       -- 人工上报
    'ai_detection',        -- AI识别(无人机图像等)
    'sensor_alert',        -- 传感器告警
    'system_inference',    -- 系统推演
    'external_system'      -- 外部系统接入
);

-- 事件状态
CREATE TYPE event_status_v2 AS ENUM (
    'pending',             -- 待确认 (AI评分<0.6)
    'pre_confirmed',       -- 预确认 (0.6≤AI评分<0.85)，30分钟倒计时等待人工复核
    'confirmed',           -- 已确认 (AI评分≥0.85自动确认 或 人工确认)
    'planning',            -- 方案制定中
    'executing',           -- 执行中
    'resolved',            -- 已解决
    'escalated',           -- 已升级
    'cancelled'            -- 已取消(误报等)
);

-- 事件优先级
CREATE TYPE event_priority_v2 AS ENUM (
    'critical',            -- 紧急(人命关天)
    'high',                -- 高
    'medium',              -- 中
    'low'                  -- 低
);

-- 方案类型
CREATE TYPE scheme_type_v2 AS ENUM (
    'search_rescue',       -- 搜救方案
    'evacuation',          -- 疏散方案
    'supply_delivery',     -- 物资调配
    'medical',             -- 医疗救护
    'communication',       -- 通信保障
    'traffic_control',     -- 交通管制
    'comprehensive'        -- 综合方案
);

-- 方案来源
CREATE TYPE scheme_source_v2 AS ENUM (
    'ai_generated',        -- AI生成
    'human_created',       -- 人工编制
    'template_based',      -- 基于预案模板
    'hybrid'               -- 混合(AI+人工)
);

-- 方案状态
CREATE TYPE scheme_status_v2 AS ENUM (
    'draft',               -- 草稿
    'pending_review',      -- 待审批
    'approved',            -- 已批准
    'executing',           -- 执行中
    'completed',           -- 已完成
    'cancelled',           -- 已取消
    'superseded'           -- 已被替代
);

-- 资源分配状态
CREATE TYPE allocation_status_v2 AS ENUM (
    'proposed',            -- AI提议
    'confirmed',           -- 已确认
    'modified',            -- 人工修改
    'rejected',            -- 已拒绝
    'executing',           -- 执行中
    'completed'            -- 已完成
);

-- ============================================================================
-- 事件表 events_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS events_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定
    scenario_id UUID NOT NULL,
    
    -- 事件编号 (场景内唯一，用于显示)
    event_code VARCHAR(50) NOT NULL,
    
    -- 事件类型
    event_type event_type_v2 NOT NULL,
    
    -- 事件来源
    source_type event_source_type_v2 NOT NULL DEFAULT 'manual_report',
    
    -- 来源详情 (报警人信息/传感器ID/AI模型等)
    source_detail JSONB DEFAULT '{}',
    
    -- 事件名称/标题
    title VARCHAR(500) NOT NULL,
    
    -- 事件描述
    description TEXT,
    
    -- 事件位置 (精确点位)
    location GEOMETRY(Point, 4326) NOT NULL,
    
    -- 影响范围 (面状区域)
    affected_area GEOMETRY(Polygon, 4326),
    
    -- 地址描述
    address TEXT,
    
    -- 事件状态
    status event_status_v2 NOT NULL DEFAULT 'pending',
    
    -- 优先级
    priority event_priority_v2 NOT NULL DEFAULT 'medium',
    
    -- 预估受困人数
    estimated_victims INTEGER DEFAULT 0,
    
    -- 已救出人数
    rescued_count INTEGER DEFAULT 0,
    
    -- 伤亡人数
    casualty_count INTEGER DEFAULT 0,
    
    -- 是否有黄金救援时间限制
    is_time_critical BOOLEAN DEFAULT false,
    
    -- 黄金时间截止 (如有)
    golden_hour_deadline TIMESTAMPTZ,
    
    -- 父事件ID (次生灾害关联)
    parent_event_id UUID REFERENCES events_v2(id),
    
    -- 合并到的事件ID (重复上报合并)
    merged_into_event_id UUID REFERENCES events_v2(id),
    
    -- 关联的地图实体ID
    entity_id UUID,
    
    -- 现场照片/视频
    media_attachments JSONB DEFAULT '[]',
    
    -- 上报人/确认人/关闭人
    reported_by UUID,
    confirmed_by UUID,
    resolved_by UUID,
    
    -- 自动确认标记 (AI评分≥0.85或满足AC规则)
    auto_confirmed BOOLEAN DEFAULT false,
    
    -- 预确认相关字段 (status='pre_confirmed'时使用)
    pre_confirm_expires_at TIMESTAMPTZ,           -- 30分钟倒计时截止时间
    pre_allocated_resources JSONB DEFAULT '[]',   -- 预锁定资源列表 [{resource_id, lock_type, expires_at}]
    pre_generated_scheme_id UUID,                 -- 预生成的草案方案ID
    
    -- AI确认评分
    confirmation_score DECIMAL(5,4),              -- 确认评分(0~1)
    matched_auto_confirm_rules VARCHAR(20)[],     -- 匹配的自动确认规则 ['AC-001', 'AC-003']
    
    -- 时间戳
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    pre_confirmed_at TIMESTAMPTZ,                 -- 预确认时间
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 唯一约束
    UNIQUE(scenario_id, event_code)
);

-- 索引
CREATE INDEX idx_events_v2_scenario ON events_v2(scenario_id);
CREATE INDEX idx_events_v2_status ON events_v2(status);
CREATE INDEX idx_events_v2_priority ON events_v2(priority);
CREATE INDEX idx_events_v2_type ON events_v2(event_type);
CREATE INDEX idx_events_v2_location ON events_v2 USING GIST(location);
CREATE INDEX idx_events_v2_affected_area ON events_v2 USING GIST(affected_area);
CREATE INDEX idx_events_v2_parent ON events_v2(parent_event_id) WHERE parent_event_id IS NOT NULL;
CREATE INDEX idx_events_v2_time_critical ON events_v2(golden_hour_deadline) WHERE is_time_critical = true;
CREATE INDEX idx_events_v2_pre_confirm_expires ON events_v2(pre_confirm_expires_at) WHERE status = 'pre_confirmed';

-- ============================================================================
-- 事件动态更新记录 event_updates_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS event_updates_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    event_id UUID NOT NULL REFERENCES events_v2(id) ON DELETE CASCADE,
    
    -- 更新类型
    update_type VARCHAR(50) NOT NULL, -- status_change/info_update/victim_update/location_update
    
    -- 更新前状态/值
    previous_value JSONB,
    
    -- 更新后状态/值
    new_value JSONB,
    
    -- 更新说明
    description TEXT,
    
    -- 更新来源
    source_type event_source_type_v2 NOT NULL DEFAULT 'manual_report',
    
    -- 更新人
    updated_by UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_event_updates_v2_event ON event_updates_v2(event_id);
CREATE INDEX idx_event_updates_v2_time ON event_updates_v2(created_at);

-- ============================================================================
-- 方案表 schemes_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS schemes_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联事件
    event_id UUID NOT NULL REFERENCES events_v2(id),
    
    -- 所属想定 (冗余，便于查询)
    scenario_id UUID NOT NULL,
    
    -- 方案编号
    scheme_code VARCHAR(50) NOT NULL,
    
    -- 方案类型
    scheme_type scheme_type_v2 NOT NULL,
    
    -- 方案来源
    source scheme_source_v2 NOT NULL DEFAULT 'ai_generated',
    
    -- 方案名称
    title VARCHAR(500) NOT NULL,
    
    -- 方案目标
    objective TEXT NOT NULL,
    
    -- 方案详细描述
    description TEXT,
    
    -- 方案状态
    status scheme_status_v2 NOT NULL DEFAULT 'draft',
    
    -- 约束条件 (JSONB)
    -- { time_limit, resource_limit, terrain_constraints, weather_constraints }
    constraints JSONB DEFAULT '{}',
    
    -- 风险评估 (JSONB)
    -- { risk_level, risk_factors[], mitigation_measures[] }
    risk_assessment JSONB DEFAULT '{}',
    
    -- 预计开始时间
    planned_start_at TIMESTAMPTZ,
    
    -- 预计完成时间
    planned_end_at TIMESTAMPTZ,
    
    -- 实际开始时间
    actual_start_at TIMESTAMPTZ,
    
    -- 实际完成时间
    actual_end_at TIMESTAMPTZ,
    
    -- 预计耗时(分钟)
    estimated_duration_minutes INTEGER,
    
    -- 方案版本 (支持多版本)
    version INTEGER NOT NULL DEFAULT 1,
    
    -- 前一版本ID
    previous_version_id UUID REFERENCES schemes_v2(id),
    
    -- 被替代的方案ID
    supersedes_scheme_id UUID REFERENCES schemes_v2(id),
    
    -- AI生成时的输入快照
    ai_input_snapshot JSONB,
    
    -- AI生成时的置信度
    ai_confidence_score DECIMAL(5,4),
    
    -- AI推理说明
    ai_reasoning TEXT,
    
    -- 创建人/审批人
    created_by UUID,
    reviewed_by UUID,
    approved_by UUID,
    
    -- 审批意见
    review_comment TEXT,
    
    -- 时间戳
    submitted_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(scenario_id, scheme_code)
);

-- 索引
CREATE INDEX idx_schemes_v2_event ON schemes_v2(event_id);
CREATE INDEX idx_schemes_v2_scenario ON schemes_v2(scenario_id);
CREATE INDEX idx_schemes_v2_status ON schemes_v2(status);
CREATE INDEX idx_schemes_v2_type ON schemes_v2(scheme_type);

-- ============================================================================
-- 方案资源分配表 scheme_resource_allocations_v2
-- 核心：记录AI推荐理由和人工修改
-- ============================================================================
CREATE TABLE IF NOT EXISTS scheme_resource_allocations_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联方案
    scheme_id UUID NOT NULL REFERENCES schemes_v2(id) ON DELETE CASCADE,
    
    -- 资源类型
    resource_type VARCHAR(50) NOT NULL, -- team/vehicle/device/equipment/supply
    
    -- 资源ID
    resource_id UUID NOT NULL,
    
    -- 资源名称 (冗余，便于展示)
    resource_name VARCHAR(200),
    
    -- 分配状态
    status allocation_status_v2 NOT NULL DEFAULT 'proposed',
    
    -- 分配角色/任务
    assigned_role VARCHAR(200), -- 在方案中承担的角色
    
    -- ===== AI推荐理由 (核心字段) =====
    
    -- 综合匹配得分 (0-100)
    match_score DECIMAL(5,2),
    
    -- 能力匹配说明
    capability_match_reason TEXT,
    
    -- 距离因素说明
    distance_reason TEXT,
    
    -- 可用性说明
    availability_reason TEXT,
    
    -- 装备适配说明
    equipment_reason TEXT,
    
    -- 历史表现说明
    experience_reason TEXT,
    
    -- 完整推荐理由 (汇总)
    full_recommendation_reason TEXT,
    
    -- 推荐排名
    recommendation_rank INTEGER,
    
    -- ===== 人工修改记录 =====
    
    -- 是否被人工修改
    is_human_modified BOOLEAN DEFAULT false,
    
    -- 人工修改原因
    human_modification_reason TEXT,
    
    -- 修改人
    modified_by UUID,
    
    -- 修改时间
    modified_at TIMESTAMPTZ,
    
    -- 原始AI推荐的资源ID (如果被替换)
    original_resource_id UUID,
    
    -- ===== 备选资源 =====
    
    -- 备选资源列表 (JSONB)
    -- [{ resource_id, resource_name, match_score, reason }]
    alternative_resources JSONB DEFAULT '[]',
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_scheme_allocations_v2_scheme ON scheme_resource_allocations_v2(scheme_id);
CREATE INDEX idx_scheme_allocations_v2_resource ON scheme_resource_allocations_v2(resource_type, resource_id);
CREATE INDEX idx_scheme_allocations_v2_status ON scheme_resource_allocations_v2(status);

-- ============================================================================
-- 任务执行分配表 task_assignments_v2 (增强版)
-- ============================================================================
CREATE TABLE IF NOT EXISTS task_assignments_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联任务
    task_id UUID NOT NULL,
    
    -- 执行者类型
    assignee_type VARCHAR(50) NOT NULL, -- team/vehicle/device/user
    
    -- 执行者ID
    assignee_id UUID NOT NULL,
    
    -- 执行者名称 (冗余)
    assignee_name VARCHAR(200),
    
    -- 分配来源
    assignment_source VARCHAR(50) NOT NULL DEFAULT 'ai_recommended', -- ai_recommended/human_assigned
    
    -- 分配理由
    assignment_reason TEXT,
    
    -- 状态
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending/accepted/rejected/executing/completed/failed
    
    -- 拒绝原因 (如果拒绝)
    rejection_reason TEXT,
    
    -- 分配人
    assigned_by UUID,
    
    -- 时间戳
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notified_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- 执行进度 (0-100)
    progress_percent INTEGER DEFAULT 0,
    
    -- 执行反馈/备注
    execution_notes TEXT,
    
    -- 完成情况说明
    completion_summary TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_task_assignments_v2_task ON task_assignments_v2(task_id);
CREATE INDEX idx_task_assignments_v2_assignee ON task_assignments_v2(assignee_type, assignee_id);
CREATE INDEX idx_task_assignments_v2_status ON task_assignments_v2(status);

-- ============================================================================
-- AI决策日志表 ai_decision_logs_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_decision_logs_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定
    scenario_id UUID NOT NULL,
    
    -- 关联事件 (如有)
    event_id UUID REFERENCES events_v2(id),
    
    -- 关联方案 (如有)
    scheme_id UUID REFERENCES schemes_v2(id),
    
    -- 决策类型
    decision_type VARCHAR(100) NOT NULL, -- resource_matching/route_planning/risk_assessment/scheme_generation
    
    -- 使用的算法
    algorithm_used VARCHAR(200),
    
    -- 输入数据快照
    input_snapshot JSONB NOT NULL,
    
    -- 输出结果
    output_result JSONB NOT NULL,
    
    -- 置信度 (0-1)
    confidence_score DECIMAL(5,4),
    
    -- 推理链条 (可解释性)
    reasoning_chain JSONB,
    
    -- 耗时(毫秒)
    processing_time_ms INTEGER,
    
    -- 是否被采纳
    is_accepted BOOLEAN,
    
    -- 人工反馈
    human_feedback TEXT,
    
    -- 反馈评分 (-1=差, 0=中, 1=好)
    feedback_rating INTEGER,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_ai_decision_logs_v2_scenario ON ai_decision_logs_v2(scenario_id);
CREATE INDEX idx_ai_decision_logs_v2_event ON ai_decision_logs_v2(event_id) WHERE event_id IS NOT NULL;
CREATE INDEX idx_ai_decision_logs_v2_type ON ai_decision_logs_v2(decision_type);
CREATE INDEX idx_ai_decision_logs_v2_time ON ai_decision_logs_v2(created_at);

-- ============================================================================
-- 视图：事件完整信息
-- ============================================================================
CREATE OR REPLACE VIEW events_full_v2 AS
SELECT 
    e.*,
    ST_AsGeoJSON(e.location)::JSONB as location_geojson,
    ST_AsGeoJSON(e.affected_area)::JSONB as affected_area_geojson,
    (SELECT COUNT(*) FROM schemes_v2 s WHERE s.event_id = e.id) as scheme_count,
    (SELECT COUNT(*) FROM events_v2 ce WHERE ce.parent_event_id = e.id) as child_event_count,
    pe.title as parent_event_title
FROM events_v2 e
LEFT JOIN events_v2 pe ON pe.id = e.parent_event_id;

-- ============================================================================
-- 视图：方案完整信息(含资源分配)
-- ============================================================================
CREATE OR REPLACE VIEW schemes_full_v2 AS
SELECT 
    s.*,
    e.title as event_title,
    e.event_type,
    e.priority as event_priority,
    (SELECT COUNT(*) FROM scheme_resource_allocations_v2 sra WHERE sra.scheme_id = s.id) as allocation_count,
    (SELECT jsonb_agg(jsonb_build_object(
        'id', sra.id,
        'resource_type', sra.resource_type,
        'resource_id', sra.resource_id,
        'resource_name', sra.resource_name,
        'match_score', sra.match_score,
        'full_recommendation_reason', sra.full_recommendation_reason,
        'is_human_modified', sra.is_human_modified,
        'status', sra.status
    ))
    FROM scheme_resource_allocations_v2 sra 
    WHERE sra.scheme_id = s.id) as resource_allocations
FROM schemes_v2 s
JOIN events_v2 e ON e.id = s.event_id;

-- ============================================================================
-- 函数：生成事件编号
-- ============================================================================
CREATE OR REPLACE FUNCTION generate_event_code(p_scenario_id UUID)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_count INTEGER;
    v_code VARCHAR(50);
BEGIN
    SELECT COUNT(*) + 1 INTO v_count FROM events_v2 WHERE scenario_id = p_scenario_id;
    v_code := 'EVT-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || LPAD(v_count::TEXT, 4, '0');
    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 函数：生成方案编号
-- ============================================================================
CREATE OR REPLACE FUNCTION generate_scheme_code(p_scenario_id UUID, p_scheme_type scheme_type_v2)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_count INTEGER;
    v_prefix VARCHAR(10);
    v_code VARCHAR(50);
BEGIN
    SELECT COUNT(*) + 1 INTO v_count FROM schemes_v2 WHERE scenario_id = p_scenario_id;
    
    v_prefix := CASE p_scheme_type
        WHEN 'search_rescue' THEN 'SR'
        WHEN 'evacuation' THEN 'EV'
        WHEN 'supply_delivery' THEN 'SD'
        WHEN 'medical' THEN 'MD'
        WHEN 'communication' THEN 'CM'
        WHEN 'traffic_control' THEN 'TC'
        ELSE 'CP'
    END;
    
    v_code := v_prefix || '-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || LPAD(v_count::TEXT, 4, '0');
    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 触发器：自动更新时间戳
-- ============================================================================
CREATE OR REPLACE FUNCTION update_timestamp_v2()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_events_v2_updated ON events_v2;
CREATE TRIGGER tr_events_v2_updated
    BEFORE UPDATE ON events_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

DROP TRIGGER IF EXISTS tr_schemes_v2_updated ON schemes_v2;
CREATE TRIGGER tr_schemes_v2_updated
    BEFORE UPDATE ON schemes_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

DROP TRIGGER IF EXISTS tr_scheme_allocations_v2_updated ON scheme_resource_allocations_v2;
CREATE TRIGGER tr_scheme_allocations_v2_updated
    BEFORE UPDATE ON scheme_resource_allocations_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

DROP TRIGGER IF EXISTS tr_task_assignments_v2_updated ON task_assignments_v2;
CREATE TRIGGER tr_task_assignments_v2_updated
    BEFORE UPDATE ON task_assignments_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

-- ============================================================================
-- 注释
-- ============================================================================
COMMENT ON TABLE events_v2 IS '事件表 - 灾情事件管理，支持父子事件、事件合并';
COMMENT ON TABLE event_updates_v2 IS '事件动态更新记录 - 追踪事件状态变化';
COMMENT ON TABLE schemes_v2 IS '方案表 - AI生成或人工编制的救援方案';
COMMENT ON TABLE scheme_resource_allocations_v2 IS '方案资源分配 - 记录AI推荐理由和人工修改';
COMMENT ON TABLE task_assignments_v2 IS '任务执行分配 - 任务指派给具体执行者';
COMMENT ON TABLE ai_decision_logs_v2 IS 'AI决策日志 - 记录所有AI决策过程，可追溯可解释';
