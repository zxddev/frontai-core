#!/usr/bin/env python3
"""
应急救灾数据初始化脚本

初始化Neo4j知识图谱TRR规则和Qdrant案例数据。
"""
from __future__ import annotations

import sys
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def init_neo4j_rules() -> int:
    """初始化Neo4j TRR规则"""
    from neo4j import GraphDatabase
    
    logger.info("开始初始化Neo4j TRR规则...")
    
    driver = GraphDatabase.driver(
        'bolt://192.168.31.50:7687',
        auth=('neo4j', 'neo4jzmkj123456')
    )
    
    # 清理旧数据（可选）
    cleanup_queries = [
        "MATCH (n:TRRRule) DETACH DELETE n",
        "MATCH (n:Capability) DETACH DELETE n",
        "MATCH (n:TaskType) DETACH DELETE n",
        "MATCH (n:ResourceType) DETACH DELETE n",
    ]
    
    # 能力节点
    capability_queries = [
        # 搜救能力
        """CREATE (c:Capability {
            code: 'LIFE_DETECTION', name: '生命探测', category: 'search_rescue',
            description: '使用生命探测仪探测废墟下被困人员'
        })""",
        """CREATE (c:Capability {
            code: 'STRUCTURAL_RESCUE', name: '结构救援', category: 'search_rescue',
            description: '从倒塌建筑中营救被困人员'
        })""",
        # 医疗能力
        """CREATE (c:Capability {
            code: 'MEDICAL_TRIAGE', name: '医疗分诊', category: 'medical',
            description: '对伤员进行快速分诊分类'
        })""",
        """CREATE (c:Capability {
            code: 'EMERGENCY_TREATMENT', name: '紧急救治', category: 'medical',
            description: '现场紧急医疗救治'
        })""",
        """CREATE (c:Capability {
            code: 'PATIENT_TRANSPORT', name: '伤员转运', category: 'medical',
            description: '将伤员安全转运至医疗机构'
        })""",
        # 消防能力
        """CREATE (c:Capability {
            code: 'FIRE_SUPPRESSION', name: '火灾扑救', category: 'fire',
            description: '扑灭各类火灾'
        })""",
        """CREATE (c:Capability {
            code: 'FIRE_SEARCH_RESCUE', name: '火场搜救', category: 'fire',
            description: '在火灾现场搜救被困人员'
        })""",
        # 危化品能力
        """CREATE (c:Capability {
            code: 'HAZMAT_DETECTION', name: '危化品检测', category: 'hazmat',
            description: '检测识别危险化学品种类和浓度'
        })""",
        """CREATE (c:Capability {
            code: 'HAZMAT_CONTAINMENT', name: '危化品围堵', category: 'hazmat',
            description: '对泄漏危化品进行围堵控制'
        })""",
        # 疏散能力
        """CREATE (c:Capability {
            code: 'EVACUATION_COORDINATION', name: '疏散协调', category: 'evacuation',
            description: '组织协调人员安全疏散'
        })""",
        """CREATE (c:Capability {
            code: 'SHELTER_MANAGEMENT', name: '安置点管理', category: 'evacuation',
            description: '管理临时安置点'
        })""",
        # 工程能力
        """CREATE (c:Capability {
            code: 'ROAD_CLEARANCE', name: '道路抢通', category: 'engineering',
            description: '清除道路障碍恢复通行'
        })""",
    ]
    
    # 任务类型节点
    task_queries = [
        """CREATE (t:TaskType {
            code: 'SEARCH_RESCUE', name: '搜索救援', category: 'rescue',
            priority_default: 'critical', golden_hour: 72
        })""",
        """CREATE (t:TaskType {
            code: 'MEDICAL_EMERGENCY', name: '医疗急救', category: 'medical',
            priority_default: 'critical', golden_hour: 1
        })""",
        """CREATE (t:TaskType {
            code: 'FIRE_SUPPRESSION', name: '火灾扑救', category: 'fire',
            priority_default: 'critical', golden_hour: 0.5
        })""",
        """CREATE (t:TaskType {
            code: 'HAZMAT_RESPONSE', name: '危化品处置', category: 'hazmat',
            priority_default: 'critical', golden_hour: 2
        })""",
        """CREATE (t:TaskType {
            code: 'EVACUATION', name: '人员疏散', category: 'evacuation',
            priority_default: 'high', golden_hour: 4
        })""",
        """CREATE (t:TaskType {
            code: 'ROAD_CLEARANCE', name: '道路抢通', category: 'engineering',
            priority_default: 'high', golden_hour: 12
        })""",
        """CREATE (t:TaskType {
            code: 'SHELTER_SETUP', name: '安置点设立', category: 'evacuation',
            priority_default: 'high', golden_hour: 6
        })""",
    ]
    
    # 资源类型节点
    resource_queries = [
        """CREATE (rt:ResourceType {code: 'RESCUE_TEAM', name: '救援队', category: 'team', typical_size: 12})""",
        """CREATE (rt:ResourceType {code: 'MEDICAL_TEAM', name: '医疗队', category: 'team', typical_size: 8})""",
        """CREATE (rt:ResourceType {code: 'FIRE_TEAM', name: '消防队', category: 'team', typical_size: 10})""",
        """CREATE (rt:ResourceType {code: 'HAZMAT_TEAM', name: '危化品处置队', category: 'team', typical_size: 8})""",
        """CREATE (rt:ResourceType {code: 'ENGINEERING_TEAM', name: '工程抢险队', category: 'team', typical_size: 15})""",
        """CREATE (rt:ResourceType {code: 'EVACUATION_TEAM', name: '疏散引导队', category: 'team', typical_size: 6})""",
        """CREATE (rt:ResourceType {code: 'AMBULANCE', name: '救护车', category: 'vehicle'})""",
    ]
    
    # TRR规则节点
    trr_queries = [
        # TRR-EQ-001: 地震建筑搜救
        """CREATE (r:TRRRule {
            rule_id: 'TRR-EQ-001', name: '地震建筑搜救规则',
            description: '地震导致建筑倒塌且有被困人员时触发搜救任务',
            disaster_type: 'earthquake', priority: 'critical', weight: 0.95,
            trigger_conditions: ['has_building_collapse = true', 'has_trapped_persons = true'],
            trigger_logic: 'AND', is_active: true
        })""",
        # TRR-EQ-002: 地震次生火灾
        """CREATE (r:TRRRule {
            rule_id: 'TRR-EQ-002', name: '地震次生火灾规则',
            description: '地震引发火灾时触发消防任务',
            disaster_type: 'earthquake', priority: 'critical', weight: 0.90,
            trigger_conditions: ['has_secondary_fire = true'],
            trigger_logic: 'AND', is_active: true
        })""",
        # TRR-EQ-003: 地震危化品泄漏
        """CREATE (r:TRRRule {
            rule_id: 'TRR-EQ-003', name: '地震危化品泄漏规则',
            description: '地震导致危化品泄漏时触发应急处置',
            disaster_type: 'earthquake', priority: 'critical', weight: 0.92,
            trigger_conditions: ['has_hazmat_leak = true'],
            trigger_logic: 'AND', is_active: true
        })""",
        # TRR-EQ-004: 地震伤员救治
        """CREATE (r:TRRRule {
            rule_id: 'TRR-EQ-004', name: '地震伤员救治规则',
            description: '地震造成人员伤亡时触发医疗救治',
            disaster_type: 'earthquake', priority: 'critical', weight: 0.88,
            trigger_conditions: ['estimated_trapped > 0'],
            trigger_logic: 'AND', is_active: true
        })""",
        # TRR-EQ-005: 地震人员疏散
        """CREATE (r:TRRRule {
            rule_id: 'TRR-EQ-005', name: '地震人员疏散规则',
            description: '地震影响区域需要疏散时触发疏散任务',
            disaster_type: 'earthquake', priority: 'high', weight: 0.85,
            trigger_conditions: ['affected_population > 100'],
            trigger_logic: 'AND', is_active: true
        })""",
        # TRR-EQ-006: 地震道路抢通
        """CREATE (r:TRRRule {
            rule_id: 'TRR-EQ-006', name: '地震道路抢通规则',
            description: '地震导致道路中断时触发抢通任务',
            disaster_type: 'earthquake', priority: 'high', weight: 0.80,
            trigger_conditions: ['has_road_damage = true'],
            trigger_logic: 'AND', is_active: true
        })""",
    ]
    
    # 关系创建
    relation_queries = [
        # TRR-EQ-001 触发搜救和医疗
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (t:TaskType {code: 'SEARCH_RESCUE'})
           CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (t:TaskType {code: 'MEDICAL_EMERGENCY'})
           CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 2}]->(t)""",
        # TRR-EQ-001 需要的能力
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (c:Capability {code: 'LIFE_DETECTION'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (c:Capability {code: 'STRUCTURAL_RESCUE'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-001'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c)""",
        
        # TRR-EQ-002 触发消防
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-002'}), (t:TaskType {code: 'FIRE_SUPPRESSION'})
           CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-002'}), (c:Capability {code: 'FIRE_SUPPRESSION'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        
        # TRR-EQ-003 触发危化品处置和疏散
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (t:TaskType {code: 'HAZMAT_RESPONSE'})
           CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (t:TaskType {code: 'EVACUATION'})
           CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 2}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (c:Capability {code: 'HAZMAT_DETECTION'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-003'}), (c:Capability {code: 'HAZMAT_CONTAINMENT'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        
        # TRR-EQ-004 触发医疗
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (t:TaskType {code: 'MEDICAL_EMERGENCY'})
           CREATE (r)-[:TRIGGERS {priority: 'critical', sequence: 1}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-004'}), (c:Capability {code: 'EMERGENCY_TREATMENT'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'critical'}]->(c)""",
        
        # TRR-EQ-005 触发疏散
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (t:TaskType {code: 'EVACUATION'})
           CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 1}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (t:TaskType {code: 'SHELTER_SETUP'})
           CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 2}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-005'}), (c:Capability {code: 'EVACUATION_COORDINATION'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c)""",
        
        # TRR-EQ-006 触发道路抢通
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-006'}), (t:TaskType {code: 'ROAD_CLEARANCE'})
           CREATE (r)-[:TRIGGERS {priority: 'high', sequence: 1}]->(t)""",
        """MATCH (r:TRRRule {rule_id: 'TRR-EQ-006'}), (c:Capability {code: 'ROAD_CLEARANCE'})
           CREATE (r)-[:REQUIRES_CAPABILITY {priority: 'high'}]->(c)""",
        
        # 能力-资源映射
        """MATCH (c:Capability {code: 'LIFE_DETECTION'}), (rt:ResourceType {code: 'RESCUE_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'STRUCTURAL_RESCUE'}), (rt:ResourceType {code: 'RESCUE_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'MEDICAL_TRIAGE'}), (rt:ResourceType {code: 'MEDICAL_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'EMERGENCY_TREATMENT'}), (rt:ResourceType {code: 'MEDICAL_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'PATIENT_TRANSPORT'}), (rt:ResourceType {code: 'AMBULANCE'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'FIRE_SUPPRESSION'}), (rt:ResourceType {code: 'FIRE_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'HAZMAT_DETECTION'}), (rt:ResourceType {code: 'HAZMAT_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'HAZMAT_CONTAINMENT'}), (rt:ResourceType {code: 'HAZMAT_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'EVACUATION_COORDINATION'}), (rt:ResourceType {code: 'EVACUATION_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        """MATCH (c:Capability {code: 'ROAD_CLEARANCE'}), (rt:ResourceType {code: 'ENGINEERING_TEAM'})
           CREATE (c)-[:PROVIDED_BY]->(rt)""",
        
        # 任务-能力映射
        """MATCH (t:TaskType {code: 'SEARCH_RESCUE'}), (c:Capability {code: 'LIFE_DETECTION'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        """MATCH (t:TaskType {code: 'SEARCH_RESCUE'}), (c:Capability {code: 'STRUCTURAL_RESCUE'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        """MATCH (t:TaskType {code: 'MEDICAL_EMERGENCY'}), (c:Capability {code: 'MEDICAL_TRIAGE'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        """MATCH (t:TaskType {code: 'FIRE_SUPPRESSION'}), (c:Capability {code: 'FIRE_SUPPRESSION'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        """MATCH (t:TaskType {code: 'HAZMAT_RESPONSE'}), (c:Capability {code: 'HAZMAT_DETECTION'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        """MATCH (t:TaskType {code: 'EVACUATION'}), (c:Capability {code: 'EVACUATION_COORDINATION'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        """MATCH (t:TaskType {code: 'ROAD_CLEARANCE'}), (c:Capability {code: 'ROAD_CLEARANCE'})
           CREATE (t)-[:REQUIRES {is_critical: true}]->(c)""",
        
        # 任务依赖
        """MATCH (t1:TaskType {code: 'MEDICAL_EMERGENCY'}), (t2:TaskType {code: 'SEARCH_RESCUE'})
           CREATE (t1)-[:DEPENDS_ON {is_strict: false, description: '救出伤员后进行医疗救治'}]->(t2)""",
        """MATCH (t1:TaskType {code: 'SHELTER_SETUP'}), (t2:TaskType {code: 'EVACUATION'})
           CREATE (t1)-[:DEPENDS_ON {is_strict: true, description: '疏散人员后设立安置点'}]->(t2)""",
    ]
    
    success_count = 0
    error_count = 0
    
    with driver.session() as session:
        # 清理
        logger.info("清理旧数据...")
        for query in cleanup_queries:
            try:
                session.run(query)
            except Exception as e:
                pass  # 忽略清理错误
        
        # 创建能力
        logger.info("创建能力节点...")
        for query in capability_queries:
            try:
                session.run(query)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"能力创建失败: {e}")
        
        # 创建任务类型
        logger.info("创建任务类型节点...")
        for query in task_queries:
            try:
                session.run(query)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"任务类型创建失败: {e}")
        
        # 创建资源类型
        logger.info("创建资源类型节点...")
        for query in resource_queries:
            try:
                session.run(query)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"资源类型创建失败: {e}")
        
        # 创建TRR规则
        logger.info("创建TRR规则节点...")
        for query in trr_queries:
            try:
                session.run(query)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"TRR规则创建失败: {e}")
        
        # 创建关系
        logger.info("创建关系...")
        for query in relation_queries:
            try:
                session.run(query)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"关系创建失败: {e}")
        
        # 验证
        result = session.run("MATCH (r:TRRRule) RETURN count(r) as count")
        trr_count = result.single()["count"]
        
        result = session.run("MATCH (c:Capability) RETURN count(c) as count")
        cap_count = result.single()["count"]
        
        result = session.run("MATCH (t:TaskType) RETURN count(t) as count")
        task_count = result.single()["count"]
    
    driver.close()
    
    logger.info(f"Neo4j初始化完成: TRR规则={trr_count}, 能力={cap_count}, 任务类型={task_count}")
    logger.info(f"成功: {success_count}, 失败: {error_count}")
    
    return trr_count


def init_qdrant_cases() -> int:
    """初始化Qdrant案例数据"""
    logger.info("开始初始化Qdrant案例数据...")
    
    # 地震救灾典型案例
    cases: List[Dict[str, Any]] = [
        {
            "case_id": "CASE-EQ-2022-LUDING",
            "title": "2022年四川泸定6.8级地震救援",
            "disaster_type": "earthquake",
            "description": "2022年9月5日四川泸定发生6.8级地震，震源深度16公里，造成多栋建筑倒塌，93人遇难。救援队伍第一时间集结，使用生命探测仪搜救被困人员，72小时内完成主要搜救任务。",
            "lessons_learned": [
                "震后道路中断严重影响救援效率，需提前规划空中救援通道",
                "通信中断导致指挥调度困难，需部署卫星通信保障",
                "高海拔地区救援人员体能消耗大，需做好轮换安排"
            ],
            "best_practices": [
                "第一时间启动应急响应，各救援力量快速集结",
                "使用无人机进行灾情侦察和物资投送",
                "建立前线指挥部统一协调救援力量",
                "72小时黄金救援期内持续搜救不间断"
            ],
        },
        {
            "case_id": "CASE-EQ-2023-JISHISHAN",
            "title": "2023年甘肃积石山6.2级地震救援",
            "disaster_type": "earthquake",
            "description": "2023年12月18日甘肃积石山发生6.2级地震，震源深度10公里，造成甘肃青海两省重大人员伤亡。低温天气给救援带来极大挑战，需同时做好伤员救治和受灾群众保暖工作。",
            "lessons_learned": [
                "冬季地震救援需特别关注低温防护",
                "农村房屋抗震能力弱是伤亡的主要原因",
                "跨省协调救援需要更高层级的统一指挥"
            ],
            "best_practices": [
                "迅速调运棉帐篷、取暖设备等御寒物资",
                "设立多个临时安置点分散安置受灾群众",
                "医疗队随救援队同步进入灾区",
                "启动跨省应急支援机制"
            ],
        },
        {
            "case_id": "CASE-EQ-2008-WENCHUAN",
            "title": "2008年四川汶川8.0级地震救援",
            "disaster_type": "earthquake",
            "description": "2008年5月12日四川汶川发生8.0级特大地震，是新中国成立以来破坏性最强的地震。造成近7万人遇难，数十万人受伤，直接经济损失8000多亿元。此次救援是我国历史上规模最大的灾害救援行动。",
            "lessons_learned": [
                "特大地震后交通生命线中断是救援最大障碍",
                "次生灾害（堰塞湖、滑坡）威胁巨大需持续监测",
                "大规模伤员救治需要建立分级诊疗体系",
                "灾后心理疏导同样重要"
            ],
            "best_practices": [
                "空降兵第一时间空降震中侦察灾情",
                "工兵部队抢修生命通道",
                "全国支援形成统一调度机制",
                "建立唐家山堰塞湖排险指挥部"
            ],
        },
        {
            "case_id": "CASE-EQ-BUILDING-COLLAPSE",
            "title": "建筑倒塌搜救标准流程",
            "disaster_type": "earthquake",
            "description": "地震导致建筑倒塌后的标准搜救流程，包括现场侦察、生命探测、安全支撑、破拆救援、医疗急救等环节。强调安全第一，避免二次伤害。",
            "lessons_learned": [
                "盲目施救可能导致建筑进一步坍塌",
                "被困人员位置判断需综合多种探测手段",
                "长时间被困人员救出后需注意挤压综合征"
            ],
            "best_practices": [
                "先侦察评估再施救，确保救援人员安全",
                "使用音频探测、视频探测、雷达探测等多手段定位",
                "破拆前做好支撑防护",
                "救出被困人员后立即进行医疗评估"
            ],
        },
        {
            "case_id": "CASE-EQ-SECONDARY-FIRE",
            "title": "地震次生火灾处置",
            "disaster_type": "earthquake",
            "description": "地震可能导致燃气泄漏、电气短路等引发火灾。震后火灾处置需同时考虑建筑受损情况，防止消防作业导致建筑进一步坍塌。",
            "lessons_learned": [
                "震后燃气管道破损是火灾主要隐患",
                "消防用水可能因管网破损无法保障",
                "受损建筑灭火作业风险极高"
            ],
            "best_practices": [
                "第一时间关闭区域燃气总阀",
                "优先使用泡沫灭火减少用水",
                "评估建筑稳定性后再进入灭火",
                "设置警戒区防止无关人员进入"
            ],
        },
        {
            "case_id": "CASE-EQ-HAZMAT-LEAK",
            "title": "地震危化品泄漏应急处置",
            "disaster_type": "earthquake",
            "description": "地震可能导致化工厂、加油站、危险品仓库等发生泄漏。需要专业危化品处置队伍进行检测、围堵和处置，同时组织下风向人员紧急疏散。",
            "lessons_learned": [
                "危化品泄漏扩散速度快，必须第一时间疏散",
                "不同化学品处置方法不同，需专业人员判断",
                "洗消设备和个人防护装备必须充足"
            ],
            "best_practices": [
                "立即设立警戒区并疏散周边群众",
                "使用检测设备确定泄漏物质种类",
                "根据泄漏物质选择合适的围堵方法",
                "处置人员必须穿戴全套防护装备"
            ],
        },
        {
            "case_id": "CASE-EQ-EVACUATION",
            "title": "地震后大规模人员疏散",
            "disaster_type": "earthquake",
            "description": "强震后需要组织危险建筑内人员和次生灾害威胁区域人员紧急疏散。疏散工作需要提前规划疏散路线、安置点和物资保障。",
            "lessons_learned": [
                "恐慌情绪可能导致踩踏等二次伤害",
                "特殊人群（老人、儿童、伤病员）需重点照顾",
                "安置点选址需避开次生灾害风险区"
            ],
            "best_practices": [
                "通过广播、喊话等多渠道发布疏散指令",
                "设置引导员指引疏散方向",
                "优先疏散危险建筑和次生灾害威胁区",
                "安置点提前储备食物、饮水、帐篷等物资"
            ],
        },
        {
            "case_id": "CASE-EQ-ROAD-REPAIR",
            "title": "地震后道路抢通",
            "disaster_type": "earthquake",
            "description": "地震导致道路塌方、桥梁损毁，严重影响救援力量进入和物资运输。道路抢通是灾后应急救援的生命线工程。",
            "lessons_learned": [
                "主要道路优先抢通，次要道路可临时绕行",
                "余震可能导致抢通道路再次中断",
                "重型机械调运需要提前规划"
            ],
            "best_practices": [
                "优先抢通连接震中的主要道路",
                "设置应急便道绕过严重损毁路段",
                "安排专人监测道路沿线地质情况",
                "重型机械24小时不间断作业"
            ],
        },
    ]
    
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance, PointStruct
        from langchain_openai import OpenAIEmbeddings
        from dotenv import load_dotenv
        
        # 加载环境变量
        import os
        os.chdir('/home/dev/gitcode/frontai/frontai-core')
        load_dotenv('/home/dev/gitcode/frontai/frontai-core/.env')
        
        qdrant_url = os.environ.get('QDRANT_URL', 'http://192.168.31.50:6333')
        qdrant_api_key = os.environ.get('QDRANT_API_KEY', '')
        embedding_base_url = os.environ.get('EMBEDDING_BASE_URL', 'http://192.168.31.50:8001/v1')
        embedding_model = os.environ.get('EMBEDDING_MODEL', 'embedding-3')
        embedding_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
        
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key if qdrant_api_key else None,
        )
        
        embeddings = OpenAIEmbeddings(
            model=embedding_model,
            base_url=embedding_base_url,
            api_key=embedding_api_key,
        )
        
        collection_name = "emergency_cases"
        
        # 检查并创建集合
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if collection_name in collection_names:
            logger.info(f"删除已有集合 {collection_name}")
            client.delete_collection(collection_name)
        
        # 获取向量维度
        test_vector = embeddings.embed_query("test")
        vector_size = len(test_vector)
        
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"创建集合 {collection_name}，向量维度: {vector_size}")
        
        # 导入案例
        points = []
        for i, case in enumerate(cases):
            search_text = f"{case['title']} {case['description']}"
            vector = embeddings.embed_query(search_text)
            
            point = PointStruct(
                id=i + 1,
                vector=vector,
                payload={
                    "case_id": case["case_id"],
                    "title": case["title"],
                    "disaster_type": case["disaster_type"],
                    "description": case["description"],
                    "lessons_learned": case["lessons_learned"],
                    "best_practices": case["best_practices"],
                },
            )
            points.append(point)
            logger.info(f"向量化案例: {case['case_id']}")
        
        client.upsert(
            collection_name=collection_name,
            points=points,
        )
        
        logger.info(f"Qdrant案例导入完成: {len(points)} 条")
        return len(points)
        
    except Exception as e:
        logger.error(f"Qdrant初始化失败: {e}")
        return 0


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始初始化应急救灾数据")
    logger.info("=" * 60)
    
    # 初始化Neo4j
    trr_count = init_neo4j_rules()
    
    # 初始化Qdrant
    case_count = init_qdrant_cases()
    
    logger.info("=" * 60)
    logger.info(f"初始化完成！TRR规则: {trr_count}, 案例: {case_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
