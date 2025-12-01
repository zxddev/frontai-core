-- ============================================================================
-- v20251130: 重点设施POI表 (poi_v2)
--
-- 目的：
--   1. 存储灾区范围内的重点设施（学校、医院、化工厂等）
--   2. 作为侦察目标的来源之一，与风险区域、救援集结点共同构成侦察任务池
--   3. 支持按想定筛选，可从 pgrouting.pointsofinterest 批量导入
--
-- 设计原则：
--   - 与 rescue_staging_sites_v2 结构对齐
--   - 支持空间查询和范围筛选
--   - 包含风险评估字段，供侦察优先级打分使用
-- ============================================================================

-- POI类型枚举
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'poi_type_v2') THEN
        CREATE TYPE operational_v2.poi_type_v2 AS ENUM (
            'hospital',          -- 医院
            'clinic',            -- 诊所/卫生院
            'school',            -- 学校（综合）
            'primary_school',    -- 小学
            'middle_school',     -- 中学
            'kindergarten',      -- 幼儿园
            'university',        -- 大学
            'nursing_home',      -- 养老院
            'chemical_plant',    -- 化工厂
            'gas_station',       -- 加油站
            'reservoir',         -- 水库
            'dam',               -- 大坝
            'substation',        -- 变电站
            'government',        -- 政府机关
            'shelter',           -- 避难所/安置点
            'warehouse',         -- 仓库
            'factory',           -- 工厂
            'other'              -- 其他
        );
    END IF;
END $$;

-- POI风险等级枚举
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'poi_risk_level_v2') THEN
        CREATE TYPE operational_v2.poi_risk_level_v2 AS ENUM (
            'critical',    -- 极高风险（化工厂、水库等）
            'high',        -- 高风险（医院、学校等人员密集）
            'medium',      -- 中等风险
            'low',         -- 低风险
            'unknown'      -- 未评估
        );
    END IF;
END $$;

-- ============================================================================
-- 重点设施POI表 poi_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.poi_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定 (NULL表示基础数据/常备POI)
    scenario_id UUID,
    
    -- 基本信息
    code VARCHAR(50),                        -- POI编号
    name VARCHAR(200) NOT NULL,              -- 名称
    poi_type operational_v2.poi_type_v2 NOT NULL DEFAULT 'other',
    
    -- 位置
    location GEOMETRY(POINT, 4326) NOT NULL,
    address TEXT,
    
    -- 人员信息（估算）
    estimated_population INT,                -- 估计人数（学校学生数、医院床位数等）
    vulnerable_population INT,               -- 脆弱人群数量（老人、儿童、病患）
    
    -- 风险评估
    risk_level operational_v2.poi_risk_level_v2 DEFAULT 'unknown',
    hazard_factors JSONB DEFAULT '[]',       -- 危险因素列表，如 ["chemical_storage", "flood_prone"]
    
    -- 与灾区的关系（动态计算或导入时填充）
    distance_to_epicenter_m DECIMAL(12,2),   -- 到震中/灾害中心距离
    in_affected_area BOOLEAN DEFAULT false,  -- 是否在受灾区域内
    nearest_risk_area_id UUID,               -- 最近的风险区域ID
    nearest_risk_area_distance_m DECIMAL(12,2),
    
    -- 设施状态（侦察后更新）
    status VARCHAR(20) DEFAULT 'unknown',    -- unknown/intact/damaged/destroyed/evacuated
    damage_assessment TEXT,                  -- 损坏评估描述
    last_reconnaissance_at TIMESTAMPTZ,      -- 最后侦察时间
    reconnaissance_priority INT DEFAULT 50,  -- 侦察优先级 0-100
    
    -- 联系方式
    contact_person VARCHAR(100),
    contact_phone VARCHAR(50),
    
    -- 数据来源
    source VARCHAR(50),                      -- pgrouting/manual/import
    source_id VARCHAR(100),                  -- 原始数据ID
    
    -- 扩展属性
    properties JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 索引
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_poi_v2_scenario 
    ON operational_v2.poi_v2(scenario_id);
CREATE INDEX IF NOT EXISTS idx_poi_v2_location 
    ON operational_v2.poi_v2 USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_poi_v2_type 
    ON operational_v2.poi_v2(poi_type);
CREATE INDEX IF NOT EXISTS idx_poi_v2_risk_level 
    ON operational_v2.poi_v2(risk_level);
CREATE INDEX IF NOT EXISTS idx_poi_v2_status 
    ON operational_v2.poi_v2(status);
CREATE INDEX IF NOT EXISTS idx_poi_v2_in_affected 
    ON operational_v2.poi_v2(in_affected_area) WHERE in_affected_area = true;
CREATE INDEX IF NOT EXISTS idx_poi_v2_recon_priority 
    ON operational_v2.poi_v2(reconnaissance_priority DESC);

-- ============================================================================
-- 更新时间触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.update_poi_v2_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_poi_v2_updated ON operational_v2.poi_v2;
CREATE TRIGGER tr_poi_v2_updated
    BEFORE UPDATE ON operational_v2.poi_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_poi_v2_timestamp();

-- ============================================================================
-- 导入函数：从 pgrouting.pointsofinterest 导入指定范围内的重点设施
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.import_poi_from_pgrouting(
    p_scenario_id UUID,
    p_center_lon DOUBLE PRECISION,
    p_center_lat DOUBLE PRECISION,
    p_radius_m DOUBLE PRECISION DEFAULT 50000,
    p_keywords TEXT[] DEFAULT ARRAY['医院', '学校', '幼儿园', '中学', '小学', '化工', '加油站', '养老', '水库', '变电站']
)
RETURNS INT AS $$
DECLARE
    v_total INT := 0;
    v_inserted INT := 0;
    v_keyword TEXT;
    v_poi_type operational_v2.poi_type_v2;
    v_risk_level operational_v2.poi_risk_level_v2;
BEGIN
    -- 遍历关键词导入
    FOREACH v_keyword IN ARRAY p_keywords
    LOOP
        -- 确定POI类型和风险等级
        CASE 
            WHEN v_keyword = '医院' THEN 
                v_poi_type := 'hospital'; v_risk_level := 'high';
            WHEN v_keyword IN ('学校', '中学', '小学') THEN 
                v_poi_type := 'school'; v_risk_level := 'high';
            WHEN v_keyword = '幼儿园' THEN 
                v_poi_type := 'kindergarten'; v_risk_level := 'high';
            WHEN v_keyword = '化工' THEN 
                v_poi_type := 'chemical_plant'; v_risk_level := 'critical';
            WHEN v_keyword = '加油站' THEN 
                v_poi_type := 'gas_station'; v_risk_level := 'critical';
            WHEN v_keyword IN ('养老', '敬老') THEN 
                v_poi_type := 'nursing_home'; v_risk_level := 'high';
            WHEN v_keyword = '水库' THEN 
                v_poi_type := 'reservoir'; v_risk_level := 'critical';
            WHEN v_keyword = '变电站' THEN 
                v_poi_type := 'substation'; v_risk_level := 'medium';
            ELSE 
                v_poi_type := 'other'; v_risk_level := 'unknown';
        END CASE;
        
        -- 导入匹配的POI
        INSERT INTO operational_v2.poi_v2 (
            scenario_id, name, poi_type, location, risk_level,
            distance_to_epicenter_m, source, source_id
        )
        SELECT 
            p_scenario_id,
            p.name,
            v_poi_type,
            p.the_geom::geometry,
            v_risk_level,
            ST_Distance(
                p.the_geom::geography,
                ST_SetSRID(ST_MakePoint(p_center_lon, p_center_lat), 4326)::geography
            ),
            'pgrouting',
            p.pid::text
        FROM pgrouting.pointsofinterest p
        WHERE p.name LIKE '%' || v_keyword || '%'
          AND ST_DWithin(
              p.the_geom::geography,
              ST_SetSRID(ST_MakePoint(p_center_lon, p_center_lat), 4326)::geography,
              p_radius_m
          )
          AND NOT EXISTS (
              SELECT 1 FROM operational_v2.poi_v2 
              WHERE scenario_id = p_scenario_id AND source_id = p.pid::text
          );
        
        GET DIAGNOSTICS v_inserted = ROW_COUNT;
        v_total := v_total + v_inserted;
    END LOOP;
    
    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 注释
-- ============================================================================
COMMENT ON TABLE operational_v2.poi_v2 IS 
    '重点设施POI表 - 存储灾区范围内的学校、医院、化工厂等重点设施，用于侦察任务规划';
COMMENT ON COLUMN operational_v2.poi_v2.poi_type IS 'POI类型：医院/学校/幼儿园/化工厂/加油站/水库等';
COMMENT ON COLUMN operational_v2.poi_v2.risk_level IS '风险等级：critical(极高)/high(高)/medium(中)/low(低)';
COMMENT ON COLUMN operational_v2.poi_v2.estimated_population IS '估计人数，用于优先级计算';
COMMENT ON COLUMN operational_v2.poi_v2.in_affected_area IS '是否在灾害影响区域内';
COMMENT ON COLUMN operational_v2.poi_v2.reconnaissance_priority IS '侦察优先级(0-100)，由算法计算';
COMMENT ON FUNCTION operational_v2.import_poi_from_pgrouting IS 
    '从pgrouting.pointsofinterest导入指定范围和关键词的POI到当前想定';

DO $$
BEGIN
    RAISE NOTICE 'v20251130: poi_v2 table and import function created successfully';
END $$;
