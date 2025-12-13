-- ============================================================================
-- Task Coordinator 执行记录表
--
-- 用途：记录任务执行实例和步骤分配（多队伍协作）
-- 执行：psql -U postgres -d frontai < sql/migrations/v20251212_task_coordinator_tables.sql
-- ============================================================================

-- 确保 schema 存在
CREATE SCHEMA IF NOT EXISTS operational_v2;

-- ============================================================================
-- 1. 任务执行实例表
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.task_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联信息
    event_id UUID NOT NULL,                          -- 关联的事件ID
    task_id UUID NOT NULL,                           -- 关联的任务ID（来自 emergency_ai）
    sop_template_id VARCHAR(100) NOT NULL,           -- 使用的 SOP 模板ID

    -- 执行状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending/in_progress/completed/failed/cancelled
    current_step_id VARCHAR(100),                    -- 当前执行的步骤ID

    -- 时间信息
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- 执行元数据
    metadata JSONB DEFAULT '{}'::jsonb,              -- 额外的执行信息

    -- 约束
    CONSTRAINT task_executions_status_check CHECK (
        status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')
    )
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_task_executions_event_id
    ON operational_v2.task_executions(event_id);
CREATE INDEX IF NOT EXISTS idx_task_executions_task_id
    ON operational_v2.task_executions(task_id);
CREATE INDEX IF NOT EXISTS idx_task_executions_status
    ON operational_v2.task_executions(status);
CREATE INDEX IF NOT EXISTS idx_task_executions_sop_template
    ON operational_v2.task_executions(sop_template_id);

-- 注释
COMMENT ON TABLE operational_v2.task_executions IS '任务执行实例表，记录每个任务的 SOP 执行情况';
COMMENT ON COLUMN operational_v2.task_executions.sop_template_id IS 'Neo4j 中的 SOPTemplate.id';

-- ============================================================================
-- 2. 步骤分配表（多队伍协作的核心）
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.step_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联信息
    execution_id UUID NOT NULL REFERENCES operational_v2.task_executions(id) ON DELETE CASCADE,
    step_id VARCHAR(100) NOT NULL,                   -- Neo4j 中的 SOPStep.id
    team_id UUID NOT NULL,                           -- 分配的队伍ID

    -- 角色和职责
    role VARCHAR(20) NOT NULL,                       -- 主攻/配合/保障/待命
    responsibilities TEXT[],                         -- 具体职责列表

    -- 设备分配
    assigned_equipment JSONB DEFAULT '[]'::jsonb,    -- 分配给该队伍的设备

    -- 协作模式
    cooperation_mode VARCHAR(20) DEFAULT 'sequential', -- sequential/parallel/support/standby

    -- 执行状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending/in_progress/completed/failed/skipped

    -- 时间信息
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- 执行反馈
    completion_notes TEXT,                           -- 完成备注
    issues_encountered TEXT[],                       -- 遇到的问题

    -- 约束
    CONSTRAINT step_assignments_role_check CHECK (
        role IN ('主攻', '配合', '保障', '待命')
    ),
    CONSTRAINT step_assignments_status_check CHECK (
        status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')
    ),
    CONSTRAINT step_assignments_cooperation_check CHECK (
        cooperation_mode IN ('sequential', 'parallel', 'support', 'standby')
    )
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_step_assignments_execution_id
    ON operational_v2.step_assignments(execution_id);
CREATE INDEX IF NOT EXISTS idx_step_assignments_team_id
    ON operational_v2.step_assignments(team_id);
CREATE INDEX IF NOT EXISTS idx_step_assignments_step_id
    ON operational_v2.step_assignments(step_id);
CREATE INDEX IF NOT EXISTS idx_step_assignments_status
    ON operational_v2.step_assignments(status);

-- 复合索引：查询某个执行的所有步骤分配
CREATE INDEX IF NOT EXISTS idx_step_assignments_exec_step
    ON operational_v2.step_assignments(execution_id, step_id);

-- 注释
COMMENT ON TABLE operational_v2.step_assignments IS '步骤分配表，记录每个步骤的多队伍分配情况';
COMMENT ON COLUMN operational_v2.step_assignments.role IS '队伍在该步骤中的角色：主攻/配合/保障/待命';
COMMENT ON COLUMN operational_v2.step_assignments.cooperation_mode IS '协作模式：sequential(顺序)/parallel(并行)/support(支援)/standby(待命)';

-- ============================================================================
-- 3. 步骤指令表（发送给队伍的具体指令）
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.step_instructions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联信息
    assignment_id UUID NOT NULL REFERENCES operational_v2.step_assignments(id) ON DELETE CASCADE,

    -- 指令内容
    instruction_text TEXT NOT NULL,                  -- 指令文本
    instruction_type VARCHAR(50) DEFAULT 'action',   -- action/safety/coordination
    priority INTEGER DEFAULT 1,                      -- 优先级（1最高）

    -- 状态
    acknowledged BOOLEAN DEFAULT FALSE,              -- 队伍是否确认收到
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    -- 时间
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_step_instructions_assignment_id
    ON operational_v2.step_instructions(assignment_id);

-- 注释
COMMENT ON TABLE operational_v2.step_instructions IS '步骤指令表，记录发送给队伍的具体指令';

-- ============================================================================
-- 4. 更新时间触发器
-- ============================================================================

-- 创建更新时间函数（如果不存在）
CREATE OR REPLACE FUNCTION operational_v2.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为 task_executions 添加触发器
DROP TRIGGER IF EXISTS update_task_executions_updated_at ON operational_v2.task_executions;
CREATE TRIGGER update_task_executions_updated_at
    BEFORE UPDATE ON operational_v2.task_executions
    FOR EACH ROW
    EXECUTE FUNCTION operational_v2.update_updated_at_column();

-- 为 step_assignments 添加触发器
DROP TRIGGER IF EXISTS update_step_assignments_updated_at ON operational_v2.step_assignments;
CREATE TRIGGER update_step_assignments_updated_at
    BEFORE UPDATE ON operational_v2.step_assignments
    FOR EACH ROW
    EXECUTE FUNCTION operational_v2.update_updated_at_column();

-- ============================================================================
-- 5. 视图：任务执行概览
-- ============================================================================

CREATE OR REPLACE VIEW operational_v2.v_task_execution_overview AS
SELECT
    te.id AS execution_id,
    te.event_id,
    te.task_id,
    te.sop_template_id,
    te.status AS execution_status,
    te.current_step_id,
    te.started_at,
    te.completed_at,
    COUNT(DISTINCT sa.id) AS total_assignments,
    COUNT(DISTINCT sa.team_id) AS total_teams,
    COUNT(DISTINCT sa.step_id) AS total_steps,
    COUNT(CASE WHEN sa.status = 'completed' THEN 1 END) AS completed_assignments,
    COUNT(CASE WHEN sa.status = 'in_progress' THEN 1 END) AS in_progress_assignments
FROM operational_v2.task_executions te
LEFT JOIN operational_v2.step_assignments sa ON te.id = sa.execution_id
GROUP BY te.id;

COMMENT ON VIEW operational_v2.v_task_execution_overview IS '任务执行概览视图';

-- ============================================================================
-- 完成
-- ============================================================================

-- 输出创建结果
DO $$
BEGIN
    RAISE NOTICE 'Task Coordinator 表创建完成';
    RAISE NOTICE '- task_executions: 任务执行实例';
    RAISE NOTICE '- step_assignments: 步骤分配（多队伍协作）';
    RAISE NOTICE '- step_instructions: 步骤指令';
    RAISE NOTICE '- v_task_execution_overview: 执行概览视图';
END $$;
