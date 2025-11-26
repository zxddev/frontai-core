-- ============================================================================
-- V2 对话与消息模型 (v2_conversation_message_model.sql)
-- AI对话、指挥消息
-- ============================================================================

-- ============================================================================
-- 枚举类型定义
-- ============================================================================

-- 对话类型
CREATE TYPE conversation_type_v2 AS ENUM (
    'general',             -- 通用对话
    'event_analysis',      -- 事件分析
    'scheme_generation',   -- 方案生成
    'resource_query',      -- 资源查询
    'situation_report',    -- 态势汇报
    'decision_support'     -- 决策支持
);

-- 消息角色
CREATE TYPE message_role_v2 AS ENUM (
    'user',                -- 用户
    'assistant',           -- AI助手
    'system'               -- 系统
);

-- 消息内容类型
CREATE TYPE content_type_v2 AS ENUM (
    'text',                -- 纯文本
    'markdown',            -- Markdown格式
    'json',                -- JSON数据
    'action',              -- 动作消息
    'image',               -- 图片
    'file',                -- 文件
    'location',            -- 位置
    'event_card',          -- 事件卡片
    'scheme_card',         -- 方案卡片
    'resource_list'        -- 资源列表
);

-- 指挥消息类型
CREATE TYPE command_message_type_v2 AS ENUM (
    'order',               -- 命令
    'report',              -- 报告
    'request',             -- 请求
    'notification',        -- 通知
    'alert',               -- 警报
    'acknowledgment',      -- 确认
    'inquiry',             -- 询问
    'response'             -- 回复
);

-- 消息优先级
CREATE TYPE message_priority_v2 AS ENUM (
    'urgent',              -- 紧急
    'high',                -- 高
    'normal',              -- 普通
    'low'                  -- 低
);

-- 接收者类型
CREATE TYPE recipient_type_v2 AS ENUM (
    'broadcast',           -- 广播(所有人)
    'role',                -- 按角色
    'user',                -- 指定用户
    'team',                -- 指定队伍
    'group'                -- 指定群组
);

-- ============================================================================
-- AI对话表 conversations_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversations_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定
    scenario_id UUID,
    
    -- 对话所属用户
    user_id UUID NOT NULL,
    
    -- 对话类型
    conversation_type conversation_type_v2 NOT NULL DEFAULT 'general',
    
    -- 对话标题
    title VARCHAR(500),
    
    -- 关联事件 (如果是事件相关对话)
    context_event_id UUID,
    
    -- 关联方案 (如果是方案相关对话)
    context_scheme_id UUID,
    
    -- 关联任务 (如果是任务相关对话)
    context_task_id UUID,
    
    -- 对话状态
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active/archived/deleted
    
    -- 是否固定/收藏
    is_pinned BOOLEAN DEFAULT false,
    
    -- 消息数量
    message_count INTEGER NOT NULL DEFAULT 0,
    
    -- token消耗统计
    total_tokens_used INTEGER DEFAULT 0,
    
    -- 系统提示词 (对话上下文)
    system_prompt TEXT,
    
    -- 对话元数据
    metadata JSONB DEFAULT '{}',
    
    -- 最后消息时间
    last_message_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_conversations_v2_user ON conversations_v2(user_id);
CREATE INDEX idx_conversations_v2_scenario ON conversations_v2(scenario_id) WHERE scenario_id IS NOT NULL;
CREATE INDEX idx_conversations_v2_event ON conversations_v2(context_event_id) WHERE context_event_id IS NOT NULL;
CREATE INDEX idx_conversations_v2_scheme ON conversations_v2(context_scheme_id) WHERE context_scheme_id IS NOT NULL;
CREATE INDEX idx_conversations_v2_type ON conversations_v2(conversation_type);
CREATE INDEX idx_conversations_v2_active ON conversations_v2(user_id, last_message_at DESC) WHERE status = 'active';

-- ============================================================================
-- 对话消息表 conversation_messages_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversation_messages_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属对话
    conversation_id UUID NOT NULL REFERENCES conversations_v2(id) ON DELETE CASCADE,
    
    -- 消息序号 (对话内排序)
    sequence_no INTEGER NOT NULL,
    
    -- 消息角色
    role message_role_v2 NOT NULL,
    
    -- 消息内容
    content TEXT NOT NULL,
    
    -- 内容类型
    content_type content_type_v2 NOT NULL DEFAULT 'text',
    
    -- 附件
    attachments JSONB DEFAULT '[]',
    -- [{ type, url, name, size, preview_url }]
    
    -- 如果是动作消息
    action_type VARCHAR(100), -- generate_scheme/dispatch_task/query_resource/analyze_event
    action_payload JSONB,     -- 动作参数
    action_result JSONB,      -- 动作执行结果
    action_status VARCHAR(50), -- pending/executing/completed/failed
    
    -- 引用的消息ID (回复某条消息)
    reply_to_message_id UUID REFERENCES conversation_messages_v2(id),
    
    -- AI相关
    model_used VARCHAR(100),  -- 使用的模型
    tokens_input INTEGER,     -- 输入token数
    tokens_output INTEGER,    -- 输出token数
    processing_time_ms INTEGER, -- 处理耗时
    
    -- 用户反馈
    user_feedback VARCHAR(50), -- good/bad/null
    feedback_comment TEXT,
    
    -- 是否已读
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(conversation_id, sequence_no)
);

-- 索引
CREATE INDEX idx_conv_messages_v2_conversation ON conversation_messages_v2(conversation_id, sequence_no);
CREATE INDEX idx_conv_messages_v2_role ON conversation_messages_v2(role);
CREATE INDEX idx_conv_messages_v2_action ON conversation_messages_v2(action_type) WHERE action_type IS NOT NULL;
CREATE INDEX idx_conv_messages_v2_time ON conversation_messages_v2(created_at);

-- ============================================================================
-- 指挥消息表 command_messages_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS command_messages_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定
    scenario_id UUID NOT NULL,
    
    -- 发送者
    sender_id UUID NOT NULL,
    sender_name VARCHAR(200),
    sender_role VARCHAR(100), -- 发送者席位角色
    
    -- 接收者类型
    recipient_type recipient_type_v2 NOT NULL,
    
    -- 接收者ID (根据类型不同含义不同)
    recipient_id UUID,
    
    -- 接收者角色 (如果是按角色发送)
    recipient_role VARCHAR(100),
    
    -- 消息类型
    message_type command_message_type_v2 NOT NULL,
    
    -- 优先级
    priority message_priority_v2 NOT NULL DEFAULT 'normal',
    
    -- 消息主题
    subject VARCHAR(500),
    
    -- 消息内容
    content TEXT NOT NULL,
    
    -- 附件
    attachments JSONB DEFAULT '[]',
    
    -- 关联事件
    related_event_id UUID,
    
    -- 关联方案
    related_scheme_id UUID,
    
    -- 关联任务
    related_task_id UUID,
    
    -- 是否需要确认
    requires_acknowledgment BOOLEAN DEFAULT false,
    
    -- 确认截止时间
    acknowledgment_deadline TIMESTAMPTZ,
    
    -- 回复的消息ID
    reply_to_message_id UUID REFERENCES command_messages_v2(id),
    
    -- 消息状态
    status VARCHAR(50) NOT NULL DEFAULT 'sent', -- draft/sent/delivered/read/acknowledged/expired
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_cmd_messages_v2_scenario ON command_messages_v2(scenario_id);
CREATE INDEX idx_cmd_messages_v2_sender ON command_messages_v2(sender_id);
CREATE INDEX idx_cmd_messages_v2_recipient ON command_messages_v2(recipient_type, recipient_id);
CREATE INDEX idx_cmd_messages_v2_type ON command_messages_v2(message_type);
CREATE INDEX idx_cmd_messages_v2_priority ON command_messages_v2(priority);
CREATE INDEX idx_cmd_messages_v2_event ON command_messages_v2(related_event_id) WHERE related_event_id IS NOT NULL;
CREATE INDEX idx_cmd_messages_v2_time ON command_messages_v2(created_at DESC);
CREATE INDEX idx_cmd_messages_v2_unack ON command_messages_v2(acknowledgment_deadline) 
    WHERE requires_acknowledgment = true AND status != 'acknowledged';

-- ============================================================================
-- 消息接收记录表 message_receipts_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS message_receipts_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 消息ID
    message_id UUID NOT NULL REFERENCES command_messages_v2(id) ON DELETE CASCADE,
    
    -- 接收者ID
    recipient_id UUID NOT NULL,
    
    -- 接收者名称
    recipient_name VARCHAR(200),
    
    -- 送达时间
    delivered_at TIMESTAMPTZ,
    
    -- 阅读时间
    read_at TIMESTAMPTZ,
    
    -- 确认时间
    acknowledged_at TIMESTAMPTZ,
    
    -- 确认内容
    acknowledgment_content TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(message_id, recipient_id)
);

-- 索引
CREATE INDEX idx_msg_receipts_v2_message ON message_receipts_v2(message_id);
CREATE INDEX idx_msg_receipts_v2_recipient ON message_receipts_v2(recipient_id);
CREATE INDEX idx_msg_receipts_v2_unread ON message_receipts_v2(recipient_id) WHERE read_at IS NULL;

-- ============================================================================
-- 触发器：更新对话统计
-- ============================================================================
CREATE OR REPLACE FUNCTION update_conversation_stats_v2()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversations_v2 
        SET message_count = message_count + 1,
            last_message_at = NEW.created_at,
            total_tokens_used = total_tokens_used + COALESCE(NEW.tokens_input, 0) + COALESCE(NEW.tokens_output, 0),
            updated_at = NOW()
        WHERE id = NEW.conversation_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_conv_messages_v2_stats ON conversation_messages_v2;
CREATE TRIGGER tr_conv_messages_v2_stats
    AFTER INSERT ON conversation_messages_v2
    FOR EACH ROW EXECUTE FUNCTION update_conversation_stats_v2();

-- ============================================================================
-- 触发器：更新对话时间戳
-- ============================================================================
DROP TRIGGER IF EXISTS tr_conversations_v2_updated ON conversations_v2;
CREATE TRIGGER tr_conversations_v2_updated
    BEFORE UPDATE ON conversations_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

-- ============================================================================
-- 视图：用户未读消息统计
-- ============================================================================
CREATE OR REPLACE VIEW user_unread_messages_v2 AS
SELECT 
    mr.recipient_id as user_id,
    COUNT(*) as unread_count,
    COUNT(*) FILTER (WHERE cm.priority = 'urgent') as urgent_count,
    COUNT(*) FILTER (WHERE cm.requires_acknowledgment AND mr.acknowledged_at IS NULL) as pending_ack_count,
    MAX(cm.created_at) as latest_message_at
FROM message_receipts_v2 mr
JOIN command_messages_v2 cm ON cm.id = mr.message_id
WHERE mr.read_at IS NULL
GROUP BY mr.recipient_id;

-- ============================================================================
-- 视图：对话列表(含最新消息)
-- ============================================================================
CREATE OR REPLACE VIEW conversation_list_v2 AS
SELECT 
    c.*,
    (SELECT content FROM conversation_messages_v2 
     WHERE conversation_id = c.id 
     ORDER BY sequence_no DESC LIMIT 1) as last_message_content,
    (SELECT role FROM conversation_messages_v2 
     WHERE conversation_id = c.id 
     ORDER BY sequence_no DESC LIMIT 1) as last_message_role
FROM conversations_v2 c
WHERE c.status = 'active';

-- ============================================================================
-- 函数：获取用户的待处理消息
-- ============================================================================
CREATE OR REPLACE FUNCTION get_pending_messages_v2(
    p_user_id UUID,
    p_scenario_id UUID DEFAULT NULL
)
RETURNS TABLE(
    message_id UUID,
    message_type command_message_type_v2,
    priority message_priority_v2,
    subject VARCHAR,
    sender_name VARCHAR,
    requires_acknowledgment BOOLEAN,
    acknowledgment_deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cm.id as message_id,
        cm.message_type,
        cm.priority,
        cm.subject,
        cm.sender_name,
        cm.requires_acknowledgment,
        cm.acknowledgment_deadline,
        cm.created_at
    FROM command_messages_v2 cm
    JOIN message_receipts_v2 mr ON mr.message_id = cm.id
    WHERE mr.recipient_id = p_user_id
      AND mr.read_at IS NULL
      AND (p_scenario_id IS NULL OR cm.scenario_id = p_scenario_id)
    ORDER BY 
        CASE cm.priority 
            WHEN 'urgent' THEN 1 
            WHEN 'high' THEN 2 
            WHEN 'normal' THEN 3 
            ELSE 4 
        END,
        cm.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 函数：发送指挥消息
-- ============================================================================
CREATE OR REPLACE FUNCTION send_command_message_v2(
    p_scenario_id UUID,
    p_sender_id UUID,
    p_sender_name VARCHAR,
    p_sender_role VARCHAR,
    p_recipient_type recipient_type_v2,
    p_recipient_id UUID,
    p_recipient_role VARCHAR,
    p_message_type command_message_type_v2,
    p_priority message_priority_v2,
    p_subject VARCHAR,
    p_content TEXT,
    p_requires_ack BOOLEAN DEFAULT false,
    p_ack_deadline TIMESTAMPTZ DEFAULT NULL,
    p_related_event_id UUID DEFAULT NULL,
    p_related_task_id UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_message_id UUID;
    v_recipient RECORD;
BEGIN
    -- 创建消息
    INSERT INTO command_messages_v2 (
        scenario_id, sender_id, sender_name, sender_role,
        recipient_type, recipient_id, recipient_role,
        message_type, priority, subject, content,
        requires_acknowledgment, acknowledgment_deadline,
        related_event_id, related_task_id
    ) VALUES (
        p_scenario_id, p_sender_id, p_sender_name, p_sender_role,
        p_recipient_type, p_recipient_id, p_recipient_role,
        p_message_type, p_priority, p_subject, p_content,
        p_requires_ack, p_ack_deadline,
        p_related_event_id, p_related_task_id
    ) RETURNING id INTO v_message_id;
    
    -- 根据接收者类型创建接收记录
    -- 注意：实际项目中需要根据recipient_type查询对应的用户列表
    -- 这里简化处理，仅处理直接发送给用户的情况
    IF p_recipient_type = 'user' AND p_recipient_id IS NOT NULL THEN
        INSERT INTO message_receipts_v2 (message_id, recipient_id, delivered_at)
        VALUES (v_message_id, p_recipient_id, NOW());
    END IF;
    
    RETURN v_message_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 注释
-- ============================================================================
COMMENT ON TABLE conversations_v2 IS 'AI对话表 - 记录用户与AI助手的对话';
COMMENT ON TABLE conversation_messages_v2 IS '对话消息表 - 对话中的每条消息';
COMMENT ON TABLE command_messages_v2 IS '指挥消息表 - 人与人之间的指挥通信';
COMMENT ON TABLE message_receipts_v2 IS '消息接收记录 - 跟踪消息的送达、阅读、确认状态';
