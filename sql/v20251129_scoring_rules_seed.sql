-- ============================================================================
-- v20251129: 通用优先级打分规则种子数据
--
-- 目的：
--   1. 在现有 config.algorithm_parameters 表中为 "scoring" 类别初始化规则集
--   2. 为无人设备首次侦察(Recon Target)提供首版打分配置
--   3. 为后续任务/通道/安置点等场景预留统一规则结构，支持跨业务复用
--
-- 设计原则：
--   - 不新增任何表结构，仅写入参数数据
--   - 无Fallback：业务侧通过 AlgorithmConfigService.get_or_raise 强依赖本配置
--   - 规则结构固定：entity_type + dimensions + hard_rules + priority_buckets
--
-- 执行方式：psql -U postgres -d frontai -f sql/v20251129_scoring_rules_seed.sql
-- ============================================================================

-- 清理旧的 scoring 规则（如果存在）
DELETE FROM config.algorithm_parameters WHERE category = 'scoring';

-- ============================================================================
-- Recon 首次无人侦察目标优先级规则
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, code, version, name, name_cn, params, reference, description
) VALUES
(
    'scoring',
    'SCORING_RECON_TARGET_V1',
    '1.0',
    'Initial Recon Target Priority',
    '首次无人侦察目标优先级',
    '{
      "entity_type": "recon_target",
      "dimensions": [
        {
          "name": "risk_level",
          "weight": 0.4,
          "source": "features.risk_level",
          "scale": "0-10"
        },
        {
          "name": "population_exposed",
          "weight": 0.2,
          "source": "features.population_exposed",
          "normalize_by": 10000
        },
        {
          "name": "route_criticality",
          "weight": 0.2,
          "source": "features.route_importance",
          "scale": "0-1"
        },
        {
          "name": "info_gap",
          "weight": 0.1,
          "source": "features.info_age_hours",
          "transform": "linear",
          "max": 24
        },
        {
          "name": "ai_residual",
          "weight": 0.1,
          "source": "ai.suggestion_score",
          "clamp": [-0.2, 0.2]
        }
      ],
      "hard_rules": [
        {
          "id": "CRITICAL_RISK_LEVEL",
          "if": {
            "field": "features.risk_level",
            "operator": "gte",
            "value": 9
          },
          "set_priority": "critical",
          "min_score": 0.9
        },
        {
          "id": "MAIN_CORRIDOR_FLOOR_HIGH",
          "if": {
            "field": "features.is_main_corridor",
            "operator": "eq",
            "value": true
          },
          "floor_priority": "high"
        }
      ],
      "priority_buckets": [
        {"name": "critical", "min_score": 0.8},
        {"name": "high",     "min_score": 0.6},
        {"name": "medium",   "min_score": 0.3},
        {"name": "low",      "min_score": 0.0}
      ]
    }'::jsonb,
    'FrontAI Core Scoring v1.0',
    'Recon首次无人侦察目标优先级规则。通过危险等级、受威胁人口、通道关键性、情报缺口以及AI残差信号综合计算得分，并通过硬规则对极高风险场景进行兜底。'
);

-- ============================================================================
-- 预留：其他场景的优先级打分规则（任务/通道/安置点/物资等）
-- 后续可在新增迁移中按相同结构插入：SCORING_TASK_V1 / SCORING_ROUTE_CLEARANCE_V1 等
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'v20251129: scoring rules seed inserted (SCORING_RECON_TARGET_V1)';
END $$;
