// ============================================================================
// neo4j_metatask_aliases.cypher
// 为MetaTask节点添加aliases属性（任务名称别名）
// 用于scheme_parsing中的任务名称到ID映射
// ============================================================================

// EM01: 无人机广域侦察
MATCH (m:MetaTask {id: 'EM01'})
SET m.aliases = ['无人机侦察', '航拍侦察', '空中侦察'];

// EM02: 地震监测数据分析
MATCH (m:MetaTask {id: 'EM02'})
SET m.aliases = ['地震监测', '震情分析'];

// EM03: 建筑倒塌区域识别
MATCH (m:MetaTask {id: 'EM03'})
SET m.aliases = ['现场评估', '倒塌识别', '建筑评估'];

// EM04: 灾情快速评估
MATCH (m:MetaTask {id: 'EM04'})
SET m.aliases = ['灾情评估', '快速评估'];

// EM05: 次生灾害风险研判
MATCH (m:MetaTask {id: 'EM05'})
SET m.aliases = ['次生灾害研判', '风险研判'];

// EM06: 埋压人员生命探测
MATCH (m:MetaTask {id: 'EM06'})
SET m.aliases = ['生命探测', '埋压探测', '人员探测'];

// EM07: 救援力量调度
MATCH (m:MetaTask {id: 'EM07'})
SET m.aliases = ['力量调度', '救援调度'];

// EM08: 疏散路线规划
MATCH (m:MetaTask {id: 'EM08'})
SET m.aliases = ['路线规划', '疏散规划'];

// EM09: 群众疏散转移
MATCH (m:MetaTask {id: 'EM09'})
SET m.aliases = ['疏散群众', '群众转移', '人员疏散'];

// EM10: 被困人员救援
MATCH (m:MetaTask {id: 'EM10'})
SET m.aliases = ['被困人员救援', '人员搜救', '搜救'];

// EM11: 废墟挖掘与破拆
MATCH (m:MetaTask {id: 'EM11'})
SET m.aliases = ['废墟挖掘', '破拆作业', '挖掘破拆'];

// EM12: 搜救犬搜索
MATCH (m:MetaTask {id: 'EM12'})
SET m.aliases = ['搜救犬', '犬搜索'];

// EM13: 机器人狭小空间探测
MATCH (m:MetaTask {id: 'EM13'})
SET m.aliases = ['机器人探测', '狭小空间探测'];

// EM14: 伤员现场急救
MATCH (m:MetaTask {id: 'EM14'})
SET m.aliases = ['伤员急救', '医疗救治', '现场急救', '急救'];

// EM15: 伤员转运后送
MATCH (m:MetaTask {id: 'EM15'})
SET m.aliases = ['伤员转运', '后送', '转运'];

// EM16: 交通管制与道路抢通
MATCH (m:MetaTask {id: 'EM16'})
SET m.aliases = ['交通管制', '道路抢通', '交通疏导'];

// EM17: 燃气管网关阀
MATCH (m:MetaTask {id: 'EM17'})
SET m.aliases = ['燃气关阀', '管网关阀'];

// EM18: 电力切断与恢复
MATCH (m:MetaTask {id: 'EM18'})
SET m.aliases = ['电力切断', '电力恢复', '断电'];

// EM19: 消防灭火作业
MATCH (m:MetaTask {id: 'EM19'})
SET m.aliases = ['火灾扑救', '灭火', '消防作业', '灭火作业'];

// EM20: 危化品泄漏侦检
MATCH (m:MetaTask {id: 'EM20'})
SET m.aliases = ['危化品侦检', '泄漏侦检', '危化品检测'];

// EM21: 危化品堵漏处置
MATCH (m:MetaTask {id: 'EM21'})
SET m.aliases = ['危化品处置', '堵漏处置', '危化品堵漏'];

// EM22: 洗消去污作业
MATCH (m:MetaTask {id: 'EM22'})
SET m.aliases = ['洗消去污', '洗消作业'];

// EM23: 山洪泥石流预警监测
MATCH (m:MetaTask {id: 'EM23'})
SET m.aliases = ['山洪监测', '泥石流预警'];

// EM24: 危险建筑排查加固
MATCH (m:MetaTask {id: 'EM24'})
SET m.aliases = ['建筑排查', '建筑加固'];

// EM25: 临时安置点设置
MATCH (m:MetaTask {id: 'EM25'})
SET m.aliases = ['安置点设置', '临时安置'];

// EM26: 信息发布与预警广播
MATCH (m:MetaTask {id: 'EM26'})
SET m.aliases = ['信息发布', '预警广播'];

// EM27: 多部门协同指挥
MATCH (m:MetaTask {id: 'EM27'})
SET m.aliases = ['协同指挥', '联合指挥'];

// EM28: 应急物资调配
MATCH (m:MetaTask {id: 'EM28'})
SET m.aliases = ['物资配送', '物资调配', '应急物资'];

// EM29: 通信保障与恢复
MATCH (m:MetaTask {id: 'EM29'})
SET m.aliases = ['通信保障', '通信恢复'];

// EM30: 灾后评估与总结
MATCH (m:MetaTask {id: 'EM30'})
SET m.aliases = ['灾后评估', '总结评估'];

// EM31: 排涝抽水作业
MATCH (m:MetaTask {id: 'EM31'})
SET m.aliases = ['排涝抽水', '抽水作业'];

// EM32: 积水点监测与预警
MATCH (m:MetaTask {id: 'EM32'})
SET m.aliases = ['积水监测', '积水预警'];

// ============================================================================
// 特殊任务别名（原TASK_TYPE_MAPPING中的映射）
// 注意：部分原映射有误，已根据实际任务名称修正
// ============================================================================

// 心理援助 - 新增任务（如果没有对应MetaTask，需要创建）
// 现场警戒 - 新增任务
// 遗体处置 - 新增任务

// ============================================================================
// 验证
// ============================================================================
MATCH (m:MetaTask)
WHERE m.aliases IS NOT NULL
RETURN m.id, m.name, m.aliases
ORDER BY m.id;
