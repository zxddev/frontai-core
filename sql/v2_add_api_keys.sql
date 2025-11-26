-- ============================================================================
-- API密钥管理表 (api_keys_v2)
-- 用于第三方系统接入认证
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 密钥信息
    key_hash VARCHAR(255) NOT NULL,                -- API密钥哈希值（存储SHA256哈希）
    key_prefix VARCHAR(8) NOT NULL,                -- 密钥前缀（用于识别，如 "fai_xxxx"）
    name VARCHAR(200) NOT NULL,                    -- 密钥名称/描述
    
    -- 来源系统标识
    source_system VARCHAR(100) NOT NULL,           -- 来源系统标识（如 110-alarm-system）
    
    -- 权限范围
    scopes VARCHAR(50)[] DEFAULT ARRAY['disaster-report', 'sensor-alert', 'telemetry', 'weather'],
    
    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active/revoked/expired
    
    -- 有效期
    expires_at TIMESTAMPTZ,                        -- 过期时间（NULL表示永不过期）
    
    -- 限制
    rate_limit_per_minute INTEGER DEFAULT 100,     -- 每分钟请求限制
    allowed_ips TEXT[],                            -- IP白名单（NULL表示不限制）
    
    -- 扩展信息
    extra_data JSONB DEFAULT '{}',                 -- 扩展信息（联系人、用途等）
    
    -- 审计信息
    created_by UUID,                               -- 创建人
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,                      -- 最后使用时间
    
    -- 唯一约束
    UNIQUE(key_prefix),
    UNIQUE(source_system)
);

-- 索引
CREATE INDEX idx_api_keys_v2_key_prefix ON api_keys_v2(key_prefix);
CREATE INDEX idx_api_keys_v2_source_system ON api_keys_v2(source_system);
CREATE INDEX idx_api_keys_v2_status ON api_keys_v2(status);

-- 注释
COMMENT ON TABLE api_keys_v2 IS 'API密钥管理表 - 用于第三方系统接入认证';
COMMENT ON COLUMN api_keys_v2.key_hash IS 'API密钥的SHA256哈希值';
COMMENT ON COLUMN api_keys_v2.key_prefix IS '密钥前8位，用于快速识别';
COMMENT ON COLUMN api_keys_v2.source_system IS '来源系统唯一标识';
COMMENT ON COLUMN api_keys_v2.scopes IS '允许的接口范围';
COMMENT ON COLUMN api_keys_v2.status IS '状态: active启用/revoked撤销/expired过期';
COMMENT ON COLUMN api_keys_v2.rate_limit_per_minute IS '每分钟请求限制';
COMMENT ON COLUMN api_keys_v2.allowed_ips IS 'IP白名单，NULL表示不限制';

-- 插入测试密钥（开发环境使用，生产环境请删除）
-- 密钥明文: fai_test_key_12345678
-- SHA256: 使用 hashlib.sha256("fai_test_key_12345678".encode()).hexdigest()
INSERT INTO api_keys_v2 (
    key_hash,
    key_prefix,
    name,
    source_system,
    scopes,
    status,
    rate_limit_per_minute,
    extra_data
) VALUES (
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',  -- 占位哈希，实际需要替换
    'fai_test',
    '开发测试密钥',
    'dev-test-system',
    ARRAY['disaster-report', 'sensor-alert', 'telemetry', 'weather'],
    'active',
    1000,
    '{"contact": "dev@example.com", "purpose": "开发测试"}'::jsonb
) ON CONFLICT (source_system) DO NOTHING;
