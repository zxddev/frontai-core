-- ============================================================================
-- 迁移脚本: 为tasks_v2表添加rescue_point_id列
-- 变更ID: add-multi-rescue-point-dispatch
-- 日期: 2025-12-07
-- 目的: 支持多救援点任务关联，每个任务可关联到具体的救援点
-- ============================================================================

-- 添加rescue_point_id列（外键关联rescue_points_v2）
ALTER TABLE operational_v2.tasks_v2 
ADD COLUMN IF NOT EXISTS rescue_point_id uuid 
REFERENCES operational_v2.rescue_points_v2(id);

-- 添加列注释
COMMENT ON COLUMN operational_v2.tasks_v2.rescue_point_id 
IS '关联的救援点ID，用于多点位救援任务，每个任务对应一个具体救援点';

-- 创建索引加速查询
CREATE INDEX IF NOT EXISTS idx_tasks_v2_rescue_point_id 
ON operational_v2.tasks_v2(rescue_point_id);

-- 验证列已创建
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'operational_v2' 
          AND table_name = 'tasks_v2' 
          AND column_name = 'rescue_point_id'
    ) THEN
        RAISE NOTICE '✅ tasks_v2.rescue_point_id 列创建成功';
    ELSE
        RAISE EXCEPTION '❌ tasks_v2.rescue_point_id 列创建失败';
    END IF;
END $$;
