-- ============================================================================
-- V2 环境与态势数据模型 (v2_environment_model.sql)
-- 天气状况、通信覆盖、疏散安置点
-- ============================================================================

-- ============================================================================
-- 枚举类型定义
-- ============================================================================

-- 天气类型
CREATE TYPE weather_type_v2 AS ENUM (
    'sunny',           -- 晴
    'cloudy',          -- 多云
    'overcast',        -- 阴
    'light_rain',      -- 小雨
    'moderate_rain',   -- 中雨
    'heavy_rain',      -- 大雨
    'rainstorm',       -- 暴雨
    'snow',            -- 雪
    'fog',             -- 雾
    'haze',            -- 霾
    'thunderstorm',    -- 雷暴
    'typhoon',         -- 台风
    'sandstorm'        -- 沙尘暴
);

-- 网络类型
CREATE TYPE network_type_v2 AS ENUM (
    '4g',              -- 4G移动网络
    '5g',              -- 5G移动网络
    'satellite',       -- 卫星通信
    'mesh',            -- 自组网
    'radio',           -- 无线电
    'fiber',           -- 光纤
    'microwave'        -- 微波
);

-- 安置点类型
CREATE TYPE shelter_type_v2 AS ENUM (
    'temporary',       -- 临时安置点
    'permanent',       -- 固定安置点
    'medical',         -- 医疗救护点
    'supply_depot',    -- 物资集散点
    'command_post',    -- 指挥所
    'helipad',         -- 直升机起降点
    'staging_area'     -- 集结区
);

-- 安置点状态
CREATE TYPE shelter_status_v2 AS ENUM (
    'preparing',       -- 准备中
    'open',            -- 开放
    'full',            -- 已满
    'limited',         -- 限流
    'closed',          -- 关闭
    'damaged'          -- 受损
);

-- ============================================================================
-- 天气状况表 weather_conditions_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS weather_conditions_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定 (NULL表示真实天气)
    scenario_id UUID,
    
    -- 区域标识/名称
    area_id VARCHAR(100),
    area_name VARCHAR(200),
    
    -- 覆盖区域 (地理范围)
    coverage_area GEOMETRY(Polygon, 4326),
    
    -- 天气类型
    weather_type weather_type_v2 NOT NULL,
    
    -- 温度 (摄氏度)
    temperature DECIMAL(5,2),
    
    -- 体感温度
    feels_like DECIMAL(5,2),
    
    -- 风速 (m/s) - 影响无人机飞行
    wind_speed DECIMAL(5,2),
    
    -- 风向 (度数, 0-360)
    wind_direction INTEGER,
    
    -- 风力等级 (0-17)
    wind_scale INTEGER,
    
    -- 能见度 (米) - 影响搜救
    visibility INTEGER,
    
    -- 降水量 (mm/h)
    precipitation DECIMAL(6,2),
    
    -- 湿度 (%)
    humidity INTEGER,
    
    -- 气压 (hPa)
    pressure DECIMAL(6,1),
    
    -- 是否适合无人机飞行
    uav_flyable BOOLEAN DEFAULT true,
    
    -- 不适合飞行原因
    uav_restriction_reason TEXT,
    
    -- 是否适合地面行动
    ground_operable BOOLEAN DEFAULT true,
    
    -- 地面行动限制原因
    ground_restriction_reason TEXT,
    
    -- 预警信息
    alerts JSONB DEFAULT '[]', -- [{type, level, message, issued_at}]
    
    -- 未来N小时预报
    forecast_data JSONB, -- [{hour, weather_type, temperature, wind_speed, precipitation}]
    
    -- 数据来源
    data_source VARCHAR(100), -- meteorological_bureau/sensor/manual
    
    -- 记录时间
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 有效期至
    valid_until TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_weather_v2_scenario ON weather_conditions_v2(scenario_id);
CREATE INDEX idx_weather_v2_area ON weather_conditions_v2(area_id);
CREATE INDEX idx_weather_v2_coverage ON weather_conditions_v2 USING GIST(coverage_area);
CREATE INDEX idx_weather_v2_time ON weather_conditions_v2(recorded_at);
CREATE INDEX idx_weather_v2_type ON weather_conditions_v2(weather_type);

-- ============================================================================
-- 通信网络覆盖表 communication_networks_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS communication_networks_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定 (NULL表示真实网络)
    scenario_id UUID,
    
    -- 网络标识
    network_id VARCHAR(100) NOT NULL,
    
    -- 网络名称
    network_name VARCHAR(200),
    
    -- 网络类型
    network_type network_type_v2 NOT NULL,
    
    -- 覆盖区域
    coverage_area GEOMETRY(Polygon, 4326) NOT NULL,
    
    -- 基站/节点位置 (如果是点状设施)
    node_location GEOMETRY(Point, 4326),
    
    -- 信号强度 (dBm, 越大越好, 通常-50到-120)
    signal_strength INTEGER,
    
    -- 信号质量描述
    signal_quality VARCHAR(50), -- excellent/good/fair/poor/none
    
    -- 可用带宽 (Mbps)
    bandwidth_available DECIMAL(10,2),
    
    -- 延迟 (ms)
    latency_ms INTEGER,
    
    -- 是否正常运行
    is_operational BOOLEAN NOT NULL DEFAULT true,
    
    -- 故障原因 (如果不正常)
    failure_reason TEXT,
    
    -- 预计恢复时间
    estimated_recovery_at TIMESTAMPTZ,
    
    -- 是否有备用网络
    backup_available BOOLEAN DEFAULT false,
    
    -- 备用网络ID
    backup_network_id VARCHAR(100),
    
    -- 运营商
    operator VARCHAR(100),
    
    -- 最后检测时间
    last_check_at TIMESTAMPTZ,
    
    -- 数据来源
    data_source VARCHAR(100),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_comm_network_v2_scenario ON communication_networks_v2(scenario_id);
CREATE INDEX idx_comm_network_v2_type ON communication_networks_v2(network_type);
CREATE INDEX idx_comm_network_v2_coverage ON communication_networks_v2 USING GIST(coverage_area);
CREATE INDEX idx_comm_network_v2_operational ON communication_networks_v2(is_operational);

-- ============================================================================
-- 疏散安置点表 evacuation_shelters_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS evacuation_shelters_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定 (NULL表示常备安置点)
    scenario_id UUID,
    
    -- 安置点编号
    shelter_code VARCHAR(50) NOT NULL,
    
    -- 安置点名称
    name VARCHAR(200) NOT NULL,
    
    -- 安置点类型
    shelter_type shelter_type_v2 NOT NULL,
    
    -- 位置
    location GEOMETRY(Point, 4326) NOT NULL,
    
    -- 占地范围
    boundary GEOMETRY(Polygon, 4326),
    
    -- 地址
    address TEXT,
    
    -- 状态
    status shelter_status_v2 NOT NULL DEFAULT 'preparing',
    
    -- 总容量 (人数)
    total_capacity INTEGER NOT NULL,
    
    -- 当前人数
    current_occupancy INTEGER NOT NULL DEFAULT 0,
    
    -- 剩余容量
    available_capacity INTEGER GENERATED ALWAYS AS (total_capacity - current_occupancy) STORED,
    
    -- 设施配置
    facilities JSONB DEFAULT '{}', 
    -- { 
    --   medical: {beds, doctors, nurses},
    --   sanitation: {toilets, showers},
    --   food: {kitchen, capacity_per_meal},
    --   water: {supply_type, daily_capacity_liters},
    --   power: {source, backup_hours},
    --   communication: {phone, internet}
    -- }
    
    -- 无障碍设施
    accessibility JSONB DEFAULT '{}',
    -- { wheelchair_accessible, sign_language, medical_equipment }
    
    -- 特殊人群容纳能力
    special_accommodations JSONB DEFAULT '{}',
    -- { elderly_capacity, children_capacity, disabled_capacity, medical_patients }
    
    -- 物资储备
    supply_inventory JSONB DEFAULT '{}',
    -- { water_bottles, food_packages, blankets, medicine_kits }
    
    -- 联系人
    contact_person VARCHAR(100),
    contact_phone VARCHAR(50),
    contact_backup VARCHAR(50),
    
    -- 管理单位
    managing_organization VARCHAR(200),
    
    -- 开放时间
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    
    -- 关联的地图实体ID
    entity_id UUID,
    
    -- 备注
    notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_shelters_v2_scenario ON evacuation_shelters_v2(scenario_id);
CREATE INDEX idx_shelters_v2_type ON evacuation_shelters_v2(shelter_type);
CREATE INDEX idx_shelters_v2_status ON evacuation_shelters_v2(status);
CREATE INDEX idx_shelters_v2_location ON evacuation_shelters_v2 USING GIST(location);
CREATE INDEX idx_shelters_v2_capacity ON evacuation_shelters_v2(available_capacity) WHERE status = 'open';

-- ============================================================================
-- 安置点人员记录表 shelter_occupants_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS shelter_occupants_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联安置点
    shelter_id UUID NOT NULL REFERENCES evacuation_shelters_v2(id) ON DELETE CASCADE,
    
    -- 人员信息
    name VARCHAR(100),
    id_number VARCHAR(50), -- 身份证号(加密存储)
    phone VARCHAR(50),
    
    -- 性别
    gender VARCHAR(10),
    
    -- 年龄
    age INTEGER,
    
    -- 特殊情况
    special_needs TEXT, -- 老人、儿童、孕妇、伤病等
    
    -- 来源事件
    source_event_id UUID,
    
    -- 原住址
    original_address TEXT,
    
    -- 入住时间
    checked_in_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 离开时间
    checked_out_at TIMESTAMPTZ,
    
    -- 离开去向
    departure_destination TEXT,
    
    -- 家属联系人
    emergency_contact VARCHAR(100),
    emergency_phone VARCHAR(50),
    
    -- 备注
    notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_shelter_occupants_v2_shelter ON shelter_occupants_v2(shelter_id);
CREATE INDEX idx_shelter_occupants_v2_event ON shelter_occupants_v2(source_event_id) WHERE source_event_id IS NOT NULL;
CREATE INDEX idx_shelter_occupants_v2_active ON shelter_occupants_v2(shelter_id) WHERE checked_out_at IS NULL;

-- ============================================================================
-- 遥测数据表 telemetry_v2 (设备实时状态)
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry_v2 (
    id UUID DEFAULT gen_random_uuid(),
    
    -- 设备ID
    device_id VARCHAR(100) NOT NULL,
    
    -- 设备类型
    device_type VARCHAR(50), -- uav/ugv/usv/vehicle/sensor
    
    -- 遥测类型
    telemetry_type VARCHAR(50) NOT NULL, -- location/battery/speed/altitude/sensor/status
    
    -- 遥测数据
    payload JSONB NOT NULL,
    -- location: {latitude, longitude, altitude, accuracy}
    -- battery: {level, voltage, temperature, charging}
    -- speed: {ground_speed, air_speed, vertical_speed}
    -- altitude: {absolute, relative, terrain}
    -- sensor: {sensor_type, readings[]}
    -- status: {state, mode, errors[]}
    
    -- 位置 (如果是位置遥测)
    location GEOMETRY(Point, 4326),
    
    -- 序列号 (保证顺序)
    sequence_no BIGINT,
    
    -- 设备时间戳
    device_timestamp TIMESTAMPTZ,
    
    -- 服务器接收时间
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 主键必须包含分区键
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- 创建分区 (按月)
CREATE TABLE telemetry_v2_2024_01 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE telemetry_v2_2024_02 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE telemetry_v2_2024_03 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE telemetry_v2_2024_04 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE telemetry_v2_2024_05 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE telemetry_v2_2024_06 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
CREATE TABLE telemetry_v2_2024_07 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
CREATE TABLE telemetry_v2_2024_08 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE telemetry_v2_2024_09 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
CREATE TABLE telemetry_v2_2024_10 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
CREATE TABLE telemetry_v2_2024_11 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
CREATE TABLE telemetry_v2_2024_12 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
CREATE TABLE telemetry_v2_2025_01 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE telemetry_v2_2025_02 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE telemetry_v2_2025_03 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE telemetry_v2_2025_04 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE telemetry_v2_2025_05 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE telemetry_v2_2025_06 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE telemetry_v2_2025_07 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE telemetry_v2_2025_08 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE telemetry_v2_2025_09 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE telemetry_v2_2025_10 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE telemetry_v2_2025_11 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE telemetry_v2_2025_12 PARTITION OF telemetry_v2
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 索引 (在分区表上自动继承)
CREATE INDEX idx_telemetry_v2_device ON telemetry_v2(device_id, recorded_at DESC);
CREATE INDEX idx_telemetry_v2_type ON telemetry_v2(telemetry_type, recorded_at DESC);
CREATE INDEX idx_telemetry_v2_location ON telemetry_v2 USING GIST(location);

-- ============================================================================
-- 视图：设备最新状态
-- ============================================================================
CREATE OR REPLACE VIEW device_latest_telemetry_v2 AS
SELECT DISTINCT ON (device_id, telemetry_type)
    device_id,
    device_type,
    telemetry_type,
    payload,
    location,
    recorded_at
FROM telemetry_v2
ORDER BY device_id, telemetry_type, recorded_at DESC;

-- ============================================================================
-- 视图：安置点汇总
-- ============================================================================
CREATE OR REPLACE VIEW shelter_summary_v2 AS
SELECT 
    s.*,
    ST_AsGeoJSON(s.location)::JSONB as location_geojson,
    ROUND(s.current_occupancy::DECIMAL / NULLIF(s.total_capacity, 0) * 100, 1) as occupancy_rate,
    (SELECT COUNT(*) FROM shelter_occupants_v2 so WHERE so.shelter_id = s.id AND so.checked_out_at IS NULL) as verified_occupancy
FROM evacuation_shelters_v2 s;

-- ============================================================================
-- 函数：查询指定位置的天气
-- ============================================================================
CREATE OR REPLACE FUNCTION get_weather_at_location_v2(
    p_location GEOMETRY,
    p_scenario_id UUID DEFAULT NULL
)
RETURNS TABLE(
    weather_type weather_type_v2,
    temperature DECIMAL,
    wind_speed DECIMAL,
    visibility INTEGER,
    uav_flyable BOOLEAN,
    alerts JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        w.weather_type,
        w.temperature,
        w.wind_speed,
        w.visibility,
        w.uav_flyable,
        w.alerts
    FROM weather_conditions_v2 w
    WHERE (p_scenario_id IS NULL OR w.scenario_id = p_scenario_id)
      AND ST_Contains(w.coverage_area, p_location)
      AND (w.valid_until IS NULL OR w.valid_until > NOW())
    ORDER BY w.recorded_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 函数：查询指定位置的通信覆盖
-- ============================================================================
CREATE OR REPLACE FUNCTION get_network_coverage_v2(
    p_location GEOMETRY,
    p_scenario_id UUID DEFAULT NULL
)
RETURNS TABLE(
    network_type network_type_v2,
    signal_quality VARCHAR,
    is_operational BOOLEAN,
    bandwidth_available DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        n.network_type,
        n.signal_quality,
        n.is_operational,
        n.bandwidth_available
    FROM communication_networks_v2 n
    WHERE (p_scenario_id IS NULL OR n.scenario_id = p_scenario_id)
      AND ST_Contains(n.coverage_area, p_location)
      AND n.is_operational = true
    ORDER BY n.signal_strength DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 函数：查找最近的可用安置点
-- ============================================================================
CREATE OR REPLACE FUNCTION find_nearest_shelters_v2(
    p_location GEOMETRY,
    p_scenario_id UUID DEFAULT NULL,
    p_required_capacity INTEGER DEFAULT 1,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE(
    shelter_id UUID,
    name VARCHAR,
    shelter_type shelter_type_v2,
    distance_meters DOUBLE PRECISION,
    available_capacity INTEGER,
    facilities JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id as shelter_id,
        s.name,
        s.shelter_type,
        ST_Distance(s.location::geography, p_location::geography) as distance_meters,
        s.available_capacity,
        s.facilities
    FROM evacuation_shelters_v2 s
    WHERE (p_scenario_id IS NULL OR s.scenario_id = p_scenario_id OR s.scenario_id IS NULL)
      AND s.status = 'open'
      AND s.available_capacity >= p_required_capacity
    ORDER BY ST_Distance(s.location, p_location)
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 触发器
-- ============================================================================
DROP TRIGGER IF EXISTS tr_comm_network_v2_updated ON communication_networks_v2;
CREATE TRIGGER tr_comm_network_v2_updated
    BEFORE UPDATE ON communication_networks_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

DROP TRIGGER IF EXISTS tr_shelters_v2_updated ON evacuation_shelters_v2;
CREATE TRIGGER tr_shelters_v2_updated
    BEFORE UPDATE ON evacuation_shelters_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

-- ============================================================================
-- 注释
-- ============================================================================
COMMENT ON TABLE weather_conditions_v2 IS '天气状况表 - 影响无人机飞行和地面行动决策';
COMMENT ON TABLE communication_networks_v2 IS '通信网络覆盖表 - 影响设备调度和指挥通信';
COMMENT ON TABLE evacuation_shelters_v2 IS '疏散安置点表 - 人员疏散目的地';
COMMENT ON TABLE shelter_occupants_v2 IS '安置点人员记录 - 跟踪安置人员';
COMMENT ON TABLE telemetry_v2 IS '遥测数据表 - 设备实时状态，按月分区';
