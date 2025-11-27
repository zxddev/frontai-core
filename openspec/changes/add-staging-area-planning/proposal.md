# Change: 添加救援队安全驻扎点选址服务

## Why

地震发生后，救援队伍需要在灾区建立前沿驻扎点。驻扎点选址需要综合考虑：
- 安全性：远离震中、次生灾害区、危险区域
- 响应时间：到多个救援目标的实际路径距离
- 后勤保障：到补给点、医疗点、指挥所的距离
- 设施条件：水电通信、场地面积
- 道路可达性：从队伍驻地到驻扎点的路径可行性

当前系统缺少这一关键能力。

## What Changes

- **ADDED**: `src/domains/staging_area/` 领域服务模块
  - `core.py`: 核心选址算法（StagingAreaCore）
  - `schemas.py`: Pydantic请求/响应模型
  - `service.py`: 业务服务层
  - `router.py`: API路由
  - `models.py`: ORM模型
  - `repository.py`: 数据访问层
- **ADDED**: `operational_v2.rescue_staging_sites_v2` 数据库表
- **ADDED**: API端点 `POST /api/v1/staging-area/recommend`

**架构决策**：
- 采用领域服务（Domain Service）架构，参考 `ResourceSchedulingCore`
- **不使用LangGraph**：核心是空间优化问题，不需要LLM参与中间决策
- 复用现有组件：`DatabaseRouteEngine`, `DisasterAssessment`, `SecondaryHazardPredictor`

## Impact

- Affected specs: staging-area (新增)
- Affected code:
  - `src/domains/staging_area/` (新增)
  - `src/main.py` (注册路由)
  - `sql/v8_rescue_staging_sites.sql` (新增表)
- Dependencies: 
  - `src/planning/algorithms/routing/db_route_engine.py`
  - `src/planning/algorithms/assessment/disaster_assessment.py`
  - `src/planning/algorithms/assessment/secondary_hazard.py`
