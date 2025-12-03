// ============================================================================
// v41_expand_scenes_taskchains.cypher
// 扩展Scene场景节点和TaskChain任务链节点
// 目标: Scene 60+个, TaskChain 40+个
// ============================================================================

// 清理旧的Scene节点（保留有数据的）
MATCH (s:Scene) WHERE s.id IS NULL DELETE s;

// ============================================================================
// 一、Scene场景节点 (60+个)
// ============================================================================

// ---------- 地震场景 (10个) ----------
CREATE (s:Scene {
  id: 'S_EQ_URBAN_DAY', 
  name: '城市地震-白天', 
  disaster_type: 'earthquake', 
  environment: 'urban', 
  time_period: 'day',
  severity_range: [5.0, 9.0],
  description: '白天城市区域发生地震，建筑密集，人员活动频繁'
});

CREATE (s:Scene {
  id: 'S_EQ_URBAN_NIGHT', 
  name: '城市地震-夜间', 
  disaster_type: 'earthquake', 
  environment: 'urban', 
  time_period: 'night',
  severity_range: [5.0, 9.0],
  description: '夜间城市地震，人员多在室内休息，救援难度增加'
});

CREATE (s:Scene {
  id: 'S_EQ_RURAL', 
  name: '农村地震', 
  disaster_type: 'earthquake', 
  environment: 'rural',
  description: '农村区域地震，建筑分散，道路条件差'
});

CREATE (s:Scene {
  id: 'S_EQ_MOUNTAIN', 
  name: '山区地震', 
  disaster_type: 'earthquake', 
  environment: 'mountain',
  description: '山区地震，易引发滑坡泥石流等次生灾害'
});

CREATE (s:Scene {
  id: 'S_EQ_INDUSTRIAL', 
  name: '工业区地震', 
  disaster_type: 'earthquake', 
  environment: 'industrial',
  description: '工业区地震，需关注危化品泄漏风险'
});

CREATE (s:Scene {
  id: 'S_EQ_SCHOOL', 
  name: '学校地震', 
  disaster_type: 'earthquake', 
  environment: 'school',
  description: '学校区域地震，人员密集，需快速疏散'
});

CREATE (s:Scene {
  id: 'S_EQ_HOSPITAL', 
  name: '医院地震', 
  disaster_type: 'earthquake', 
  environment: 'hospital',
  description: '医院区域地震，需保障重症患者安全'
});

CREATE (s:Scene {
  id: 'S_EQ_SECONDARY_FIRE', 
  name: '地震次生火灾', 
  disaster_type: 'earthquake', 
  secondary_disaster: 'fire',
  description: '地震引发火灾，需同时处置地震和火灾'
});

CREATE (s:Scene {
  id: 'S_EQ_SECONDARY_HAZMAT', 
  name: '地震次生危化品泄漏', 
  disaster_type: 'earthquake', 
  secondary_disaster: 'hazmat',
  description: '地震导致危化品泄漏，需专业处置'
});

CREATE (s:Scene {
  id: 'S_EQ_SECONDARY_FLOOD', 
  name: '地震次生洪水', 
  disaster_type: 'earthquake', 
  secondary_disaster: 'flood',
  description: '地震损坏水利设施导致洪水'
});

// ---------- 洪水场景 (8个) ----------
CREATE (s:Scene {
  id: 'S_FLOOD_RIVER', 
  name: '河流洪水', 
  disaster_type: 'flood', 
  flood_type: 'river',
  description: '河流水位暴涨，沿岸区域受灾'
});

CREATE (s:Scene {
  id: 'S_FLOOD_URBAN', 
  name: '城市内涝', 
  disaster_type: 'flood', 
  flood_type: 'urban_waterlog',
  description: '暴雨导致城市排水不畅，低洼区域积水'
});

CREATE (s:Scene {
  id: 'S_FLOOD_FLASH', 
  name: '山洪暴发', 
  disaster_type: 'flood', 
  flood_type: 'flash_flood',
  description: '山区突发洪水，来势迅猛'
});

CREATE (s:Scene {
  id: 'S_FLOOD_DAM', 
  name: '溃坝洪水', 
  disaster_type: 'flood', 
  flood_type: 'dam_break',
  description: '水库大坝溃决导致洪水'
});

CREATE (s:Scene {
  id: 'S_FLOOD_COASTAL', 
  name: '风暴潮', 
  disaster_type: 'flood', 
  flood_type: 'storm_surge',
  description: '台风引发风暴潮，沿海区域受灾'
});

CREATE (s:Scene {
  id: 'S_FLOOD_TRAPPED_VEHICLE', 
  name: '车辆被困洪水', 
  disaster_type: 'flood', 
  scenario: 'vehicle_trapped',
  description: '车辆被洪水围困，人员需救援'
});

CREATE (s:Scene {
  id: 'S_FLOOD_TRAPPED_BUILDING', 
  name: '建筑被困洪水', 
  disaster_type: 'flood', 
  scenario: 'building_trapped',
  description: '人员被困在被洪水包围的建筑中'
});

CREATE (s:Scene {
  id: 'S_FLOOD_DEBRIS_FLOW', 
  name: '泥石流', 
  disaster_type: 'debris_flow',
  description: '山区暴雨引发泥石流'
});

// ---------- 火灾场景 (10个) ----------
CREATE (s:Scene {
  id: 'S_FIRE_RESIDENTIAL', 
  name: '住宅火灾', 
  disaster_type: 'fire', 
  fire_type: 'residential',
  description: '居民住宅发生火灾'
});

CREATE (s:Scene {
  id: 'S_FIRE_HIGHRISE', 
  name: '高层建筑火灾', 
  disaster_type: 'fire', 
  fire_type: 'highrise',
  description: '高层建筑火灾，疏散和灭火难度大'
});

CREATE (s:Scene {
  id: 'S_FIRE_INDUSTRIAL', 
  name: '工业厂房火灾', 
  disaster_type: 'fire', 
  fire_type: 'industrial',
  description: '工业厂房火灾，可能涉及危险品'
});

CREATE (s:Scene {
  id: 'S_FIRE_WAREHOUSE', 
  name: '仓库火灾', 
  disaster_type: 'fire', 
  fire_type: 'warehouse',
  description: '仓库火灾，物资损失风险大'
});

CREATE (s:Scene {
  id: 'S_FIRE_FOREST', 
  name: '森林火灾', 
  disaster_type: 'fire', 
  fire_type: 'forest',
  description: '森林火灾，蔓延快，扑救困难'
});

CREATE (s:Scene {
  id: 'S_FIRE_CHEMICAL', 
  name: '化学品火灾', 
  disaster_type: 'fire', 
  fire_type: 'chemical',
  description: '化学品引发火灾，需专业处置'
});

CREATE (s:Scene {
  id: 'S_FIRE_ELECTRICAL', 
  name: '电气火灾', 
  disaster_type: 'fire', 
  fire_type: 'electrical',
  description: '电气设备引发火灾'
});

CREATE (s:Scene {
  id: 'S_FIRE_VEHICLE', 
  name: '车辆火灾', 
  disaster_type: 'fire', 
  fire_type: 'vehicle',
  description: '车辆起火燃烧'
});

CREATE (s:Scene {
  id: 'S_FIRE_UNDERGROUND', 
  name: '地下空间火灾', 
  disaster_type: 'fire', 
  fire_type: 'underground',
  description: '地下车库、隧道等火灾，排烟困难'
});

CREATE (s:Scene {
  id: 'S_FIRE_CROWDED', 
  name: '人员密集场所火灾', 
  disaster_type: 'fire', 
  fire_type: 'crowded_place',
  description: '商场、影院等人员密集场所火灾'
});

// ---------- 危化品场景 (8个) ----------
CREATE (s:Scene {
  id: 'S_HAZMAT_LEAK_GAS', 
  name: '有毒气体泄漏', 
  disaster_type: 'hazmat', 
  hazmat_type: 'toxic_gas',
  description: '有毒气体泄漏，需疏散和洗消'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_LEAK_LIQUID', 
  name: '危险液体泄漏', 
  disaster_type: 'hazmat', 
  hazmat_type: 'liquid',
  description: '危险液体泄漏，需围堵和处置'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_EXPLOSION', 
  name: '危化品爆炸', 
  disaster_type: 'hazmat', 
  hazmat_type: 'explosion',
  description: '危化品发生爆炸'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_TRANSPORT', 
  name: '危化品运输事故', 
  disaster_type: 'hazmat', 
  hazmat_type: 'transport',
  description: '危化品运输车辆事故'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_RADIATION', 
  name: '放射性物质泄漏', 
  disaster_type: 'hazmat', 
  hazmat_type: 'radiation',
  description: '放射性物质泄漏，需专业防护'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_PIPELINE', 
  name: '管道泄漏', 
  disaster_type: 'hazmat', 
  hazmat_type: 'pipeline',
  description: '天然气或化工管道泄漏'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_STORAGE', 
  name: '储罐泄漏', 
  disaster_type: 'hazmat', 
  hazmat_type: 'storage_tank',
  description: '危化品储罐泄漏'
});

CREATE (s:Scene {
  id: 'S_HAZMAT_BIOLOGICAL', 
  name: '生物危害', 
  disaster_type: 'hazmat', 
  hazmat_type: 'biological',
  description: '生物制剂或病原体泄漏'
});

// ---------- 地质灾害场景 (6个) ----------
CREATE (s:Scene {
  id: 'S_GEO_LANDSLIDE', 
  name: '山体滑坡', 
  disaster_type: 'landslide',
  description: '山体滑坡掩埋道路或建筑'
});

CREATE (s:Scene {
  id: 'S_GEO_ROCKFALL', 
  name: '崩塌落石', 
  disaster_type: 'rockfall',
  description: '岩石崩落，威胁道路和人员安全'
});

CREATE (s:Scene {
  id: 'S_GEO_SUBSIDENCE', 
  name: '地面塌陷', 
  disaster_type: 'subsidence',
  description: '地面突然塌陷，可能吞噬车辆行人'
});

CREATE (s:Scene {
  id: 'S_GEO_MINE_COLLAPSE', 
  name: '矿井坍塌', 
  disaster_type: 'mine_collapse',
  description: '矿井发生坍塌，人员被困'
});

CREATE (s:Scene {
  id: 'S_GEO_MINE_GAS', 
  name: '矿井瓦斯', 
  disaster_type: 'mine_gas',
  description: '矿井瓦斯泄漏或爆炸'
});

CREATE (s:Scene {
  id: 'S_GEO_MINE_FLOOD', 
  name: '矿井透水', 
  disaster_type: 'mine_flood',
  description: '矿井发生透水事故'
});

// ---------- 交通事故场景 (6个) ----------
CREATE (s:Scene {
  id: 'S_TRAFFIC_HIGHWAY', 
  name: '高速公路事故', 
  disaster_type: 'traffic_accident', 
  road_type: 'highway',
  description: '高速公路发生重大交通事故'
});

CREATE (s:Scene {
  id: 'S_TRAFFIC_TUNNEL', 
  name: '隧道事故', 
  disaster_type: 'traffic_accident', 
  road_type: 'tunnel',
  description: '隧道内发生事故，救援空间受限'
});

CREATE (s:Scene {
  id: 'S_TRAFFIC_BRIDGE', 
  name: '桥梁事故', 
  disaster_type: 'traffic_accident', 
  road_type: 'bridge',
  description: '桥梁上发生事故或车辆坠桥'
});

CREATE (s:Scene {
  id: 'S_TRAFFIC_BUS', 
  name: '客车事故', 
  disaster_type: 'traffic_accident', 
  vehicle_type: 'bus',
  description: '客运车辆发生事故，人员伤亡多'
});

CREATE (s:Scene {
  id: 'S_TRAFFIC_TRAIN', 
  name: '列车事故', 
  disaster_type: 'traffic_accident', 
  vehicle_type: 'train',
  description: '列车脱轨或相撞事故'
});

CREATE (s:Scene {
  id: 'S_TRAFFIC_AIRCRAFT', 
  name: '航空事故', 
  disaster_type: 'traffic_accident', 
  vehicle_type: 'aircraft',
  description: '飞机失事或迫降'
});

// ---------- 气象灾害场景 (6个) ----------
CREATE (s:Scene {
  id: 'S_WEATHER_TYPHOON', 
  name: '台风', 
  disaster_type: 'typhoon',
  description: '台风登陆，狂风暴雨'
});

CREATE (s:Scene {
  id: 'S_WEATHER_TORNADO', 
  name: '龙卷风', 
  disaster_type: 'tornado',
  description: '龙卷风袭击，破坏力强'
});

CREATE (s:Scene {
  id: 'S_WEATHER_BLIZZARD', 
  name: '暴风雪', 
  disaster_type: 'blizzard',
  description: '暴风雪导致道路封闭，人员被困'
});

CREATE (s:Scene {
  id: 'S_WEATHER_HAIL', 
  name: '冰雹', 
  disaster_type: 'hail',
  description: '大冰雹袭击，损坏建筑车辆'
});

CREATE (s:Scene {
  id: 'S_WEATHER_LIGHTNING', 
  name: '雷击', 
  disaster_type: 'lightning',
  description: '雷击引发火灾或人员伤亡'
});

CREATE (s:Scene {
  id: 'S_WEATHER_HEATWAVE', 
  name: '高温热浪', 
  disaster_type: 'heatwave',
  description: '极端高温天气，中暑风险高'
});

// ---------- 建筑事故场景 (4个) ----------
CREATE (s:Scene {
  id: 'S_BUILDING_COLLAPSE', 
  name: '建筑倒塌', 
  disaster_type: 'building_collapse',
  description: '建筑结构失效导致倒塌'
});

CREATE (s:Scene {
  id: 'S_BUILDING_EXPLOSION', 
  name: '建筑爆炸', 
  disaster_type: 'explosion', 
  location: 'building',
  description: '建筑内发生爆炸'
});

CREATE (s:Scene {
  id: 'S_BUILDING_ELEVATOR', 
  name: '电梯困人', 
  disaster_type: 'elevator_trapped',
  description: '电梯故障导致人员被困'
});

CREATE (s:Scene {
  id: 'S_BUILDING_SCAFFOLD', 
  name: '脚手架坍塌', 
  disaster_type: 'scaffold_collapse',
  description: '建筑工地脚手架坍塌'
});

// ============================================================================
// 二、TaskChain任务链节点 (40+个)
// ============================================================================

// ---------- 通用任务链 (7个) ----------
CREATE (tc:TaskChain {
  id: 'TC_RECON', 
  name: '侦察评估链', 
  phase: 'reconnaissance',
  description: '灾情侦察和快速评估',
  typical_duration_hours: 2
});

CREATE (tc:TaskChain {
  id: 'TC_SEARCH', 
  name: '搜索定位链', 
  phase: 'search',
  description: '搜索和定位被困人员',
  typical_duration_hours: 6
});

CREATE (tc:TaskChain {
  id: 'TC_RESCUE', 
  name: '救援实施链', 
  phase: 'rescue',
  description: '实施救援行动',
  typical_duration_hours: 12
});

CREATE (tc:TaskChain {
  id: 'TC_MEDICAL', 
  name: '医疗救治链', 
  phase: 'medical',
  description: '伤员救治和转运',
  typical_duration_hours: 24
});

CREATE (tc:TaskChain {
  id: 'TC_EVAC', 
  name: '疏散安置链', 
  phase: 'evacuation',
  description: '人员疏散和临时安置',
  typical_duration_hours: 8
});

CREATE (tc:TaskChain {
  id: 'TC_SUPPORT', 
  name: '后勤保障链', 
  phase: 'support',
  description: '物资保障和后勤支援',
  typical_duration_hours: 72
});

CREATE (tc:TaskChain {
  id: 'TC_RECOVERY', 
  name: '恢复重建链', 
  phase: 'recovery',
  description: '灾后恢复和重建',
  typical_duration_hours: 720
});

// ---------- 地震专项任务链 (5个) ----------
CREATE (tc:TaskChain {
  id: 'TC_EQ_STRUCTURAL', 
  name: '结构救援链', 
  disaster_type: 'earthquake',
  phase: 'rescue',
  description: '建筑结构中救援被困人员'
});

CREATE (tc:TaskChain {
  id: 'TC_EQ_HEAVY', 
  name: '重型救援链', 
  disaster_type: 'earthquake',
  phase: 'rescue',
  description: '使用重型机械进行救援'
});

CREATE (tc:TaskChain {
  id: 'TC_EQ_SECONDARY', 
  name: '次生灾害处置链', 
  disaster_type: 'earthquake',
  phase: 'secondary',
  description: '处置地震次生灾害'
});

CREATE (tc:TaskChain {
  id: 'TC_EQ_AFTERSHOCK', 
  name: '余震监测链', 
  disaster_type: 'earthquake',
  phase: 'monitoring',
  description: '监测余震并预警'
});

CREATE (tc:TaskChain {
  id: 'TC_EQ_INFRASTRUCTURE', 
  name: '基础设施抢修链', 
  disaster_type: 'earthquake',
  phase: 'repair',
  description: '抢修道路、电力、通信等基础设施'
});

// ---------- 洪水专项任务链 (5个) ----------
CREATE (tc:TaskChain {
  id: 'TC_FLOOD_WATER_RESCUE', 
  name: '水域救援链', 
  disaster_type: 'flood',
  phase: 'rescue',
  description: '洪水中救援被困人员'
});

CREATE (tc:TaskChain {
  id: 'TC_FLOOD_DRAINAGE', 
  name: '排水抢险链', 
  disaster_type: 'flood',
  phase: 'engineering',
  description: '排除积水，恢复排水系统'
});

CREATE (tc:TaskChain {
  id: 'TC_FLOOD_DAM', 
  name: '堤防抢险链', 
  disaster_type: 'flood',
  phase: 'engineering',
  description: '加固堤防，防止溃堤'
});

CREATE (tc:TaskChain {
  id: 'TC_FLOOD_BOAT', 
  name: '舟艇转运链', 
  disaster_type: 'flood',
  phase: 'evacuation',
  description: '使用舟艇转移被困群众'
});

CREATE (tc:TaskChain {
  id: 'TC_FLOOD_DEBRIS', 
  name: '泥石流救援链', 
  disaster_type: 'debris_flow',
  phase: 'rescue',
  description: '泥石流灾害救援'
});

// ---------- 火灾专项任务链 (6个) ----------
CREATE (tc:TaskChain {
  id: 'TC_FIRE_SUPPRESS', 
  name: '火灾扑救链', 
  disaster_type: 'fire',
  phase: 'suppression',
  description: '扑灭火灾'
});

CREATE (tc:TaskChain {
  id: 'TC_FIRE_SEARCH', 
  name: '火场搜救链', 
  disaster_type: 'fire',
  phase: 'rescue',
  description: '火场中搜救被困人员'
});

CREATE (tc:TaskChain {
  id: 'TC_FIRE_VENT', 
  name: '排烟通风链', 
  disaster_type: 'fire',
  phase: 'support',
  description: '火场排烟和通风'
});

CREATE (tc:TaskChain {
  id: 'TC_FIRE_WATER', 
  name: '消防供水链', 
  disaster_type: 'fire',
  phase: 'support',
  description: '保障消防用水供应'
});

CREATE (tc:TaskChain {
  id: 'TC_FIRE_FOREST', 
  name: '森林灭火链', 
  disaster_type: 'fire',
  fire_type: 'forest',
  description: '森林火灾扑救'
});

CREATE (tc:TaskChain {
  id: 'TC_FIRE_HIGHRISE', 
  name: '高层灭火链', 
  disaster_type: 'fire',
  fire_type: 'highrise',
  description: '高层建筑火灾扑救'
});

// ---------- 危化品专项任务链 (5个) ----------
CREATE (tc:TaskChain {
  id: 'TC_HAZMAT_DETECT', 
  name: '危化品检测链', 
  disaster_type: 'hazmat',
  phase: 'detection',
  description: '检测危化品种类和浓度'
});

CREATE (tc:TaskChain {
  id: 'TC_HAZMAT_CONTAIN', 
  name: '危化品围堵链', 
  disaster_type: 'hazmat',
  phase: 'containment',
  description: '围堵泄漏的危化品'
});

CREATE (tc:TaskChain {
  id: 'TC_HAZMAT_DECON', 
  name: '洗消处置链', 
  disaster_type: 'hazmat',
  phase: 'decontamination',
  description: '人员和区域洗消'
});

CREATE (tc:TaskChain {
  id: 'TC_HAZMAT_TRANSFER', 
  name: '危化品转移链', 
  disaster_type: 'hazmat',
  phase: 'transfer',
  description: '安全转移危化品'
});

CREATE (tc:TaskChain {
  id: 'TC_HAZMAT_RADIATION', 
  name: '核辐射处置链', 
  disaster_type: 'hazmat',
  hazmat_type: 'radiation',
  description: '处置放射性物质泄漏'
});

// ---------- 矿山救援任务链 (4个) ----------
CREATE (tc:TaskChain {
  id: 'TC_MINE_VENTILATION', 
  name: '矿井通风链', 
  disaster_type: 'mine',
  phase: 'ventilation',
  description: '恢复矿井通风'
});

CREATE (tc:TaskChain {
  id: 'TC_MINE_DRILLING', 
  name: '生命通道钻探链', 
  disaster_type: 'mine',
  phase: 'drilling',
  description: '钻探生命通道输送物资'
});

CREATE (tc:TaskChain {
  id: 'TC_MINE_SUPPORT', 
  name: '巷道支护链', 
  disaster_type: 'mine',
  phase: 'support',
  description: '加固巷道防止二次坍塌'
});

CREATE (tc:TaskChain {
  id: 'TC_MINE_PUMP', 
  name: '矿井排水链', 
  disaster_type: 'mine',
  phase: 'pumping',
  description: '矿井透水事故排水'
});

// ---------- 交通事故任务链 (4个) ----------
CREATE (tc:TaskChain {
  id: 'TC_TRAFFIC_EXTRICATE', 
  name: '车辆救援链', 
  disaster_type: 'traffic',
  phase: 'extrication',
  description: '车辆中救出被困人员'
});

CREATE (tc:TaskChain {
  id: 'TC_TRAFFIC_TUNNEL', 
  name: '隧道救援链', 
  disaster_type: 'traffic',
  location: 'tunnel',
  description: '隧道内事故救援'
});

CREATE (tc:TaskChain {
  id: 'TC_TRAFFIC_CLEARANCE', 
  name: '道路清障链', 
  disaster_type: 'traffic',
  phase: 'clearance',
  description: '清除事故车辆恢复通行'
});

CREATE (tc:TaskChain {
  id: 'TC_TRAFFIC_CONTROL', 
  name: '交通管制链', 
  disaster_type: 'traffic',
  phase: 'control',
  description: '事故现场交通管制'
});

// ---------- 指挥协调任务链 (3个) ----------
CREATE (tc:TaskChain {
  id: 'TC_COMMAND', 
  name: '指挥协调链', 
  phase: 'command',
  description: '现场指挥和力量协调'
});

CREATE (tc:TaskChain {
  id: 'TC_COMM', 
  name: '通信保障链', 
  phase: 'communication',
  description: '保障现场通信畅通'
});

CREATE (tc:TaskChain {
  id: 'TC_INFO', 
  name: '信息发布链', 
  phase: 'information',
  description: '灾情信息收集和发布'
});

// ============================================================================
// 三、验证创建结果
// ============================================================================
MATCH (s:Scene) WHERE s.id IS NOT NULL RETURN 'Scene' as type, count(s) as count
UNION ALL
MATCH (tc:TaskChain) WHERE tc.id IS NOT NULL RETURN 'TaskChain' as type, count(tc) as count;
