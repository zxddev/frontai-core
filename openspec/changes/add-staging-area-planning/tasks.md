# Tasks: 添加救援队安全驻扎点选址服务

## 1. 数据库表设计
- [x] 1.1 创建 `sql/v8_rescue_staging_sites.sql` DDL文件
- [x] 1.2 定义 `rescue_staging_sites_v2` 表结构
- [x] 1.3 创建空间索引
- [ ] 1.4 提供给用户执行SQL

## 2. 领域模型
- [x] 2.1 创建 `src/domains/staging_area/__init__.py`
- [x] 2.2 创建 `src/domains/staging_area/models.py` (SQLAlchemy ORM)
- [x] 2.3 创建 `src/domains/staging_area/schemas.py` (Pydantic模型)
- [x] 2.4 创建 `src/domains/staging_area/repository.py` (数据访问层)

## 3. 核心算法实现
- [x] 3.1 创建 `src/domains/staging_area/core.py`
- [x] 3.2 实现 `StagingAreaCore.__init__()` 初始化
- [x] 3.3 实现 `_calculate_risk_zones()` 风险区域计算
  - 复用 DisasterAssessment 计算烈度分布
  - 查询 disaster_affected_areas_v2
  - 合并风险区域多边形
- [x] 3.4 实现 `_search_candidates()` 候选点搜索
  - PostGIS空间查询排除风险区
  - 检查通信覆盖
  - 检查坡度约束
- [x] 3.5 实现 `_validate_routes_batch()` 路径验证
  - 复用 DatabaseRouteEngine
  - 批量规划：驻地→候选点
  - 批量规划：候选点→救援目标
- [x] 3.6 实现 `_evaluate_and_rank()` 多目标评估
  - 响应时间得分计算
  - 安全性得分计算
  - 后勤保障得分计算
  - 设施条件得分计算
  - 通信质量得分计算
  - 加权总分排序
- [x] 3.7 实现 `recommend()` 主入口方法

## 4. 业务服务与API
- [x] 4.1 创建 `src/domains/staging_area/service.py`
- [x] 4.2 创建 `src/domains/staging_area/router.py`
- [x] 4.3 实现 `POST /api/v1/staging-area/recommend` 端点
- [x] 4.4 在 `src/main.py` 注册路由

## 5. 测试
- [x] 5.1 创建 `scripts/test_staging_area.py` 集成测试脚本
- [ ] 5.2 测试风险区域计算
- [ ] 5.3 测试候选点搜索
- [ ] 5.4 测试路径验证
- [ ] 5.5 测试评分排序

## 6. 日志与监控
- [x] 6.1 添加关键位置日志
- [x] 6.2 记录耗时统计

## Dependencies
- 任务1完成后才能执行任务2-6
- 任务2完成后才能执行任务3
- 任务3完成后才能执行任务4-5
