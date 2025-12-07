-- ============================================================================
-- 修复Overall Plan Agent测试数据
-- 问题：scenarios_v2.affected_population为NULL，events_v2.source_detail缺少灾情字段
-- 执行前请确认scenario_id是否正确
-- ============================================================================

-- 1. 更新想定的受灾人口（必填字段）
-- 茂县6.8级地震，根据历史数据估算受影响人口约10万人
UPDATE operational_v2.scenarios_v2 
SET affected_population = 100000,
    affected_area_km2 = 500.0
WHERE id = '182c4b66-f368-4763-84a1-84b44c2439d9';

-- 2. 更新主震事件的source_detail，添加伤亡和建筑损毁数据
-- 参考：2017年九寨沟7.0级地震造成25人死亡、525人受伤
UPDATE operational_v2.events_v2
SET estimated_victims = 200,  -- 被困人数
    casualty_count = 30,       -- 死亡人数
    source_detail = jsonb_set(
        COALESCE(source_detail, '{}')::jsonb,
        '{}',
        '{
            "magnitude": 6.8,
            "depth_km": 10.0,
            "injuries": 500,
            "missing": 50,
            "buildings_collapsed": 1200,
            "buildings_damaged": 8500,
            "simulation": true
        }'::jsonb
    )
WHERE scenario_id = '182c4b66-f368-4763-84a1-84b44c2439d9'
  AND event_type = 'earthquake';

-- 3. 更新被困人员事件的source_detail
UPDATE operational_v2.events_v2
SET source_detail = jsonb_set(
        COALESCE(source_detail, '{}')::jsonb,
        '{}',
        '{
            "injuries": 2,
            "missing": 0,
            "buildings_collapsed": 1,
            "buildings_damaged": 3
        }'::jsonb
    )
WHERE scenario_id = '182c4b66-f368-4763-84a1-84b44c2439d9'
  AND event_type = 'trapped_person';

-- 4. 验证更新结果
SELECT 'scenarios_v2' as table_name, id, name, affected_population, affected_area_km2
FROM operational_v2.scenarios_v2 
WHERE id = '182c4b66-f368-4763-84a1-84b44c2439d9';

SELECT 'events_v2' as table_name, event_code, event_type, estimated_victims, casualty_count, 
       source_detail::text
FROM operational_v2.events_v2 
WHERE scenario_id = '182c4b66-f368-4763-84a1-84b44c2439d9';
