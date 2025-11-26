-- ============================================================================
-- 为 vehicles_v2 表添加实时位置字段
-- 
-- 说明：扩展车辆表，支持实时位置追踪功能
-- 用途：接收车辆GPS遥测数据，实现车辆位置实时更新和轨迹追踪
-- 
-- 依赖：需要先执行 v2_rescue_resource_model.sql 创建 vehicles_v2 表
-- ============================================================================

-- ============================================================================
-- 1. 添加实时位置相关字段
-- ============================================================================
ALTER TABLE operational_v2.vehicles_v2 
    -- 车辆当前位置（地理坐标点）
    ADD COLUMN IF NOT EXISTS current_location GEOGRAPHY(POINT),
    -- 位置最后更新时间（用于判断数据新鲜度）
    ADD COLUMN IF NOT EXISTS last_location_update TIMESTAMPTZ;

-- ============================================================================
-- 2. 创建空间索引（支持位置查询）
-- ============================================================================
-- 用于：查询某区域内的车辆、查找最近车辆等空间查询
CREATE INDEX IF NOT EXISTS idx_vehicles_v2_current_location 
    ON operational_v2.vehicles_v2 
    USING GIST(current_location);

-- ============================================================================
-- 3. 添加字段注释
-- ============================================================================
COMMENT ON COLUMN operational_v2.vehicles_v2.current_location IS 
    '车辆当前位置（实时更新，由GPS遥测数据写入）';
COMMENT ON COLUMN operational_v2.vehicles_v2.last_location_update IS 
    '位置最后更新时间（用于判断位置数据是否过期）';

-- ============================================================================
-- 4. 初始化位置数据
-- ============================================================================
-- 将车辆的 current_location 初始化为所属队伍的驻地位置(base_location)
-- 关联关系：vehicles_v2 ← team_equipment_v2 → rescue_teams_v2
UPDATE operational_v2.vehicles_v2 v
SET 
    current_location = (
        SELECT t.base_location 
        FROM operational_v2.rescue_teams_v2 t
        JOIN operational_v2.team_equipment_v2 te ON te.team_id = t.id
        WHERE te.equipment_type = 'vehicle' 
          AND te.equipment_id = v.id
        LIMIT 1
    ),
    last_location_update = NOW()
WHERE current_location IS NULL;

-- ============================================================================
-- 5. 验证数据（查看初始化结果）
-- ============================================================================
-- 查询已有位置信息的车辆
SELECT 
    code AS 车辆编号,
    name AS 车辆名称,
    ST_AsText(current_location) AS 当前位置,
    last_location_update AS 位置更新时间
FROM operational_v2.vehicles_v2
WHERE current_location IS NOT NULL;

-- ============================================================================
-- 使用说明：
-- 
-- 1. 更新车辆位置（接收GPS遥测数据时调用）：
--    UPDATE operational_v2.vehicles_v2 
--    SET current_location = ST_GeogFromText('POINT(116.4074 39.9042)'),
--        last_location_update = NOW()
--    WHERE id = 'vehicle-uuid';
--
-- 2. 查询某点附近5公里内的车辆：
--    SELECT id, name, 
--           ST_Distance(current_location, ST_GeogFromText('POINT(116.4 39.9)')) AS distance_m
--    FROM operational_v2.vehicles_v2
--    WHERE ST_DWithin(current_location, ST_GeogFromText('POINT(116.4 39.9)'), 5000)
--    ORDER BY distance_m;
--
-- 3. 查询位置超过10分钟未更新的车辆（可能离线）：
--    SELECT id, name, last_location_update
--    FROM operational_v2.vehicles_v2
--    WHERE last_location_update < NOW() - INTERVAL '10 minutes';
-- ============================================================================
