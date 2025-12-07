-- 修复多个 active scenario 问题
-- 问题: 数据库中存在多条 status='active' 的记录，违反业务规则

-- 方案B: 清理数据库脏数据，只保留最新的 active 想定
UPDATE operational_v2.scenarios_v2 
SET status = 'resolved', updated_at = NOW()
WHERE status = 'active' 
  AND id NOT IN (
    SELECT id FROM operational_v2.scenarios_v2 
    WHERE status = 'active' 
    ORDER BY updated_at DESC 
    LIMIT 1
  );

-- 方案C: 添加部分唯一索引，防止将来出现多个 active 记录
CREATE UNIQUE INDEX IF NOT EXISTS idx_scenarios_single_active 
ON operational_v2.scenarios_v2 (status) 
WHERE status = 'active';
