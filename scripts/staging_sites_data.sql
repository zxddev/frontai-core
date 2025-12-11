-- ============================================================
-- 救援驻扎点候选数据 - 茂县区域
-- 自动生成，数据来源: 高德POI API
-- ============================================================

BEGIN;

-- 清除旧的POI数据（保留手动添加的SS-开头数据）
DELETE FROM operational_v2.rescue_staging_sites_v2
WHERE site_code LIKE 'POI-%';

INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f1e89ae8-0a4e-450a-a0f0-3dbd424dd436', 'POI-B0KKB72K', '安全文化广场', 'other',
    ST_SetSRID(ST_MakePoint(103.850582, 31.683573), 4326),
    '羌兴大道263号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c3581481-deb7-44e4-8af3-ff0039e7657a', 'POI-B0FFHMAU', '西亚港城音乐汇所', 'other',
    ST_SetSRID(ST_MakePoint(103.850195, 31.682623), 4326),
    '凤仪镇德惠超市', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b222f5cf-a753-4717-87a0-9f1a9ca462b9', 'POI-B0345007', '中国电信(城中营业厅)', 'other',
    ST_SetSRID(ST_MakePoint(103.849608, 31.683956), 4326),
    '凤仪大道南段与羌兴大道交叉口北150米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5bded697-96f6-4758-b0c4-534feeabf51d', 'POI-B0FFG7HD', '停车场(茂县人民医院西)', 'other',
    ST_SetSRID(ST_MakePoint(103.851183, 31.684766), 4326),
    '东大街与羌兴大道交叉口东60米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3638e360-ff49-4566-be9e-6bf0bcbe5f1b', 'POI-B0I2GHEX', '喜相逢量贩式KTV(茂县店)', 'other',
    ST_SetSRID(ST_MakePoint(103.848502, 31.68331), 4326),
    '中心大道与步行街交叉口东北20米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0c89f71a-f04e-451d-9ddd-6b87daa94d1e', 'POI-B034500W', '茂县同心幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.850499, 31.681259), 4326),
    '凤仪镇羌新街', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'bc946061-0e0b-45e5-aa1e-c7fea37239aa', 'POI-B0JKVOOO', '凤仪镇粮食购销公司', 'other',
    ST_SetSRID(ST_MakePoint(103.849323, 31.68161), 4326),
    '内南街与中心大道交叉口南160米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c686d49e-d49c-47e3-87ba-63ad47d33de0', 'POI-B0L2B5K2', '茂州时代广场地面停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.848311, 31.682385), 4326),
    '茂州时代广场', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7bd37e9e-2b74-49fc-ade7-2536ab0ad3ee', 'POI-B0JUMS92', '华黔设计有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.853264, 31.684675), 4326),
    '凤仪镇东大街茂县综合行政执法局对面', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6f240c64-b7f2-4954-ad26-13f2ced57cd2', 'POI-B0FFGD3U', '停车场(步行街)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.847942, 31.684117), 4326),
    '汾岷路与中心大道交叉口东北100米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4f4ea0b3-6d31-4fe5-baaa-9aaac7c57494', 'POI-B0FFKH8D', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.851314, 31.686184), 4326),
    '羌兴大道与东大街交叉口东北160米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0647afd3-fa13-4edd-a462-3fe5516b7f2c', 'POI-B0FFI1B0', '停车场(羌兴大道)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.849302, 31.680421), 4326),
    '外南街与胜利街交叉口东北80米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7dd038f7-d8d4-4337-9f6d-c67671adb029', 'POI-B0H33LY6', '梦之约网咖', 'other',
    ST_SetSRID(ST_MakePoint(103.847371, 31.681766), 4326),
    '滨河路与中心大道交叉口南160米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3443a625-3f7c-408c-be5f-40115a1c880f', 'POI-B0J6SU2Q', '四川茂沃农业科技有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.849428, 31.686666), 4326),
    '凤仪镇禹乡村三组97号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5716a133-0256-4594-9465-507563a30961', 'POI-B0H1PHQN', '阿坝州艺家装饰有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.848348, 31.686302), 4326),
    '内南街与坡头街交叉口西北200米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '97cbc569-f30b-40a3-8a8f-172f553cd23f', 'POI-B0345004', '欢欢幼儿园(外南街)', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.847638, 31.680842), 4326),
    '凤仪镇羌兴大道欢欢幼儿园', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '968d94ff-8d90-4502-9ed2-fab07fe3a3a0', 'POI-B0L0SGIE', '凤凰阁大酒店南侧停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.849308, 31.679405), 4326),
    '外南街与胜利街交叉口东南100米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8387b015-b952-49e3-8c4e-09f1d6ab9fc0', 'POI-B0FFGK2Y', '凤仪小学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.853898, 31.686566), 4326),
    '凤仪镇东大街', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '00f323b6-f9c2-43b9-9a25-7257a101e414', 'POI-B0LR9BOF', '茂县老年大学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.855481, 31.684925), 4326),
    '东大街与槐树巷交叉口东北100米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '52568e52-30aa-48cb-975a-ada6e9ec58fd', 'POI-B0FFGD3U', '停车场(福兴苑东北)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.84526, 31.682959), 4326),
    '西羌家园酒店南(西羌大道南段东)', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '871ffa6c-2870-454c-b563-0adb3b598b9a', 'POI-B0FFIAR9', '童乐幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.847094, 31.679435), 4326),
    '外南街与胜利街交叉口西南160米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b1929a64-0dd0-4891-a594-79458a9d4a48', 'POI-B0H6FK09', '众旺商贸行', 'other',
    ST_SetSRID(ST_MakePoint(103.849667, 31.688266), 4326),
    '古城巷与羌兴大道交叉口西180米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4e55ba6f-77e5-4431-8b71-ffc56aff6fb5', 'POI-B0FFGBJR', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.844999, 31.68435), 4326),
    '213国道与恒山路交叉口东140米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9e3e3db0-b4b6-49ec-acef-4627e5a4bd95', 'POI-B0345007', '茂县七一民族中学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.855859, 31.686389), 4326),
    '东大街', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'da9c4903-1530-4b6a-9c9e-fab87e2e4e96', 'POI-B0FFJ2OI', '茂县英才实验幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.848041, 31.678637), 4326),
    '凤仪镇茂县无影塔旁', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6b1e1108-f95c-4e2b-bcff-973fcdd4ea3e', 'POI-B0JGBU5R', '茂县小庙山石材雕刻场', 'other',
    ST_SetSRID(ST_MakePoint(103.856986, 31.682596), 4326),
    '围城路小庙山脚下', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '91018a19-7a8f-45f1-877e-7c95d57c226c', 'POI-B0KDYSY5', '茂县铁塔公司', 'other',
    ST_SetSRID(ST_MakePoint(103.846089, 31.679827), 4326),
    '并州路130号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a1ecc873-7b30-43dc-8ce5-1fcf7bd32804', 'POI-B0JK95CL', '凤仪镇兴茂小学校', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.857267, 31.684344), 4326),
    '凤仪镇东大街45号', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'bcfff6a9-0361-4d6d-8b49-3729e2187615', 'POI-B0FFI0TO', '停车场(茂县测绘地理信息局北)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.844629, 31.685396), 4326),
    '晋茂大道北段与恒山路交叉口南140米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '97d23938-2425-442a-aaef-ecb5234328e9', 'POI-B0KKBLZ5', '四川梓贝建筑劳务有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.849751, 31.689258), 4326),
    '古城巷与羌兴大道交叉口西北240米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7f5bbfd6-9cd3-4bca-8ba4-5511c1f5dcc0', 'POI-B0FFJRW5', '茂县毓清五金加工有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.857926, 31.68331), 4326),
    '凤仪林场围城路', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '57e05712-fdd7-4016-b2be-ded0c453e747', 'POI-B0FFKWH7', '启蒙实验幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.852112, 31.689361), 4326),
    '羌兴大道与古城巷交叉口北180米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '64afd0ce-1b42-46d8-9ba2-ec921d6c0c2f', 'POI-B0FFG8PI', '茂县城北停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.853271, 31.689258), 4326),
    '老茂北路与太行路交叉口西南220米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd46b6375-389a-4858-9910-ae18c60fec66', 'POI-B0FFKXTD', '半岛KTV', 'other',
    ST_SetSRID(ST_MakePoint(103.847956, 31.689305), 4326),
    '城北小区246号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd002ffea-7255-411f-bb0b-5b1d0fdc7547', 'POI-B0K3S7PQ', '温馨水族', 'other',
    ST_SetSRID(ST_MakePoint(103.847462, 31.677426), 4326),
    '凤仪镇南桥村三晋路359号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'be8343f3-bb4a-4a05-83ba-1673e967d04c', 'POI-B0K1PSI9', '茂投集团', 'other',
    ST_SetSRID(ST_MakePoint(103.84431, 31.686919), 4326),
    '恒山路与川汶公路交叉口西北40米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b30b1c44-c178-4513-80d8-b032c3e16509', 'POI-B03450MK', '停车场(福兴苑南)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.843845, 31.680373), 4326),
    '胜利街与外南街交叉口西440米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'dc93beee-7d8e-4b63-b8d9-33e10bea84da', 'POI-B0FFFV9B', '茂县闽乐三友桥隧物资供应站', 'other',
    ST_SetSRID(ST_MakePoint(103.84328, 31.685281), 4326),
    '西羌大道225号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0fc022ff-31ce-4ec1-b376-96a43fe739d0', 'POI-B0G1Z56G', '茂县筑茂装饰工程有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.845087, 31.678317), 4326),
    '凤仪镇滨河路茂州花园17-1-负1-48', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '983b9a0a-2456-4b5a-b465-340ec1787258', 'POI-B0FFGCVE', '新能源停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.844946, 31.688236), 4326),
    '川汶公路与恒山路交叉口北180米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8fd83478-52db-4e9e-ae22-7ff9f2c761ef', 'POI-B0LKPBYT', '启蒙幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.854643, 31.690038), 4326),
    '老茂北路与太行路交叉口西60米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8fbfe2e9-516f-4ad5-8a58-4c1c23a9a2a8', 'POI-B0FFG0DO', '茂县体育场', 'sports_field',
    ST_SetSRID(ST_MakePoint(103.856426, 31.689069), 4326),
    '凤仪镇羌兴大道体育场', 8000.0, 1500.0, 3.0,
    'unknown', true, true,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '88645c8c-2441-4ec3-a488-e353670ef9a6', 'POI-B0KU7U15', '茂县星未来幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.846725, 31.676652), 4326),
    '自治州茂县镇南桥村永祥街一巷70号', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '257bcbb4-4684-4405-af80-a781513836d7', 'POI-B0FFGD3U', '停车场(九顶山国际大酒店东北)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.842867, 31.678706), 4326),
    '西羌大道与五台路交叉口东北320米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '37b557bb-abb2-4c27-9384-b211e14f12f2', 'POI-B0JDBDG6', '茂县华利农业科技有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.855986, 31.690458), 4326),
    '太行路与老茂北路交叉口东60米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '005b6c9c-65a9-46c2-acf2-5483b7f487bd', 'POI-B0FFGD3V', '停车场(茂县公路运输管理所西北)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.84104, 31.684988), 4326),
    '恒山路与213国道交叉口西220米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f58ebb79-4789-43b8-8d2f-cbf89d72a527', 'POI-B0345007', '凤仪镇学校', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.847164, 31.675388), 4326),
    '凤仪镇南桥村9段', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1bfd4dae-3689-40a4-a7a3-80954866528e', 'POI-B0L3X12T', '河西B区停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.841304, 31.680406), 4326),
    '凤仪镇西羌大道河西小区B区', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a43e990a-7d37-4125-8277-1168eb64a9e4', 'POI-B0FFIDR8', '港湾装饰有限公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.843952, 31.676805), 4326),
    '滨河路17-19号', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e12225d9-5f19-435b-96eb-0154d6614e94', 'POI-B0FFG6S0', '羌龙酒店停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.846063, 31.675538), 4326),
    '凤仪镇三晋路289号茂县羌龙商务酒店', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '703bfec2-a89e-4ec4-8b7f-f44470866490', 'POI-B0KBOA5R', '阿坝州茂县洪荣建筑劳务有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.855457, 31.691308), 4326),
    '凤仪镇太行路1幢1层1-7', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8a4ae8fd-2cbf-48ba-866d-98455ccdfd6c', 'POI-B03450MK', '茂县河西小学校', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.840585, 31.68143), 4326),
    '凤仪镇西羌大道137号', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b879fadd-c34f-41f1-83c9-b649e6cdccf2', 'POI-B03450MK', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.849649, 31.692838), 4326),
    '半岛花园东北侧280米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5509b172-d315-4dcf-acb6-93b22a669c7a', 'POI-B03450MK', '茂县蓝天幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.839487, 31.681686), 4326),
    '凤仪镇坪头村', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5d757cb0-0243-4ece-9c7f-5dccedfbace1', 'POI-B0J2P7D3', '茂县北福幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.857869, 31.691297), 4326),
    '凤仪镇静州村164号', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5e84c423-10dc-4c87-a44c-5155f68e934e', 'POI-B03450MJ', '停车场(九顶山国际大酒店南)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.842549, 31.675982), 4326),
    '滨河路与永祥街交叉口北60米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b3d122da-aef8-454a-91c7-b71de66114d4', 'POI-B0LDLU4F', '阿坝金盾爆破有限公司茂县分公司', 'other',
    ST_SetSRID(ST_MakePoint(103.853986, 31.693323), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2d5bf571-1ca9-47a1-96e4-c1c7cffd9e7b', 'POI-B0KB1Z3D', '音浪KTV', 'other',
    ST_SetSRID(ST_MakePoint(103.843051, 31.674882), 4326),
    '凤仪镇滨河大道畅馨苑商1A三层1号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e44c2b90-4521-4420-84f5-eddd9dfb2cd1', 'POI-B0JD5DBY', '茂县锦豪再生资源回收有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.852819, 31.694256), 4326),
    '老茂北路181号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'dd8ebeee-0e75-458f-9625-f7697fb8bb61', 'POI-B0LU2ST8', '阿坝州茂县飞航无人机科技有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.838191, 31.680453), 4326),
    '西羌大道93号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1b97109d-4223-4342-8a8b-7d56fb7b71c6', 'POI-B0L1AZIK', '国家电网阿坝成都东1000kv特高压输变电线路项目部', 'other',
    ST_SetSRID(ST_MakePoint(103.846113, 31.672731), 4326),
    '凤仪大道南段168号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd25b04ce-c262-4ef6-9af4-94055a7cc47b', 'POI-B0LUD9BR', '响袋自助台球', 'other',
    ST_SetSRID(ST_MakePoint(103.843898, 31.673645), 4326),
    '凤仪大道南段与永祥街交叉口西140米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2c5a1578-b3a0-43d7-9492-62675663b684', 'POI-B0FFGD3V', '停车场(茂县凤仪镇财政所东)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.84134, 31.674646), 4326),
    '滨河路与并州路交叉口东北120米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '488db194-5e6e-4b1b-a13f-1fbe66bd6678', 'POI-B0FFGXLR', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.849436, 31.69539), 4326),
    '川汶公路东南40米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fdeb3ee3-49fb-422f-8a02-43d22ab1b133', 'POI-B0FFIZUJ', '羌祖庙', 'other',
    ST_SetSRID(ST_MakePoint(103.837153, 31.687814), 4326),
    'G213(西羌大道北段)坪头羌寨内', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '03804f97-a41b-4028-9d6a-bd28a7c5e7ef', 'POI-B0FFIZRL', '傩文化广场', 'other',
    ST_SetSRID(ST_MakePoint(103.836716, 31.686993), 4326),
    'G213(西羌大道北段)坪头羌寨内', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8d051182-1ec3-4f2e-a813-9f904172a3c5', 'POI-B0I6CHJT', '阿坝州净土阿坝农业投资发展有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.84431, 31.672012), 4326),
    '凤仪镇三晋路152号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7fe6b64a-2f29-4f95-bd70-8e1887c1377e', 'POI-B0JDP7UH', '娱乐休闲', 'sports_field',
    ST_SetSRID(ST_MakePoint(103.843366, 31.672425), 4326),
    '凤仪大道南段与永祥街交叉口西南240米', 8000.0, 1500.0, 3.0,
    'unknown', true, true,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0b6d4a54-1599-4f1d-ae2f-03f28b37fe4b', 'POI-B0KRDZLC', '茂县椒小果花椒种植合作社', 'other',
    ST_SetSRID(ST_MakePoint(103.855108, 31.695454), 4326),
    '老茂北路99号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2d6a8af0-0fab-4580-8bf1-62c83739afa9', 'POI-B0FFM1WG', '中国邮政集团茂县分公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.845664, 31.671409), 4326),
    '凤仪大道南段与永祥街交叉口南280米', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4214f6cf-a6c8-473f-91c5-dd5e72328402', 'POI-B03450MJ', '中国移动通信集团茂县分公司(并州路)', 'other',
    ST_SetSRID(ST_MakePoint(103.841223, 31.673291), 4326),
    '畅馨苑B区西门南130米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3617ffe5-a150-4d79-904c-3e072ce88019', 'POI-B0K1TSUO', '中国羌族博物馆停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.837783, 31.676594), 4326),
    '西羌大道12号', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8e6eb8b6-a134-4a51-92d4-4ee75d3cb62d', 'POI-B0K0J741', '川汶电力四川路桥项目部', 'other',
    ST_SetSRID(ST_MakePoint(103.858575, 31.694636), 4326),
    '老茂北路113号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7d5c1116-7026-4bd1-a15b-75861b3a2bb2', 'POI-B0JRX56V', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.835477, 31.682482), 4326),
    '羌寨皓晨民宿西侧100米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '346fdde4-0f3d-4df1-ba32-b2060484b539', 'POI-B0L1YBDP', '九顶农业科技有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.856193, 31.69577), 4326),
    '常来民宿南侧', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'db372df1-fa03-4644-9076-eed7b0318893', 'POI-B0KG0LAT', '葛洲坝新能源有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.838952, 31.674628), 4326),
    '永康路与西羌大道交叉口西40米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9e13a9c0-9047-47c9-a8cd-e87b452e42f2', 'POI-B03450MQ', '白石羌寨', 'plaza',
    ST_SetSRID(ST_MakePoint(103.848393, 31.696494), 4326),
    '凤仪镇川汶公路(山菜王旁)', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b8b51e81-d145-48d9-9394-9007566d6cd8', 'POI-B0FFF6VQ', '中国古羌城', 'plaza',
    ST_SetSRID(ST_MakePoint(103.836644, 31.676783), 4326),
    '凤仪镇茂县八一中学北侧', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '48af1692-c51a-4239-a78f-4d5f5334d09a', 'POI-B0FFIDFG', '阿坝州财达财务代理记账有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.842182, 31.671713), 4326),
    '凤仪镇城南小区一街', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9f250e7c-160f-40d0-92c2-605b0fb49834', 'POI-B0FFG6RZ', '茂县六月红花椒专业合作社', 'other',
    ST_SetSRID(ST_MakePoint(103.85964, 31.695102), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1a90cfd6-ffd2-46a9-b492-1aaa30efeb12', 'POI-B0LR9RQL', '茂县湘印天下广告有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.838333, 31.673721), 4326),
    '晋茂大道273号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c40f1a4c-f43a-42c1-a0f5-cd8b6ce173b7', 'POI-B0FFJ5CV', '阿坝州宇兴冷冻食品销售有限公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.856898, 31.696715), 4326),
    '凤仪镇太行路', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c3e0e9f1-83a1-4670-ba0d-d78bcc992d67', 'POI-B0KU1CS3', '碉楼', 'plaza',
    ST_SetSRID(ST_MakePoint(103.834318, 31.680114), 4326),
    '望碉楼东侧180米', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6953731b-bfb1-444b-96c8-46ec00eba4b5', 'POI-B0LUURS4', '中国古羌城东停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.836429, 31.675496), 4326),
    '中国古羌城内(南侧)', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7bdbffc2-219a-4880-8c95-4eb69f5e5f8b', 'POI-B0FFGCNN', '阿坝州电力公司', 'other',
    ST_SetSRID(ST_MakePoint(103.836939, 31.674402), 4326),
    '晋茂大道与永康路交叉口南140米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'da32ca74-46c5-4215-a922-17a540211fd0', 'POI-B0H6VUHE', '中国古羌城游客中心地上停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.835395, 31.676329), 4326),
    '中国古羌城内(西侧)', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '09ad7d9c-18e2-4665-bdde-f7d77b992c9a', 'POI-B0LUDA8P', '中国古羌城景区-爱情文化广场', 'plaza',
    ST_SetSRID(ST_MakePoint(103.834246, 31.678486), 4326),
    '中国古羌城(西北角)', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c208fcf6-d01c-4e7b-87cb-80ef15bdac98', 'POI-B0FFI0HW', '茂县城南幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.841214, 31.670697), 4326),
    '滨河路与并州路交叉口南320米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f086a09b-d14e-4a3d-80f3-f5e6afe1b335', 'POI-B0J0DBO8', '纯粮酒厂', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.84611, 31.66876), 4326),
    '凤仪镇尔玛果业旁边', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f2c443f5-e49e-48fd-a07e-bfa995391efc', 'POI-B0LAT169', '茂县凤仪镇新苗幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.860972, 31.695888), 4326),
    '茂县六月红花椒专业合作社东北侧150米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9020d53d-7e7c-431c-84f6-d06e83571e01', 'POI-B0H697L1', '四川领地酒庄酒业销售有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.839575, 31.671364), 4326),
    '滨河路东侧(滨江小区)12幢H101和201号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3ce0c6d2-a518-46b6-ab15-8bd9112de153', 'POI-B0H33CY3', '茂县中医院停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.842305, 31.669698), 4326),
    '凤仪大道南段与观凤路交叉口东北260米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fde536da-4160-4032-8ac1-1cbc1ca0b1c6', 'POI-B0FFGD3U', '停车场(茂县烟草专卖局南)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.83744, 31.672638), 4326),
    '西羌大道与永康路交叉口西南280米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '56610914-eb59-4f95-8cd6-c27a993095d7', 'POI-B0FFJIYC', '阿坝职业学院', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.844134, 31.668674), 4326),
    '凤仪镇凤仪大道南段', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b463fb21-c731-406f-89a7-96b02c869d68', 'POI-B0LDBZDL', '茂县24小时自助喜越棋牌', 'other',
    ST_SetSRID(ST_MakePoint(103.840091, 31.670143), 4326),
    '凤仪镇滨江路东侧滨滨江小区9幢E区310号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4486d292-9831-4d99-84a9-75e4b4a0ac3e', 'POI-B0JAXS62', '集达废品回收再生资源有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.859324, 31.697754), 4326),
    '静州村组522号s302', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a14e70d9-a62f-497f-9f09-da1a0d61caff', 'POI-B0LUSSZB', '中国古羌城景区-羌文化广场', 'plaza',
    ST_SetSRID(ST_MakePoint(103.835039, 31.674356), 4326),
    '中国古羌城(西南角)', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd07a78cb-16b1-4561-bcc2-79fd251c5ec9', 'POI-B0FFMC8J', '太清宫', 'other',
    ST_SetSRID(ST_MakePoint(103.847594, 31.667385), 4326),
    '拉法基水泥东侧190米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f7897afe-e088-4b6c-801a-69c4f33a806f', 'POI-B0H0KALW', '茂县绍春再生资源回收有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.858377, 31.698365), 4326),
    '凤仪镇凤北路58号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b8e838d1-a3f8-461b-b7d0-da65e7adb19b', 'POI-B0KKO72M', '茂县石榴沟旅游景区', 'plaza',
    ST_SetSRID(ST_MakePoint(103.844537, 31.734564), 4326),
    '川汶公路东侧', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '44ad3ade-1dc7-451c-be19-9cc5532e731b', 'POI-B0IR4D0L', '新思维全屋定制厂', 'other',
    ST_SetSRID(ST_MakePoint(103.854128, 31.702434), 4326),
    '老茂北路181号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd1d1d2e8-ba26-4ea4-a56f-4360708dcc11', 'POI-B0LDVC6B', '茂县弘毅气体销售有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.853664, 31.701464), 4326),
    '宏泰汽车修理厂(道路救援)南侧190米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ee0fe993-55aa-45ea-8d90-17172e96598a', 'POI-B0L0HPQ0', '榴桐寨明洞', 'plaza',
    ST_SetSRID(ST_MakePoint(103.820115, 31.761974), 4326),
    '兰明宫广河清真饭馆(兰州牛肉面)东南侧390米', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0e0d632f-eb5c-4b76-8f5a-69243ac831be', 'POI-B0LG7U4J', '花屿线上工作室', 'other',
    ST_SetSRID(ST_MakePoint(103.831688, 31.678819), 4326),
    '云茂里民宿旅店南侧50米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3f503264-3056-47df-8155-94ca10e94068', 'POI-B0KDDHBU', '茂县源丰制砖有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.863435, 31.698816), 4326),
    '静州村附近', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3facf795-ac28-4d73-8a1b-5be7b4f73164', 'POI-B0JR2HHK', '茂县古羌城大酒店管理有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.831323, 31.676272), 4326),
    '凤仪镇禹羌大道南段(中国古羌城内)', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'bfc9ef36-eaeb-415f-a60b-cc422d65ce33', 'POI-B0GRJ5NU', '茂县星宇彩钢复合板厂', 'other',
    ST_SetSRID(ST_MakePoint(103.867016, 31.698655), 4326),
    '茂北公路', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '26a492a3-18e6-4d6d-87fe-d8471ae8974c', 'POI-B0H0CCVM', '茂县古羌城酒店停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.830494, 31.674869), 4326),
    '茂县古羌城酒店停车场', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd9a247a3-a36d-4f09-954f-0238dea70003', 'POI-B0LBO65D', '中国古羌城景区-萨朗广场', 'plaza',
    ST_SetSRID(ST_MakePoint(103.831873, 31.67506), 4326),
    '中国古羌城', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7bdc866c-8984-4e52-86d3-f942c6464e66', 'POI-B0LRLNME', '古羌城门', 'plaza',
    ST_SetSRID(ST_MakePoint(103.833538, 31.674525), 4326),
    '晋茂大道与永康路交叉口西380米', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3b77b8e4-42d7-44c3-ae86-bb428b72c8ed', 'POI-B0JDDHTJ', '茂县绿生源家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.825699, 31.67128), 4326),
    '茂县水西村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '08e59dc4-58e4-4180-aa01-213eba27bdb9', 'POI-B0JKOGHI', '阿坝州鼎峰消防技术有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.833347, 31.671872), 4326),
    '中国石油茂县加油站西北侧230米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c6df748c-3433-4a60-8881-965c57d2b7d4', 'POI-B034500W', '茂县八一中学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.835753, 31.672296), 4326),
    '迎宾大道435号', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7bc47a1f-ab4c-43b3-b4b8-9bf486ba3a34', 'POI-B0JRXZ55', '雨露滋润优质脆李茂县包装中心', 'other',
    ST_SetSRID(ST_MakePoint(103.829556, 31.669054), 4326),
    '凤仪镇坪头村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '20e9baeb-f257-424e-a8f7-9da1f67eae01', 'POI-B0FFFDD7', '茂县水西红葡萄酒加工厂', 'other',
    ST_SetSRID(ST_MakePoint(103.83481, 31.669865), 4326),
    '凤仪镇晋茂大道195号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'eb17a132-f180-4367-8979-7b391fbc7316', 'POI-B0FFI0XN', '东祥监理阿坝州分公司', 'other',
    ST_SetSRID(ST_MakePoint(103.83096, 31.668849), 4326),
    '凤仪镇坪头村水西三组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'db05d99f-1aa5-435f-8487-8fd107700015', 'POI-B0FFIR4R', '星期8KTV(滨河路店)', 'other',
    ST_SetSRID(ST_MakePoint(103.838579, 31.670556), 4326),
    '晋茂新园1幢', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd7b9cc0f-2a9c-40a3-ab5e-5e730d887d13', 'POI-B0IG3A0M', '茂县南庄雅李苑家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.843197, 31.659343), 4326),
    '凤仪镇南庄村1组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fe4d7e84-996a-42f9-8c6a-b0b15a98af1c', 'POI-B0HBBN2G', '茂县中学高中部', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.844295, 31.665282), 4326),
    '民族医院东南', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1ede3ddc-1a43-4967-a02f-df60b19992c6', 'POI-B0FFGDHM', '茂县玉明农牧产业开发有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.841494, 31.663942), 4326),
    '凤仪镇青沙沟', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ba2e956d-07b6-4e90-a205-726f4be151a0', 'POI-B0FFG7HH', '停车场(凤仪大道南段)', 'other',
    ST_SetSRID(ST_MakePoint(103.841665, 31.668408), 4326),
    '凤仪大道南段与观凤路交叉口东北100米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2ed93652-aedc-4dd4-8ae3-39af56ff3aa5', 'POI-B0FFJM9H', '阿坝直通商务用车服务有限公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.840597, 31.666982), 4326),
    '109乡道与观凤路交叉口西南80米', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2e39eab6-afbb-4ca4-941e-47eb9b44f251', 'POI-B0FFFVSL', '四川羌寨绣庄', 'other',
    ST_SetSRID(ST_MakePoint(103.838914, 31.665791), 4326),
    '109乡道与观凤路交叉口西南280米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b88d47e0-7cbd-4425-a3a8-864a0ba7a51c', 'POI-B0FFKQK2', '南凤小区停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.839978, 31.668611), 4326),
    '南凤小区', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '220e8591-d0b2-4e9e-a7ab-006462c9bfd9', 'POI-B0H2H1IL', '茂州供电公司', 'other',
    ST_SetSRID(ST_MakePoint(103.83892, 31.667646), 4326),
    '并州路7号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e0e72612-c2e1-449a-bbf7-6658c1981b49', 'POI-B0LA7UOC', '四川路桥集团川汶C3总包部', 'other',
    ST_SetSRID(ST_MakePoint(103.835551, 31.663803), 4326),
    '台茂路东段与台茂路南段交叉口东北240米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '02805996-3446-427e-adaa-fba2a36fa2fc', 'POI-B0LUL1BD', '四川盛豪(茂县)律师事务所', 'other',
    ST_SetSRID(ST_MakePoint(103.836337, 31.666712), 4326),
    '茂县人民政府征兵办公室西南侧60米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a7de3b67-aea7-40d7-9a24-3d46408dc54c', 'POI-B0FFG0DQ', '茂县富民畜牧技术服务有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.837292, 31.668901), 4326),
    '凤仪镇滨河路晋茂新园b区20栋', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5ff870c7-c1db-4cf1-9907-a4413de9105b', 'POI-B0LU9DCR', '雨露滋润茂县农副产品产业园', 'other',
    ST_SetSRID(ST_MakePoint(103.833068, 31.659539), 4326),
    '晋茂大道22号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a0d5238c-b2ad-4b98-a647-7422b43acd33', 'POI-B0FFG0DN', '茂县中天水泥制品有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.832926, 31.662325), 4326),
    '晋茂大道31-41号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5f82bcc3-c991-4dc3-bb02-88d24f8648ff', 'POI-B0HR9C8L', '茂县建灵水果包装', 'other',
    ST_SetSRID(ST_MakePoint(103.832865, 31.664829), 4326),
    '新车友汽修旁', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '681eb8e8-2953-49fa-8087-02f2c8172736', 'POI-B0L2B5JV', '兴隆精选酒店(古羌城店)停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.833422, 31.666486), 4326),
    '台茂路东段与台茂路南段交叉口北460米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '993e7528-db1d-4eae-9bee-eee0ec7aeb7f', 'POI-B0JUT7NE', '茂县西部农业发展有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.831232, 31.66046), 4326),
    '西羌大道400号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '80ed1dcd-6c95-4f99-be0a-595c80ced9fe', 'POI-B0FFFQ1S', '尔玛国际酒店停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.83371, 31.668235), 4326),
    '凤仪镇文化街88号尔玛国际酒店', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'eba67e14-0243-4831-bc91-3ce0d20f41f3', 'POI-B0KKHH73', '振新包装万众筐厂', 'other',
    ST_SetSRID(ST_MakePoint(103.831571, 31.663496), 4326),
    '台茂路东段与台茂路南段交叉口西北220米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a10eeb4e-f084-4a36-8d0e-759e6dbf2bc4', 'POI-B0LDCHTT', '东大街体育场', 'sports_field',
    ST_SetSRID(ST_MakePoint(103.854416, 31.688614), 4326),
    '太行路与老茂北路交叉口西南200米', 8000.0, 1500.0, 3.0,
    'unknown', true, true,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b77bab1e-8a61-47c5-80de-47645352e66e', 'POI-B0FFFDD8', '新月停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.829209, 31.662554), 4326),
    '西羌大道', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e0c8e564-5618-4122-9cb0-0aac2a085303', 'POI-B0H3JR9N', '汶川县明和欣家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.628333, 31.471406), 4326),
    '威州镇月里村1组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fafc2ac3-3f09-477c-a6fc-a8ab7bcbe668', 'POI-B0LD2AIF', '云朵上的阿哥车厘子果园', 'other',
    ST_SetSRID(ST_MakePoint(103.620985, 31.465769), 4326),
    '白水村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3b87237f-d104-4a81-b81f-74729cb55aa0', 'POI-B0JDKR6I', '邓四哥车厘子采摘基地停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.650624, 31.492715), 4326),
    '006乡道', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1ee230e1-c11c-492c-b2ce-3c8a11d81899', 'POI-B0IDHSIG', '汶川成果农产品销售有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.623825, 31.477531), 4326),
    '雁门镇麦地村一组037号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6c7cd944-15c7-4e84-8884-5fe9485c3baf', 'POI-B0LUD63J', '阿会果园基地', 'other',
    ST_SetSRID(ST_MakePoint(103.615831, 31.466264), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '475f0fdb-9449-4cbc-ac93-ff5d680824b2', 'POI-B0JAY7J2', '汶川余能家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.655012, 31.496816), 4326),
    '雁门乡索桥村2组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'be24750d-d177-4a51-8401-bb387cb63922', 'POI-B0KD9SRK', '汶川尔玛阿勇家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.615533, 31.470568), 4326),
    '威州镇白水村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'bc6c8a9c-99b9-4385-a59e-e6470af9ca3c', 'POI-B0KDFS7I', '好又多优质水果基地', 'other',
    ST_SetSRID(ST_MakePoint(103.64068, 31.493835), 4326),
    '四哥樱桃基地西侧420米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b844488d-3a86-4b40-b7f1-2451ccb28dda', 'POI-B0FFKCAV', '汶川果果多优态农场', 'other',
    ST_SetSRID(ST_MakePoint(103.6336, 31.49031), 4326),
    '雁门乡索桥村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0ab18e6c-67f4-4d16-a873-b74bc8b6db26', 'POI-B0IR1USG', '汶川悠然农业有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.623267, 31.484085), 4326),
    '威州镇麦通村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ba01a12e-5fba-4597-804e-f48eeafde493', 'POI-B0J2HRIO', '雁门砂场', 'other',
    ST_SetSRID(ST_MakePoint(103.621965, 31.483803), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '16654474-cf46-404b-b3bb-12a6a846fa8f', 'POI-B0K11DIK', '纳呷停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.668567, 31.501051), 4326),
    '006乡道', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '808d9c25-c75e-4133-8c5a-64a4c6514a9f', 'POI-B0FFF65Q', '萝卜寨羌文化生态旅游区', 'plaza',
    ST_SetSRID(ST_MakePoint(103.62951, 31.491384), 4326),
    '威州镇雁萝路附近', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8b561e77-14a4-4d85-b8b1-6a71b9d2a648', 'POI-B0H1KZZC', '萝卜寨停车点', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.670708, 31.501473), 4326),
    '萝卜寨村萝卜寨', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '899a34fa-2fa9-42cd-9637-32676b75f108', 'POI-B0FFKKTA', '汶川县民生燃气有限责任公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.623083, 31.486824), 4326),
    '007乡道西50米', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ca80a999-1adc-45af-8da9-c325739b3a5a', 'POI-B0KUS5WL', '宏二哥家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.646477, 31.499653), 4326),
    '索桥村一组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9f636abd-542b-45db-aa4a-e809f01486aa', 'POI-B0K11HPQ', '萝卜寨3号停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.673153, 31.502554), 4326),
    '006乡道', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a9c7e7e3-db9c-4843-a67a-cca67bd85e10', 'POI-B0K115O5', '萝卜寨2号停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.670445, 31.503369), 4326),
    '006乡道', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '82604c75-67d7-4a5d-9c43-022716e921af', 'POI-B0KGSZES', '银山家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.658917, 31.507402), 4326),
    '萝卜寨附近', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '146a67df-55b8-4a6c-8a6b-848f4398d5cf', 'POI-B0HGBSP6', '汶川长鸿彩钢夹芯板厂', 'other',
    ST_SetSRID(ST_MakePoint(103.61817, 31.493856), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fa6330e4-656c-4565-b84a-ed46ba80cab3', 'POI-B0FFGBCX', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.615385, 31.492732), 4326),
    '213国道与江情大道交叉口东100米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'de0b7b80-88f4-4579-832c-7e8b90af44b1', 'POI-B0H3TRLY', '阿坝开放大学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.616986, 31.494669), 4326),
    '威州镇江爱大道1号', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c687887e-4c74-420f-a27c-7ee0063ba9b6', 'POI-B0JA5ZF5', '汶川县开裕家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.602711, 31.477955), 4326),
    '高峰新村秉里组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4c41e2d3-69e8-46ec-8822-f5798371710c', 'POI-B0GR5G0M', '阿坝卅汶川县雁门幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.611216, 31.490623), 4326),
    '213国道与江情大道交叉口西南380米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0d85f5cd-1ed2-41c8-9138-17560b132fc6', 'POI-B03450MQ', '汶川县雁门小学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.615451, 31.495083), 4326),
    '威州镇江雁大道', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '10b98776-1c0f-4c3c-a0a5-4999ceaa31d8', 'POI-B03450MK', '青坡古庙', 'other',
    ST_SetSRID(ST_MakePoint(103.654298, 31.512023), 4326),
    '雁门乡213国道', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f1b66b3b-14f8-438d-bfa3-607a4bc1ce69', 'POI-B034500X', '四川省汶川中学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.612354, 31.49338), 4326),
    '威州镇过街楼村', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '33e8d5e5-1486-4065-bf42-921a3a96d8b7', 'POI-B0H6P7RP', '汶川兴翼鲜家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.665934, 31.513433), 4326),
    '雁门乡青坡村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'be3b255f-e02f-4d6b-8ff1-5095dbe2221f', 'POI-B0I6AU3Y', '汶川公路养护和应急保通中心', 'other',
    ST_SetSRID(ST_MakePoint(103.604242, 31.484917), 4326),
    '鹏晨江屿里销售中心北侧280米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2a88c60e-8b70-4a83-ae48-cda4f36346b4', 'POI-B0LBDSXW', '劲豹游泳馆', 'other',
    ST_SetSRID(ST_MakePoint(103.611031, 31.492825), 4326),
    '东街125号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1847c65a-e436-4736-8433-a2a052a049fe', 'POI-B0FFG5BV', '辉煌装饰', 'other',
    ST_SetSRID(ST_MakePoint(103.600297, 31.481045), 4326),
    '威州镇姜射坝组小卖部旁', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9bd30965-89b0-4ada-9bdc-174bf3687773', 'POI-B0I1MZAK', '阿坝中新燃新能源科技有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.598883, 31.480428), 4326),
    '威州镇双河村姜射坝组村民活动中心第一层', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2b2a9089-fe7d-49fa-b551-760cf67ba1c1', 'POI-B0LUD9CB', '张娜家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.589959, 31.462863), 4326),
    '茨里村村民委员会西南侧130米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '85567651-e114-4f6c-be1a-7a8a28406323', 'POI-B0L1BMY0', '姜射坝水厂', 'other',
    ST_SetSRID(ST_MakePoint(103.595146, 31.478619), 4326),
    '东街与童话公路交叉口西南420米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '92ffb15a-9281-463b-acff-48f4dd1fd47d', 'POI-B0KUPZAI', '彬哥果园', 'other',
    ST_SetSRID(ST_MakePoint(103.590619, 31.472427), 4326),
    '威州镇高锋新村110号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '85adcb0c-27f7-472c-bcaa-26eb3083977f', 'POI-B0I6YSQW', '新汶川大酒店停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.588424, 31.479467), 4326),
    '东街与013乡道交叉口西200米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1344b7ac-2a48-4d33-ae97-76586797e464', 'POI-B03450MO', '广东援建汶川纪念碑', 'plaza',
    ST_SetSRID(ST_MakePoint(103.5878, 31.480699), 4326),
    '213国道南150米', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c0b9d0ad-01ff-4a3e-9af9-a217d9fed7ff', 'POI-B0FFGBJZ', '停车场(汶川县卫生执法监督所东南)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.586967, 31.479386), 4326),
    '213国道与317国道交叉口东南300米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8fc58b5d-d89f-43db-8fa3-fba68f538c5a', 'POI-B0KKSZ25', '汶川县永康蜂场', 'other',
    ST_SetSRID(ST_MakePoint(103.672972, 31.525649), 4326),
    '213国道', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6a8bae5d-56d1-426d-8991-47d16ca37da3', 'POI-B0H1LSHM', '牟托观景台', 'other',
    ST_SetSRID(ST_MakePoint(103.683084, 31.532999), 4326),
    '牟托村入口处', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '547c5148-7b1d-47ae-849e-ee5c293a8a87', 'POI-B03450MK', '羌乡古寨牟托景区', 'plaza',
    ST_SetSRID(ST_MakePoint(103.680007, 31.533857), 4326),
    '南新镇牟托村', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '21bfbc23-389c-4a5e-abf7-d81b6f81c75c', 'POI-B0LUUAN7', '九鼎山风景区.太子岭滑雪场停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.735429, 31.52569), 4326),
    '九鼎山·太子岭滑雪场西北侧', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7f408380-6379-4c6b-ab18-187335e7a3b5', 'POI-B0KR4A3V', '九鼎山夫妻树停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.744191, 31.519951), 4326),
    NULL, 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2deb91a1-7586-483c-b88e-9aa5e9aad323', 'POI-B0FFKXIK', '羌乡古寨牟托景区南停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.681231, 31.535506), 4326),
    '牟托村羌乡古寨牟托景区', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b68441d7-445d-48cd-8583-29d4d7672952', 'POI-B0LDV963', '茂县奕辰家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.676949, 31.53486), 4326),
    '南新镇牟托村退役军人服务站西侧50米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fe95a218-f859-412d-943b-e806ecf55fb8', 'POI-B03450MK', '羌乡古寨牟托景区北停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.680302, 31.537215), 4326),
    '牟托村羌乡古寨牟托景区', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f8649b61-e75b-453d-8335-4ed5f1363dea', 'POI-B0LUFZ13', '四川路桥川汶高速公路TJ15标项目经理部', 'other',
    ST_SetSRID(ST_MakePoint(103.681538, 31.539713), 4326),
    '213国道', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4c796a6e-f519-4d5c-b087-b9ae430f4fa3', 'POI-B0KKG77T', '茂县老赵种植家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.68511, 31.541818), 4326),
    '南新镇文镇村二组', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '45c3b1c7-4cd6-4036-ab6d-13eb93e2f550', 'POI-B0FFITNX', '汶川开心牧场', 'other',
    ST_SetSRID(ST_MakePoint(103.636424, 31.526366), 4326),
    '213国道雁门村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '63e838ca-edf0-4b6c-ad13-7528bf67cbce', 'POI-B0IUSA8O', '茂县克尔布家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.725778, 31.546882), 4326),
    '南新镇安乡村六组44号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7c8e4d68-6ec7-4490-8813-a691929466c5', 'POI-B0FFHQST', '九鼎山风景区(暂停开放)', 'plaza',
    ST_SetSRID(ST_MakePoint(103.757364, 31.506155), 4326),
    '南新镇二一三国道', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '58e1cde1-0a39-4038-bc2f-157b47ebe38f', 'POI-B0FFJ913', '七盘沟', 'plaza',
    ST_SetSRID(ST_MakePoint(103.606093, 31.393055), 4326),
    NULL, 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f7e5a29a-fab9-4804-8416-ca29ce213001', 'POI-B0GUZOIF', '汶川县快乐山寨樱桃种植专业合作社', 'other',
    ST_SetSRID(ST_MakePoint(103.566529, 31.444855), 4326),
    '威州镇七盘沟村窝竹头', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7c783983-214c-409f-90cb-42d1442e2953', 'POI-B0LG2SE4', '川勘集团汶川县威绵水利项目经理部', 'other',
    ST_SetSRID(ST_MakePoint(103.570531, 31.461102), 4326),
    '012乡道与213国道交叉口东南220米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b39f2a72-d649-4bf2-9908-96e782bb3c48', 'POI-B0FFIG35', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.568715, 31.460952), 4326),
    'G4217蓉昌高速出口与213国道交叉口东北140米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '7943e9e9-ffdb-45da-8d59-656b0b50144c', 'POI-B0HDX79L', '长城现代挖机阿坝州分公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.566786, 31.460086), 4326),
    '213国道西50米五菱汽车隔壁', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4dc62f71-3e16-49bc-a7a7-2ce1fe2b764c', 'POI-B0FFFDDC', '新国旅大酒店停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.577815, 31.470694), 4326),
    '较场街下段77号新国旅大酒店', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f4e88979-5d7d-47a1-848d-ac8173413295', 'POI-B0LDH7PK', '四川昊桐农业有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.576525, 31.469799), 4326),
    '岷江路下段374号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '492d1239-eb1a-4c73-866b-d98dfd06fe67', 'POI-B0LDFUXE', '金尚环保生物质厨房燃料', 'other',
    ST_SetSRID(ST_MakePoint(103.569736, 31.463804), 4326),
    '213国道与012乡道交叉口北100米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'bc40150c-4fe8-4a8e-af4f-a7500e98fa10', 'POI-B0JD5MC5', '七盘沟百安车厘子果园', 'other',
    ST_SetSRID(ST_MakePoint(103.556566, 31.444545), 4326),
    '恒通驾校有限公司东北侧70米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6f126177-747f-4b27-b49e-e6830e2078fc', 'POI-B034500X', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.571478, 31.466437), 4326),
    '213国道与012乡道交叉口东北420米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5c8cbe26-ed45-4e00-a20c-8e89a2dbc15c', 'POI-B0JDD7L7', '万村一组沙窝子老寨子采摘停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.558809, 31.450699), 4326),
    '威州镇万村一组沙窝子老寨子', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'dfaec049-4714-421d-bdaf-249adbab5b06', 'POI-B0KR5RTG', '阿坝州清捷能源投资集团有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.577928, 31.472005), 4326),
    '威州镇岷江假日酒店(较场街)五楼', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '33e94c58-e4b3-426b-ba14-07fa1ba76494', 'POI-B0K3YLIC', '成都建工汶川全民健身中心项目部', 'other',
    ST_SetSRID(ST_MakePoint(103.572639, 31.467857), 4326),
    '沿江路2号阳光家园一期旁', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e1bb2891-4821-41be-b488-8564a37470f1', 'POI-B0KRVNGR', '锦泓装修', 'other',
    ST_SetSRID(ST_MakePoint(103.57607, 31.470794), 4326),
    '沿江路与穗威路交叉口东180米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '485834b3-ea2c-475e-8b86-d71ea14f7dc6', 'POI-B0GD7Z9Y', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.576825, 31.471614), 4326),
    '较场街与园林路交叉口西南200米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8687042e-e22a-47bd-98f3-ba2163f48ba6', 'POI-B0JKSH3G', '汶川县第三幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.572853, 31.469088), 4326),
    '汶川县融媒体中心附近', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fa49ff02-5d5b-4705-bf0a-e16138309352', 'POI-B0GR2LB4', '停车场(岷江路下段)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.578042, 31.473784), 4326),
    '人保大厦东门旁', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9e7c22e4-2fdf-4ff9-9091-12ccf1a84e49', 'POI-B0LRFH6E', '瀚江钢化玻璃厂', 'other',
    ST_SetSRID(ST_MakePoint(103.58496, 31.478206), 4326),
    '威州镇岷江路上段143号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd4e992d3-017c-4c32-9d55-8b03920c31fc', 'POI-B0H3TUJI', '汶川县人民医院停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.574245, 31.471143), 4326),
    '威州镇穗威路1号汶川县人民医院', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'bfabd830-f5bd-41de-86ca-e731c1ded77e', 'POI-B0KRAP98', '阿坝交投', 'other',
    ST_SetSRID(ST_MakePoint(103.577022, 31.473522), 4326),
    '威州镇岷江假日酒店(较场街)五楼', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f2b1a7ac-d9d0-4659-b177-72258bfec81a', 'POI-B0L0Z6DE', '阳光家园(一)二期停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.569286, 31.467103), 4326),
    '大九寨旅游环线与213国道交叉口西北160米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '62e792f2-3ae0-48a4-806d-5115784ae641', 'POI-B0FFGCVB', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.578412, 31.475013), 4326),
    '较场街124号附近', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '99811e69-0217-4f90-83ec-1bd8786bc682', 'POI-B0HGTC9X', '来点音乐吧', 'other',
    ST_SetSRID(ST_MakePoint(103.577382, 31.474525), 4326),
    '岷江路下段与岷江路中段交叉口东南80米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1a026d3f-03a7-479c-b351-e525027086ad', 'POI-B03450MP', '姜维城', 'plaza',
    ST_SetSRID(ST_MakePoint(103.585682, 31.479694), 4326),
    '213国道与317国道交叉口东南200米', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2209aed7-2547-4d19-be61-746e881a70d9', 'POI-B03450MF', '汶川体育馆', 'sports_field',
    ST_SetSRID(ST_MakePoint(103.586706, 31.480304), 4326),
    '东街44号', 8000.0, 1500.0, 3.0,
    'unknown', true, true,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a923aaa8-89e9-425b-bc9e-164b48ccbc3c', 'POI-B0FFG37Q', '汶川县城大型货车停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.560586, 31.45854), 4326),
    '213国道与S9都汶高速入口交叉口东北100米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8a7a9f88-300f-4191-b854-bde8b3aaa38c', 'POI-B0FFGD3U', '地下停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.577442, 31.475561), 4326),
    '岷江路中段与岷江路下段交叉口东北100米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ea7b0077-0e7b-4ef5-8c6b-f789a58c52f4', 'POI-B0KD4M2S', '阿坝州九寨工业科技有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.552089, 31.444676), 4326),
    '沿江路4号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '14901c01-4c84-4b3a-9683-ddcc7cbd8d57', 'POI-B034500X', '汶川县第一幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.578585, 31.476495), 4326),
    '威州镇校场街', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '864f809b-65b2-4d9c-acdb-8a1daea7c865', 'POI-B0J04ZZL', '汶川县欣禹林业有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.584046, 31.479964), 4326),
    '东街1号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '30d244a1-d42a-4bcf-b957-7cdcca52d7ae', 'POI-B0FFIBRJ', '网忆网咖(德惠超市店)', 'other',
    ST_SetSRID(ST_MakePoint(103.582901, 31.479417), 4326),
    '威州镇德惠超市二楼', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'cc20c59a-2fcc-4bc4-bf61-933ddb34b079', 'POI-B0FFGCVX', '停车场(岷江路上段)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.580549, 31.478207), 4326),
    '岷江路上段与东街交叉口西南280米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'dde3610b-bf94-43d3-904b-33392e1e6cc4', 'POI-B0KARA9J', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.581675, 31.478959), 4326),
    '岷江路上段55号', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b38cb58f-1d50-4537-a770-65efde6b2e50', 'POI-B0H1ZC97', '四川汶马高速公路有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.555019, 31.452186), 4326),
    '威州镇沙窝子汶川汽车站旁', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c3db57b3-2288-458c-b00c-1d0ff207f755', 'POI-B0FFGCVF', '红军桥', 'plaza',
    ST_SetSRID(ST_MakePoint(103.584671, 31.480699), 4326),
    'G213(兰磨线)', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3cb3e423-71d2-4072-8742-c78ead93ab68', 'POI-B0FFKDVS', '奇恒广告', 'other',
    ST_SetSRID(ST_MakePoint(103.57681, 31.476357), 4326),
    '岷闲居花园东门旁', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '333d0762-ac41-46ad-9a02-37f69a22b22a', 'POI-B0J0DGNL', '伟业广告图文(岷江路中段店)', 'other',
    ST_SetSRID(ST_MakePoint(103.578605, 31.477744), 4326),
    '威州花园西门东70米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6893e614-e30a-4c91-99bd-fd999f03b07b', 'POI-B0LR01O2', '民族团结塔', 'plaza',
    ST_SetSRID(ST_MakePoint(103.585442, 31.481748), 4326),
    '213国道与317国道交叉口东北60米', 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f4d61432-3405-43b0-ae68-c4c734195088', 'POI-B034500X', '汶川县第一小学校', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.579521, 31.478657), 4326),
    '威州镇岷江路上段', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ce578cda-2c9a-411d-a98f-23937adc4c21', 'POI-B0L16ZRQ', '汶川县建筑工程公司', 'other',
    ST_SetSRID(ST_MakePoint(103.583979, 31.482095), 4326),
    '317国道与213国道交叉口西北120米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '73fd7236-51bc-4310-8227-799f56057023', 'POI-B0FFJCSN', '四川省威州民族师范学校附属小学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.582794, 31.48236), 4326),
    '二小旁大桥路4号附3号汶川县第二小学附近', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '288c3559-30c9-48a4-a7fa-0903a4bc0854', 'POI-B0LANCXR', '四川顺汶新能源科技有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.585272, 31.483686), 4326),
    '威州镇桑坪路39号附66号.67号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '54a489d7-0425-4cde-8b3c-4695aca96561', 'POI-B03450MJ', '停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.544359, 31.428392), 4326),
    '213国道东50米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6fca403b-2c73-4389-9b22-25b09c39d590', 'POI-B0FFLB25', '中国邮政集团公司四川省汶川县分公司', 'other',
    ST_SetSRID(ST_MakePoint(103.583597, 31.483201), 4326),
    '威州镇桑坪路37号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '73f58f19-b8f0-44c8-89ca-85a7b7d97d65', 'POI-B0FFGCVE', '北峰银座停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.580206, 31.481383), 4326),
    '凤洲路北峰银座', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a011b27b-77cc-4101-bc54-23cedc6f58a9', 'POI-B03450MK', '地上停车场(板桥村)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.544342, 31.430636), 4326),
    '兰磨线', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '737ef003-e4d6-458d-97a7-d1bc09f17745', 'POI-B0GKNU7V', '小雍家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.723839, 31.560336), 4326),
    '南新镇安乡村三组55号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3db2c184-1684-4c00-9b05-16339dc6fc31', 'POI-B0LR3SCV', '丰茂牦牛屠宰中心', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.731041, 31.576028), 4326),
    '九鼎山牦牛庄北侧', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9c6b3793-fea3-46e2-9d57-d3fb17770490', 'POI-B0L21CTG', '光华小学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.73207, 31.580866), 4326),
    '109乡道与童话公路交叉口西南420米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '16622049-7021-4150-8ef3-a0a04ae16021', 'POI-B0JDOZFO', '茂县友君养殖家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.740741, 31.58551), 4326),
    '南新镇棉簇村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b55b15cb-2cc8-4c08-8218-33047c3eef5e', 'POI-B0FFG8OQ', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.743713, 31.58692), 4326),
    '川汶公路西50米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '170a829a-946b-4858-aac3-cbb99c5f74df', 'POI-B0HRMZJK', '四川阿坝茂县尔玛巧妹商贸有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.747491, 31.590654), 4326),
    '南新镇棉簇村中寨组156号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b8134ddf-7e4d-4d9f-9bbb-32e7514dacc4', 'POI-B034500X', '茂县建隆硅业有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.736817, 31.590523), 4326),
    '南新镇', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c28b4e63-77d2-4187-b9c5-e5957df28693', 'POI-B0FFKJN2', '茂县盛佳硅业有限责任公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.734091, 31.591973), 4326),
    '南新镇棉簇村', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'b1db7ba6-275c-43be-8ceb-d6b091a44504', 'POI-B0FFG8PI', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.749877, 31.594457), 4326),
    '川汶公路西50米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'fc8b48e9-7a05-49df-9945-3abae92020b4', 'POI-B0G336VA', '别立牧场', 'other',
    ST_SetSRID(ST_MakePoint(103.779178, 31.585418), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e15064ce-20fd-482a-953f-5102e79eeef8', 'POI-B0LAV1A3', '九鼎山文镇沟大峡谷风景名胜区', 'plaza',
    ST_SetSRID(ST_MakePoint(103.817407, 31.552998), 4326),
    NULL, 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4a22d313-29f8-448b-b9ef-9de41c9d9c0f', 'POI-B0FFI8KP', '龙王庙', 'other',
    ST_SetSRID(ST_MakePoint(103.692291, 31.603757), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a7b9d7b2-19ab-40fa-8600-84783b95ef99', 'POI-B0H60HK6', '茂县弟兄五金加工厂', 'other',
    ST_SetSRID(ST_MakePoint(103.927347, 31.724743), 4326),
    '富顺镇胜利村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4bd3030f-d667-42b4-b786-a6af69bf7284', 'POI-B0KR5ZWL', '中国铁路成都局集团有限公司茂县综合维修基地', 'other',
    ST_SetSRID(ST_MakePoint(103.941737, 31.730696), 4326),
    '347国道', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'dc9875c0-b067-4851-b90a-800fd58b02bb', 'POI-B0I1G7YV', '绵茂路(茂县段)灾后恢复重建工程路面机电交安及管理中心项目', 'other',
    ST_SetSRID(ST_MakePoint(103.916055, 31.710059), 4326),
    '545国道', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3869a360-4f9a-4182-9ef2-144ccee0ae84', 'POI-B0K1P5KS', '茂县站停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.942108, 31.72575), 4326),
    NULL, 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd88ad630-9719-4869-b59e-546b88566ef4', 'POI-B0FFJRVD', '光明永华中药材种植专业合作社', 'other',
    ST_SetSRID(ST_MakePoint(103.945197, 31.728485), 4326),
    '光明乡', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd521a39d-b9a8-4362-bf5c-9bbf035cf0d7', 'POI-B0L2B5KT', '九龙山', 'plaza',
    ST_SetSRID(ST_MakePoint(103.954835, 31.788832), 4326),
    NULL, 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '303dcf56-6ace-4953-b0b8-fea0ad1b7386', 'POI-B0FFG6RZ', '茂县明脚清真寺', 'other',
    ST_SetSRID(ST_MakePoint(103.972737, 31.748616), 4326),
    '光明乡302省道', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '572225e5-1554-4fba-aad2-2b0005b95f2b', 'POI-B0FFIA9V', '龙王庙', 'other',
    ST_SetSRID(ST_MakePoint(103.887263, 31.816694), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4cc9c7c2-5a29-4916-8b42-0ef6ea27ec87', 'POI-B0FFG6RZ', '一品鱼庄停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.787932, 31.627188), 4326),
    '川汶公路东50米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2adce77f-96e6-4c39-9a4c-7b170360061f', 'POI-B0FFME9U', '石林寺', 'other',
    ST_SetSRID(ST_MakePoint(103.825788, 31.584474), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'e18861ff-727e-4b2e-97ad-239b29394ba6', 'POI-B0FFG7HI', '停车场(109乡道)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.803669, 31.641678), 4326),
    '川汶公路与移民感恩路交叉口南80米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '865a3cf9-23ab-43ea-a84d-a92b16020a02', 'POI-B0FFG7H4', '停车场(移民感恩路)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.804345, 31.642663), 4326),
    '川汶公路与移民感恩路交叉口东北40米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '0e268a26-dbff-4b4a-82cd-c9d093372334', 'POI-B0LB6RHS', '茂县凤仪镇宗渠小学校', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.806348, 31.642806), 4326),
    '川汶公路109乡', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5c5b8ccb-ef45-4d14-90f9-57f33cf4b48d', 'POI-B0LDOU1J', '川汶高速TJ14项目经理部', 'other',
    ST_SetSRID(ST_MakePoint(103.80528, 31.64434), 4326),
    '川汶公路109乡', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a0492e2f-0148-4221-8a54-adf916cb1a07', 'POI-B0L19XJE', '茂县飞哥鱼养殖基地', 'other',
    ST_SetSRID(ST_MakePoint(103.810191, 31.658629), 4326),
    '松清石油加油站西北侧150米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'cd9eb399-51b3-46bb-873e-34134aed1849', 'POI-B0FFG6S0', '四川嘉盛金扬电力设备有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.811685, 31.661035), 4326),
    '凤仪镇河西C区背后', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '8dd47c85-b79e-4ed9-8b27-9489a2cc511c', 'POI-B0L1451Y', '龙翔桥隧物资', 'other',
    ST_SetSRID(ST_MakePoint(103.812286, 31.662086), 4326),
    '京东快递阿坝茂县营业部西南侧110米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '79c5c235-9ccd-44b1-9ed7-7ce588288e87', 'POI-B0KKBL4A', '领军建机办事处', 'other',
    ST_SetSRID(ST_MakePoint(103.818684, 31.660543), 4326),
    '平安汽修南侧50米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '3965cd80-d6d4-40a9-9145-205f94befa4c', 'POI-B03450MK', '茂县格桑花牦牛角梳生产基地', 'other',
    ST_SetSRID(ST_MakePoint(103.817875, 31.662172), 4326),
    '凤仪镇宗渠村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ad6e7f58-ff89-4c82-9346-254f869265b5', 'POI-B0FFKM4E', '阿坝州江原石油液化气有限责任公司', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.81138, 31.665685), 4326),
    NULL, 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'acad2339-1fac-4c1c-ab28-9b05054a26b6', 'POI-B0FFIKLJ', '老君庙', 'other',
    ST_SetSRID(ST_MakePoint(103.989121, 31.774927), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '4915b55e-da67-4495-9295-3796cc31f4d0', 'POI-B0FFIKO6', '山王庙', 'other',
    ST_SetSRID(ST_MakePoint(104.028847, 31.81912), 4326),
    '富顺乡山王庙', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '844e0009-62d1-4c0f-ae13-0759621acfcc', 'POI-B0FFKRVH', '茂县七一富顺镇小学', 'school_yard',
    ST_SetSRID(ST_MakePoint(104.011577, 31.755766), 4326),
    '302省道南100米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '1041c07d-b5b4-43c7-86a4-3245d31c05e4', 'POI-B0L6GAVM', '拾悦牧场', 'other',
    ST_SetSRID(ST_MakePoint(103.595745, 31.50689), 4326),
    '威州镇布瓦村', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6662e167-f7af-46ef-a39e-edc70e5ea197', 'POI-B0L2BCLA', '汶川无优地观景台', 'other',
    ST_SetSRID(ST_MakePoint(103.582825, 31.506391), 4326),
    '肇庆大道3号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '05baa1fb-0167-438c-a997-cde31ac7675f', 'POI-B0J131KN', '四川九耕农业开发有限责任公司', 'other',
    ST_SetSRID(ST_MakePoint(103.582493, 31.497153), 4326),
    '勇根樱桃李子种植专业合作社西侧230米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '449cf405-3666-43b6-9c98-6bf20dbaa212', 'POI-B0IDBCM0', '汶川县康顺家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.582089, 31.493757), 4326),
    '西街29号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '27aa5a6e-1d5d-4c43-aba8-958a8a60bbb1', 'POI-B0LDFZXA', '汶川孟园甜樱桃家庭农场', 'other',
    ST_SetSRID(ST_MakePoint(103.58117, 31.492987), 4326),
    '317国道与012乡道交叉口东北340米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'd3a88f59-555f-46a2-9bef-8124690e53ea', 'POI-B0IDGMRM', '阿仑家庭农场甜樱桃基地', 'other',
    ST_SetSRID(ST_MakePoint(103.579243, 31.492518), 4326),
    '瓦桥头村弯道户(G317成那线)', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'eb6276c8-b6f6-487d-ac69-6710284fc333', 'POI-B0FFLB7F', '张玉华野生蜂蜜场', 'open_ground',
    ST_SetSRID(ST_MakePoint(103.596515, 31.521737), 4326),
    '大寺村磊底组8号', 2000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '413fae07-84e2-48e2-b654-bb0d90999f1b', 'POI-B0I11M64', '灌成环卫有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.580933, 31.488197), 4326),
    '黄岩观音庙东北门西北480米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '84b4b5c1-9c5e-4cb7-87e6-b6ebbcb33368', 'POI-B0FFILMC', '汶川县航翔五金机械桥隧物资部', 'other',
    ST_SetSRID(ST_MakePoint(103.581448, 31.48736), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'c9b50cec-bd65-48f5-af84-b67ef4dba53e', 'POI-B0FFKKAG', '汶川县惠丰商贸有限公司', 'other',
    ST_SetSRID(ST_MakePoint(103.582308, 31.486535), 4326),
    '黄岩观音庙东北门西北210米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '2e88425d-c984-4548-817c-c2d69f11a300', 'POI-B0FFGCVE', '汶川县国有林场', 'other',
    ST_SetSRID(ST_MakePoint(103.583293, 31.48554), 4326),
    '西街21号', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '620f4019-4e05-4495-a951-e6e4858c8ce4', 'POI-B0FFMH2L', '汶川龙腾果蔬开发有限责任公司一号采摘园', 'other',
    ST_SetSRID(ST_MakePoint(103.579026, 31.488702), 4326),
    '012乡道路旁', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'ee34fa88-f02f-496b-9153-a86eeed86791', 'POI-B0FFGD3V', '停车场(西街)', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.583898, 31.4848), 4326),
    '西街与桑坪路交叉口东北140米', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '789302eb-1c85-4e59-a875-405cf8d007cd', 'POI-B0FFG0DA', '桑坪小博士幼儿园', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.582271, 31.48482), 4326),
    '威州镇桑坪社区', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5b5b74a7-ce1a-4fb8-95ab-238a0241c954', 'POI-B0LR5DBD', '汶川县林业医院停车场', 'parking_lot',
    ST_SetSRID(ST_MakePoint(103.582093, 31.483685), 4326),
    '县西街4号附3号汶川县林业医院', 3000.0, 1500.0, 3.0,
    'unknown', false, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '80a240ac-2984-4b01-9f79-67ed00b9a1b3', 'POI-B0GU9MUF', '汶川时代广告', 'other',
    ST_SetSRID(ST_MakePoint(103.581154, 31.482937), 4326),
    '明珠广场西南门北130米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '5d520a06-68f3-44fe-98dc-6f18890487b1', 'POI-B0LR74HI', '汶川周永盛大樱桃种植专业合作社', 'other',
    ST_SetSRID(ST_MakePoint(103.568667, 31.506951), 4326),
    '后街与中心街交叉口东南220米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '6f01365d-547f-4db0-9381-78bb635fdb0f', 'POI-B0LRLNMJ', '灞州小学', 'school_yard',
    ST_SetSRID(ST_MakePoint(103.567905, 31.507593), 4326),
    '肇庆大道与后街交叉口东南120米', 5000.0, 1500.0, 3.0,
    'unknown', true, true,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9b3ff7a5-b357-4a2a-b61b-c865a67bf851', 'POI-B0LDL7TF', '骞家果园', 'other',
    ST_SetSRID(ST_MakePoint(103.56558, 31.496248), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '03b62527-b793-47f0-b57b-a6cad87bf1e7', 'POI-B0FFHQ3R', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.564544, 31.510584), 4326),
    '317国道与G4217蓉昌高速出口交叉口东南140米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f34b30b1-faed-4455-ad85-6333c53a72eb', 'POI-B0FFG8PI', '停车场(出入口)', 'other',
    ST_SetSRID(ST_MakePoint(103.55377, 31.516294), 4326),
    '317国道北50米', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9c37c8b9-20a3-4b0a-9003-42609044499a', 'POI-B0L61URN', '大寺冰瀑', 'plaza',
    ST_SetSRID(ST_MakePoint(103.597229, 31.543167), 4326),
    NULL, 4000.0, 1500.0, 3.0,
    'unknown', false, false,
    true, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'a040f052-ca8a-4855-a223-e3a4b1f1d7e2', 'POI-B0LRORWR', '车厘子青红脆李基地', 'other',
    ST_SetSRID(ST_MakePoint(103.618647, 31.462386), 4326),
    '红康诚信车厘子采摘园西侧', 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '23e1ce59-9680-4016-9c68-eda2cb6138c7', 'POI-B0FFMD6X', '石古作些寺', 'other',
    ST_SetSRID(ST_MakePoint(103.58419, 31.557138), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '9d1333b5-e627-4dc9-b5f7-a6caf02c3295', 'POI-B0FFIKLE', '山王庙', 'other',
    ST_SetSRID(ST_MakePoint(103.849081, 31.892595), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    '34a11f21-a05f-4699-aaf1-b27364f741b0', 'POI-B0FFIKW5', '龙王庙', 'other',
    ST_SetSRID(ST_MakePoint(103.824655, 31.898123), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);
INSERT INTO operational_v2.rescue_staging_sites_v2 (
    id, site_code, name, site_type,
    location, address, area_m2, elevation_m, slope_degree,
    ground_stability, has_water_supply, has_power_supply,
    can_helicopter_land, primary_network_type, signal_quality,
    status, properties
) VALUES (
    'f81bd360-e4be-45c6-8017-1d8b06fd2564', 'POI-B0FFIKRX', '东岳庙', 'other',
    ST_SetSRID(ST_MakePoint(103.80498, 31.817985), 4326),
    NULL, 1500.0, 1500.0, 3.0,
    'unknown', false, false,
    false, '4g_lte', 'good',
    'available', '{"source": "amap_poi"}'
);

COMMIT;

-- 共插入 296 条记录

-- 验证查询
-- SELECT COUNT(*) as total, site_type, COUNT(*) as count
-- FROM operational_v2.rescue_staging_sites_v2
-- GROUP BY site_type;