-- ============================================================================
-- 修改tasks_v2表的scheme_id字段为可选
-- 背景: 准备任务在方案生成前创建，此时无关联方案
-- ============================================================================

-- 移除scheme_id的NOT NULL约束
ALTER TABLE operational_v2.tasks_v2 
    ALTER COLUMN scheme_id DROP NOT NULL;

-- 更新字段注释
COMMENT ON COLUMN operational_v2.tasks_v2.scheme_id IS '所属方案ID（可选，准备任务可能无关联方案）';
