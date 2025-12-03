// ============================================================================
// v46_fix_trr_rule_ids.cypher
// 为Neo4j TRRRule节点添加id字段
// ============================================================================

// 说明：Neo4j社区版不支持APOC，使用Python脚本执行更新
// 本文件记录ID分配规则：
//
// 灾害类型        | ID前缀      | 示例
// --------------|------------|------------------
// earthquake    | TRR-EQ     | TRR-EQ-001
// fire          | TRR-FIRE   | TRR-FIRE-001
// (空/通用)      | TRR-GEN    | TRR-GEN-001
// hazmat        | TRR-HAZ    | TRR-HAZ-001
// flood         | TRR-FLOOD  | TRR-FLOOD-001
// landslide     | TRR-LAND   | TRR-LAND-001
// traffic_accident | TRR-TRAF | TRR-TRAF-001
// mine_accident | TRR-MINE   | TRR-MINE-001
// typhoon       | TRR-TYP    | TRR-TYP-001
// aftershock    | TRR-AFTER  | TRR-AFTER-001
// dammed_lake   | TRR-DAM    | TRR-DAM-001
// debris_flow   | TRR-DEB    | TRR-DEB-001
// thunderstorm  | TRR-THUN   | TRR-THUN-001
// hail          | TRR-HAIL   | TRR-HAIL-001

// 验证查询
// MATCH (r:TRRRule) RETURN r.id, r.name, r.disaster_type ORDER BY r.id;
