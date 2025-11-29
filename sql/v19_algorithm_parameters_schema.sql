-- ============================================================================
-- v19: 算法参数配置表
-- 
-- 目的: 将硬编码的算法参数迁移到数据库，支持：
--   1. 不同政府部门的定制化配置
--   2. 不同地区的本地化配置
--   3. 标准版本升级（如Sphere 2018 → 2024）
--   4. 运行时配置变更（无需代码发版）
--
-- 设计原则：
--   - 无Fallback：配置缺失时必须报错，不静默降级
--   - 版本化：支持同一标准的多个版本共存
--   - 优先级：部门定制 > 地区定制 > 全国通用
--
-- 执行方式: psql -U postgres -d frontai -f sql/v19_algorithm_parameters_schema.sql
-- ============================================================================

-- 创建config schema（如果不存在）
CREATE SCHEMA IF NOT EXISTS config;

-- ============================================================================
-- 算法参数配置表
-- ============================================================================
CREATE TABLE IF NOT EXISTS config.algorithm_parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 分类标识
    category VARCHAR(50) NOT NULL,
    -- 'sphere'     : Sphere人道主义标准
    -- 'casualty'   : 伤亡估算模型参数
    -- 'routing'    : 道路/地形速度参数
    -- 'assessment' : 灾情等级评估阈值
    -- 'confirmation': 事件确认评分阈值
    
    code VARCHAR(100) NOT NULL,
    -- 唯一编码，如 'SPHERE-WASH-001', 'CASUALTY-BUILDING-C'
    
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    -- 版本号，支持标准更新（如Sphere 2018 vs 2024）
    
    -- 配置内容
    name VARCHAR(200) NOT NULL,
    name_cn VARCHAR(200),
    
    -- 核心参数（JSONB灵活存储，结构因category而异）
    params JSONB NOT NULL,
    
    -- 元数据
    reference VARCHAR(500),
    -- 数据来源/标准文献，如 'Sphere Handbook 2018, WASH Standard 1'
    
    description TEXT,
    
    -- 适用范围（实现配置优先级）
    region_code VARCHAR(50),
    -- NULL = 全国通用
    -- 省级代码 = 省级定制（如 '510000' 四川省）
    -- 市级代码 = 市级定制（如 '510100' 成都市）
    
    department_code VARCHAR(50),
    -- NULL = 通用
    -- 部门代码 = 部门定制（如 'MEM' 应急管理部, 'FIRE' 消防救援）
    
    -- 状态与审计
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    
    -- 约束：同一配置在同一适用范围内唯一
    CONSTRAINT uq_algo_param UNIQUE (category, code, version, region_code, department_code)
);

-- 添加注释
COMMENT ON TABLE config.algorithm_parameters IS '算法参数配置表 - 存储所有可配置的算法参数，支持地区/部门定制';
COMMENT ON COLUMN config.algorithm_parameters.category IS '参数类别: sphere/casualty/routing/assessment/confirmation';
COMMENT ON COLUMN config.algorithm_parameters.code IS '参数唯一编码';
COMMENT ON COLUMN config.algorithm_parameters.version IS '版本号，支持标准升级';
COMMENT ON COLUMN config.algorithm_parameters.params IS 'JSONB格式的参数内容，结构因category而异';
COMMENT ON COLUMN config.algorithm_parameters.region_code IS '地区代码，NULL表示全国通用';
COMMENT ON COLUMN config.algorithm_parameters.department_code IS '部门代码，NULL表示通用';

-- ============================================================================
-- 索引
-- ============================================================================

-- 按类别查询（最常用）
CREATE INDEX IF NOT EXISTS idx_algo_param_category 
ON config.algorithm_parameters(category) 
WHERE is_active = TRUE;

-- 按编码查询
CREATE INDEX IF NOT EXISTS idx_algo_param_code 
ON config.algorithm_parameters(code) 
WHERE is_active = TRUE;

-- 按地区查询（支持地区定制）
CREATE INDEX IF NOT EXISTS idx_algo_param_region 
ON config.algorithm_parameters(region_code) 
WHERE is_active = TRUE AND region_code IS NOT NULL;

-- 按部门查询（支持部门定制）
CREATE INDEX IF NOT EXISTS idx_algo_param_department 
ON config.algorithm_parameters(department_code) 
WHERE is_active = TRUE AND department_code IS NOT NULL;

-- 复合索引：按类别+编码+版本查询（精确匹配）
CREATE INDEX IF NOT EXISTS idx_algo_param_lookup 
ON config.algorithm_parameters(category, code, version) 
WHERE is_active = TRUE;

-- ============================================================================
-- 触发器：自动更新 updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION config.update_algo_param_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_algo_param_updated ON config.algorithm_parameters;
CREATE TRIGGER trg_algo_param_updated
    BEFORE UPDATE ON config.algorithm_parameters
    FOR EACH ROW
    EXECUTE FUNCTION config.update_algo_param_timestamp();

-- ============================================================================
-- 验证函数：检查必需配置是否存在
-- ============================================================================
CREATE OR REPLACE FUNCTION config.validate_required_parameters(
    p_category VARCHAR,
    p_required_codes VARCHAR[]
) RETURNS TABLE(code VARCHAR, exists BOOLEAN) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        unnest(p_required_codes) AS code,
        EXISTS(
            SELECT 1 FROM config.algorithm_parameters ap
            WHERE ap.category = p_category 
            AND ap.code = unnest(p_required_codes)
            AND ap.is_active = TRUE
        ) AS exists;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION config.validate_required_parameters IS '验证指定类别的必需配置是否存在';

-- ============================================================================
-- 完成
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE 'v19: config.algorithm_parameters 表创建完成';
END $$;
