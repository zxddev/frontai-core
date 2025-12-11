-- ============================================================================
-- 迁移: 为task_assignments_v2表添加mission_detail字段
-- 日期: 2025-12-11
-- 目的: 存储一线队员的任务详情（AI生成的任务描述、协作队伍、风险预警等）
-- ============================================================================

-- 添加mission_detail字段
-- 存储结构:
-- {
--   "task_description": "负责A楼搜救，重点关注3-5层被困人员",
--   "rescue_point_name": "倒塌建筑A",
--   "target_situation": "预估被困12人，建筑结构不稳定",
--   "collaborating_teams": ["武警搜救队", "医疗救援队"],
--   "risk_warnings": ["存在次生火灾风险", "道路损毁，注意绕行"],
--   "equipments": ["生命探测仪", "液压破拆工具"],
--   "eta_minutes": 25,
--   "commander_order": "优先救援老人和儿童"
-- }

ALTER TABLE operational_v2.task_assignments_v2
ADD COLUMN IF NOT EXISTS mission_detail JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN operational_v2.task_assignments_v2.mission_detail IS
'一线队员任务详情（AI生成）：task_description任务描述、rescue_point_name救援点、collaborating_teams协作队伍、risk_warnings风险预警、equipments装备、eta_minutes预计到达时间、commander_order指挥员命令';

-- 创建索引以支持JSONB查询（可选，根据查询需求决定）
-- CREATE INDEX IF NOT EXISTS idx_task_assignments_mission_detail
-- ON operational_v2.task_assignments_v2 USING gin (mission_detail);
