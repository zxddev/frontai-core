-- 用户设备推送Token表
-- 存储APP端上报的设备推送Token，用于发送原生推送通知

CREATE TABLE IF NOT EXISTS operational_v2.user_device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES operational_v2.users_v2(id) ON DELETE CASCADE,
    expo_push_token VARCHAR(500),
    device_token VARCHAR(500),
    platform VARCHAR(20) NOT NULL,
    device_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, platform)
);

COMMENT ON TABLE operational_v2.user_device_tokens IS '用户设备推送Token表';
COMMENT ON COLUMN operational_v2.user_device_tokens.user_id IS '用户ID';
COMMENT ON COLUMN operational_v2.user_device_tokens.expo_push_token IS 'Expo推送Token';
COMMENT ON COLUMN operational_v2.user_device_tokens.device_token IS '原生设备Token(FCM/APNs)';
COMMENT ON COLUMN operational_v2.user_device_tokens.platform IS '平台类型: ios/android';
COMMENT ON COLUMN operational_v2.user_device_tokens.device_name IS '设备名称';

CREATE INDEX IF NOT EXISTS idx_user_device_tokens_user_id ON operational_v2.user_device_tokens(user_id);
