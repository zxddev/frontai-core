-- ============================================================================
-- GRA全局资源仲裁器配置迁移脚本
-- 版本: v20251207
-- 目的: 添加GRA优先级映射和切换成本参数到 config.algorithm_parameters 表
-- 
-- GRA (Global Resource Arbiter) 设计:
--   1. 优先级金字塔: L0(生命优先) > L1(次要救援) > L2(侦察) > L3(基础保障)
--   2. 切换成本计算: 防止任务震荡，只有高优先级任务才能抢占低优先级
--   3. 抢占规则: 优先级差>=2 或 (差=1 且 切换成本<0.3) 才允许抢占
--
-- 执行前请备份数据！
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. 插入 GRA 优先级映射配置
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, 
    code, 
    name, 
    name_cn, 
    params, 
    description,
    is_active
)
VALUES (
    'gra',
    'GRA-PRIORITY-MAP',
    'GRA Priority Mapping',
    'GRA优先级映射',
    '{
        "priority_map": {
            "life_rescue_confirmed": 0,
            "secondary_disaster_prevention": 0,
            "medical_transport": 1,
            "hazard_zone_recon": 1,
            "suspect_point_recon": 2,
            "panoramic_recon": 2,
            "supply_delivery": 2,
            "infrastructure_inspection": 3
        },
        "priority_levels": {
            "L0": {
                "name": "生命优先",
                "description": "已确认的被困人员救援、二次灾害预防",
                "task_types": ["life_rescue_confirmed", "secondary_disaster_prevention"]
            },
            "L1": {
                "name": "次要救援",
                "description": "医疗转运、危险区域侦察",
                "task_types": ["medical_transport", "hazard_zone_recon"]
            },
            "L2": {
                "name": "侦察任务",
                "description": "疑似点侦察、全景侦察、物资配送",
                "task_types": ["suspect_point_recon", "panoramic_recon", "supply_delivery"]
            },
            "L3": {
                "name": "基础保障",
                "description": "基础设施巡检、设备维护",
                "task_types": ["infrastructure_inspection"]
            }
        },
        "default_priority": 3,
        "unknown_task_handling": "assign_default"
    }'::jsonb,
    'GRA全局资源仲裁器优先级映射，L0最高优先级，L3最低',
    TRUE
)
ON CONFLICT (category, code) DO UPDATE SET
    params = EXCLUDED.params,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- 2. 插入 GRA 切换成本参数
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, 
    code, 
    name, 
    name_cn, 
    params, 
    description,
    is_active
)
VALUES (
    'gra',
    'GRA-SWITCHING-COST',
    'GRA Switching Cost Parameters',
    'GRA切换成本参数',
    '{
        "cost_threshold": 0.2,
        "min_priority_diff_for_preemption": 1,
        "auto_preempt_priority_diff": 2,
        "weights": {
            "distance_weight": 0.4,
            "remaining_capacity_weight": 0.3,
            "task_progress_weight": 0.3
        },
        "penalties": {
            "return_to_base_penalty": 0.2,
            "partial_completion_penalty": 0.15,
            "equipment_change_penalty": 0.1
        },
        "cooldown": {
            "preemption_cooldown_minutes": 5,
            "max_preemptions_per_resource": 3
        }
    }'::jsonb,
    'GRA切换成本计算参数，控制抢占行为防止任务震荡',
    TRUE
)
ON CONFLICT (category, code) DO UPDATE SET
    params = EXCLUDED.params,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- 3. 插入 GRA 抢占规则配置
-- ============================================================================

INSERT INTO config.algorithm_parameters (
    category, 
    code, 
    name, 
    name_cn, 
    params, 
    description,
    is_active
)
VALUES (
    'gra',
    'GRA-PREEMPTION-RULES',
    'GRA Preemption Rules',
    'GRA抢占规则',
    '{
        "rules": [
            {
                "rule_id": "PREEMPT-001",
                "name": "高优先级直接抢占",
                "condition": "priority_diff >= 2",
                "action": "preempt",
                "check_cost": false,
                "description": "L0任务可直接抢占L2/L3，无需检查切换成本"
            },
            {
                "rule_id": "PREEMPT-002",
                "name": "低成本抢占",
                "condition": "priority_diff == 1 AND switching_cost < 0.3",
                "action": "preempt",
                "check_cost": true,
                "description": "相邻优先级需切换成本<30%才允许抢占"
            },
            {
                "rule_id": "PREEMPT-003",
                "name": "同优先级不抢占",
                "condition": "priority_diff == 0",
                "action": "queue",
                "description": "同优先级任务排队等待，不抢占"
            },
            {
                "rule_id": "PREEMPT-004",
                "name": "不可抢占资源保护",
                "condition": "resource.is_preemptible == false",
                "action": "reject",
                "description": "标记为不可抢占的资源不参与抢占"
            }
        ],
        "preempted_task_handling": {
            "strategy": "requeue_with_priority_boost",
            "priority_boost": 0,
            "max_requeue_times": 2,
            "timeout_minutes": 30
        }
    }'::jsonb,
    'GRA抢占规则配置，定义何时允许抢占及被抢占任务处理',
    TRUE
)
ON CONFLICT (category, code) DO UPDATE SET
    params = EXCLUDED.params,
    description = EXCLUDED.description,
    updated_at = NOW();

COMMIT;

-- ============================================================================
-- 验证
-- ============================================================================
-- SELECT code, name_cn FROM config.algorithm_parameters WHERE category = 'gra';
-- 预期: GRA-PRIORITY-MAP, GRA-SWITCHING-COST, GRA-PREEMPTION-RULES
