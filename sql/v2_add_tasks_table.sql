-- ============================================================================
-- 任务表 tasks_v2 
-- 
-- 说明：简化的任务执行表，配合 task_assignments_v2 使用
-- 用途：存储从方案(scheme)分解出的具体可执行任务
-- 关系：scenario → event → scheme → task → assignment
-- 
-- 依赖：需要先执行 v2_event_scheme_model.sql 创建 task_assignments_v2 表
-- ============================================================================

-- ============================================================================
-- 1. 创建任务表
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.tasks_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- ========== 关联关系 ==========
    scheme_id UUID NOT NULL,                       -- 所属方案ID（必填）
    scenario_id UUID NOT NULL,                     -- 所属想定ID（必填，冗余便于查询）
    event_id UUID,                                 -- 关联事件ID（可选，任务可能不直接关联事件）
    
    -- ========== 任务标识 ==========
    task_code VARCHAR(50) NOT NULL,                -- 任务编号，格式：TSK-0001（场景内唯一）
    
    -- ========== 任务类型 ==========
    -- search: 搜索任务（搜寻失踪人员）
    -- rescue: 救援任务（营救被困人员）
    -- evacuation: 疏散任务（转移群众）
    -- transport: 运输任务（物资/人员运输）
    -- medical: 医疗任务（现场急救/转运伤员）
    -- supply: 物资任务（物资发放/补给）
    -- reconnaissance: 侦察任务（无人机侦查/现场勘察）
    -- communication: 通信任务（建立通信/信息传递）
    -- other: 其他任务
    task_type VARCHAR(50) NOT NULL,
    
    -- ========== 基本信息 ==========
    title VARCHAR(500) NOT NULL,                   -- 任务标题
    description TEXT,                              -- 任务详细描述
    
    -- ========== 任务状态 ==========
    -- created: 已创建（初始状态）
    -- assigned: 已分配（已指派执行者）
    -- accepted: 已接受（执行者确认接受）
    -- in_progress: 执行中（正在执行）
    -- paused: 已暂停（暂时中断）
    -- completed: 已完成（成功完成）
    -- failed: 已失败（执行失败）
    -- cancelled: 已取消（任务取消）
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    
    -- ========== 优先级 ==========
    -- critical: 紧急（生命危险，立即处理）
    -- high: 高优先级
    -- medium: 中优先级（默认）
    -- low: 低优先级
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    
    -- ========== 目标位置 ==========
    target_location GEOMETRY(Point, 4326),         -- 任务目标点位（WGS84坐标）
    target_address TEXT,                           -- 目标地址描述（如：XX路XX号）
    
    -- ========== 时间计划 ==========
    planned_start_at TIMESTAMPTZ,                  -- 计划开始时间
    planned_end_at TIMESTAMPTZ,                    -- 计划结束时间
    actual_start_at TIMESTAMPTZ,                   -- 实际开始时间（开始执行时自动填充）
    actual_end_at TIMESTAMPTZ,                     -- 实际结束时间（完成/失败时自动填充）
    estimated_duration_minutes INTEGER,            -- 预计执行时长（分钟）
    
    -- ========== 执行说明 ==========
    instructions TEXT,                             -- 执行指令/注意事项
    
    -- ========== 任务需求（JSON格式）==========
    -- 示例：{
    --   "min_personnel": 4,           -- 最少人员数
    --   "required_capabilities": ["水域救援", "绳索救援"],  -- 所需能力
    --   "required_equipment": ["冲锋舟", "救生衣"],        -- 所需装备
    --   "special_requirements": "需要潜水资质"           -- 特殊要求
    -- }
    requirements JSONB DEFAULT '{}',
    
    -- ========== 执行结果 ==========
    rescued_count INTEGER DEFAULT 0,               -- 救出人数（救援类任务统计）
    progress_percent INTEGER DEFAULT 0,            -- 执行进度（0-100%）
    
    -- ========== 审计字段 ==========
    created_by UUID,                               -- 创建人ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- 创建时间
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- 更新时间（自动维护）
    
    -- ========== 约束 ==========
    UNIQUE(scenario_id, task_code)                 -- 场景内任务编号唯一
);

-- ============================================================================
-- 2. 创建索引（提升查询性能）
-- ============================================================================

-- 按方案查询任务
CREATE INDEX IF NOT EXISTS idx_tasks_v2_scheme 
    ON operational_v2.tasks_v2(scheme_id);

-- 按想定查询任务
CREATE INDEX IF NOT EXISTS idx_tasks_v2_scenario 
    ON operational_v2.tasks_v2(scenario_id);

-- 按事件查询任务（部分索引，仅索引非空值）
CREATE INDEX IF NOT EXISTS idx_tasks_v2_event 
    ON operational_v2.tasks_v2(event_id) 
    WHERE event_id IS NOT NULL;

-- 按状态筛选任务
CREATE INDEX IF NOT EXISTS idx_tasks_v2_status 
    ON operational_v2.tasks_v2(status);

-- 按优先级筛选任务
CREATE INDEX IF NOT EXISTS idx_tasks_v2_priority 
    ON operational_v2.tasks_v2(priority);

-- 空间索引（按位置查询附近任务）
CREATE INDEX IF NOT EXISTS idx_tasks_v2_location 
    ON operational_v2.tasks_v2 USING GIST(target_location);

-- ============================================================================
-- 3. 添加外键约束
-- ============================================================================
-- 为 task_assignments_v2 表添加外键（关联到 tasks_v2）
-- 注意：task_assignments_v2 在 v2_event_scheme_model.sql 中已定义（public schema）
DO $$
BEGIN
    -- 检查外键是否已存在，不存在则添加
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_task_assignments_task'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE public.task_assignments_v2 
        ADD CONSTRAINT fk_task_assignments_task 
        FOREIGN KEY (task_id) 
        REFERENCES operational_v2.tasks_v2(id) 
        ON DELETE CASCADE;  -- 删除任务时级联删除分配记录
    END IF;
END $$;

-- ============================================================================
-- 4. 创建触发器（自动更新 updated_at）
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.update_tasks_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 删除旧触发器（如存在）
DROP TRIGGER IF EXISTS tr_tasks_v2_updated ON operational_v2.tasks_v2;

-- 创建新触发器
CREATE TRIGGER tr_tasks_v2_updated
    BEFORE UPDATE ON operational_v2.tasks_v2
    FOR EACH ROW 
    EXECUTE FUNCTION operational_v2.update_tasks_timestamp();

-- ============================================================================
-- 5. 添加表和字段注释
-- ============================================================================
COMMENT ON TABLE operational_v2.tasks_v2 IS 
    '任务表 - 存储从救援方案分解出的具体可执行任务';

COMMENT ON COLUMN operational_v2.tasks_v2.id IS '任务唯一标识（UUID）';
COMMENT ON COLUMN operational_v2.tasks_v2.scheme_id IS '所属方案ID';
COMMENT ON COLUMN operational_v2.tasks_v2.scenario_id IS '所属想定ID（冗余字段，便于直接查询）';
COMMENT ON COLUMN operational_v2.tasks_v2.event_id IS '关联事件ID（可选）';
COMMENT ON COLUMN operational_v2.tasks_v2.task_code IS '任务编号，格式：TSK-0001';
COMMENT ON COLUMN operational_v2.tasks_v2.task_type IS 
    '任务类型: search(搜索)/rescue(救援)/evacuation(疏散)/transport(运输)/medical(医疗)/supply(物资)/reconnaissance(侦察)/communication(通信)/other(其他)';
COMMENT ON COLUMN operational_v2.tasks_v2.title IS '任务标题';
COMMENT ON COLUMN operational_v2.tasks_v2.description IS '任务详细描述';
COMMENT ON COLUMN operational_v2.tasks_v2.status IS 
    '任务状态: created(已创建)→assigned(已分配)→accepted(已接受)→in_progress(执行中)→completed(已完成)/failed(已失败)/cancelled(已取消)';
COMMENT ON COLUMN operational_v2.tasks_v2.priority IS 
    '优先级: critical(紧急)/high(高)/medium(中)/low(低)';
COMMENT ON COLUMN operational_v2.tasks_v2.target_location IS '任务目标位置（WGS84坐标点）';
COMMENT ON COLUMN operational_v2.tasks_v2.target_address IS '目标地址描述';
COMMENT ON COLUMN operational_v2.tasks_v2.planned_start_at IS '计划开始时间';
COMMENT ON COLUMN operational_v2.tasks_v2.planned_end_at IS '计划结束时间';
COMMENT ON COLUMN operational_v2.tasks_v2.actual_start_at IS '实际开始时间';
COMMENT ON COLUMN operational_v2.tasks_v2.actual_end_at IS '实际结束时间';
COMMENT ON COLUMN operational_v2.tasks_v2.estimated_duration_minutes IS '预计执行时长（分钟）';
COMMENT ON COLUMN operational_v2.tasks_v2.instructions IS '执行指令和注意事项';
COMMENT ON COLUMN operational_v2.tasks_v2.requirements IS '任务需求（JSON格式：人员数、能力要求、装备要求等）';
COMMENT ON COLUMN operational_v2.tasks_v2.rescued_count IS '救出人数（救援类任务统计）';
COMMENT ON COLUMN operational_v2.tasks_v2.progress_percent IS '执行进度百分比（0-100）';
COMMENT ON COLUMN operational_v2.tasks_v2.created_by IS '创建人ID';
COMMENT ON COLUMN operational_v2.tasks_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.tasks_v2.updated_at IS '最后更新时间（自动维护）';
