## ADDED Requirements

### Requirement: 五级验证架构（现状）
当前仓库主要保留 E2E 测试（`tests/e2e/`），未按照 L1-L5 全量分层；不存在 `tests/unit/`、`tests/integration/` 目录。

现有覆盖：
- E2E：`test_recon_full_validation.py`、`test_recon_scheduler_e2e.py`、`test_emergency_ai_e2e.py` 等。
- 数学/节点级验证多数嵌入在 E2E 中，未单列 L1/L2 文件。

后续新增测试时，可按五级模型扩展；当前文档反映现状，不强制分层目录。

### Requirement: 数学验证公式
航线相关计算 MUST 使用以下公式验证：

**Haversine距离公式**
```
R = 6371000  # 地球半径(米)
a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlng/2)
c = 2 * atan2(√a, √(1-a))
d = R * c
```

**纬度/经度转米**
```
lat_meters = Δlat * 111000
lng_meters = Δlng * 111000 * cos(avg_lat)
```

**Z字形航线距离估算**
```
swath_width = 2 * altitude * tan(fov/2)
line_spacing = swath_width * (1 - overlap)
num_lines = area_width / line_spacing
scan_distance = num_lines * area_length
turn_distance = (num_lines - 1) * line_spacing
return_distance = diagonal * 2
total ≈ scan_distance + turn_distance + return_distance
```

**飞行时间计算**
```
flight_time_min = total_distance_m / (speed_ms * 60)
```

#### Scenario: 距离计算验证
- **WHEN** 测试距离计算函数
- **THEN** 使用已知两点（如成都→茂县约125km）
- **AND** 计算误差必须 < 1%

### Requirement: 边界条件测试
系统 MUST 测试以下边界条件：

| 场景 | 输入 | 预期结果 |
|------|------|----------|
| 小区域 | 1km × 1km | status=completed, plans>0 |
| 大区域 | 11km × 11km | status=failed, 明确错误 |
| 设备能力边界 | 刚好超出/刚好在内 | 正确接受/拒绝 |
| 验证失败+重试达限 | L1失败3次 | handle_error, 不跳过 |
| 空区域 | 无坐标 | 优雅处理 |
| 无可用设备 | 设备列表为空 | 明确错误 |

#### Scenario: 边界测试覆盖
- **WHEN** 提交救援相关代码
- **THEN** 必须包含边界条件测试
- **AND** 测试必须验证错误信息的明确性

### Requirement: 测试文件结构（现状）
当前结构：

```
tests/
├── e2e/
│   ├── test_recon_full_validation.py
│   ├── test_recon_scheduler_e2e.py
│   ├── test_emergency_ai_e2e.py
│   ├── test_frontend_api.py
│   ├── test_confirm_deploy.py
│   └── utils/
└── test_confirm_deploy_e2e.py
```

命名仍建议遵循 pytest 规范（文件 `test_*.py`，类 `Test*`，方法 `test_*`），但目前无 unit/integration 子目录。

### Requirement: 测试执行命令
测试 SHALL 使用以下命令执行：

```bash
# 完整验证测试
PYTHONPATH=. pytest tests/e2e/test_recon_full_validation.py -v -s --log-cli-level=INFO

# 快速单元测试
PYTHONPATH=. pytest tests/unit/ -v

# 带覆盖率
PYTHONPATH=. pytest tests/ --cov=src --cov-report=html
```

#### Scenario: CI/CD集成
- **WHEN** 代码提交到仓库
- **THEN** 自动运行单元测试和关键端到端测试
- **AND** 测试失败阻止合并

### Requirement: 异步测试规范
异步测试 MUST 使用pytest-asyncio：

```python
import pytest

class TestReconScheduler:
    @pytest.mark.asyncio
    async def test_small_area_success(self) -> None:
        """小区域应该成功生成航线"""
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            resp = await client.post("/api/v2/ai/recon-schedule", json=request_data)
            assert resp.status_code == 202
            
            result = await self._poll_result(client, task_id)
            assert result["status"] == "completed"
            assert result["success"] is True
            assert len(result["flight_plans"]) > 0
```

#### Scenario: 异步测试超时
- **WHEN** 异步测试等待外部服务
- **THEN** 必须设置合理的超时时间
- **AND** 超时后测试应明确失败而非挂起
