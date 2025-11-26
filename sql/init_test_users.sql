-- ============================================================================
-- 测试用户数据初始化
-- 用于前端联调测试，设置用户密码
-- 密码统一为: 123456 (bcrypt哈希)
-- ============================================================================

-- bcrypt哈希值 for '123456' (cost=12)
-- 可通过Python生成: from passlib.hash import bcrypt; bcrypt.hash('123456')

-- 更新现有用户密码
UPDATE operational_v2.users_v2 
SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.q4X5s2.q6J5r5e'
WHERE password_hash IS NULL;

-- 如果用户表为空，插入测试用户
INSERT INTO operational_v2.users_v2 (
    username, 
    password_hash,
    real_name, 
    employee_id, 
    user_type, 
    department, 
    position, 
    phone,
    status
)
SELECT 
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.q4X5s2.q6J5r5e',
    '系统管理员',
    'ADMIN-001',
    'internal',
    '系统管理',
    '管理员',
    '13800000000',
    'active'
WHERE NOT EXISTS (SELECT 1 FROM operational_v2.users_v2 WHERE username = 'admin');

INSERT INTO operational_v2.users_v2 (
    username, 
    password_hash,
    real_name, 
    employee_id, 
    user_type, 
    department, 
    position, 
    phone,
    status
)
SELECT 
    'commander',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.q4X5s2.q6J5r5e',
    '张指挥',
    'CMD-001',
    'internal',
    '指挥中心',
    '总指挥',
    '13800000001',
    'active'
WHERE NOT EXISTS (SELECT 1 FROM operational_v2.users_v2 WHERE username = 'commander');

INSERT INTO operational_v2.users_v2 (
    username, 
    password_hash,
    real_name, 
    employee_id, 
    user_type, 
    department, 
    position, 
    phone,
    status
)
SELECT 
    'scout',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.q4X5s2.q6J5r5e',
    '李侦察',
    'SCT-001',
    'internal',
    '侦察组',
    '侦察员',
    '13800000002',
    'active'
WHERE NOT EXISTS (SELECT 1 FROM operational_v2.users_v2 WHERE username = 'scout');

INSERT INTO operational_v2.users_v2 (
    username, 
    password_hash,
    real_name, 
    employee_id, 
    user_type, 
    department, 
    position, 
    phone,
    status
)
SELECT 
    'coordinator',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.q4X5s2.q6J5r5e',
    '王协调',
    'CRD-001',
    'internal',
    '调度中心',
    '协调员',
    '13800000003',
    'active'
WHERE NOT EXISTS (SELECT 1 FROM operational_v2.users_v2 WHERE username = 'coordinator');

-- 为测试用户分配角色
-- admin -> SUPER_ADMIN
INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'admin' AND r.code = 'SUPER_ADMIN'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.user_roles_v2 ur 
    WHERE ur.user_id = u.id AND ur.role_id = r.id
);

-- commander -> COMMANDER_IN_CHIEF
INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'commander' AND r.code = 'COMMANDER_IN_CHIEF'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.user_roles_v2 ur 
    WHERE ur.user_id = u.id AND ur.role_id = r.id
);

-- scout -> SCOUT
INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'scout' AND r.code = 'SCOUT'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.user_roles_v2 ur 
    WHERE ur.user_id = u.id AND ur.role_id = r.id
);

-- coordinator -> COORDINATOR
INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'coordinator' AND r.code = 'COORDINATOR'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.user_roles_v2 ur 
    WHERE ur.user_id = u.id AND ur.role_id = r.id
);

-- 输出结果
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM operational_v2.users_v2 WHERE password_hash IS NOT NULL;
    RAISE NOTICE '========================================';
    RAISE NOTICE '测试用户初始化完成';
    RAISE NOTICE '有密码的用户数: %', v_count;
    RAISE NOTICE '测试账号: admin/commander/scout/coordinator';
    RAISE NOTICE '统一密码: 123456';
    RAISE NOTICE '========================================';
END $$;
