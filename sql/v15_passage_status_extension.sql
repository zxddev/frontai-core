-- ============================================================================
-- v15_passage_status_extension.sql
-- 扩展 disaster_affected_areas_v2 表，增加通行状态管理字段
-- 
-- 业务背景：
-- 原表只有 passable (bool) 字段，无法表达"需侦察确认"等中间状态
-- 新增 passage_status 枚举字段，支持更细粒度的通行决策
-- ============================================================================

-- 1. 添加 passage_status 字段
ALTER TABLE operational_v2.disaster_affected_areas_v2
ADD COLUMN IF NOT EXISTS passage_status VARCHAR(30) DEFAULT 'unknown';

-- 2. 添加约束检查
ALTER TABLE operational_v2.disaster_affected_areas_v2
DROP CONSTRAINT IF EXISTS disaster_affected_areas_v2_passage_status_check;

ALTER TABLE operational_v2.disaster_affected_areas_v2
ADD CONSTRAINT disaster_affected_areas_v2_passage_status_check
CHECK (passage_status IN (
    'confirmed_blocked',      -- 已确认完全不可通行（塌方、断桥、深水）
    'needs_reconnaissance',   -- 高危险但未确认，需侦察后判断
    'passable_with_caution',  -- 可通行但有风险（降速、救援车辆优先）
    'clear',                  -- 已确认安全通行
    'unknown'                 -- 未知状态（初始值，需评估）
));

-- 3. 添加侦察相关字段
ALTER TABLE operational_v2.disaster_affected_areas_v2
ADD COLUMN IF NOT EXISTS reconnaissance_required BOOLEAN DEFAULT false;

ALTER TABLE operational_v2.disaster_affected_areas_v2
ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;

ALTER TABLE operational_v2.disaster_affected_areas_v2
ADD COLUMN IF NOT EXISTS verified_by UUID;

-- 4. 添加字段注释
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.passage_status IS 
    '通行状态: confirmed_blocked(已确认不可通行), needs_reconnaissance(需侦察), passable_with_caution(谨慎通行), clear(安全), unknown(未知)';

COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.reconnaissance_required IS 
    '是否需要侦察确认';

COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.last_verified_at IS 
    '最后验证时间';

COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.verified_by IS 
    '验证者ID（侦察队伍/无人机）';

-- 5. 迁移现有数据：根据 passable 字段设置初始 passage_status
UPDATE operational_v2.disaster_affected_areas_v2
SET passage_status = CASE
    WHEN passable = false AND risk_level >= 8 THEN 'confirmed_blocked'
    WHEN passable = false AND risk_level >= 5 THEN 'needs_reconnaissance'
    WHEN passable = true AND risk_level >= 5 THEN 'passable_with_caution'
    WHEN passable = true AND risk_level < 5 THEN 'clear'
    ELSE 'unknown'
END
WHERE passage_status = 'unknown' OR passage_status IS NULL;

-- 6. 创建索引加速查询
CREATE INDEX IF NOT EXISTS idx_disaster_areas_v2_passage_status 
ON operational_v2.disaster_affected_areas_v2(passage_status);

CREATE INDEX IF NOT EXISTS idx_disaster_areas_v2_recon_required 
ON operational_v2.disaster_affected_areas_v2(reconnaissance_required) 
WHERE reconnaissance_required = true;

-- 7. 输出结果
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'disaster_affected_areas_v2 表扩展完成';
    RAISE NOTICE '新增字段: passage_status, reconnaissance_required, last_verified_at, verified_by';
    RAISE NOTICE '========================================';
END $$;
