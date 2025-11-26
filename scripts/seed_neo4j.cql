// 创建基础场景与规则节点及关联
MERGE (s1:Scene {id:"S1", name:"隐身空战"})
MERGE (s2:Scene {id:"S2", name:"常规空战"})
MERGE (s3:Scene {id:"S3", name:"对海突击"})
MERGE (s4:Scene {id:"S4", name:"防空压制"})

MERGE (r1:Rule {id:"R-001", name:"反隐身空战"})
MERGE (r2:Rule {id:"R-002", name:"电子诱骗"})
MERGE (r4:Rule {id:"R-004", name:"对海饱和攻击"})
MERGE (r5:Rule {id:"R-005", name:"防空压制"})
MERGE (r6:Rule {id:"R-006", name:"预警机引导"})

// 绑定场景-规则关系
MERGE (s1)-[:HAS_RULE]->(r1)
MERGE (s1)-[:HAS_RULE]->(r2)
MERGE (s2)-[:HAS_RULE]->(r6)
MERGE (s3)-[:HAS_RULE]->(r4)
MERGE (s4)-[:HAS_RULE]->(r5)

// 绑定规则描述，便于查询
SET r1.description = "隐身目标，诱骗开机后远程打击"
SET r2.description = "无人诱饵前出引导雷达暴露"
SET r4.description = "防区外多轴向饱和攻击驱护舰"
SET r5.description = "诱饵前出+反辐射压制地面防空"
SET r6.description = "预警机远程搜索与分发"
