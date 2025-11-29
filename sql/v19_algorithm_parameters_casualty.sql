-- ============================================================================
-- v19: 伤亡估算模型参数
-- 
-- 数据来源: 
--   - USGS PAGER (Prompt Assessment of Global Earthquakes for Response)
--   - 2008汶川地震校准数据
--
-- 参数说明:
--   - base_rate: 基础死亡率（MMI VII基准）
--   - coefficient_b: 对数衰减系数
--   - collapse_rate: MMI VIII时建筑倒塌率
--   - fatality_rate_if_collapsed: 倒塌后死亡率
--   - injury_ratio_severe: 重伤/死亡比
--   - injury_ratio_minor: 轻伤/死亡比
--   - trapped_ratio: 被困率（占倒塌建筑内人口）
--
-- 执行方式: psql -U postgres -d frontai -f sql/v19_algorithm_parameters_casualty.sql
-- ============================================================================

-- 清理旧数据
DELETE FROM config.algorithm_parameters WHERE category = 'casualty';

-- ============================================================================
-- 建筑类型脆弱性参数（基于USGS PAGER）
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('casualty', 'CASUALTY-BUILDING-A', '1.0', 'Adobe Building Vulnerability', '土坯/生土结构脆弱性',
 '{
   "building_type": "A",
   "base_rate": 0.0002,
   "coefficient_b": 0.40,
   "collapse_rate": 0.35,
   "fatality_rate_if_collapsed": 0.15,
   "injury_ratio_severe": 3.0,
   "injury_ratio_minor": 10.0,
   "trapped_ratio": 0.30,
   "description_cn": "土坯、生土、未加固石砌"
 }'::jsonb,
 'USGS PAGER empirical data',
 '最高脆弱性建筑，常见于农村地区'),

('casualty', 'CASUALTY-BUILDING-B', '1.0', 'Brick-Timber Building Vulnerability', '砖木结构脆弱性',
 '{
   "building_type": "B",
   "base_rate": 0.00015,
   "coefficient_b": 0.38,
   "collapse_rate": 0.20,
   "fatality_rate_if_collapsed": 0.20,
   "injury_ratio_severe": 3.0,
   "injury_ratio_minor": 10.0,
   "trapped_ratio": 0.30,
   "description_cn": "未加固砖墙+木楼板"
 }'::jsonb,
 'USGS PAGER empirical data',
 '高脆弱性建筑，常见于老旧城区'),

('casualty', 'CASUALTY-BUILDING-C', '1.0', 'Reinforced Masonry Vulnerability', '砖混结构脆弱性',
 '{
   "building_type": "C",
   "base_rate": 0.0001,
   "coefficient_b": 0.35,
   "collapse_rate": 0.08,
   "fatality_rate_if_collapsed": 0.25,
   "injury_ratio_severe": 3.0,
   "injury_ratio_minor": 10.0,
   "trapped_ratio": 0.30,
   "description_cn": "加固砖砌、约束砌体"
 }'::jsonb,
 'USGS PAGER empirical data, calibrated to 2008 Wenchuan',
 '中等脆弱性，中国城市最常见类型'),

('casualty', 'CASUALTY-BUILDING-D', '1.0', 'RC Frame Vulnerability', '框架结构脆弱性',
 '{
   "building_type": "D",
   "base_rate": 0.00005,
   "coefficient_b": 0.32,
   "collapse_rate": 0.03,
   "fatality_rate_if_collapsed": 0.10,
   "injury_ratio_severe": 3.0,
   "injury_ratio_minor": 10.0,
   "trapped_ratio": 0.30,
   "description_cn": "钢筋混凝土框架、轻型木结构"
 }'::jsonb,
 'USGS PAGER empirical data',
 '低脆弱性，现代住宅/商业建筑'),

('casualty', 'CASUALTY-BUILDING-E', '1.0', 'Steel Frame Vulnerability', '钢结构脆弱性',
 '{
   "building_type": "E",
   "base_rate": 0.00002,
   "coefficient_b": 0.30,
   "collapse_rate": 0.01,
   "fatality_rate_if_collapsed": 0.05,
   "injury_ratio_severe": 3.0,
   "injury_ratio_minor": 10.0,
   "trapped_ratio": 0.30,
   "description_cn": "钢结构、工程设计建筑"
 }'::jsonb,
 'USGS PAGER empirical data',
 '最低脆弱性，高层/工业建筑');

-- ============================================================================
-- 时间因素（室内占用率）
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('casualty', 'CASUALTY-TIME-FACTORS', '1.0', 'Time of Day Indoor Factors', '时段室内因子',
 '{
   "night_0_6": 1.2,
   "morning_6_8": 0.9,
   "work_8_18": 0.7,
   "evening_18_22": 1.0,
   "late_22_24": 1.1,
   "default": 1.0
 }'::jsonb,
 'USGS PAGER methodology',
 '不同时段的室内人口比例调整因子');

-- ============================================================================
-- 洪涝灾害参数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('casualty', 'CASUALTY-FLOOD-DV', '1.0', 'Flood Depth-Velocity Hazard', '洪涝深度-流速危险度',
 '{
   "dv_thresholds": {
     "low": {"max_dv": 0.5, "fatality_rate": 0.0001},
     "medium": {"max_dv": 1.0, "fatality_rate": 0.001},
     "high": {"max_dv": 3.0, "fatality_rate": 0.01},
     "extreme": {"max_dv": 999, "fatality_rate": 0.05}
   },
   "warning_time_factor": 0.1,
   "night_factor": 1.5
 }'::jsonb,
 'Depth-velocity product model',
 '深度(m)×流速(m/s)危险度模型');

-- ============================================================================
-- 次生灾害参数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('casualty', 'CASUALTY-SECONDARY-LANDSLIDE', '1.0', 'Landslide Secondary Hazard', '滑坡次生灾害',
 '{
   "trigger_magnitude": 5.5,
   "base_probability": 0.1,
   "fatality_rate": 0.02,
   "injury_rate": 0.05,
   "slope_factor": {"flat": 0.1, "moderate": 0.5, "steep": 1.0, "very_steep": 1.5}
 }'::jsonb,
 'Earthquake-triggered landslide models',
 '地震触发滑坡的伤亡估算参数'),

('casualty', 'CASUALTY-SECONDARY-FIRE', '1.0', 'Fire Secondary Hazard', '火灾次生灾害',
 '{
   "trigger_magnitude": 6.0,
   "base_probability": 0.05,
   "fatality_rate": 0.01,
   "injury_rate": 0.03,
   "urban_density_factor": {"low": 0.5, "medium": 1.0, "high": 2.0}
 }'::jsonb,
 'Post-earthquake fire models',
 '地震后火灾的伤亡估算参数');

-- ============================================================================
-- 验证数据完整性
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM config.algorithm_parameters WHERE category = 'casualty';
    RAISE NOTICE 'v19: 伤亡模型参数插入完成，共%条记录', v_count;
END $$;
