## ADDED Requirements

### Requirement: 审计日志域结构
系统 SHALL 新建 src/domains/audit/ 域处理审计日志：

```
src/domains/audit/
├── __init__.py          # 导出公共接口
├── service.py           # AuditService
├── repository.py        # AuditRepository
├── schemas.py           # Pydantic模型
└── router.py            # FastAPI路由
```

#### Scenario: 审计域职责
- **WHEN** 需要记录安全相关操作
- **THEN** 调用 AuditService 的相应方法
- **AND** 数据存储到 audit schema 下的表

### Requirement: Break Glass审计记录Schema
每次Break Glass操作 MUST 记录完整信息：

```python
class BreakGlassOverride(BaseModel):
    """Break Glass操作审计记录"""
    id: UUID
    timestamp: datetime
    
    # 操作者信息
    operator_id: str
    operator_name: str
    operator_role: str           # 主指挥员/副指挥员
    auth_method: str             # long_press_5s
    
    # 规则信息
    rule_id: str                 # BG_003
    rule_name: str               # 无防化装备进毒区
    risk_overridden: str         # 风险描述
    
    # 操作详情
    action_type: str             # deploy_team, start_mission等
    target_resource: Dict        # 被操作的资源（队伍/设备）
    target_event: Dict           # 关联的事件
    
    # AI建议
    ai_recommendation: Optional[Dict]  # AI建议的替代方案
    was_adopted: bool            # 是否采纳AI建议
    
    # 环境快照
    context: Dict                # 决策时的环境信息
    
    # 事后结果（可后续更新）
    outcome: Optional[Dict] = None
```

#### Scenario: 记录Break Glass操作
- **WHEN** 用户完成5秒长按确认
- **THEN** 调用 AuditService.record_break_glass()
- **AND** 记录包含操作者、规则、上下文、AI建议等完整信息

### Requirement: 审计日志数据库表
系统 SHALL 创建 audit.safety_overrides 表：

```sql
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE audit.safety_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 操作者
    operator_id VARCHAR(64) NOT NULL,
    operator_name VARCHAR(128) NOT NULL,
    operator_role VARCHAR(32) NOT NULL,
    auth_method VARCHAR(32) NOT NULL,
    
    -- 规则
    rule_id VARCHAR(32) NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    risk_overridden TEXT NOT NULL,
    
    -- 操作
    action_type VARCHAR(64) NOT NULL,
    target_resource JSONB NOT NULL,
    target_event JSONB,
    
    -- AI建议
    ai_recommendation JSONB,
    was_adopted BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- 上下文
    context JSONB NOT NULL,
    
    -- 结果
    outcome JSONB,
    outcome_recorded_at TIMESTAMPTZ,
    
    -- 索引
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_safety_overrides_operator ON audit.safety_overrides(operator_id);
CREATE INDEX idx_safety_overrides_rule ON audit.safety_overrides(rule_id);
CREATE INDEX idx_safety_overrides_timestamp ON audit.safety_overrides(timestamp);
```

#### Scenario: 数据库表创建
- **WHEN** 执行数据库迁移
- **THEN** 创建 audit schema（如不存在）
- **AND** 创建 safety_overrides 表
- **AND** 创建必要索引

### Requirement: AuditService接口
AuditService SHALL 提供以下方法：

```python
class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AuditRepository(db)
    
    async def record_break_glass(
        self,
        operator: OperatorInfo,
        rule: HardRuleResult,
        action: ActionInfo,
        ai_recommendation: Optional[Dict],
        context: Dict,
    ) -> BreakGlassOverride:
        """记录Break Glass操作"""
    
    async def update_outcome(
        self,
        override_id: UUID,
        outcome: OutcomeInfo,
    ) -> None:
        """更新操作结果（事后记录）"""
    
    async def query_break_glass_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operator_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[BreakGlassOverride]:
        """查询Break Glass日志"""
```

#### Scenario: 记录并返回ID
- **WHEN** 调用 record_break_glass()
- **THEN** 创建审计记录
- **AND** 返回包含ID的完整对象
- **AND** 可用于后续更新outcome

### Requirement: 审计查询API
系统 SHALL 提供审计日志查询接口：

```python
# src/domains/audit/router.py
@router.get("/api/audit/break-glass")
async def query_break_glass_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    operator_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
) -> List[BreakGlassOverrideResponse]:
    """查询Break Glass操作日志"""
    service = AuditService(db)
    return await service.query_break_glass_logs(
        start_time=start_time,
        end_time=end_time,
        operator_id=operator_id,
        rule_id=rule_id,
        limit=limit,
    )
```

#### Scenario: 按时间范围查询
- **WHEN** 调用 GET /api/audit/break-glass?start_time=xxx&end_time=yyy
- **THEN** 返回该时间范围内的所有Break Glass记录
- **AND** 按时间倒序排列

#### Scenario: 按操作者查询
- **WHEN** 调用 GET /api/audit/break-glass?operator_id=xxx
- **THEN** 返回该操作者的所有Break Glass记录

### Requirement: 事后结果记录
系统 SHALL 支持事后记录操作结果：

```python
class OutcomeInfo(BaseModel):
    """操作结果信息"""
    result: str                  # success/failure/partial
    casualties: int = 0          # 伤亡人数
    notes: str                   # 备注说明
    evidence: Optional[List[str]] = None  # 相关证据（照片URL等）
```

#### Scenario: 更新操作结果
- **WHEN** 任务完成后
- **THEN** 调用 AuditService.update_outcome()
- **AND** 记录实际结果用于事后复盘

### Requirement: 审计日志不可删除
审计日志 MUST 只能追加，禁止删除或修改：

```python
class AuditRepository:
    async def create(self, record: BreakGlassOverride) -> BreakGlassOverride:
        """创建审计记录（只允许追加）"""
    
    async def update_outcome(self, id: UUID, outcome: Dict) -> None:
        """仅允许更新outcome字段"""
    
    # 禁止实现 delete 方法
    # 禁止实现通用 update 方法
```

#### Scenario: 禁止删除审计记录
- **WHEN** 尝试删除审计记录
- **THEN** 抛出 PermissionDeniedError
- **AND** 记录该尝试到安全日志
