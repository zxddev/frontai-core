-- ============================================================================
-- V13 装备推荐表 (v13_equipment_recommendations.sql)
-- 
-- 功能: 存储AI智能体生成的出发前装备推荐结果
-- 关联: 与 events_v2 关联，每个事件可有一个装备推荐
-- ============================================================================

SET search_path TO operational_v2, public;

-- ============================================================================
-- 创建装备推荐状态枚举
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE operational_v2.equipment_recommendation_status AS ENUM (
        'pending',      -- 待处理（智能体正在分析）
        'ready',        -- 已就绪（分析完成，等待确认）
        'confirmed',    -- 已确认（指挥员已确认选择）
        'cancelled'     -- 已取消
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 创建装备推荐表
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.equipment_recommendations_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联事件
    event_id UUID NOT NULL UNIQUE,  -- 一个事件只有一个推荐
    
    -- 推荐状态
    status operational_v2.equipment_recommendation_status NOT NULL DEFAULT 'pending',
    
    -- ==================== AI分析结果 ====================
    
    -- 灾情分析结果（来自灾情理解子图）
    disaster_analysis JSONB,
    -- {
    --   disaster_type, severity, has_building_collapse, 
    --   has_trapped_persons, estimated_trapped, 
    --   has_secondary_fire, has_hazmat_leak, has_road_damage,
    --   affected_population, additional_info
    -- }
    
    -- 需求分析结果
    requirement_analysis JSONB,
    -- {
    --   required_capabilities: ["life_detection", "thermal_imaging"],
    --   required_device_types: ["drone", "dog"],
    --   required_supply_categories: ["medical", "rescue"],
    --   environment_factors: ["collapsed_building", "narrow_space"],
    --   estimated_personnel: 50
    -- }
    
    -- ==================== 推荐清单 ====================
    
    -- 推荐的设备列表
    recommended_devices JSONB NOT NULL DEFAULT '[]',
    -- [{
    --   device_id, device_name, device_type,
    --   modules: [{module_id, module_name, reason}],
    --   reason: "选择理由",
    --   priority: "critical/high/medium/low"
    -- }]
    
    -- 推荐的物资列表
    recommended_supplies JSONB NOT NULL DEFAULT '[]',
    -- [{
    --   supply_id, supply_name, quantity, unit,
    --   reason: "选择理由",
    --   priority: "critical/high/medium/low"
    -- }]
    
    -- ==================== 缺口告警 ====================
    
    shortage_alerts JSONB NOT NULL DEFAULT '[]',
    -- [{
    --   item_type: "device/module/supply",
    --   item_name, required, available, shortage,
    --   severity: "critical/warning",
    --   suggestion: "调配建议"
    -- }]
    
    -- ==================== 装载方案 ====================
    
    loading_plan JSONB,
    -- {
    --   "vehicle_id_1": {
    --     vehicle_name: "消防车-01",
    --     devices: ["device_id_1", "device_id_2"],
    --     supplies: [{supply_id, quantity}],
    --     weight_usage: 0.85,
    --     volume_usage: 0.72
    --   }
    -- }
    
    -- ==================== 确认信息 ====================
    
    -- 最终选择（确认后填充）
    confirmed_devices JSONB,    -- 指挥员确认的设备列表
    confirmed_supplies JSONB,   -- 指挥员确认的物资列表
    confirmation_note TEXT,     -- 确认备注
    
    -- ==================== 追踪信息 ====================
    
    -- 智能体执行追踪
    agent_trace JSONB,
    -- {
    --   phases_executed: [],
    --   llm_calls: 3,
    --   total_time_ms: 5000,
    --   errors: []
    -- }
    
    -- ==================== 时间戳 ====================
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ready_at TIMESTAMPTZ,           -- 分析完成时间
    confirmed_at TIMESTAMPTZ,       -- 确认时间
    confirmed_by UUID,              -- 确认人
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 创建索引
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_equipment_rec_event 
    ON operational_v2.equipment_recommendations_v2(event_id);
    
CREATE INDEX IF NOT EXISTS idx_equipment_rec_status 
    ON operational_v2.equipment_recommendations_v2(status);
    
CREATE INDEX IF NOT EXISTS idx_equipment_rec_created 
    ON operational_v2.equipment_recommendations_v2(created_at);

-- ============================================================================
-- 创建触发器 - 自动更新时间戳
-- ============================================================================

DROP TRIGGER IF EXISTS tr_equipment_rec_updated ON operational_v2.equipment_recommendations_v2;
CREATE TRIGGER tr_equipment_rec_updated
    BEFORE UPDATE ON operational_v2.equipment_recommendations_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- ============================================================================
-- 添加外键约束
-- ============================================================================

-- 如果外键不存在则添加（兼容已有约束）
DO $$ BEGIN
    ALTER TABLE operational_v2.equipment_recommendations_v2 
        ADD CONSTRAINT fk_equipment_rec_event 
        FOREIGN KEY (event_id) 
        REFERENCES operational_v2.events_v2(id) 
        ON DELETE CASCADE;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 添加表注释
-- ============================================================================

COMMENT ON TABLE operational_v2.equipment_recommendations_v2 
    IS '装备推荐表 - 存储AI智能体生成的出发前装备推荐结果';

COMMENT ON COLUMN operational_v2.equipment_recommendations_v2.disaster_analysis 
    IS '灾情分析结果（来自灾情理解子图）';

COMMENT ON COLUMN operational_v2.equipment_recommendations_v2.requirement_analysis 
    IS '装备需求分析结果';

COMMENT ON COLUMN operational_v2.equipment_recommendations_v2.recommended_devices 
    IS '推荐的设备列表，含选择理由';

COMMENT ON COLUMN operational_v2.equipment_recommendations_v2.recommended_supplies 
    IS '推荐的物资列表，含选择理由';

COMMENT ON COLUMN operational_v2.equipment_recommendations_v2.shortage_alerts 
    IS '缺口告警列表';

COMMENT ON COLUMN operational_v2.equipment_recommendations_v2.loading_plan 
    IS '装载方案（设备和物资如何分配到车辆）';

-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'V13 Equipment Recommendations migration completed!' AS result;
