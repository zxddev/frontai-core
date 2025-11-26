-- ============================================================================
-- 补充缺失字段迁移脚本
-- 
-- 包含:
-- 1. tasks_v2.parent_task_id - 支持子任务层级
-- 2. rescue_teams_v2.current_location - 队伍实时位置
-- 3. rescue_teams_v2.last_location_update - 位置更新时间
-- ============================================================================

-- ============================================================================
-- 1. tasks_v2 添加 parent_task_id 字段 (支持子任务)
-- ============================================================================
ALTER TABLE operational_v2.tasks_v2 
    ADD COLUMN IF NOT EXISTS parent_task_id UUID REFERENCES operational_v2.tasks_v2(id);

COMMENT ON COLUMN operational_v2.tasks_v2.parent_task_id IS 
    '父任务ID，用于支持任务层级结构（子任务）';

-- 创建索引加速子任务查询
CREATE INDEX IF NOT EXISTS idx_tasks_v2_parent 
    ON operational_v2.tasks_v2(parent_task_id) 
    WHERE parent_task_id IS NOT NULL;

-- ============================================================================
-- 2. rescue_teams_v2 添加实时位置字段
-- ============================================================================
ALTER TABLE operational_v2.rescue_teams_v2 
    ADD COLUMN IF NOT EXISTS current_location GEOGRAPHY(POINT),
    ADD COLUMN IF NOT EXISTS last_location_update TIMESTAMPTZ;

COMMENT ON COLUMN operational_v2.rescue_teams_v2.current_location IS 
    '队伍当前位置（实时更新，由GPS遥测数据写入）';
COMMENT ON COLUMN operational_v2.rescue_teams_v2.last_location_update IS 
    '位置最后更新时间（用于判断位置数据是否过期）';

-- 创建空间索引
CREATE INDEX IF NOT EXISTS idx_teams_v2_current_location 
    ON operational_v2.rescue_teams_v2 
    USING GIST(current_location);

-- 初始化：将current_location设为base_location
UPDATE operational_v2.rescue_teams_v2 
SET current_location = base_location,
    last_location_update = NOW()
WHERE current_location IS NULL AND base_location IS NOT NULL;

-- ============================================================================
-- 3. 验证迁移结果
-- ============================================================================
DO $$
DECLARE
    v_tasks_parent_exists BOOLEAN;
    v_teams_location_exists BOOLEAN;
BEGIN
    -- 检查tasks_v2.parent_task_id
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'operational_v2' 
        AND table_name = 'tasks_v2' 
        AND column_name = 'parent_task_id'
    ) INTO v_tasks_parent_exists;
    
    -- 检查rescue_teams_v2.current_location
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'operational_v2' 
        AND table_name = 'rescue_teams_v2' 
        AND column_name = 'current_location'
    ) INTO v_teams_location_exists;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '迁移验证结果:';
    RAISE NOTICE 'tasks_v2.parent_task_id: %', CASE WHEN v_tasks_parent_exists THEN '✓ 已添加' ELSE '✗ 失败' END;
    RAISE NOTICE 'rescue_teams_v2.current_location: %', CASE WHEN v_teams_location_exists THEN '✓ 已添加' ELSE '✗ 失败' END;
    RAISE NOTICE '========================================';
END $$;
