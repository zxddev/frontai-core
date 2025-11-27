-- v9_disaster_scenario_linking.sql
-- 增强灾害-想定-事件关联机制

-- 为disaster_situations表添加关联字段
ALTER TABLE operational_v2.disaster_situations 
ADD COLUMN IF NOT EXISTS needs_response BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS linked_event_id UUID,
ADD COLUMN IF NOT EXISTS map_entity_id UUID;

-- 添加注释
COMMENT ON COLUMN operational_v2.disaster_situations.needs_response IS '是否需要救援响应（false=仅预警如天气预报）';
COMMENT ON COLUMN operational_v2.disaster_situations.linked_event_id IS '关联事件ID';
COMMENT ON COLUMN operational_v2.disaster_situations.map_entity_id IS '关联地图实体ID';
COMMENT ON COLUMN operational_v2.disaster_situations.scenario_id IS '关联想定ID';

-- 创建索引优化查询
CREATE INDEX IF NOT EXISTS idx_disaster_situations_scenario_id 
ON operational_v2.disaster_situations(scenario_id) 
WHERE scenario_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_disaster_situations_linked_event_id 
ON operational_v2.disaster_situations(linked_event_id) 
WHERE linked_event_id IS NOT NULL;
