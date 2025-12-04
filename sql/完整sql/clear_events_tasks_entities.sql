-- ============================================
-- 清空事件、任务、实体数据脚本
-- 数据库: emergency_agent
-- Schema: operational_v2
-- 创建日期: 2025-12-04
-- ============================================

-- 开启事务，确保原子性
BEGIN;

-- ============================================
-- 方案一：使用 DELETE (推荐，更安全，可回滚)
-- ============================================

-- 1. 清空任务相关子表（先删子表再删主表）
DELETE FROM operational_v2.task_assignments_v2;
DELETE FROM operational_v2.task_reports_v2;
UPDATE operational_v2.planned_routes_v2 SET task_id = NULL WHERE task_id IS NOT NULL;

-- 2. 清空任务主表（先清空子任务外键引用）
UPDATE operational_v2.tasks_v2 SET parent_task_id = NULL;
DELETE FROM operational_v2.tasks_v2;
DELETE FROM operational_v2.task_requirements_v2;

-- 3. 清空方案相关
DELETE FROM operational_v2.schemes_v2;

-- 4. 清空事件相关子表（有外键约束的会自动级联删除，这里显式清除更安全）
DELETE FROM operational_v2.event_updates_v2;
DELETE FROM operational_v2.equipment_preparation_dispatch_v2;
DELETE FROM operational_v2.equipment_recommendations_v2;
DELETE FROM operational_v2.car_item_assignment;
DELETE FROM operational_v2.rescue_points_v2;
DELETE FROM operational_v2.evaluation_reports_v2;

-- 5. 清空事件主表（先清空自引用）
UPDATE operational_v2.events_v2 SET parent_event_id = NULL, merged_into_event_id = NULL;
DELETE FROM operational_v2.events_v2;

-- 6. 清空实体相关
DELETE FROM operational_v2.entity_tracks_v2;
DELETE FROM operational_v2.entities_v2;

-- 7. 清空AI决策日志
DELETE FROM operational_v2.ai_decision_logs_v2;

-- 8. 清空风险区域（灾害影响区域）
DELETE FROM operational_v2.disaster_affected_areas_v2;

-- 9. 恢复救援队伍状态（出发状态恢复为待命）
UPDATE operational_v2.rescue_teams_v2 
SET status = 'standby', 
    current_task_id = NULL, 
    current_location = NULL,
    last_location_update = NULL
WHERE status != 'standby' OR current_task_id IS NOT NULL;

-- 10. 恢复车辆状态
UPDATE operational_v2.vehicles_v2 
SET status = 'available', 
    current_location = NULL
WHERE status != 'available';

-- 11. 恢复装备状态（available_quantity 恢复为 quantity）
UPDATE operational_v2.team_equipment_v2 
SET status = 'ready', 
    available_quantity = quantity,
    current_location = NULL
WHERE status != 'ready' OR available_quantity != quantity;

-- 12. 清空对话和消息记录（可选）
-- DELETE FROM operational_v2.command_messages_v2;
-- DELETE FROM operational_v2.conversations_v2;

-- 提交事务
COMMIT;

-- ============================================
-- 方案二：使用 TRUNCATE CASCADE (更快，不可回滚)
-- 如果需要使用此方案，请注释掉上面的方案一，取消下面的注释
-- ============================================

/*
TRUNCATE TABLE operational_v2.task_assignments_v2 CASCADE;
TRUNCATE TABLE operational_v2.task_reports_v2 CASCADE;
TRUNCATE TABLE operational_v2.tasks_v2 CASCADE;
TRUNCATE TABLE operational_v2.task_requirements_v2 CASCADE;
TRUNCATE TABLE operational_v2.event_updates_v2 CASCADE;
TRUNCATE TABLE operational_v2.equipment_preparation_dispatch_v2 CASCADE;
TRUNCATE TABLE operational_v2.equipment_recommendations_v2 CASCADE;
TRUNCATE TABLE operational_v2.events_v2 CASCADE;
TRUNCATE TABLE operational_v2.entity_tracks_v2 CASCADE;
TRUNCATE TABLE operational_v2.entities_v2 CASCADE;
TRUNCATE TABLE operational_v2.ai_decision_logs_v2 CASCADE;
TRUNCATE TABLE operational_v2.disaster_affected_areas_v2 CASCADE;
*/

-- ============================================
-- 重置序列 (可选)
-- ============================================

/*
ALTER SEQUENCE operational_v2.entity_tracks_v2_id_seq RESTART WITH 1;
ALTER SEQUENCE operational_v2.rescue_point_progress_v2_id_seq RESTART WITH 1;
*/
