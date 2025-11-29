-- ============================================================================
-- v19: 灾情评估与事件确认参数
-- 
-- 数据来源: 
--   - 国家突发事件应对法
--   - 应急管理部灾情分级标准
--
-- 执行方式: psql -U postgres -d frontai -f sql/v19_algorithm_parameters_assessment.sql
-- ============================================================================

-- 清理旧数据
DELETE FROM config.algorithm_parameters WHERE category IN ('assessment', 'confirmation');

-- ============================================================================
-- 灾情等级阈值 - 地震
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('assessment', 'DISASTER-LEVEL-EARTHQUAKE-I', '1.0', 'Earthquake Level I Threshold', '地震I级阈值',
 '{
   "level": "I",
   "level_name": "特别重大",
   "magnitude_threshold": 7.0,
   "casualty_threshold": 100,
   "affected_population_threshold": 500000,
   "description": "死亡100人以上或震级7.0级以上"
 }'::jsonb,
 '国家突发事件应对法',
 '特别重大地震灾害判定标准'),

('assessment', 'DISASTER-LEVEL-EARTHQUAKE-II', '1.0', 'Earthquake Level II Threshold', '地震II级阈值',
 '{
   "level": "II",
   "level_name": "重大",
   "magnitude_threshold": 6.0,
   "casualty_threshold": 50,
   "affected_population_threshold": 100000,
   "description": "死亡50-99人或震级6.0-6.9级"
 }'::jsonb,
 '国家突发事件应对法',
 '重大地震灾害判定标准'),

('assessment', 'DISASTER-LEVEL-EARTHQUAKE-III', '1.0', 'Earthquake Level III Threshold', '地震III级阈值',
 '{
   "level": "III",
   "level_name": "较大",
   "magnitude_threshold": 5.0,
   "casualty_threshold": 10,
   "affected_population_threshold": 10000,
   "description": "死亡10-49人或震级5.0-5.9级"
 }'::jsonb,
 '国家突发事件应对法',
 '较大地震灾害判定标准'),

('assessment', 'DISASTER-LEVEL-EARTHQUAKE-IV', '1.0', 'Earthquake Level IV Threshold', '地震IV级阈值',
 '{
   "level": "IV",
   "level_name": "一般",
   "magnitude_threshold": 4.0,
   "casualty_threshold": 0,
   "affected_population_threshold": 1000,
   "description": "死亡10人以下或震级4.0-4.9级"
 }'::jsonb,
 '国家突发事件应对法',
 '一般地震灾害判定标准');

-- ============================================================================
-- 灾情等级阈值 - 洪涝
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('assessment', 'DISASTER-LEVEL-FLOOD-I', '1.0', 'Flood Level I Threshold', '洪涝I级阈值',
 '{
   "level": "I",
   "level_name": "特别重大",
   "affected_population_threshold": 100000,
   "depth_threshold_m": 2.0,
   "casualties_threshold": 30,
   "description": "受灾10万人以上或积水2米以上"
 }'::jsonb,
 '国家防汛抗旱应急预案',
 '特别重大洪涝灾害判定标准'),

('assessment', 'DISASTER-LEVEL-FLOOD-II', '1.0', 'Flood Level II Threshold', '洪涝II级阈值',
 '{
   "level": "II",
   "level_name": "重大",
   "affected_population_threshold": 50000,
   "depth_threshold_m": 1.0,
   "casualties_threshold": 10,
   "description": "受灾5-10万人或积水1-2米"
 }'::jsonb,
 '国家防汛抗旱应急预案',
 '重大洪涝灾害判定标准'),

('assessment', 'DISASTER-LEVEL-FLOOD-III', '1.0', 'Flood Level III Threshold', '洪涝III级阈值',
 '{
   "level": "III",
   "level_name": "较大",
   "affected_population_threshold": 10000,
   "depth_threshold_m": 0.5,
   "casualties_threshold": 3,
   "description": "受灾1-5万人或积水0.5-1米"
 }'::jsonb,
 '国家防汛抗旱应急预案',
 '较大洪涝灾害判定标准'),

('assessment', 'DISASTER-LEVEL-FLOOD-IV', '1.0', 'Flood Level IV Threshold', '洪涝IV级阈值',
 '{
   "level": "IV",
   "level_name": "一般",
   "affected_population_threshold": 1000,
   "depth_threshold_m": 0.3,
   "casualties_threshold": 0,
   "description": "受灾1万人以下或积水0.3-0.5米"
 }'::jsonb,
 '国家防汛抗旱应急预案',
 '一般洪涝灾害判定标准');

-- ============================================================================
-- 灾情等级阈值 - 危化品
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('assessment', 'DISASTER-LEVEL-HAZMAT-I', '1.0', 'Hazmat Level I Threshold', '危化品I级阈值',
 '{
   "level": "I",
   "level_name": "特别重大",
   "affected_population_threshold": 10000,
   "toxicity": "high",
   "casualties_threshold": 30,
   "description": "高毒性泄漏或影响1万人以上"
 }'::jsonb,
 '危险化学品事故应急预案',
 '特别重大危化品事故判定标准'),

('assessment', 'DISASTER-LEVEL-HAZMAT-II', '1.0', 'Hazmat Level II Threshold', '危化品II级阈值',
 '{
   "level": "II",
   "level_name": "重大",
   "affected_population_threshold": 5000,
   "toxicity": "medium",
   "casualties_threshold": 10,
   "description": "中等毒性泄漏或影响5000人以上"
 }'::jsonb,
 '危险化学品事故应急预案',
 '重大危化品事故判定标准'),

('assessment', 'DISASTER-LEVEL-HAZMAT-III', '1.0', 'Hazmat Level III Threshold', '危化品III级阈值',
 '{
   "level": "III",
   "level_name": "较大",
   "affected_population_threshold": 1000,
   "toxicity": "low",
   "casualties_threshold": 3,
   "description": "低毒性泄漏或影响1000人以上"
 }'::jsonb,
 '危险化学品事故应急预案',
 '较大危化品事故判定标准'),

('assessment', 'DISASTER-LEVEL-HAZMAT-IV', '1.0', 'Hazmat Level IV Threshold', '危化品IV级阈值',
 '{
   "level": "IV",
   "level_name": "一般",
   "affected_population_threshold": 100,
   "toxicity": "low",
   "casualties_threshold": 0,
   "description": "影响100人以上"
 }'::jsonb,
 '危险化学品事故应急预案',
 '一般危化品事故判定标准');

-- ============================================================================
-- 烈度衰减模型参数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('assessment', 'INTENSITY-ATTENUATION', '1.0', 'Intensity Attenuation Model', '烈度衰减模型',
 '{
   "model": "simplified_usgs",
   "k": 1.5,
   "c": 0.003,
   "site_amplification": {
     "rock": 0.0,
     "stiff_soil": 0.3,
     "soft_soil": 0.6,
     "fill": 0.9
   },
   "formula": "MMI = 1.5*M - 0.5*log10(D_km) - k*log10(R_km) - c*R_km + site_factor"
 }'::jsonb,
 'Simplified USGS ShakeMap model',
 '地震烈度衰减简化模型');

-- ============================================================================
-- 事件确认评分参数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('confirmation', 'CONFIRMATION-WEIGHTS', '1.0', 'Event Confirmation Weights', '事件确认权重',
 '{
   "weight_multi_source": 0.35,
   "weight_ai_confidence": 0.25,
   "weight_rule_match": 0.30,
   "weight_source_trust": 0.10,
   "total": 1.0
 }'::jsonb,
 '事件确认算法设计',
 '多维度确认评分权重'),

('confirmation', 'CONFIRMATION-THRESHOLDS', '1.0', 'Event Confirmation Thresholds', '事件确认阈值',
 '{
   "auto_confirm": 0.85,
   "pre_confirm": 0.60,
   "pending": 0.0,
   "description": {
     "auto_confirm": ">=0.85自动确认",
     "pre_confirm": "0.60-0.85预确认等待人工复核",
     "pending": "<0.60待人工确认"
   }
 }'::jsonb,
 '事件确认算法设计',
 '自动确认/预确认/待确认阈值'),

('confirmation', 'CONFIRMATION-SOURCE-TRUST', '1.0', 'Source Trust Scores', '信息源信任度',
 '{
   "official_systems": ["110", "119", "120"],
   "trust_scores": {
     "110": 0.95,
     "119": 0.95,
     "120": 0.95,
     "seismic_station": 0.90,
     "weather_station": 0.85,
     "social_media": 0.40,
     "citizen_report": 0.50,
     "iot_sensor": 0.75,
     "ai_detection": 0.70,
     "unknown": 0.30
   }
 }'::jsonb,
 '事件确认算法设计',
 '各类信息源的基础信任度评分');

-- ============================================================================
-- 验证数据完整性
-- ============================================================================
DO $$
DECLARE
    v_assessment_count INTEGER;
    v_confirmation_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_assessment_count FROM config.algorithm_parameters WHERE category = 'assessment';
    SELECT COUNT(*) INTO v_confirmation_count FROM config.algorithm_parameters WHERE category = 'confirmation';
    RAISE NOTICE 'v19: 灾情评估参数插入完成，共%条记录', v_assessment_count;
    RAISE NOTICE 'v19: 事件确认参数插入完成，共%条记录', v_confirmation_count;
END $$;
