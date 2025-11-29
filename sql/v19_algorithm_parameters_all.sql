-- ============================================================================
-- v19: 算法参数配置 - 完整迁移脚本
-- 
-- 此脚本包含所有v19迁移内容，一次性执行：
-- 1. 创建 config.algorithm_parameters 表
-- 2. 预置 Sphere 人道主义标准 (25条)
-- 3. 预置 伤亡估算模型参数
-- 4. 预置 道路/地形参数
-- 5. 预置 灾情等级阈值
--
-- 执行方式: psql -U postgres -d frontai -f sql/v19_algorithm_parameters_all.sql
-- ============================================================================

BEGIN;

-- 引入各个子脚本
\i v19_algorithm_parameters_schema.sql
\i v19_algorithm_parameters_sphere.sql
\i v19_algorithm_parameters_casualty.sql
\i v19_algorithm_parameters_routing.sql
\i v19_algorithm_parameters_assessment.sql

-- 最终验证
DO $$
DECLARE
    v_total INTEGER;
    v_by_category RECORD;
BEGIN
    SELECT COUNT(*) INTO v_total FROM config.algorithm_parameters WHERE is_active = TRUE;
    
    RAISE NOTICE '';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'v19 算法参数配置迁移完成';
    RAISE NOTICE '============================================================';
    RAISE NOTICE '总记录数: %', v_total;
    RAISE NOTICE '';
    RAISE NOTICE '按类别统计:';
    
    FOR v_by_category IN 
        SELECT category, COUNT(*) as cnt 
        FROM config.algorithm_parameters 
        WHERE is_active = TRUE 
        GROUP BY category 
        ORDER BY category
    LOOP
        RAISE NOTICE '  - %: % 条', v_by_category.category, v_by_category.cnt;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '============================================================';
END $$;

COMMIT;
