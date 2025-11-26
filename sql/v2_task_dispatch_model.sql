-- ============================================================================
-- 任务派遣数据模型 V2
-- 支持：任务需求定义、队伍匹配、路径规划、调度优化
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 创建新schema
CREATE SCHEMA IF NOT EXISTS operational_v2;

-- ============================================================================
-- 1. 任务状态枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.task_status_v2 CASCADE;
CREATE TYPE operational_v2.task_status_v2 AS ENUM (
    'pending',               -- 待处理
    'planning',              -- 规划中
    'assigned',              -- 已分配
    'dispatched',            -- 已派遣
    'en_route',              -- 途中
    'on_site',               -- 现场
    'in_progress',           -- 执行中
    'completed',             -- 已完成
    'failed',                -- 失败
    'cancelled'              -- 已取消
);

-- ============================================================================
-- 2. 任务优先级枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.task_priority_v2 CASCADE;
CREATE TYPE operational_v2.task_priority_v2 AS ENUM (
    'critical',              -- 紧急(生命危险)
    'high',                  -- 高
    'medium',                -- 中
    'low'                    -- 低
);

-- ============================================================================
-- 3. 任务需求表 (task_requirements_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.task_requirements_v2 CASCADE;
CREATE TABLE operational_v2.task_requirements_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联
    scenario_id UUID,                              -- 关联想定
    event_id UUID,                                 -- 关联事件
    scheme_id UUID,                                -- 关联方案
    
    -- 任务基本信息
    task_code VARCHAR(50) UNIQUE,                  -- 任务编号 TASK-001
    task_name VARCHAR(200) NOT NULL,               -- 任务名称
    task_type VARCHAR(50) NOT NULL,                -- search/rescue/medical/hazmat/engineering/logistics
    priority operational_v2.task_priority_v2 DEFAULT 'medium',
    
    -- 位置信息
    location GEOGRAPHY(POINT, 4326),               -- 任务位置
    location_address VARCHAR(300),                 -- 地址描述
    affected_area GEOGRAPHY(POLYGON, 4326),        -- 影响区域
    
    -- 时间要求
    created_at TIMESTAMPTZ DEFAULT now(),
    deadline_at TIMESTAMPTZ,                       -- 截止时间
    expected_duration_minutes INT,                 -- 预计执行时长
    response_time_max_minutes INT,                 -- 最大响应时间
    
    -- 能力需求
    required_capabilities TEXT[] NOT NULL,         -- 所需能力编码列表
    
    -- 人员需求
    min_personnel INT DEFAULT 1,                   -- 最少人数
    recommended_personnel INT,                     -- 推荐人数
    required_certifications TEXT[],                -- 所需资质
    
    -- 装备需求
    required_equipment_codes TEXT[],               -- 所需装备编码
    required_equipment_categories TEXT[],          -- 所需装备类别
    
    -- 车辆需求
    min_vehicles INT DEFAULT 1,                    -- 最少车辆数
    required_vehicle_capabilities TEXT[],          -- 车辆能力要求 {all_terrain,flood}
    
    -- 约束条件
    terrain_constraints TEXT[],                    -- 地形约束
    weather_constraints TEXT[],                    -- 天气约束
    special_requirements TEXT,                     -- 特殊要求描述
    
    -- 状态
    status operational_v2.task_status_v2 DEFAULT 'pending',
    
    -- 执行信息
    assigned_team_ids UUID[],                      -- 已分配的队伍
    assigned_vehicle_ids UUID[],                   -- 已分配的车辆
    planned_route_id UUID,                         -- 规划路径ID
    
    properties JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_task_requirements_v2_scenario ON operational_v2.task_requirements_v2(scenario_id);
CREATE INDEX idx_task_requirements_v2_status ON operational_v2.task_requirements_v2(status);
CREATE INDEX idx_task_requirements_v2_priority ON operational_v2.task_requirements_v2(priority);
CREATE INDEX idx_task_requirements_v2_location ON operational_v2.task_requirements_v2 USING GIST(location);

COMMENT ON TABLE operational_v2.task_requirements_v2 IS '任务需求表 - 定义任务的详细需求';
COMMENT ON COLUMN operational_v2.task_requirements_v2.id IS '任务唯一标识符';
COMMENT ON COLUMN operational_v2.task_requirements_v2.scenario_id IS '关联想定ID';
COMMENT ON COLUMN operational_v2.task_requirements_v2.event_id IS '关联事件ID';
COMMENT ON COLUMN operational_v2.task_requirements_v2.scheme_id IS '关联方案ID';
COMMENT ON COLUMN operational_v2.task_requirements_v2.task_code IS '任务编号';
COMMENT ON COLUMN operational_v2.task_requirements_v2.task_name IS '任务名称';
COMMENT ON COLUMN operational_v2.task_requirements_v2.task_type IS '任务类型: search搜索/rescue救援/medical医疗/hazmat危化/engineering工程/logistics保障';
COMMENT ON COLUMN operational_v2.task_requirements_v2.priority IS '优先级枚举';
COMMENT ON COLUMN operational_v2.task_requirements_v2.location IS '任务位置坐标';
COMMENT ON COLUMN operational_v2.task_requirements_v2.location_address IS '任务位置地址描述';
COMMENT ON COLUMN operational_v2.task_requirements_v2.affected_area IS '任务影响区域多边形';
COMMENT ON COLUMN operational_v2.task_requirements_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.task_requirements_v2.deadline_at IS '截止完成时间';
COMMENT ON COLUMN operational_v2.task_requirements_v2.expected_duration_minutes IS '预计执行时长（分钟）';
COMMENT ON COLUMN operational_v2.task_requirements_v2.response_time_max_minutes IS '最大允许响应时间（分钟）';
COMMENT ON COLUMN operational_v2.task_requirements_v2.required_capabilities IS '所需能力编码数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.min_personnel IS '最少人员数量';
COMMENT ON COLUMN operational_v2.task_requirements_v2.recommended_personnel IS '推荐人员数量';
COMMENT ON COLUMN operational_v2.task_requirements_v2.required_certifications IS '所需资质数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.required_equipment_codes IS '所需装备编码数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.required_equipment_categories IS '所需装备类别数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.min_vehicles IS '最少车辆数';
COMMENT ON COLUMN operational_v2.task_requirements_v2.required_vehicle_capabilities IS '车辆能力要求数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.terrain_constraints IS '地形约束数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.weather_constraints IS '天气约束数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.special_requirements IS '特殊要求描述';
COMMENT ON COLUMN operational_v2.task_requirements_v2.status IS '任务状态枚举';
COMMENT ON COLUMN operational_v2.task_requirements_v2.assigned_team_ids IS '已分配队伍ID数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.assigned_vehicle_ids IS '已分配车辆ID数组';
COMMENT ON COLUMN operational_v2.task_requirements_v2.planned_route_id IS '规划路径ID';
COMMENT ON COLUMN operational_v2.task_requirements_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.task_requirements_v2.updated_at IS '更新时间';

-- ============================================================================
-- 4. 规划路径表 (planned_routes_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.planned_routes_v2 CASCADE;
CREATE TABLE operational_v2.planned_routes_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联
    task_id UUID REFERENCES operational_v2.task_requirements_v2(id),
    vehicle_id UUID,                               -- 关联车辆
    team_id UUID,                                  -- 关联队伍
    
    -- 路径信息
    route_geometry GEOGRAPHY(LINESTRING, 4326),    -- 路径几何
    route_edges UUID[],                            -- 路径经过的边ID列表
    route_nodes UUID[],                            -- 路径经过的节点ID列表
    
    -- 起终点
    start_location GEOGRAPHY(POINT, 4326),         -- 起点
    end_location GEOGRAPHY(POINT, 4326),           -- 终点
    waypoints GEOGRAPHY(MULTIPOINT, 4326),         -- 途经点
    
    -- 统计信息
    total_distance_m DOUBLE PRECISION,             -- 总距离(米)
    estimated_time_minutes INT,                    -- 预计时间(分钟)
    total_cost DOUBLE PRECISION,                   -- A*总代价
    
    -- 路况信息
    blocked_segments INT DEFAULT 0,                -- 封锁路段数
    alternative_count INT DEFAULT 0,               -- 备选路径数
    risk_level INT DEFAULT 1,                      -- 风险等级1-10
    
    -- 高程信息
    max_gradient_percent DOUBLE PRECISION,         -- 最大坡度
    total_elevation_gain_m DOUBLE PRECISION,       -- 总爬升
    
    -- 状态
    status VARCHAR(20) DEFAULT 'planned',          -- planned/active/completed/cancelled
    
    planned_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    properties JSONB DEFAULT '{}'
);

CREATE INDEX idx_planned_routes_v2_task ON operational_v2.planned_routes_v2(task_id);
CREATE INDEX idx_planned_routes_v2_vehicle ON operational_v2.planned_routes_v2(vehicle_id);
CREATE INDEX idx_planned_routes_v2_geometry ON operational_v2.planned_routes_v2 USING GIST(route_geometry);

COMMENT ON TABLE operational_v2.planned_routes_v2 IS '规划路径表 - 存储A*规划的路径';
COMMENT ON COLUMN operational_v2.planned_routes_v2.id IS '路径唯一标识符';
COMMENT ON COLUMN operational_v2.planned_routes_v2.task_id IS '关联任务ID';
COMMENT ON COLUMN operational_v2.planned_routes_v2.vehicle_id IS '关联车辆ID';
COMMENT ON COLUMN operational_v2.planned_routes_v2.team_id IS '关联队伍ID';
COMMENT ON COLUMN operational_v2.planned_routes_v2.route_geometry IS '路径几何线串';
COMMENT ON COLUMN operational_v2.planned_routes_v2.route_edges IS '经过的路网边ID数组';
COMMENT ON COLUMN operational_v2.planned_routes_v2.route_nodes IS '经过的路网节点ID数组';
COMMENT ON COLUMN operational_v2.planned_routes_v2.start_location IS '起点位置';
COMMENT ON COLUMN operational_v2.planned_routes_v2.end_location IS '终点位置';
COMMENT ON COLUMN operational_v2.planned_routes_v2.waypoints IS '途经点';
COMMENT ON COLUMN operational_v2.planned_routes_v2.total_distance_m IS '总距离（米）';
COMMENT ON COLUMN operational_v2.planned_routes_v2.estimated_time_minutes IS '预计时间（分钟）';
COMMENT ON COLUMN operational_v2.planned_routes_v2.total_cost IS 'A*算法总代价';
COMMENT ON COLUMN operational_v2.planned_routes_v2.blocked_segments IS '途中封锁路段数量';
COMMENT ON COLUMN operational_v2.planned_routes_v2.alternative_count IS '备选路径数量';
COMMENT ON COLUMN operational_v2.planned_routes_v2.risk_level IS '风险等级1-10';
COMMENT ON COLUMN operational_v2.planned_routes_v2.max_gradient_percent IS '路径最大坡度';
COMMENT ON COLUMN operational_v2.planned_routes_v2.total_elevation_gain_m IS '总爬升高度（米）';
COMMENT ON COLUMN operational_v2.planned_routes_v2.status IS '状态: planned已规划/active执行中/completed已完成/cancelled已取消';
COMMENT ON COLUMN operational_v2.planned_routes_v2.planned_at IS '规划时间';
COMMENT ON COLUMN operational_v2.planned_routes_v2.started_at IS '开始执行时间';
COMMENT ON COLUMN operational_v2.planned_routes_v2.completed_at IS '完成时间';
COMMENT ON COLUMN operational_v2.planned_routes_v2.properties IS '扩展属性JSON';

-- ============================================================================
-- 5. 函数：匹配任务所需队伍
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.match_teams_for_task(
    p_task_id UUID,
    p_max_results INT DEFAULT 10
) RETURNS TABLE (
    team_id UUID,
    team_name VARCHAR(200),
    team_type operational_v2.team_type_v2,
    capability_match_score DOUBLE PRECISION,
    distance_km DOUBLE PRECISION,
    estimated_response_minutes INT,
    available_personnel INT,
    overall_score DOUBLE PRECISION
) AS $$
DECLARE
    v_task operational_v2.task_requirements_v2%ROWTYPE;
BEGIN
    SELECT * INTO v_task FROM operational_v2.task_requirements_v2 WHERE id = p_task_id;
    
    IF v_task.id IS NULL THEN
        RETURN;
    END IF;
    
    RETURN QUERY
    WITH team_capabilities AS (
        -- 计算每个队伍的能力匹配度
        SELECT 
            t.id AS tid,
            t.name AS tname,
            t.team_type AS ttype,
            t.base_location,
            t.available_personnel,
            t.response_time_minutes,
            t.capability_level,
            -- 能力匹配分数 = 匹配能力数 / 需求能力数
            COALESCE(
                (SELECT COUNT(*)::float FROM operational_v2.team_capabilities_v2 tc 
                 WHERE tc.team_id = t.id 
                 AND tc.capability_code = ANY(v_task.required_capabilities))
                / GREATEST(array_length(v_task.required_capabilities, 1), 1)::float,
                0
            ) AS cap_score
        FROM operational_v2.rescue_teams_v2 t
        WHERE t.status = 'standby'
          AND t.available_personnel >= v_task.min_personnel
    ),
    team_distances AS (
        -- 计算距离
        SELECT 
            tc.*,
            CASE 
                WHEN tc.base_location IS NOT NULL AND v_task.location IS NOT NULL
                THEN ST_Distance(tc.base_location, v_task.location) / 1000  -- 转km
                ELSE 999999
            END AS dist_km
        FROM team_capabilities tc
        WHERE tc.cap_score > 0  -- 至少匹配一项能力
    )
    SELECT 
        td.tid,
        td.tname,
        td.ttype,
        td.cap_score,
        td.dist_km,
        COALESCE(td.response_time_minutes, 30) + (td.dist_km * 2)::int AS est_response,  -- 简单估算
        td.available_personnel,
        -- 综合评分: 能力40% + 距离30% + 响应时间20% + 能力等级10%
        (td.cap_score * 0.4 + 
         (1 - LEAST(td.dist_km / 100, 1)) * 0.3 +
         (1 - LEAST((COALESCE(td.response_time_minutes, 30) + td.dist_km * 2) / 120, 1)) * 0.2 +
         td.capability_level / 5.0 * 0.1
        ) AS overall
    FROM team_distances td
    ORDER BY overall DESC
    LIMIT p_max_results;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.match_teams_for_task IS '为任务匹配合适的救援队伍，返回排序后的候选队伍';

-- ============================================================================
-- 6. 函数：匹配任务所需车辆
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.match_vehicles_for_task(
    p_task_id UUID,
    p_team_id UUID DEFAULT NULL,
    p_max_results INT DEFAULT 10
) RETURNS TABLE (
    vehicle_id UUID,
    vehicle_name VARCHAR(200),
    vehicle_type operational_v2.vehicle_type_v2,
    terrain_match BOOLEAN,
    available_capacity_kg DOUBLE PRECISION,
    distance_km DOUBLE PRECISION,
    overall_score DOUBLE PRECISION
) AS $$
DECLARE
    v_task operational_v2.task_requirements_v2%ROWTYPE;
    v_team operational_v2.rescue_teams_v2%ROWTYPE;
BEGIN
    SELECT * INTO v_task FROM operational_v2.task_requirements_v2 WHERE id = p_task_id;
    
    IF v_task.id IS NULL THEN
        RETURN;
    END IF;
    
    IF p_team_id IS NOT NULL THEN
        SELECT * INTO v_team FROM operational_v2.rescue_teams_v2 WHERE id = p_team_id;
    END IF;
    
    RETURN QUERY
    SELECT 
        v.id,
        v.name,
        v.vehicle_type,
        -- 检查地形兼容性
        CASE 
            WHEN v_task.required_vehicle_capabilities IS NULL THEN true
            WHEN v.is_all_terrain THEN true
            ELSE v.terrain_capabilities && v_task.required_vehicle_capabilities
        END AS terrain_ok,
        -- 可用载重
        v.max_weight_kg - v.current_weight_kg AS avail_cap,
        -- 距离
        CASE 
            WHEN v_team.base_location IS NOT NULL AND v_task.location IS NOT NULL
            THEN ST_Distance(v_team.base_location, v_task.location) / 1000
            ELSE 999999
        END AS dist,
        -- 综合评分
        (CASE WHEN v.is_all_terrain THEN 0.3 ELSE 0.1 END +
         (v.max_weight_kg - v.current_weight_kg) / v.max_weight_kg * 0.3 +
         v.max_device_slots / 10.0 * 0.2 +
         COALESCE(v.range_km, 500) / 1000.0 * 0.2
        ) AS score
    FROM operational_v2.vehicles_v2 v
    WHERE v.status = 'available'
      AND (v_task.required_vehicle_capabilities IS NULL 
           OR v.is_all_terrain 
           OR v.terrain_capabilities && v_task.required_vehicle_capabilities)
    ORDER BY score DESC
    LIMIT p_max_results;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.match_vehicles_for_task IS '为任务匹配合适的车辆';

-- ============================================================================
-- 7. 函数：创建任务派遣
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.create_task_dispatch(
    p_task_id UUID,
    p_team_id UUID,
    p_vehicle_ids UUID[],
    p_dispatched_by VARCHAR(100) DEFAULT 'system'
) RETURNS UUID AS $$
DECLARE
    v_task operational_v2.task_requirements_v2%ROWTYPE;
    v_team operational_v2.rescue_teams_v2%ROWTYPE;
    v_dispatch_id UUID;
BEGIN
    SELECT * INTO v_task FROM operational_v2.task_requirements_v2 WHERE id = p_task_id;
    SELECT * INTO v_team FROM operational_v2.rescue_teams_v2 WHERE id = p_team_id;
    
    IF v_task.id IS NULL OR v_team.id IS NULL THEN
        RAISE EXCEPTION '任务或队伍不存在';
    END IF;
    
    -- 更新任务状态
    UPDATE operational_v2.task_requirements_v2
    SET status = 'assigned',
        assigned_team_ids = array_append(COALESCE(assigned_team_ids, '{}'), p_team_id),
        assigned_vehicle_ids = p_vehicle_ids,
        updated_at = now()
    WHERE id = p_task_id;
    
    -- 更新队伍状态
    UPDATE operational_v2.rescue_teams_v2
    SET status = 'deployed',
        current_task_id = p_task_id,
        updated_at = now()
    WHERE id = p_team_id;
    
    -- 更新车辆状态
    UPDATE operational_v2.vehicles_v2
    SET status = 'deployed',
        updated_at = now()
    WHERE id = ANY(p_vehicle_ids);
    
    -- 创建调度记录
    INSERT INTO operational_v2.resource_dispatches_v2 (
        scenario_id, task_id, team_id,
        dispatch_type, destination, destination_address,
        mission_description, created_by
    ) VALUES (
        v_task.scenario_id, p_task_id, p_team_id,
        'initial', v_task.location, v_task.location_address,
        v_task.task_name, p_dispatched_by
    )
    RETURNING id INTO v_dispatch_id;
    
    RETURN v_dispatch_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.create_task_dispatch IS '创建任务派遣，更新相关状态';

-- ============================================================================
-- 8. 视图：待处理任务概览
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.v_pending_tasks_v2 AS
SELECT 
    t.id,
    t.task_code,
    t.task_name,
    t.task_type,
    t.priority,
    t.status,
    t.location_address,
    t.required_capabilities,
    t.min_personnel,
    t.min_vehicles,
    t.deadline_at,
    t.response_time_max_minutes,
    EXTRACT(EPOCH FROM (t.deadline_at - now())) / 60 AS minutes_until_deadline,
    array_length(t.assigned_team_ids, 1) AS assigned_teams_count,
    s.name AS scenario_name
FROM operational_v2.task_requirements_v2 t
LEFT JOIN operational_v2.scenarios_v2 s ON t.scenario_id = s.id
WHERE t.status IN ('pending', 'planning', 'assigned')
ORDER BY 
    CASE t.priority 
        WHEN 'critical' THEN 1 
        WHEN 'high' THEN 2 
        WHEN 'medium' THEN 3 
        ELSE 4 
    END,
    t.deadline_at NULLS LAST;

COMMENT ON VIEW operational_v2.v_pending_tasks_v2 IS '待处理任务视图';

-- ============================================================================
-- 9. 插入示例任务数据
-- ============================================================================

-- 首先获取想定ID
DO $$
DECLARE
    v_scenario_id UUID;
BEGIN
    SELECT id INTO v_scenario_id FROM operational_v2.scenarios_v2 WHERE name LIKE '%茂县%' LIMIT 1;
    
    IF v_scenario_id IS NOT NULL THEN
        INSERT INTO operational_v2.task_requirements_v2 (
            scenario_id, task_code, task_name, task_type, priority,
            location, location_address,
            required_capabilities, min_personnel, recommended_personnel,
            required_equipment_categories, min_vehicles, required_vehicle_capabilities,
            response_time_max_minutes, expected_duration_minutes
        ) VALUES
        -- 任务1: 建筑倒塌救援
        (v_scenario_id, 'TASK-001', '凤仪镇居民楼倒塌救援', 'rescue', 'critical',
         ST_GeogFromText('POINT(103.851 31.682)'), '茂县凤仪镇幸福路12号',
         '{SEARCH_LIFE_DETECT,RESCUE_STRUCTURAL,MEDICAL_FIRST_AID}', 15, 25,
         '{search_detect,rescue_tool,medical}', 2, '{mountain}',
         30, 240),
        
        -- 任务2: 学校人员搜救
        (v_scenario_id, 'TASK-002', '凤仪小学被困人员搜救', 'search', 'critical',
         ST_GeogFromText('POINT(103.853 31.680)'), '茂县凤仪镇凤仪小学',
         '{SEARCH_LIFE_DETECT,RESCUE_CONFINED}', 10, 20,
         '{search_detect}', 2, '{urban,mountain}',
         20, 180),
        
        -- 任务3: 医疗救护点设立
        (v_scenario_id, 'TASK-003', '震中医疗救护点设立', 'medical', 'high',
         ST_GeogFromText('POINT(103.850 31.685)'), '茂县凤仪镇中心广场',
         '{MEDICAL_TRIAGE,MEDICAL_FIRST_AID}', 8, 15,
         '{medical}', 1, '{urban}',
         45, 480),
        
        -- 任务4: 道路抢通
        (v_scenario_id, 'TASK-004', 'G213国道茂县段抢通', 'engineering', 'high',
         ST_GeogFromText('POINT(103.840 31.670)'), 'G213国道K125+500处',
         '{ENG_DEMOLITION,ENG_LIFTING}', 20, 30,
         '{rescue_tool}', 3, '{all_terrain,mountain}',
         60, 360),
        
        -- 任务5: 危化品处置
        (v_scenario_id, 'TASK-005', '加油站泄漏处置', 'hazmat', 'critical',
         ST_GeogFromText('POINT(103.855 31.678)'), '茂县凤仪镇中石化加油站',
         '{HAZMAT_DETECT,HAZMAT_CONTAIN}', 8, 12,
         '{hazmat,protection}', 1, '{urban}',
         15, 120);
         
        RAISE NOTICE '已插入5条示例任务';
    ELSE
        RAISE NOTICE '未找到茂县想定，跳过任务插入';
    END IF;
END $$;

-- ============================================================================
-- 输出创建结果
-- ============================================================================
DO $$
DECLARE
    v_tasks INT;
BEGIN
    SELECT COUNT(*) INTO v_tasks FROM operational_v2.task_requirements_v2;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '任务派遣模型 V2 创建完成';
    RAISE NOTICE '表: task_requirements_v2, planned_routes_v2';
    RAISE NOTICE '函数: match_teams_for_task, match_vehicles_for_task, create_task_dispatch';
    RAISE NOTICE '任务数: %', v_tasks;
    RAISE NOTICE '========================================';
END $$;
