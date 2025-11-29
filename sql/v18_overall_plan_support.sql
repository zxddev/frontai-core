-- ============================================================================
-- 总体救灾方案支持表
-- 
-- 包含：
-- 1. task_reports_v2 - 任务执行报告表（支持多次上报）
-- 2. command_group_templates_v2 - 工作组模板配置表（基于国家预案）
-- 
-- 依据：《国家地震应急预案》国办函〔2025〕102号
-- ============================================================================

-- ============================================================================
-- 1. 任务执行报告表
-- 说明：支持救援队伍多次上报任务执行进展
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.task_reports_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联任务
    task_id UUID NOT NULL REFERENCES operational_v2.tasks_v2(id) ON DELETE CASCADE,
    
    -- ========== 上报类型 ==========
    -- progress: 进展报告（常规进度更新）
    -- completion: 完成报告（任务完成确认）
    -- incident: 突发情况（遇到意外/困难）
    -- resource_request: 资源请求（请求增援/物资）
    -- status_change: 状态变更（暂停/恢复等）
    report_type VARCHAR(50) NOT NULL,
    
    -- ========== 状态信息 ==========
    status VARCHAR(50) NOT NULL,                   -- 当前任务状态
    progress_percent INT,                          -- 完成百分比 0-100
    
    -- ========== 人员情况统计 ==========
    rescued_count INT DEFAULT 0,                   -- 本次报告期间救出人数
    casualties_found INT DEFAULT 0,                -- 本次报告期间发现遇难者
    injured_found INT DEFAULT 0,                   -- 本次报告期间发现伤员
    evacuated_count INT DEFAULT 0,                 -- 本次报告期间疏散人数
    
    -- ========== 资源情况 ==========
    -- 已消耗资源示例：{"饮用水": 50, "急救包": 10, "燃油": 100}
    resources_used JSONB DEFAULT '{}',
    -- 需要补充资源示例：{"救生衣": 20, "担架": 5}
    resources_needed JSONB DEFAULT '{}',
    
    -- ========== 现场情况 ==========
    field_conditions TEXT,                         -- 现场情况描述
    obstacles TEXT,                                -- 遇到的困难/障碍
    weather_impact TEXT,                           -- 天气影响
    
    -- ========== 位置信息 ==========
    current_location GEOMETRY(Point, 4326),        -- 当前位置坐标
    current_address TEXT,                          -- 当前位置描述
    
    -- ========== 附件 ==========
    attachments JSONB DEFAULT '[]',                -- 附件列表（照片、视频URL等）
    
    -- ========== 上报人信息 ==========
    reported_by UUID,                              -- 上报人ID
    reporter_name VARCHAR(200),                    -- 上报人姓名
    reporter_team VARCHAR(200),                    -- 上报队伍名称
    reporter_contact VARCHAR(100),                 -- 联系方式
    
    -- ========== 时间戳 ==========
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),-- 上报时间
    
    -- ========== 约束 ==========
    CONSTRAINT valid_progress CHECK (progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)),
    CONSTRAINT valid_rescued CHECK (rescued_count >= 0),
    CONSTRAINT valid_casualties CHECK (casualties_found >= 0),
    CONSTRAINT valid_injured CHECK (injured_found >= 0)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_task_reports_task ON operational_v2.task_reports_v2(task_id);
CREATE INDEX IF NOT EXISTS idx_task_reports_type ON operational_v2.task_reports_v2(report_type);
CREATE INDEX IF NOT EXISTS idx_task_reports_time ON operational_v2.task_reports_v2(reported_at DESC);

-- 注释
COMMENT ON TABLE operational_v2.task_reports_v2 IS '任务执行报告表 - 支持救援队伍多次上报任务进展';
COMMENT ON COLUMN operational_v2.task_reports_v2.report_type IS '上报类型: progress(进展)/completion(完成)/incident(突发)/resource_request(资源请求)/status_change(状态变更)';
COMMENT ON COLUMN operational_v2.task_reports_v2.resources_used IS '已消耗资源（JSON格式）';
COMMENT ON COLUMN operational_v2.task_reports_v2.resources_needed IS '需要补充资源（JSON格式）';

-- ============================================================================
-- 2. 工作组模板配置表
-- 说明：基于国家应急预案的工作组配置模板
-- 依据：《国家地震应急预案》国办函〔2025〕102号
-- ============================================================================

-- 创建config_v2 schema（如不存在）
CREATE SCHEMA IF NOT EXISTS config_v2;

CREATE TABLE IF NOT EXISTS config_v2.command_group_templates_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- ========== 适用条件 ==========
    disaster_type VARCHAR(50) NOT NULL,            -- 灾害类型: earthquake/flood/fire/landslide/all
    response_level VARCHAR(10) NOT NULL,           -- 响应级别: I/II/III/IV/all
    region_code VARCHAR(20),                       -- 地区代码（NULL表示通用配置）
    
    -- ========== 工作组信息 ==========
    group_code VARCHAR(50) NOT NULL,               -- 工作组编码
    group_name VARCHAR(100) NOT NULL,              -- 工作组名称
    group_name_en VARCHAR(200),                    -- 英文名称
    sort_order INT NOT NULL DEFAULT 0,             -- 显示排序
    
    -- ========== 职责与组成 ==========
    responsibilities TEXT,                          -- 主要职责描述
    lead_department VARCHAR(200) NOT NULL,         -- 牵头单位
    participating_units JSONB NOT NULL DEFAULT '[]', -- 参与单位列表
    
    -- ========== 联系方式模板 ==========
    contact_template JSONB DEFAULT '{}',           -- 联系方式模板
    
    -- ========== 状态与来源 ==========
    is_active BOOLEAN DEFAULT TRUE,                -- 是否启用
    reference VARCHAR(500),                        -- 依据文件
    
    -- ========== 审计字段 ==========
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- ========== 约束 ==========
    -- 注意：region_code可为NULL，使用唯一索引处理
    CONSTRAINT uq_command_group_template UNIQUE NULLS NOT DISTINCT (disaster_type, response_level, region_code, group_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_command_groups_lookup 
    ON config_v2.command_group_templates_v2(disaster_type, response_level, region_code);
CREATE INDEX IF NOT EXISTS idx_command_groups_active 
    ON config_v2.command_group_templates_v2(is_active) WHERE is_active = TRUE;

-- 注释
COMMENT ON TABLE config_v2.command_group_templates_v2 IS '工作组模板配置表 - 基于国家应急预案的工作组设置';
COMMENT ON COLUMN config_v2.command_group_templates_v2.disaster_type IS '灾害类型: earthquake(地震)/flood(洪涝)/fire(火灾)/landslide(滑坡)/all(通用)';
COMMENT ON COLUMN config_v2.command_group_templates_v2.response_level IS '响应级别: I(一级)/II(二级)/III(三级)/IV(四级)/all(通用)';
COMMENT ON COLUMN config_v2.command_group_templates_v2.group_code IS '工作组编码: coordination/rescue/medical/communication/traffic/monitoring/livelihood/security/publicity/military/reconstruction/foreign_affairs';
COMMENT ON COLUMN config_v2.command_group_templates_v2.lead_department IS '牵头单位';
COMMENT ON COLUMN config_v2.command_group_templates_v2.participating_units IS '参与单位列表（JSON数组）';
COMMENT ON COLUMN config_v2.command_group_templates_v2.reference IS '依据文件（如"国办函〔2025〕102号"）';

-- ============================================================================
-- 3. 预置国家标准12类工作组数据（一级响应）
-- 依据：《国家地震应急预案》国办函〔2025〕102号 第4.2.1.2节
-- ============================================================================
INSERT INTO config_v2.command_group_templates_v2 
(disaster_type, response_level, group_code, group_name, group_name_en, sort_order, lead_department, participating_units, responsibilities, reference)
VALUES 
-- 1. 综合协调组
('earthquake', 'I', 'coordination', '综合协调组', 'Coordination Group', 1, 
 '应急管理厅', 
 '["省政府办公厅", "省发展改革委", "省财政厅"]',
 '信息汇总和综合协调，发挥运转枢纽作用，统一协调各工作组行动',
 '国办函〔2025〕102号'),

-- 2. 抢险救援组
('earthquake', 'I', 'rescue', '抢险救援组', 'Search and Rescue Group', 2,
 '应急管理厅',
 '["省消防救援总队", "武警部队", "民兵组织", "社会救援力量"]',
 '派遣消防救援队伍、地震救援队伍、工程抢险队伍，组织搜救被困人员',
 '国办函〔2025〕102号'),

-- 3. 医疗防疫组
('earthquake', 'I', 'medical', '医疗防疫组', 'Medical and Epidemic Prevention Group', 3,
 '省卫生健康委',
 '["省疾病预防控制中心", "省红十字会", "各医疗机构"]',
 '组织医疗卫生救援、伤病员救治、卫生防疫、心理援助工作',
 '国办函〔2025〕102号'),

-- 4. 通信保障组
('earthquake', 'I', 'communication', '通信保障组', 'Communication Support Group', 4,
 '省工业和信息化厅',
 '["省通信管理局", "各通信运营商", "应急通信保障队"]',
 '组织抢修通信设施，协调应急通信资源，保障指挥通信畅通',
 '国办函〔2025〕102号'),

-- 5. 交通保障组
('earthquake', 'I', 'traffic', '交通保障组', 'Transportation Support Group', 5,
 '省交通运输厅',
 '["省公安厅交管局", "省民航局", "省铁路局", "省邮政管理局"]',
 '抢通修复交通基础设施，协调运力保障，实施交通管制',
 '国办函〔2025〕102号'),

-- 6. 地震监测和次生灾害防范处置组
('earthquake', 'I', 'monitoring', '地震监测和次生灾害防范处置组', 'Earthquake Monitoring and Secondary Disaster Prevention Group', 6,
 '省地震局',
 '["省自然资源厅", "省生态环境厅", "省水利厅", "省气象局"]',
 '布设地震观测设施，监视震情发展，排查次生灾害隐患，组织除险加固',
 '国办函〔2025〕102号'),

-- 7. 群众生活保障组
('earthquake', 'I', 'livelihood', '群众生活保障组', 'Public Livelihood Support Group', 7,
 '省应急管理厅',
 '["省民政厅", "省住房城乡建设厅", "省商务厅", "省粮食和储备局"]',
 '开放应急避难场所，组织调运救灾物资，保障群众基本生活需要',
 '国办函〔2025〕102号'),

-- 8. 社会治安组
('earthquake', 'I', 'security', '社会治安组', 'Public Security Group', 8,
 '省公安厅',
 '["省司法厅", "武警部队"]',
 '加强治安管理，打击违法犯罪，维护灾区社会秩序稳定',
 '国办函〔2025〕102号'),

-- 9. 新闻宣传组
('earthquake', 'I', 'publicity', '新闻宣传组', 'News and Publicity Group', 9,
 '省委宣传部',
 '["省广播电视局", "省政府新闻办", "各新闻媒体"]',
 '统一发布灾情信息，做好抗震救灾宣传报道，回应社会关切',
 '国办函〔2025〕102号'),

-- 10. 军队工作组
('earthquake', 'I', 'military', '军队工作组', 'Military Work Group', 10,
 '省军区',
 '["武警部队", "民兵预备役部队"]',
 '协调解放军、武警部队参与抢险救援，组织军地联合行动',
 '国办函〔2025〕102号'),

-- 11. 恢复重建组
('earthquake', 'I', 'reconstruction', '恢复重建组', 'Recovery and Reconstruction Group', 11,
 '省发展改革委',
 '["省住房城乡建设厅", "省财政厅", "省自然资源厅"]',
 '开展灾害调查评估，编制恢复重建规划，组织实施恢复重建',
 '国办函〔2025〕102号'),

-- 12. 涉外涉港澳台事务组
('earthquake', 'I', 'foreign_affairs', '涉外涉港澳台事务组', 'Foreign and HK/Macao/TW Affairs Group', 12,
 '省外事办',
 '["省台办", "省港澳办", "省商务厅"]',
 '协调国（境）外救援队入境，接收国际援助物资，处理涉外事务',
 '国办函〔2025〕102号')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. 二级响应工作组配置（精简版）
-- ============================================================================
INSERT INTO config_v2.command_group_templates_v2 
(disaster_type, response_level, group_code, group_name, sort_order, lead_department, participating_units, responsibilities, reference)
VALUES 
('earthquake', 'II', 'coordination', '综合协调组', 1, '应急管理厅', '["省政府办公厅"]', '信息汇总、综合协调', '国办函〔2025〕102号'),
('earthquake', 'II', 'rescue', '抢险救援组', 2, '应急管理厅', '["省消防救援总队", "民兵组织"]', '组织搜救被困人员', '国办函〔2025〕102号'),
('earthquake', 'II', 'medical', '医疗防疫组', 3, '省卫生健康委', '["各医疗机构"]', '组织医疗救治和卫生防疫', '国办函〔2025〕102号'),
('earthquake', 'II', 'communication', '通信保障组', 4, '省工业和信息化厅', '["各通信运营商"]', '保障应急通信', '国办函〔2025〕102号'),
('earthquake', 'II', 'traffic', '交通保障组', 5, '省交通运输厅', '["省公安厅交管局"]', '交通管制和运输保障', '国办函〔2025〕102号'),
('earthquake', 'II', 'livelihood', '群众生活保障组', 6, '省应急管理厅', '["省民政厅"]', '保障群众基本生活', '国办函〔2025〕102号'),
('earthquake', 'II', 'security', '社会治安组', 7, '省公安厅', '[]', '维护社会治安秩序', '国办函〔2025〕102号'),
('earthquake', 'II', 'publicity', '新闻宣传组', 8, '省委宣传部', '["省政府新闻办"]', '信息发布和舆论引导', '国办函〔2025〕102号')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 5. 更新触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION config_v2.update_command_groups_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_command_groups_updated ON config_v2.command_group_templates_v2;
CREATE TRIGGER tr_command_groups_updated
    BEFORE UPDATE ON config_v2.command_group_templates_v2
    FOR EACH ROW 
    EXECUTE FUNCTION config_v2.update_command_groups_timestamp();

-- ============================================================================
-- 6. 验证
-- ============================================================================
DO $$
DECLARE
    report_count INT;
    group_count INT;
BEGIN
    SELECT COUNT(*) INTO report_count FROM information_schema.tables 
    WHERE table_schema = 'operational_v2' AND table_name = 'task_reports_v2';
    
    SELECT COUNT(*) INTO group_count FROM config_v2.command_group_templates_v2;
    
    RAISE NOTICE '迁移完成: task_reports_v2表已创建, command_group_templates_v2表包含%条工作组配置', group_count;
END $$;
