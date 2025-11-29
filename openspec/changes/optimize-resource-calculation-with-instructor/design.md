# Design: 使用Instructor优化资源计算模块

## Context

资源计算模块负责生成模块1-4, 6-8的内容，核心是：
1. 基于SPHERE国际人道主义标准的**确定性计算**
2. 使用LLM将计算结果转换为**专业报告文本**

当前实现直接使用LangChain的`ChatOpenAI.ainvoke()`，输出格式不稳定。

## Goals

1. 使用Instructor实现结构化LLM输出
2. 使用Jinja2模板分离报告格式与生成逻辑
3. 保持SPHERE计算逻辑不变
4. 支持vLLM作为后端

## Non-Goals

- 不替换CrewAI（态势感知模块保持不变）
- 不修改SPHERE估算公式
- 不改变API接口

## Design

### 1. 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    resource_calculation_node                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐                                       │
│  │ estimators.py   │ ← SPHERE标准计算（确定性）             │
│  │ - 帐篷数量      │                                       │
│  │ - 饮水量        │                                       │
│  │ - 救援队伍数    │                                       │
│  └────────┬────────┘                                       │
│           │ 计算结果                                        │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │ instructor/     │ ← 结构化LLM生成                        │
│  │ - models.py     │   (Pydantic约束)                      │
│  │ - client.py     │   (vLLM兼容)                          │
│  └────────┬────────┘                                       │
│           │ 结构化输出                                      │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │ templates/      │ ← Jinja2渲染                          │
│  │ - modules.py    │   (ICS标准格式)                       │
│  └────────┬────────┘                                       │
│           │ 最终报告文本                                    │
│           ▼                                                 │
│      [模块1-4, 6-8]                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. Pydantic输出模型

```python
from pydantic import BaseModel, Field

class ModuleSuggestions(BaseModel):
    """LLM生成的建议内容"""
    deployment_suggestions: list[str] = Field(
        description="部署建议列表，每条建议50字以内"
    )
    priority_areas: list[str] = Field(
        description="重点区域列表"
    )
    timeline: str = Field(
        description="时间节点规划，按小时/天划分"
    )
    special_considerations: str = Field(
        description="特殊注意事项"
    )

class ShelterModuleOutput(BaseModel):
    """模块4: 临时安置与生活保障 - LLM输出"""
    site_selection_criteria: list[str] = Field(
        description="安置点选址标准"
    )
    special_groups_care: str = Field(
        description="特殊群体（老人、儿童、孕妇）照护建议"
    )
    sanitation_plan: str = Field(
        description="卫生设施配置建议"
    )
    expansion_considerations: str = Field(
        description="后续扩展安置的考虑"
    )
```

### 3. Instructor客户端封装

```python
import instructor
from openai import OpenAI

def create_instructor_client(
    base_url: str,
    api_key: str,
    model: str,
) -> instructor.Instructor:
    """创建Instructor客户端，支持vLLM"""
    client = OpenAI(base_url=base_url, api_key=api_key)
    return instructor.from_openai(client, mode=instructor.Mode.JSON)
```

### 4. Jinja2模板示例

```python
MODULE_4_TEMPLATE = """
## 四、临时安置与生活保障

### （一）安置规模
根据SPHERE国际人道主义标准，需安置受灾群众{{ affected_population | format_number }}人。

### （二）物资需求
| 物资类型 | 数量 | 标准依据 |
|---------|------|----------|
| 救灾帐篷 | {{ tents }}顶 | 每顶容纳5人 |
| 棉被 | {{ blankets }}床 | 每人2床 |
| 饮用水 | {{ water_liters | format_number }}升 | 每人每天20升×{{ days }}天 |
| 应急食品 | {{ food_kg | format_number }}公斤 | 每人每天0.5公斤×{{ days }}天 |

### （三）安置点选址建议
{% for criteria in site_selection_criteria %}
- {{ criteria }}
{% endfor %}

### （四）特殊群体照护
{{ special_groups_care }}

### （五）卫生设施配置
{{ sanitation_plan }}

### （六）扩展预案
{{ expansion_considerations }}
"""
```

### 5. 集成流程

```python
async def calculate_shelter_module(
    llm_client: instructor.Instructor,
    input_data: ResourceCalculationInput,
) -> tuple[str, dict]:
    """生成模块4 - 临时安置与生活保障"""
    
    # Step 1: SPHERE计算（确定性）
    calculation = estimate_shelter_needs(
        input_data.affected_population,
        input_data.emergency_duration_days,
    )
    
    # Step 2: Instructor结构化生成（LLM建议）
    suggestions = llm_client.chat.completions.create(
        model=model_name,
        response_model=ShelterModuleOutput,
        messages=[{
            "role": "user",
            "content": SHELTER_PROMPT.format(
                affected_population=input_data.affected_population,
                disaster_type=input_data.disaster_type,
                **calculation
            )
        }],
        max_retries=2,
    )
    
    # Step 3: Jinja2渲染最终文本
    text = render_template("module_4", {
        **calculation,
        **suggestions.model_dump(),
        "affected_population": input_data.affected_population,
        "days": input_data.emergency_duration_days,
    })
    
    return text, calculation
```

## Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| vLLM不支持JSON mode | Instructor无法工作 | 使用`mode=instructor.Mode.MD_JSON`或回退到LiteLLM |
| LLM持续输出不合规 | 重试耗尽 | 设置合理的`max_retries`，记录失败日志 |
| 模板渲染错误 | 输出不完整 | Jinja2 StrictUndefined模式 + 单元测试 |

## Testing Strategy

1. **单元测试**
   - estimators.py: 已有测试
   - models.py: Pydantic模型约束测试
   - templates: 模板渲染测试

2. **集成测试**
   - Mock LLM测试完整流程
   - 真实vLLM端到端测试

3. **对比测试**
   - 新旧方案输出质量对比
