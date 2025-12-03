-- ============================================================================
-- v43_expand_teams.sql
-- 扩展PostgreSQL队伍数据
-- 目标: 新增50+支专业队伍
-- ============================================================================

-- 获取茂县附近的坐标作为基准 (103.85, 31.68)
-- 新队伍分布在四川省各地

-- ============================================================================
-- 一、指挥协调类队伍 (5支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('CMD_ABA_001', '阿坝州应急指挥中心', 'command', '阿坝州应急管理局', '张指挥', '13800000001',
 ST_SetSRID(ST_MakePoint(102.22, 31.90), 4326), '阿坝州马尔康市', 50, 45, 5, 15, 'standby'),
 
('CMD_CD_001', '成都市应急指挥中心', 'command', '成都市应急管理局', '李指挥', '13800000002',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市锦江区', 80, 70, 5, 30, 'standby'),
 
('CMD_MY_001', '绵阳市应急指挥中心', 'command', '绵阳市应急管理局', '王指挥', '13800000003',
 ST_SetSRID(ST_MakePoint(104.73, 31.47), 4326), '绵阳市涪城区', 60, 55, 5, 25, 'standby'),
 
('CMD_DY_001', '德阳市应急指挥中心', 'command', '德阳市应急管理局', '赵指挥', '13800000004',
 ST_SetSRID(ST_MakePoint(104.40, 31.13), 4326), '德阳市旌阳区', 55, 50, 5, 20, 'standby'),

('CMD_SC_001', '四川省应急指挥中心', 'command', '四川省应急管理厅', '陈指挥', '13800000005',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市武侯区', 100, 90, 5, 45, 'standby');

-- ============================================================================
-- 二、专业搜救类队伍 (10支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('SAR_DOG_001', '四川搜救犬中队', 'search_rescue', '四川省消防救援总队', '孙队长', '13800000011',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市金牛区', 30, 28, 5, 60, 'standby'),

('SAR_ROBOT_001', '四川机器人搜救队', 'search_rescue', '四川省应急管理厅', '周队长', '13800000012',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市高新区', 25, 22, 5, 90, 'standby'),

('SAR_UAV_001', '四川无人机侦察队', 'search_rescue', '四川省消防救援总队', '吴队长', '13800000013',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市双流区', 35, 32, 5, 45, 'standby'),

('SAR_THERMAL_001', '热成像搜救队', 'search_rescue', '四川省消防救援总队', '郑队长', '13800000014',
 ST_SetSRID(ST_MakePoint(104.73, 31.47), 4326), '绵阳市游仙区', 20, 18, 4, 50, 'standby'),

('SAR_HIGH_001', '高空救援队', 'search_rescue', '四川省消防救援总队', '冯队长', '13800000015',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 40, 36, 5, 40, 'standby'),

('SAR_CONFINED_001', '狭小空间救援队', 'search_rescue', '四川省消防救援总队', '陈队长', '13800000016',
 ST_SetSRID(ST_MakePoint(104.40, 31.13), 4326), '德阳市广汉市', 35, 32, 4, 35, 'standby'),

('SAR_MOUNTAIN_001', '山地救援队', 'search_rescue', '四川省应急管理厅', '杨队长', '13800000017',
 ST_SetSRID(ST_MakePoint(103.00, 30.00), 4326), '雅安市雨城区', 45, 40, 4, 55, 'standby'),

('SAR_URBAN_001', '城市搜救队', 'search_rescue', '成都市消防救援支队', '朱队长', '13800000018',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市成华区', 50, 45, 4, 30, 'standby'),

('SAR_ABA_001', '阿坝州搜救队', 'search_rescue', '阿坝州应急管理局', '马队长', '13800000019',
 ST_SetSRID(ST_MakePoint(103.85, 31.68), 4326), '阿坝州茂县', 40, 36, 4, 20, 'standby'),

('SAR_NIGHT_001', '夜间搜救队', 'search_rescue', '四川省消防救援总队', '林队长', '13800000020',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市武侯区', 30, 28, 4, 40, 'standby');

-- ============================================================================
-- 三、医疗救护类队伍 (8支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('MED_HUAXI_ICU', '华西医院ICU转运队', 'medical', '四川大学华西医院', '何主任', '13800000021',
 ST_SetSRID(ST_MakePoint(104.03, 30.63), 4326), '成都市武侯区', 30, 25, 5, 45, 'standby'),

('MED_FIELD_001', '野战医疗队', 'medical', '解放军西部战区总医院', '谢主任', '13800000022',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市金牛区', 60, 55, 5, 60, 'standby'),

('MED_BURN_001', '烧伤救治队', 'medical', '四川省人民医院', '曾主任', '13800000023',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 25, 22, 5, 50, 'standby'),

('MED_TRAUMA_001', '创伤急救队', 'medical', '成都市第三人民医院', '邓主任', '13800000024',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 35, 32, 4, 35, 'standby'),

('MED_PSYCH_001', '心理援助队', 'medical', '四川省精神卫生中心', '汪主任', '13800000025',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市锦江区', 20, 18, 4, 60, 'standby'),

('MED_PEDIATRIC_001', '儿科急救队', 'medical', '成都市妇女儿童中心医院', '孟主任', '13800000026',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 25, 22, 4, 40, 'standby'),

('MED_TOXIC_001', '中毒救治队', 'medical', '四川省人民医院', '龙主任', '13800000027',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 20, 18, 5, 55, 'standby'),

('MED_ABA_001', '阿坝州医疗救援队', 'medical', '阿坝州人民医院', '史主任', '13800000028',
 ST_SetSRID(ST_MakePoint(102.22, 31.90), 4326), '阿坝州马尔康市', 40, 35, 4, 30, 'standby');

-- ============================================================================
-- 四、工程抢险类队伍 (8支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('ENG_CRANE_001', '重型起吊救援队', 'engineering', '四川省住建厅', '唐队长', '13800000031',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市龙泉驿区', 45, 40, 4, 60, 'standby'),

('ENG_BLAST_001', '爆破救援队', 'engineering', '四川省应急管理厅', '韩队长', '13800000032',
 ST_SetSRID(ST_MakePoint(104.40, 31.13), 4326), '德阳市什邡市', 25, 22, 5, 90, 'standby'),

('ENG_BRIDGE_001', '桥梁抢修队', 'engineering', '四川省交通运输厅', '贾队长', '13800000033',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市新都区', 50, 45, 4, 50, 'standby'),

('ENG_TUNNEL_001', '隧道抢险队', 'engineering', '四川省交通运输厅', '夏队长', '13800000034',
 ST_SetSRID(ST_MakePoint(103.00, 30.00), 4326), '雅安市名山区', 40, 36, 4, 55, 'standby'),

('ENG_DEMOLITION_001', '破拆作业队', 'engineering', '成都市住建局', '蒋队长', '13800000035',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青白江区', 35, 32, 4, 40, 'standby'),

('ENG_SHORING_001', '建筑支撑队', 'engineering', '四川省住建厅', '沈队长', '13800000036',
 ST_SetSRID(ST_MakePoint(104.73, 31.47), 4326), '绵阳市涪城区', 30, 28, 4, 45, 'standby'),

('ENG_POWER_001', '电力抢修队', 'engineering', '国网四川电力', '梁队长', '13800000037',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市金牛区', 60, 55, 4, 30, 'standby'),

('ENG_WATER_001', '供水抢修队', 'engineering', '成都市水务局', '宋队长', '13800000038',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市锦江区', 45, 40, 4, 35, 'standby');

-- ============================================================================
-- 五、水域救援类队伍 (6支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('WATER_DIVE_001', '潜水救援队', 'water_rescue', '四川省消防救援总队', '郭队长', '13800000041',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市新津区', 30, 28, 5, 50, 'standby'),

('WATER_SWIFT_001', '急流救援队', 'water_rescue', '四川省消防救援总队', '罗队长', '13800000042',
 ST_SetSRID(ST_MakePoint(103.00, 30.00), 4326), '雅安市雨城区', 35, 32, 5, 45, 'standby'),

('WATER_FLOOD_001', '抗洪抢险队', 'water_rescue', '四川省水利厅', '胡队长', '13800000043',
 ST_SetSRID(ST_MakePoint(104.73, 31.47), 4326), '绵阳市涪城区', 80, 70, 4, 40, 'standby'),

('WATER_BOAT_001', '舟艇救援队', 'water_rescue', '四川省消防救援总队', '许队长', '13800000044',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市郫都区', 40, 36, 4, 35, 'standby'),

('WATER_DAM_001', '堤防抢险队', 'water_rescue', '四川省水利厅', '刘队长', '13800000045',
 ST_SetSRID(ST_MakePoint(104.40, 31.13), 4326), '德阳市旌阳区', 100, 90, 4, 50, 'standby'),

('WATER_PUMP_001', '排涝抢险队', 'water_rescue', '成都市水务局', '田队长', '13800000046',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市双流区', 50, 45, 4, 30, 'standby');

-- ============================================================================
-- 六、危化品处置类队伍 (5支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('HAZMAT_DETECT_001', '危化品检测队', 'hazmat', '四川省生态环境厅', '方队长', '13800000051',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市成华区', 25, 22, 5, 45, 'standby'),

('HAZMAT_DECON_001', '洗消处置队', 'hazmat', '四川省消防救援总队', '石队长', '13800000052',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市武侯区', 30, 28, 5, 40, 'standby'),

('HAZMAT_NUCLEAR_001', '核辐射处置队', 'hazmat', '四川省生态环境厅', '程队长', '13800000053',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市高新区', 20, 18, 5, 90, 'standby'),

('HAZMAT_GAS_001', '气体泄漏处置队', 'hazmat', '四川省消防救援总队', '曹队长', '13800000054',
 ST_SetSRID(ST_MakePoint(104.40, 31.13), 4326), '德阳市广汉市', 35, 32, 4, 35, 'standby'),

('HAZMAT_OIL_001', '油品泄漏处置队', 'hazmat', '中国石油四川分公司', '袁队长', '13800000055',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市金牛区', 40, 36, 4, 50, 'standby');

-- ============================================================================
-- 七、通信保障类队伍 (4支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('COMM_SAT_001', '卫星通信保障队', 'communication', '四川省应急管理厅', '丁队长', '13800000061',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市高新区', 25, 22, 5, 60, 'standby'),

('COMM_MOBILE_001', '移动通信保障队', 'communication', '中国移动四川分公司', '魏队长', '13800000062',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市武侯区', 40, 36, 4, 40, 'standby'),

('COMM_NETWORK_001', '网络恢复队', 'communication', '四川省通信管理局', '贺队长', '13800000063',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 30, 28, 4, 45, 'standby'),

('COMM_RADIO_001', '无线电保障队', 'communication', '四川省无线电管理办公室', '顾队长', '13800000064',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市锦江区', 20, 18, 4, 50, 'standby');

-- ============================================================================
-- 八、矿山救援类队伍 (4支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('MINE_RESCUE_001', '四川省矿山救援队', 'mine_rescue', '四川煤矿安全监察局', '潘队长', '13800000071',
 ST_SetSRID(ST_MakePoint(104.76, 29.35), 4326), '宜宾市翠屏区', 80, 70, 5, 90, 'standby'),

('MINE_VENT_001', '矿井通风队', 'mine_rescue', '四川煤矿安全监察局', '葛队长', '13800000072',
 ST_SetSRID(ST_MakePoint(105.44, 28.88), 4326), '泸州市江阳区', 40, 36, 4, 80, 'standby'),

('MINE_DRILL_001', '生命通道钻探队', 'mine_rescue', '四川省应急管理厅', '范队长', '13800000073',
 ST_SetSRID(ST_MakePoint(104.40, 31.13), 4326), '德阳市什邡市', 30, 28, 5, 120, 'standby'),

('MINE_PUMP_001', '矿井排水队', 'mine_rescue', '四川煤矿安全监察局', '彭队长', '13800000074',
 ST_SetSRID(ST_MakePoint(104.76, 29.35), 4326), '宜宾市南溪区', 35, 32, 4, 100, 'standby');

-- ============================================================================
-- 九、志愿者和社会救援类队伍 (5支)
-- ============================================================================
INSERT INTO operational_v2.rescue_teams_v2 (
    code, name, team_type, parent_org, contact_person, contact_phone,
    base_location, base_address, total_personnel, available_personnel,
    capability_level, response_time_minutes, status
) VALUES
('VOL_BLUESKY_CD', '蓝天救援队成都分队', 'volunteer', '中国蓝天救援队', '苏队长', '13800000081',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市金牛区', 150, 120, 4, 60, 'standby'),

('VOL_GREENRIBBON_001', '绿丝带救援队', 'volunteer', '四川省红十字会', '卢队长', '13800000082',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市锦江区', 100, 80, 3, 90, 'standby'),

('VOL_REDCROSS_001', '红十字救援队', 'volunteer', '四川省红十字会', '蔡队长', '13800000083',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市武侯区', 80, 70, 3, 75, 'standby'),

('VOL_YOUTH_001', '青年志愿者救援队', 'volunteer', '共青团四川省委', '董队长', '13800000084',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市青羊区', 200, 150, 3, 120, 'standby'),

('VOL_COMMUNITY_001', '社区应急志愿队', 'volunteer', '成都市应急管理局', '袁队长', '13800000085',
 ST_SetSRID(ST_MakePoint(104.07, 30.67), 4326), '成都市成华区', 300, 250, 2, 30, 'standby');

-- ============================================================================
-- 验证插入结果
-- ============================================================================
SELECT team_type, COUNT(*) as count 
FROM operational_v2.rescue_teams_v2 
GROUP BY team_type 
ORDER BY count DESC;

SELECT COUNT(*) as total_teams FROM operational_v2.rescue_teams_v2;
