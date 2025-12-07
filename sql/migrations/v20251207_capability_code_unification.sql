-- ============================================================================
-- 能力代码统一迁移脚本
-- 
-- 问题：capability_equipment_v2 表中的能力代码与 capability_codes_v2 不一致
-- 导致装备调度查询时无法匹配，返回空结果
--
-- 解决方案：统一使用 capability_codes_v2 中的标准代码
-- ============================================================================

BEGIN;

-- 备份原表数据（可选）
-- CREATE TABLE operational_v2.capability_equipment_v2_backup AS 
-- SELECT * FROM operational_v2.capability_equipment_v2;

-- ============================================================================
-- 1. 更新能力代码映射
-- ============================================================================

-- 结构救援：STRUCTURAL_RESCUE -> RESCUE_STRUCTURAL
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'RESCUE_STRUCTURAL',
    capability_name = '建筑物救援'
WHERE capability_code = 'STRUCTURAL_RESCUE';

-- 生命探测：LIFE_DETECTION -> SEARCH_LIFE_DETECT
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'SEARCH_LIFE_DETECT',
    capability_name = '生命探测'
WHERE capability_code = 'LIFE_DETECTION';

-- 水域救援：WATER_RESCUE -> RESCUE_WATER_SWIFT
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'RESCUE_WATER_SWIFT',
    capability_name = '急流水域救援'
WHERE capability_code = 'WATER_RESCUE';

-- 危化品处置：HAZMAT_HANDLING -> HAZMAT_DETECT
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'HAZMAT_DETECT',
    capability_name = '危化品检测'
WHERE capability_code = 'HAZMAT_HANDLING';

-- 医疗急救：MEDICAL_EMERGENCY -> MEDICAL_FIRST_AID
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'MEDICAL_FIRST_AID',
    capability_name = '现场急救'
WHERE capability_code = 'MEDICAL_EMERGENCY';

-- 照明保障：LIGHTING_SUPPORT -> LOG_LIGHTING
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'LOG_LIGHTING',
    capability_name = '照明保障'
WHERE capability_code = 'LIGHTING_SUPPORT';

-- 道路清障：ROAD_CLEARANCE -> ENG_DEMOLITION
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'ENG_DEMOLITION',
    capability_name = '破拆清障'
WHERE capability_code = 'ROAD_CLEARANCE';

-- 无人机侦察：UAV_RECONNAISSANCE -> UAV_THERMAL
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'UAV_THERMAL',
    capability_name = '无人机热成像'
WHERE capability_code = 'UAV_RECONNAISSANCE';

-- 通信保障：COMMUNICATION_SUPPORT -> LOG_COMM
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'LOG_COMM',
    capability_name = '通信保障'
WHERE capability_code = 'COMMUNICATION_SUPPORT';

-- 疏散协调：保留（已存在于 capability_codes_v2）
-- EVACUATION_COORDINATION 已存在

-- 火灾扑救：FIRE_SUPPRESSION -> FIRE_SUPPRESS
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'FIRE_SUPPRESS',
    capability_name = '火灾扑救'
WHERE capability_code = 'FIRE_SUPPRESSION';

-- 紧急救治：EMERGENCY_TREATMENT -> MEDICAL_TRAUMA
UPDATE operational_v2.capability_equipment_v2
SET capability_code = 'MEDICAL_TRAUMA',
    capability_name = '创伤处理'
WHERE capability_code = 'EMERGENCY_TREATMENT';

-- ============================================================================
-- 2. 验证更新结果
-- ============================================================================

-- 检查是否还有不在 capability_codes_v2 中的代码
DO $$
DECLARE
    invalid_count INTEGER;
BEGIN
    SELECT COUNT(DISTINCT ce.capability_code)
    INTO invalid_count
    FROM operational_v2.capability_equipment_v2 ce
    LEFT JOIN operational_v2.capability_codes_v2 cc ON ce.capability_code = cc.code
    WHERE cc.code IS NULL;
    
    IF invalid_count > 0 THEN
        RAISE NOTICE '警告: 仍有 % 个能力代码未在 capability_codes_v2 中定义', invalid_count;
    ELSE
        RAISE NOTICE '验证通过: 所有能力代码已统一';
    END IF;
END $$;

-- ============================================================================
-- 3. 显示更新后的映射关系
-- ============================================================================

SELECT DISTINCT ce.capability_code, ce.capability_name, 
       CASE WHEN cc.code IS NOT NULL THEN '已匹配' ELSE '未匹配' END as status
FROM operational_v2.capability_equipment_v2 ce
LEFT JOIN operational_v2.capability_codes_v2 cc ON ce.capability_code = cc.code
ORDER BY status DESC, ce.capability_code;

COMMIT;
