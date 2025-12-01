-- ============================================================================
-- v20251129: Frontline 多事件救援调度规则种子数据
--
-- 目的：
--   1. 为一线多事件救援调度(FrontlineRescueAgent) 初始化统一的打分、约束与硬规则配置
--   2. 所有关键阈值从 Postgres config.algorithm_parameters 表加载，禁止在代码中硬编码
--   3. 规则结构与已有 scoring 配置兼容，便于通过 AlgorithmConfigService 统一访问
--
-- 设计原则：
--   - 不新增任何表结构，仅写入参数数据
--   - 无 Fallback：业务侧通过 AlgorithmConfigService.get_or_raise 强依赖本配置
--   - 分为三类：
--       * scoring   : 事件优先级打分
--       * allocation: 资源分配约束
--       * scoring   : Frontline 专用硬规则（与通用 TRR 互补）
--
-- 执行方式：psql -U postgres -d frontai -f sql/v20251129_frontline_rescue_rules.sql
-- ============================================================================

-- ====================================================================================
-- 1. Frontline 事件优先级打分规则
--    结构兼容 PriorityScoringEngine (entity_type + dimensions + hard_rules + priority_buckets)
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, code, version, name, name_cn, params, reference, description
) VALUES
(
    'scoring',
    'SCORING_FRONTLINE_EVENT_V1',
    '1.0',
    'Frontline Multi-Event Rescue Priority',
    '一线多事件救援优先级',
    '{
      "entity_type": "frontline_event",
      "dimensions": [
        {
          "name": "life_threat",
          "weight": 0.35,
          "source": "features.life_threat_level",
          "scale": "0-1"
        },
        {
          "name": "time_urgency",
          "weight": 0.25,
          "source": "features.time_urgency_score",
          "scale": "0-1"
        },
        {
          "name": "affected_population",
          "weight": 0.20,
          "source": "features.affected_population",
          "normalize_by": 1000
        },
        {
          "name": "success_probability",
          "weight": 0.20,
          "source": "features.success_probability",
          "scale": "0-1"
        }
      ],
      "hard_rules": [
        {
          "id": "CRITICAL_GOLDEN_TIME",
          "if": {
            "field": "features.golden_time_remaining_min",
            "operator": "lte",
            "value": 30
          },
          "set_priority": "critical",
          "min_score": 0.9
        },
        {
          "id": "MAJOR_CASUALTIES_HIGH_PRIORITY",
          "if": {
            "field": "features.affected_population",
            "operator": "gte",
            "value": 100
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
    'FrontAI Core Frontline Scoring v1.0',
    'Frontline 多事件救援优先级规则。通过生命威胁、时间紧迫性、受影响人数和救援成功概率综合计算得分，并对黄金时间极短或伤亡人数巨大的场景给予更高优先级。'
);

-- ====================================================================================
-- 2. Frontline 资源分配约束配置
--    供 ResourceSchedulingCore / FrontlineRescueAgent 使用，统一控制 ETA / 覆盖率 等硬阈值
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, code, version, name, name_cn, params, reference, description
) VALUES
(
    'allocation',
    'FRONTLINE_ALLOCATION_CONSTRAINTS_V1',
    '1.0',
    'Frontline Global Resource Allocation Constraints',
    '一线多事件资源分配约束',
    '{
      "max_assignments_per_resource": 1,
      "min_coverage_rate": 0.7,
      "max_response_time_minutes": 180,
      "max_distance_km": 100,
      "max_resources": 20
    }'::jsonb,
    'FrontAI Core Frontline Constraints v1.0',
    'Frontline 资源分配约束配置。限定单支队伍只能服务一个事件，并对能力覆盖率、最大响应时间和搜索半径给出全局安全阈值。'
);

-- ====================================================================================
-- 3. Frontline 硬规则配置
--    由 FrontlineRescueAgent 的 hard_rules_check 阶段加载并执行，用于对整体方案进行红线检查
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, code, version, name, name_cn, params, reference, description
) VALUES
(
    'scoring',
    'HARD_RULES_FRONTLINE_V1',
    '1.0',
    'Frontline Hard Safety Rules',
    '一线救援硬安全规则',
    '{
      "rules": [
        {
          "id": "HR_FRONTLINE_MAX_ETA",
          "field": "solution.max_eta_minutes",
          "operator": "gt",
          "threshold": 180,
          "severity": "critical",
          "action": "reject",
          "message": "最大响应时间超过 180 分钟，违反黄金救援时间约束"
        },
        {
          "id": "HR_FRONTLINE_MIN_COVERAGE",
          "field": "solution.coverage_rate",
          "operator": "lt",
          "threshold": 0.7,
          "severity": "critical",
          "action": "reject",
          "message": "能力覆盖率低于 70%，无法满足基本救援能力要求"
        }
      ]
    }'::jsonb,
    'FrontAI Core Frontline Hard Rules v1.0',
    'Frontline 一线救援硬规则。对整体方案的最大响应时间和能力覆盖率进行红线检查，用于在下发任务前进行最后否决。'
);

DO $$
BEGIN
    RAISE NOTICE 'v20251129: frontline rescue rules inserted (SCORING_FRONTLINE_EVENT_V1, FRONTLINE_ALLOCATION_CONSTRAINTS_V1, HARD_RULES_FRONTLINE_V1)';
END $$;
