-- ============================================================================
-- 应急救灾用户权限数据模型 V2
-- 支持：RBAC权限控制、内外部用户、席位角色、数据权限
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS operational_v2;

-- ============================================================================
-- 1. 用户类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.user_type_v2 CASCADE;
CREATE TYPE operational_v2.user_type_v2 AS ENUM (
    'internal',              -- 内部人员（本单位）
    'external_team',         -- 外部救援队伍
    'external_expert',       -- 外部专家（顾问）
    'external_volunteer',    -- 志愿者
    'system'                 -- 系统账户
);

-- ============================================================================
-- 2. 席位角色枚举（车载/指挥所席位）
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.seat_role_v2 CASCADE;
CREATE TYPE operational_v2.seat_role_v2 AS ENUM (
    'commander',             -- 指挥席（总指挥/副指挥）
    'coordinator',           -- 协调席（调度协调）
    'scout',                 -- 侦察席（情报分析）
    'operator',              -- 操作席（设备操控）
    'driver'                 -- 驾驶席
);

-- ============================================================================
-- 3. 组织机构表 (organizations_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.organizations_v2 CASCADE;
CREATE TABLE operational_v2.organizations_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,              -- 机构编码
    name VARCHAR(200) NOT NULL,                    -- 机构名称
    short_name VARCHAR(50),                        -- 简称
    
    -- 层级关系
    parent_id UUID REFERENCES operational_v2.organizations_v2(id),
    org_level INT DEFAULT 1,                       -- 层级：1省/2市/3区县/4乡镇/5村
    org_path VARCHAR(500),                         -- 路径：/省/市/区县/
    
    -- 机构类型
    org_type VARCHAR(50) NOT NULL,                 -- government/military/fire/medical/volunteer/enterprise
    
    -- 联系信息
    contact_person VARCHAR(100),
    contact_phone VARCHAR(20),
    address VARCHAR(300),
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_organizations_v2_parent ON operational_v2.organizations_v2(parent_id);
CREATE INDEX idx_organizations_v2_type ON operational_v2.organizations_v2(org_type);

COMMENT ON TABLE operational_v2.organizations_v2 IS '组织机构表 - 支持多级组织架构';
COMMENT ON COLUMN operational_v2.organizations_v2.id IS '机构唯一标识符';
COMMENT ON COLUMN operational_v2.organizations_v2.code IS '机构编码';
COMMENT ON COLUMN operational_v2.organizations_v2.name IS '机构全称';
COMMENT ON COLUMN operational_v2.organizations_v2.short_name IS '机构简称';
COMMENT ON COLUMN operational_v2.organizations_v2.parent_id IS '上级机构ID';
COMMENT ON COLUMN operational_v2.organizations_v2.org_level IS '机构层级：1省级/2市级/3区县/4乡镇/5村社';
COMMENT ON COLUMN operational_v2.organizations_v2.org_path IS '机构路径，如/四川省/阿坝州/茂县/';
COMMENT ON COLUMN operational_v2.organizations_v2.org_type IS '机构类型：government政府/military部队/fire消防/medical医疗/volunteer志愿者/enterprise企业';
COMMENT ON COLUMN operational_v2.organizations_v2.contact_person IS '联系人';
COMMENT ON COLUMN operational_v2.organizations_v2.contact_phone IS '联系电话';
COMMENT ON COLUMN operational_v2.organizations_v2.address IS '地址';
COMMENT ON COLUMN operational_v2.organizations_v2.status IS '状态：active激活/inactive停用';
COMMENT ON COLUMN operational_v2.organizations_v2.properties IS '扩展属性JSON';

-- ============================================================================
-- 4. 用户表 (users_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.users_v2 CASCADE;
CREATE TABLE operational_v2.users_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 账户信息
    username VARCHAR(100) UNIQUE NOT NULL,         -- 登录账号
    password_hash VARCHAR(255),                    -- 密码哈希
    
    -- 基本信息
    real_name VARCHAR(100) NOT NULL,               -- 真实姓名
    employee_id VARCHAR(50),                       -- 工号/编号
    user_type operational_v2.user_type_v2 DEFAULT 'internal',
    
    -- 所属组织
    org_id UUID REFERENCES operational_v2.organizations_v2(id),
    department VARCHAR(100),                       -- 部门
    position VARCHAR(100),                         -- 职务
    rank VARCHAR(50),                              -- 职级/军衔
    
    -- 联系方式
    phone VARCHAR(20),
    email VARCHAR(100),
    
    -- 专业资质
    certifications TEXT[],                         -- 资质证书列表
    specialties TEXT[],                            -- 专长领域
    
    -- 设备操作资质
    can_operate_uav BOOLEAN DEFAULT false,         -- 无人机操作资质
    can_operate_ugv BOOLEAN DEFAULT false,         -- 机器狗操作资质
    can_operate_usv BOOLEAN DEFAULT false,         -- 无人艇操作资质
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',           -- active/inactive/suspended
    last_login_at TIMESTAMPTZ,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_v2_org ON operational_v2.users_v2(org_id);
CREATE INDEX idx_users_v2_type ON operational_v2.users_v2(user_type);
CREATE INDEX idx_users_v2_status ON operational_v2.users_v2(status);

COMMENT ON TABLE operational_v2.users_v2 IS '用户表 - 存储系统用户信息';
COMMENT ON COLUMN operational_v2.users_v2.id IS '用户唯一标识符';
COMMENT ON COLUMN operational_v2.users_v2.username IS '登录账号';
COMMENT ON COLUMN operational_v2.users_v2.password_hash IS '密码哈希值';
COMMENT ON COLUMN operational_v2.users_v2.real_name IS '真实姓名';
COMMENT ON COLUMN operational_v2.users_v2.employee_id IS '工号或编号';
COMMENT ON COLUMN operational_v2.users_v2.user_type IS '用户类型枚举';
COMMENT ON COLUMN operational_v2.users_v2.org_id IS '所属组织ID';
COMMENT ON COLUMN operational_v2.users_v2.department IS '部门';
COMMENT ON COLUMN operational_v2.users_v2.position IS '职务';
COMMENT ON COLUMN operational_v2.users_v2.rank IS '职级或军衔';
COMMENT ON COLUMN operational_v2.users_v2.phone IS '手机号码';
COMMENT ON COLUMN operational_v2.users_v2.email IS '电子邮箱';
COMMENT ON COLUMN operational_v2.users_v2.certifications IS '资质证书数组';
COMMENT ON COLUMN operational_v2.users_v2.specialties IS '专长领域数组';
COMMENT ON COLUMN operational_v2.users_v2.can_operate_uav IS '是否有无人机操作资质';
COMMENT ON COLUMN operational_v2.users_v2.can_operate_ugv IS '是否有机器狗操作资质';
COMMENT ON COLUMN operational_v2.users_v2.can_operate_usv IS '是否有无人艇操作资质';
COMMENT ON COLUMN operational_v2.users_v2.status IS '状态：active激活/inactive停用/suspended暂停';
COMMENT ON COLUMN operational_v2.users_v2.last_login_at IS '最后登录时间';

-- ============================================================================
-- 5. 角色表 (roles_v2) - 系统功能角色
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.roles_v2 CASCADE;
CREATE TABLE operational_v2.roles_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,              -- 角色编码
    name VARCHAR(100) NOT NULL,                    -- 角色名称
    description TEXT,                              -- 角色描述
    
    -- 角色分类
    role_category VARCHAR(50) NOT NULL,            -- command/operation/support/external
    role_level INT DEFAULT 5,                      -- 角色等级1-10，1最高
    
    -- 是否系统内置角色
    is_system BOOLEAN DEFAULT false,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE operational_v2.roles_v2 IS '角色表 - 定义系统角色';
COMMENT ON COLUMN operational_v2.roles_v2.id IS '角色唯一标识符';
COMMENT ON COLUMN operational_v2.roles_v2.code IS '角色编码，如COMMANDER/COORDINATOR';
COMMENT ON COLUMN operational_v2.roles_v2.name IS '角色名称';
COMMENT ON COLUMN operational_v2.roles_v2.description IS '角色描述';
COMMENT ON COLUMN operational_v2.roles_v2.role_category IS '角色分类：command指挥类/operation操作类/support保障类/external外部';
COMMENT ON COLUMN operational_v2.roles_v2.role_level IS '角色等级1-10，数字越小权限越高';
COMMENT ON COLUMN operational_v2.roles_v2.is_system IS '是否系统内置角色';
COMMENT ON COLUMN operational_v2.roles_v2.status IS '状态';

-- ============================================================================
-- 6. 权限表 (permissions_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.permissions_v2 CASCADE;
CREATE TABLE operational_v2.permissions_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(100) UNIQUE NOT NULL,             -- 权限编码
    name VARCHAR(100) NOT NULL,                    -- 权限名称
    description TEXT,
    
    -- 权限分类
    module VARCHAR(50) NOT NULL,                   -- 所属模块
    action VARCHAR(50) NOT NULL,                   -- 操作类型：view/create/edit/delete/execute/approve
    resource_type VARCHAR(50),                     -- 资源类型
    
    -- 是否需要数据权限控制
    need_data_scope BOOLEAN DEFAULT false,
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_permissions_v2_module ON operational_v2.permissions_v2(module);

COMMENT ON TABLE operational_v2.permissions_v2 IS '权限表 - 定义系统权限点';
COMMENT ON COLUMN operational_v2.permissions_v2.id IS '权限唯一标识符';
COMMENT ON COLUMN operational_v2.permissions_v2.code IS '权限编码，如scenario:view、task:execute';
COMMENT ON COLUMN operational_v2.permissions_v2.name IS '权限名称';
COMMENT ON COLUMN operational_v2.permissions_v2.description IS '权限描述';
COMMENT ON COLUMN operational_v2.permissions_v2.module IS '所属模块：scenario/task/resource/device/map/report/system';
COMMENT ON COLUMN operational_v2.permissions_v2.action IS '操作类型：view查看/create创建/edit编辑/delete删除/execute执行/approve审批';
COMMENT ON COLUMN operational_v2.permissions_v2.resource_type IS '资源类型';
COMMENT ON COLUMN operational_v2.permissions_v2.need_data_scope IS '是否需要数据权限控制';

-- ============================================================================
-- 7. 角色-权限关联表 (role_permissions_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.role_permissions_v2 CASCADE;
CREATE TABLE operational_v2.role_permissions_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id UUID NOT NULL REFERENCES operational_v2.roles_v2(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES operational_v2.permissions_v2(id) ON DELETE CASCADE,
    
    -- 数据范围
    data_scope VARCHAR(50) DEFAULT 'all',          -- all/org/self
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(role_id, permission_id)
);

CREATE INDEX idx_role_permissions_v2_role ON operational_v2.role_permissions_v2(role_id);

COMMENT ON TABLE operational_v2.role_permissions_v2 IS '角色权限关联表';
COMMENT ON COLUMN operational_v2.role_permissions_v2.role_id IS '角色ID';
COMMENT ON COLUMN operational_v2.role_permissions_v2.permission_id IS '权限ID';
COMMENT ON COLUMN operational_v2.role_permissions_v2.data_scope IS '数据范围：all全部/org本机构/self仅自己';

-- ============================================================================
-- 8. 用户-角色关联表 (user_roles_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.user_roles_v2 CASCADE;
CREATE TABLE operational_v2.user_roles_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES operational_v2.users_v2(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES operational_v2.roles_v2(id) ON DELETE CASCADE,
    
    -- 角色生效范围（可指定特定想定）
    scope_type VARCHAR(50) DEFAULT 'global',       -- global/scenario
    scope_id UUID,                                 -- 如果是scenario，则为想定ID
    
    -- 有效期（临时授权）
    valid_from TIMESTAMPTZ DEFAULT now(),
    valid_until TIMESTAMPTZ,
    
    -- 授权信息
    granted_by UUID,
    granted_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(user_id, role_id, scope_type, scope_id)
);

CREATE INDEX idx_user_roles_v2_user ON operational_v2.user_roles_v2(user_id);
CREATE INDEX idx_user_roles_v2_role ON operational_v2.user_roles_v2(role_id);

COMMENT ON TABLE operational_v2.user_roles_v2 IS '用户角色关联表';
COMMENT ON COLUMN operational_v2.user_roles_v2.user_id IS '用户ID';
COMMENT ON COLUMN operational_v2.user_roles_v2.role_id IS '角色ID';
COMMENT ON COLUMN operational_v2.user_roles_v2.scope_type IS '角色生效范围：global全局/scenario特定想定';
COMMENT ON COLUMN operational_v2.user_roles_v2.scope_id IS '范围ID，如想定ID';
COMMENT ON COLUMN operational_v2.user_roles_v2.valid_from IS '角色生效开始时间';
COMMENT ON COLUMN operational_v2.user_roles_v2.valid_until IS '角色生效结束时间（临时授权）';
COMMENT ON COLUMN operational_v2.user_roles_v2.granted_by IS '授权人ID';
COMMENT ON COLUMN operational_v2.user_roles_v2.granted_at IS '授权时间';

-- ============================================================================
-- 9. 席位分配表 (seat_assignments_v2) - 想定/任务中的席位分配
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.seat_assignments_v2 CASCADE;
CREATE TABLE operational_v2.seat_assignments_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联
    scenario_id UUID NOT NULL,                     -- 关联想定
    vehicle_id UUID,                               -- 关联车辆（如果是车载席位）
    
    -- 席位信息
    seat_role operational_v2.seat_role_v2 NOT NULL,
    seat_name VARCHAR(100),                        -- 席位名称（可自定义）
    
    -- 分配的用户
    user_id UUID REFERENCES operational_v2.users_v2(id),
    
    -- 席位状态
    status VARCHAR(20) DEFAULT 'vacant',           -- vacant/assigned/active/offline
    
    -- 上下线时间
    online_at TIMESTAMPTZ,
    offline_at TIMESTAMPTZ,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_seat_assignments_v2_scenario ON operational_v2.seat_assignments_v2(scenario_id);
CREATE INDEX idx_seat_assignments_v2_user ON operational_v2.seat_assignments_v2(user_id);
CREATE INDEX idx_seat_assignments_v2_vehicle ON operational_v2.seat_assignments_v2(vehicle_id);

COMMENT ON TABLE operational_v2.seat_assignments_v2 IS '席位分配表 - 想定中的席位人员分配';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.scenario_id IS '关联想定ID';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.vehicle_id IS '关联车辆ID（车载席位）';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.seat_role IS '席位角色枚举';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.seat_name IS '席位名称';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.user_id IS '分配的用户ID';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.status IS '状态：vacant空缺/assigned已分配/active在岗/offline离线';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.online_at IS '上线时间';
COMMENT ON COLUMN operational_v2.seat_assignments_v2.offline_at IS '离线时间';

-- ============================================================================
-- 10. 外部队伍授权表 (external_team_authorizations_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.external_team_authorizations_v2 CASCADE;
CREATE TABLE operational_v2.external_team_authorizations_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联
    scenario_id UUID NOT NULL,                     -- 关联想定
    team_id UUID NOT NULL,                         -- 关联救援队伍
    org_id UUID REFERENCES operational_v2.organizations_v2(id), -- 外部机构
    
    -- 授权范围
    auth_level VARCHAR(20) DEFAULT 'view',         -- view/operate/command
    
    -- 可访问的资源
    can_view_all_tasks BOOLEAN DEFAULT false,      -- 是否可查看所有任务
    can_view_own_tasks BOOLEAN DEFAULT true,       -- 是否可查看本队任务
    can_update_task_status BOOLEAN DEFAULT true,   -- 是否可更新任务状态
    can_request_resources BOOLEAN DEFAULT false,   -- 是否可申请资源
    can_view_map BOOLEAN DEFAULT true,             -- 是否可查看地图
    can_report_events BOOLEAN DEFAULT true,        -- 是否可上报事件
    
    -- 可操作的设备
    authorized_device_ids UUID[],                  -- 授权操作的设备ID列表
    
    -- 通信权限
    can_voice_communicate BOOLEAN DEFAULT true,    -- 是否可语音通信
    communication_channels TEXT[],                 -- 可用通信频道
    
    -- 授权有效期
    valid_from TIMESTAMPTZ DEFAULT now(),
    valid_until TIMESTAMPTZ,
    
    -- 授权信息
    authorized_by UUID,
    authorized_at TIMESTAMPTZ DEFAULT now(),
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_external_auth_v2_scenario ON operational_v2.external_team_authorizations_v2(scenario_id);
CREATE INDEX idx_external_auth_v2_team ON operational_v2.external_team_authorizations_v2(team_id);

COMMENT ON TABLE operational_v2.external_team_authorizations_v2 IS '外部队伍授权表 - 定义外部救援队伍在想定中的权限';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.id IS '授权记录ID';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.scenario_id IS '想定ID';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.team_id IS '救援队伍ID';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.org_id IS '外部机构ID';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.auth_level IS '授权级别：view只读/operate可操作/command可指挥';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_view_all_tasks IS '是否可查看所有任务';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_view_own_tasks IS '是否可查看本队任务';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_update_task_status IS '是否可更新任务状态';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_request_resources IS '是否可申请资源';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_view_map IS '是否可查看态势地图';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_report_events IS '是否可上报事件';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.authorized_device_ids IS '授权操作的设备ID数组';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.can_voice_communicate IS '是否可语音通信';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.communication_channels IS '可用通信频道';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.valid_from IS '授权开始时间';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.valid_until IS '授权结束时间';
COMMENT ON COLUMN operational_v2.external_team_authorizations_v2.authorized_by IS '授权人ID';

-- ============================================================================
-- 11. 操作日志表 (operation_logs_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.operation_logs_v2 CASCADE;
CREATE TABLE operational_v2.operation_logs_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 操作人
    user_id UUID,
    username VARCHAR(100),
    user_ip VARCHAR(50),
    
    -- 操作信息
    module VARCHAR(50) NOT NULL,                   -- 模块
    action VARCHAR(50) NOT NULL,                   -- 操作
    resource_type VARCHAR(50),                     -- 资源类型
    resource_id UUID,                              -- 资源ID
    
    -- 操作详情
    description TEXT,                              -- 操作描述
    request_data JSONB,                            -- 请求数据
    response_data JSONB,                           -- 响应数据
    
    -- 结果
    status VARCHAR(20) DEFAULT 'success',          -- success/failed
    error_message TEXT,
    
    -- 关联想定（如果有）
    scenario_id UUID,
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_operation_logs_v2_user ON operational_v2.operation_logs_v2(user_id);
CREATE INDEX idx_operation_logs_v2_time ON operational_v2.operation_logs_v2(created_at);
CREATE INDEX idx_operation_logs_v2_scenario ON operational_v2.operation_logs_v2(scenario_id);

COMMENT ON TABLE operational_v2.operation_logs_v2 IS '操作日志表 - 记录用户操作审计';

-- ============================================================================
-- 12. 插入默认角色数据
-- ============================================================================
INSERT INTO operational_v2.roles_v2 (code, name, description, role_category, role_level, is_system) VALUES
-- 指挥类角色
('SUPER_ADMIN', '超级管理员', '系统最高权限，可管理所有功能和数据', 'command', 1, true),
('COMMANDER_IN_CHIEF', '总指挥', '应急指挥最高负责人，拥有全部指挥权限', 'command', 2, true),
('DEPUTY_COMMANDER', '副指挥', '协助总指挥，可代行指挥权', 'command', 3, true),
('SECTOR_COMMANDER', '分区指挥', '负责特定区域的指挥调度', 'command', 4, true),

-- 协调调度类角色
('COORDINATOR', '协调员', '负责资源协调、任务调度、信息汇总', 'operation', 5, true),
('DISPATCHER', '调度员', '负责具体任务分配和进度跟踪', 'operation', 6, true),

-- 情报侦察类角色
('SCOUT_LEAD', '侦察组长', '负责侦察任务规划和情报分析', 'operation', 5, true),
('SCOUT', '侦察员', '执行侦察任务，收集和上报灾情信息', 'operation', 7, true),
('INTELLIGENCE_ANALYST', '情报分析员', '分析处理各类情报信息', 'operation', 6, true),

-- 设备操作类角色
('UAV_OPERATOR_LEAD', '无人机组长', '负责无人机编队管理和任务规划', 'operation', 5, true),
('UAV_OPERATOR', '无人机操作手', '操控无人机执行侦察、投送等任务', 'operation', 7, true),
('UGV_OPERATOR', '机器狗操作手', '操控机器狗执行地面任务', 'operation', 7, true),
('USV_OPERATOR', '无人艇操作手', '操控无人艇执行水上任务', 'operation', 7, true),

-- 通信保障类角色
('COMM_OFFICER', '通信主管', '负责通信保障和网络管理', 'support', 5, true),
('COMM_OPERATOR', '通信员', '执行通信保障任务', 'support', 7, true),

-- 后勤保障类角色
('LOGISTICS_OFFICER', '后勤主管', '负责物资、装备、车辆保障', 'support', 5, true),
('LOGISTICS_STAFF', '保障员', '执行后勤保障任务', 'support', 7, true),

-- 医疗救护类角色
('MEDICAL_OFFICER', '医疗主管', '负责医疗救护工作', 'support', 5, true),
('MEDIC', '医护人员', '执行现场医疗救护', 'support', 7, true),

-- 外部队伍角色
('EXTERNAL_TEAM_LEAD', '外部队伍负责人', '外部救援队伍负责人', 'external', 6, true),
('EXTERNAL_MEMBER', '外部队伍成员', '外部救援队伍普通成员', 'external', 8, true),
('VOLUNTEER_LEAD', '志愿者组长', '志愿者队伍负责人', 'external', 7, true),
('VOLUNTEER', '志愿者', '志愿者', 'external', 9, true),

-- 观察员
('OBSERVER', '观察员', '只读权限，用于学习观摩', 'external', 10, true);

-- ============================================================================
-- 13. 插入权限数据
-- ============================================================================
INSERT INTO operational_v2.permissions_v2 (code, name, module, action, resource_type, need_data_scope, description) VALUES
-- 想定管理权限
('scenario:view', '查看想定', 'scenario', 'view', 'scenario', true, '查看想定列表和详情'),
('scenario:create', '创建想定', 'scenario', 'create', 'scenario', false, '创建新想定'),
('scenario:edit', '编辑想定', 'scenario', 'edit', 'scenario', true, '编辑想定信息'),
('scenario:delete', '删除想定', 'scenario', 'delete', 'scenario', true, '删除想定'),
('scenario:activate', '启动想定', 'scenario', 'execute', 'scenario', true, '启动/暂停想定'),
('scenario:archive', '归档想定', 'scenario', 'execute', 'scenario', true, '归档想定'),

-- 任务管理权限
('task:view', '查看任务', 'task', 'view', 'task', true, '查看任务列表和详情'),
('task:create', '创建任务', 'task', 'create', 'task', false, '创建新任务'),
('task:edit', '编辑任务', 'task', 'edit', 'task', true, '编辑任务信息'),
('task:delete', '删除任务', 'task', 'delete', 'task', true, '删除任务'),
('task:assign', '分配任务', 'task', 'execute', 'task', true, '分配任务给队伍'),
('task:execute', '执行任务', 'task', 'execute', 'task', true, '执行任务/更新状态'),
('task:approve', '审批任务', 'task', 'approve', 'task', true, '审批任务完成'),

-- 资源管理权限
('resource:view', '查看资源', 'resource', 'view', 'resource', true, '查看救援资源'),
('resource:manage', '管理资源', 'resource', 'edit', 'resource', true, '管理救援队伍/装备'),
('resource:dispatch', '调度资源', 'resource', 'execute', 'resource', true, '调度救援资源'),
('resource:request', '申请资源', 'resource', 'create', 'resource', true, '申请资源支援'),

-- 设备操作权限
('device:view', '查看设备', 'device', 'view', 'device', true, '查看设备列表和状态'),
('device:operate_uav', '操控无人机', 'device', 'execute', 'uav', false, '操控无人机'),
('device:operate_ugv', '操控机器狗', 'device', 'execute', 'ugv', false, '操控机器狗'),
('device:operate_usv', '操控无人艇', 'device', 'execute', 'usv', false, '操控无人艇'),
('device:manage', '管理设备', 'device', 'edit', 'device', false, '管理设备配置'),

-- 地图权限
('map:view', '查看地图', 'map', 'view', 'map', false, '查看态势地图'),
('map:edit', '编辑地图', 'map', 'edit', 'map', false, '编辑地图标注'),
('map:draw', '标绘', 'map', 'create', 'map', false, '地图标绘功能'),

-- 事件权限
('event:view', '查看事件', 'event', 'view', 'event', true, '查看事件列表'),
('event:report', '上报事件', 'event', 'create', 'event', false, '上报灾情事件'),
('event:handle', '处置事件', 'event', 'execute', 'event', true, '处置事件'),

-- 方案权限
('scheme:view', '查看方案', 'scheme', 'view', 'scheme', true, '查看救援方案'),
('scheme:create', '创建方案', 'scheme', 'create', 'scheme', false, '创建救援方案'),
('scheme:edit', '编辑方案', 'scheme', 'edit', 'scheme', true, '编辑救援方案'),
('scheme:approve', '审批方案', 'scheme', 'approve', 'scheme', true, '审批救援方案'),
('scheme:execute', '执行方案', 'scheme', 'execute', 'scheme', true, '执行救援方案'),

-- 报告权限
('report:view', '查看报告', 'report', 'view', 'report', true, '查看各类报告'),
('report:create', '生成报告', 'report', 'create', 'report', false, '生成报告'),
('report:export', '导出报告', 'report', 'execute', 'report', false, '导出报告'),

-- 通信权限
('comm:voice', '语音通信', 'comm', 'execute', 'voice', false, '语音通信功能'),
('comm:broadcast', '广播', 'comm', 'execute', 'broadcast', false, '广播消息'),
('comm:video', '视频通信', 'comm', 'execute', 'video', false, '视频通信功能'),

-- 系统管理权限
('system:user_manage', '用户管理', 'system', 'edit', 'user', false, '管理系统用户'),
('system:role_manage', '角色管理', 'system', 'edit', 'role', false, '管理系统角色'),
('system:org_manage', '机构管理', 'system', 'edit', 'org', false, '管理组织机构'),
('system:config', '系统配置', 'system', 'edit', 'config', false, '系统参数配置'),
('system:log_view', '查看日志', 'system', 'view', 'log', false, '查看操作日志');

-- ============================================================================
-- 14. 角色-权限关联（预设）
-- ============================================================================
-- 超级管理员：全部权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'all'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'SUPER_ADMIN';

-- 总指挥：除系统管理外全部权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'all'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'COMMANDER_IN_CHIEF' AND p.module != 'system';

-- 副指挥：指挥类权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'all'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'DEPUTY_COMMANDER' 
AND p.code IN ('scenario:view', 'scenario:edit', 'scenario:activate',
               'task:view', 'task:create', 'task:edit', 'task:assign', 'task:approve',
               'resource:view', 'resource:dispatch',
               'device:view', 'map:view', 'map:edit', 'map:draw',
               'event:view', 'event:handle',
               'scheme:view', 'scheme:create', 'scheme:edit', 'scheme:approve', 'scheme:execute',
               'report:view', 'report:create', 'comm:voice', 'comm:broadcast', 'comm:video');

-- 协调员：协调调度权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'all'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'COORDINATOR'
AND p.code IN ('scenario:view', 'task:view', 'task:create', 'task:edit', 'task:assign',
               'resource:view', 'resource:dispatch', 'resource:request',
               'device:view', 'map:view', 'map:edit', 'map:draw',
               'event:view', 'event:handle',
               'scheme:view', 'scheme:edit',
               'report:view', 'comm:voice', 'comm:broadcast');

-- 侦察员：侦察相关权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'self'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'SCOUT'
AND p.code IN ('scenario:view', 'task:view', 'task:execute',
               'device:view', 'map:view', 'map:draw',
               'event:view', 'event:report',
               'comm:voice');

-- 无人机操作手：设备操作权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'self'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'UAV_OPERATOR'
AND p.code IN ('scenario:view', 'task:view', 'task:execute',
               'device:view', 'device:operate_uav',
               'map:view', 'event:report', 'comm:voice');

-- 机器狗操作手
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'self'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'UGV_OPERATOR'
AND p.code IN ('scenario:view', 'task:view', 'task:execute',
               'device:view', 'device:operate_ugv',
               'map:view', 'event:report', 'comm:voice');

-- 无人艇操作手
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'self'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'USV_OPERATOR'
AND p.code IN ('scenario:view', 'task:view', 'task:execute',
               'device:view', 'device:operate_usv',
               'map:view', 'event:report', 'comm:voice');

-- 外部队伍负责人：有限权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'org'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'EXTERNAL_TEAM_LEAD'
AND p.code IN ('scenario:view', 'task:view', 'task:execute',
               'resource:view', 'resource:request',
               'device:view', 'map:view',
               'event:view', 'event:report',
               'report:view', 'comm:voice');

-- 外部队伍成员：最小权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'self'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'EXTERNAL_MEMBER'
AND p.code IN ('scenario:view', 'task:view', 'task:execute',
               'map:view', 'event:report', 'comm:voice');

-- 观察员：只读权限
INSERT INTO operational_v2.role_permissions_v2 (role_id, permission_id, data_scope)
SELECT r.id, p.id, 'all'
FROM operational_v2.roles_v2 r, operational_v2.permissions_v2 p
WHERE r.code = 'OBSERVER'
AND p.action = 'view';

-- ============================================================================
-- 15. 插入示例组织数据
-- ============================================================================
INSERT INTO operational_v2.organizations_v2 (code, name, short_name, org_level, org_path, org_type, contact_person, contact_phone) VALUES
('ORG-SC', '四川省应急管理厅', '省应急厅', 1, '/四川省/', 'government', '张厅长', '028-12350'),
('ORG-AB', '阿坝州应急管理局', '州应急局', 2, '/四川省/阿坝州/', 'government', '李局长', '0837-12350'),
('ORG-MX', '茂县应急管理局', '县应急局', 3, '/四川省/阿坝州/茂县/', 'government', '王局长', '0837-7422350'),
('ORG-FIRE-AB', '阿坝州消防救援支队', '州消防支队', 2, '/四川省/阿坝州/', 'fire', '赵支队长', '0837-119'),
('ORG-FIRE-MX', '茂县消防救援大队', '县消防大队', 3, '/四川省/阿坝州/茂县/', 'fire', '钱大队长', '0837-7422119'),
('ORG-MED-MX', '茂县人民医院', '县医院', 3, '/四川省/阿坝州/茂县/', 'medical', '孙院长', '0837-7422120'),
('ORG-VOL-BSR', '蓝天救援队阿坝分队', '蓝天救援队', 3, '/四川省/阿坝州/', 'volunteer', '周队长', '13800138000');

-- 设置父级关系
UPDATE operational_v2.organizations_v2 SET parent_id = (SELECT id FROM operational_v2.organizations_v2 WHERE code = 'ORG-SC') WHERE code = 'ORG-AB';
UPDATE operational_v2.organizations_v2 SET parent_id = (SELECT id FROM operational_v2.organizations_v2 WHERE code = 'ORG-AB') WHERE code IN ('ORG-MX', 'ORG-FIRE-AB', 'ORG-VOL-BSR');
UPDATE operational_v2.organizations_v2 SET parent_id = (SELECT id FROM operational_v2.organizations_v2 WHERE code = 'ORG-MX') WHERE code IN ('ORG-FIRE-MX', 'ORG-MED-MX');

-- ============================================================================
-- 16. 插入示例用户数据
-- ============================================================================
INSERT INTO operational_v2.users_v2 (username, real_name, employee_id, user_type, org_id, department, position, phone, certifications, specialties, can_operate_uav, can_operate_ugv, can_operate_usv)
SELECT 
    'commander01', '张明远', 'CMD-001', 'internal', o.id, '指挥中心', '总指挥', '13900001001',
    '{应急管理师,指挥员资格证}', '{应急指挥,灾害评估}', false, false, false
FROM operational_v2.organizations_v2 o WHERE o.code = 'ORG-MX';

INSERT INTO operational_v2.users_v2 (username, real_name, employee_id, user_type, org_id, department, position, phone, certifications, specialties, can_operate_uav, can_operate_ugv, can_operate_usv)
SELECT 
    'coordinator01', '李协调', 'CRD-001', 'internal', o.id, '调度中心', '协调员', '13900001002',
    '{应急调度员}', '{资源调度,任务协调}', false, false, false
FROM operational_v2.organizations_v2 o WHERE o.code = 'ORG-MX';

INSERT INTO operational_v2.users_v2 (username, real_name, employee_id, user_type, org_id, department, position, phone, certifications, specialties, can_operate_uav, can_operate_ugv, can_operate_usv)
SELECT 
    'scout01', '王侦察', 'SCT-001', 'internal', o.id, '侦察组', '侦察员', '13900001003',
    '{无人机驾驶证,侦察员证}', '{灾情侦察,情报分析}', true, false, false
FROM operational_v2.organizations_v2 o WHERE o.code = 'ORG-MX';

INSERT INTO operational_v2.users_v2 (username, real_name, employee_id, user_type, org_id, department, position, phone, certifications, specialties, can_operate_uav, can_operate_ugv, can_operate_usv)
SELECT 
    'uav_pilot01', '赵飞手', 'UAV-001', 'internal', o.id, '无人机组', '无人机操作手', '13900001004',
    '{AOPA无人机驾驶证,CAAC执照}', '{无人机操控,航拍测绘}', true, false, false
FROM operational_v2.organizations_v2 o WHERE o.code = 'ORG-MX';

INSERT INTO operational_v2.users_v2 (username, real_name, employee_id, user_type, org_id, department, position, phone, certifications, specialties, can_operate_uav, can_operate_ugv, can_operate_usv)
SELECT 
    'ugv_operator01', '钱地勤', 'UGV-001', 'internal', o.id, '机器人组', '机器狗操作手', '13900001005',
    '{机器人操作员证}', '{机器狗操控,地面侦察}', false, true, false
FROM operational_v2.organizations_v2 o WHERE o.code = 'ORG-MX';

INSERT INTO operational_v2.users_v2 (username, real_name, employee_id, user_type, org_id, department, position, phone, certifications, specialties, can_operate_uav, can_operate_ugv, can_operate_usv)
SELECT 
    'external_lead01', '周蓝天', 'EXT-001', 'external_team', o.id, NULL, '队长', '13800138001',
    '{救援员证,急救员证}', '{山地救援,水域救援}', false, false, false
FROM operational_v2.organizations_v2 o WHERE o.code = 'ORG-VOL-BSR';

-- ============================================================================
-- 17. 分配用户角色
-- ============================================================================
INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'commander01' AND r.code = 'COMMANDER_IN_CHIEF';

INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'coordinator01' AND r.code = 'COORDINATOR';

INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'scout01' AND r.code = 'SCOUT';

INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'uav_pilot01' AND r.code = 'UAV_OPERATOR';

INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'ugv_operator01' AND r.code = 'UGV_OPERATOR';

INSERT INTO operational_v2.user_roles_v2 (user_id, role_id, scope_type)
SELECT u.id, r.id, 'global'
FROM operational_v2.users_v2 u, operational_v2.roles_v2 r
WHERE u.username = 'external_lead01' AND r.code = 'EXTERNAL_TEAM_LEAD';

-- ============================================================================
-- 18. 创建权限检查函数
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.check_user_permission(
    p_user_id UUID,
    p_permission_code VARCHAR(100),
    p_resource_id UUID DEFAULT NULL
) RETURNS TABLE (
    has_permission BOOLEAN,
    data_scope VARCHAR(50),
    reason TEXT
) AS $$
DECLARE
    v_user operational_v2.users_v2%ROWTYPE;
    v_perm_record RECORD;
BEGIN
    -- 获取用户信息
    SELECT * INTO v_user FROM operational_v2.users_v2 WHERE id = p_user_id;
    
    IF v_user.id IS NULL THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, '用户不存在';
        RETURN;
    END IF;
    
    IF v_user.status != 'active' THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, '用户已停用';
        RETURN;
    END IF;
    
    -- 检查角色权限
    SELECT rp.data_scope INTO v_perm_record
    FROM operational_v2.user_roles_v2 ur
    JOIN operational_v2.role_permissions_v2 rp ON ur.role_id = rp.role_id
    JOIN operational_v2.permissions_v2 p ON rp.permission_id = p.id
    WHERE ur.user_id = p_user_id
      AND p.code = p_permission_code
      AND (ur.valid_until IS NULL OR ur.valid_until > now())
    ORDER BY 
        CASE rp.data_scope 
            WHEN 'all' THEN 1 
            WHEN 'org' THEN 2 
            ELSE 3 
        END
    LIMIT 1;
    
    IF v_perm_record IS NULL THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, '无此权限';
        RETURN;
    END IF;
    
    RETURN QUERY SELECT TRUE, v_perm_record.data_scope, '权限验证通过';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.check_user_permission IS '检查用户是否拥有指定权限，返回权限状态和数据范围';

-- ============================================================================
-- 19. 创建视图：用户权限汇总
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.v_user_permissions_summary_v2 AS
SELECT 
    u.id AS user_id,
    u.username,
    u.real_name,
    u.user_type,
    o.name AS org_name,
    array_agg(DISTINCT r.name) AS roles,
    array_agg(DISTINCT p.code) AS permissions
FROM operational_v2.users_v2 u
LEFT JOIN operational_v2.organizations_v2 o ON u.org_id = o.id
LEFT JOIN operational_v2.user_roles_v2 ur ON u.id = ur.user_id
LEFT JOIN operational_v2.roles_v2 r ON ur.role_id = r.id
LEFT JOIN operational_v2.role_permissions_v2 rp ON r.id = rp.role_id
LEFT JOIN operational_v2.permissions_v2 p ON rp.permission_id = p.id
WHERE u.status = 'active'
  AND (ur.valid_until IS NULL OR ur.valid_until > now())
GROUP BY u.id, u.username, u.real_name, u.user_type, o.name;

COMMENT ON VIEW operational_v2.v_user_permissions_summary_v2 IS '用户权限汇总视图';

-- ============================================================================
-- 输出统计信息
-- ============================================================================
DO $$
DECLARE
    v_orgs INT;
    v_users INT;
    v_roles INT;
    v_perms INT;
BEGIN
    SELECT COUNT(*) INTO v_orgs FROM operational_v2.organizations_v2;
    SELECT COUNT(*) INTO v_users FROM operational_v2.users_v2;
    SELECT COUNT(*) INTO v_roles FROM operational_v2.roles_v2;
    SELECT COUNT(*) INTO v_perms FROM operational_v2.permissions_v2;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '用户权限模型 V2 创建完成';
    RAISE NOTICE '组织机构数: %', v_orgs;
    RAISE NOTICE '用户数: %', v_users;
    RAISE NOTICE '角色数: %', v_roles;
    RAISE NOTICE '权限数: %', v_perms;
    RAISE NOTICE '========================================';
END $$;
