"""CrewAI Task definitions for overall rescue plan generation.

业务场景：向省级指挥大厅/省委书记汇报态势并申请资源

使用async_execution=True实现并行执行，加速生成。
"""

from crewai import Agent, Task

# 所有Task共用的禁止编造数据说明
NO_FABRICATION_RULE = """
## 严禁编造数据（违反将被视为严重错误）

### 强制规则
1. 所有数值必须且只能来自"系统数据"部分
2. 如果系统数据中某项为0或显示"待核实"，输出必须写"待核实"或"暂无数据"
3. 绝对禁止编造任何数字，包括但不限于：
   - 人员伤亡数字（死亡、受伤、失联、被困人数）
   - 建筑损毁数量（倒塌栋数、受损栋数）
   - 道路损毁公里数
   - 受灾人口数量
4. 不要编造人名、电话、地址等具体信息
5. 不要编造不在系统数据中的队伍名称
6. 签名处只写职务（如"省应急指挥中心 XX协调官"），不要写具体人名
7. 联系方式写"详见指挥部通讯录"，不要编造电话号码

### 数据来源说明
- 所有灾情数据来自数据库实际记录
- 如果数据库无记录，显示"待核实"
- 不允许基于"估算"或"推测"编造任何数字
"""


# ============================================================================
# 模块0: 灾情态势汇报 (并行)
# ============================================================================
def create_disaster_briefing_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块0 - 灾情态势汇报"""
    return Task(
        description="""基于系统数据，生成灾情态势汇报。

## 系统数据（来自数据库，不可编造）
### 人员伤亡情况
- 死亡：{deaths_count_display}
- 受伤：{injured_count_display}
- 失联：{missing_count_display}
- 被困：{trapped_count_display}

### 建筑损毁情况
- 倒塌：{buildings_collapsed_display}
- 受损：{buildings_damaged_display}

### 想定基本信息
{scenario_data}

## 输出要求
生成简洁的灾情态势汇报，包含：
1. 灾害基本情况（类型、时间、地点、强度）
2. 人员伤亡情况（必须使用上面的数据，不可编造）
3. 建筑损毁情况（必须使用上面的数据，不可编造）
4. 当前紧急程度评估

## 格式
使用markdown格式，简洁专业。

## 重要（必须遵守）
- 人员伤亡和建筑损毁数据必须使用"系统数据"部分提供的数值
- 如果数据显示"待核实"，输出也必须写"待核实"
- 绝对禁止编造任何数字
""" + NO_FABRICATION_RULE,
        expected_output="灾情态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块1: 救援力量态势 (并行)
# ============================================================================
def create_rescue_force_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块1 - 救援力量态势汇报"""
    return Task(
        description="""基于系统数据，生成救援力量态势汇报。

## 系统数据（来自数据库，不可编造）
- 被困人员：{trapped_count_display}

可用救援队伍（来自数据库）：
{available_teams}

## 输出要求
生成救援力量态势汇报，包含：

### 一、当前态势
- 已确认被困人员数量（必须使用上面的数据）
- 已派出救援力量（从可用队伍中选择，标注"建议调派"）

### 二、资源需求测算
基于SPHERE标准（每50名被困人员配1支救援队）测算

### 三、请求事项
向上级明确申请的资源

## 重要（必须遵守）
- 被困人员数据必须使用"系统数据"中的数值
- 如果数据显示"待核实"，输出也必须写"待核实"
- 只能从"可用救援队伍"中选择队伍名称
- 不要编造不存在的队伍
""" + NO_FABRICATION_RULE,
        expected_output="救援力量态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块2: 医疗救护态势 (并行)
# ============================================================================
def create_medical_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块2 - 医疗救护态势汇报"""
    return Task(
        description="""基于系统数据，生成医疗救护态势汇报。

## 系统数据（来自数据库，不可编造）
- 受伤人员：{injured_count_display}
- 重伤人员：{serious_injury_count}人（如为0则写"待核实"）

可用医疗队伍（来自数据库）：
{available_medical_teams}

## 输出要求
生成医疗救护态势汇报，包含：

### 一、当前态势
- 伤员情况（必须使用上面的数据）

### 二、资源需求测算
基于SPHERE标准测算

### 三、请求事项
向卫健委申请的医疗资源

## 重要（必须遵守）
- 伤员数据必须使用"系统数据"中的数值
- 如果数据显示"待核实"，输出也必须写"待核实"
- 只从数据库队伍中选择
""" + NO_FABRICATION_RULE,
        expected_output="医疗救护态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块3: 工程抢险态势 (并行)
# ============================================================================
def create_infrastructure_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块3 - 工程抢险态势汇报"""
    return Task(
        description="""基于系统数据，生成基础设施损毁和抢修态势汇报。

## 系统数据（来自数据库，不可编造）
损毁情况：
- 倒塌建筑：{buildings_collapsed_display}
- 受损建筑：{buildings_damaged_display}
- 损毁道路：{roads_damaged_km}公里（如为0则写"待核实"）

可用工程队伍：
{available_engineering_teams}

## 输出要求
生成工程抢险态势汇报。

## 重要（必须遵守）
- 必须使用上面"系统数据"中的数值
- 如果数据显示"待核实"，输出也必须写"待核实"
- 绝对禁止编造任何损毁数字
""" + NO_FABRICATION_RULE,
        expected_output="工程抢险态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块4: 群众安置态势 (并行)
# ============================================================================
def create_shelter_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块4 - 群众安置态势汇报"""
    return Task(
        description="""基于系统数据，生成群众安置态势汇报。

## 系统数据（来自数据库，不可编造）
- 受灾人口：{affected_population_display}
- 安置期限：{days}天

可用物资（来自数据库）：
{available_supplies}

## 输出要求
基于SPHERE标准测算物资需求，列出缺口

## 重要（必须遵守）
- 受灾人口必须使用"系统数据"中的数值
- 如果数据显示"待核实"，输出也必须写"待核实"
- 参考数据库物资库存
""" + NO_FABRICATION_RULE,
        expected_output="群众安置态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块5: 次生灾害分析 (并行)
# ============================================================================
def create_secondary_disaster_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块5 - 次生灾害风险分析"""
    return Task(
        description="""基于灾情数据，分析次生灾害风险。

## 系统数据
灾害类型：{disaster_type}
受灾区域：{affected_area}
震级：{magnitude}

## 输出要求
识别风险、评估等级、提出防范措施""",
        expected_output="次生灾害风险分析文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块6: 通信保障态势 (并行)
# ============================================================================
def create_communication_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块6 - 通信保障态势汇报"""
    return Task(
        description="""基于系统数据，生成通信保障态势汇报。

## 系统数据
- 救援队伍数量：{rescue_teams_count}支

## 输出要求
测算通信设备需求，向通信管理局申请资源
""" + NO_FABRICATION_RULE,
        expected_output="通信保障态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块7: 物资调配态势 (并行)
# ============================================================================
def create_logistics_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块7 - 物资调配态势汇报"""
    return Task(
        description="""基于系统数据，生成物资调配态势汇报。

## 系统数据
- 受灾人口：{affected_population}人

可用物资来源：
{available_supplies}

## 输出要求
测算运输需求，向交通厅申请运输资源
""" + NO_FABRICATION_RULE,
        expected_output="物资调配态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 模块8: 自身保障态势 (并行)
# ============================================================================
def create_self_support_task(agent: Agent, async_exec: bool = True) -> Task:
    """模块8 - 救援力量自身保障态势汇报"""
    return Task(
        description="""基于系统数据，生成救援力量自身保障态势汇报。

## 系统数据
- 救援人员：{rescue_personnel}人
- 医护人员：{medical_staff}人
- 总计：{total_responders}人
- 保障期限：{days}天

## 输出要求
基于SPHERE标准测算后勤保障需求
""" + NO_FABRICATION_RULE,
        expected_output="自身保障态势汇报文本",
        agent=agent,
        async_execution=async_exec,
    )


# ============================================================================
# 汇总任务 - 等待所有并行任务完成
# ============================================================================
def create_summary_task(agent: Agent, context_tasks: list[Task]) -> Task:
    """汇总任务 - 等待所有并行任务完成后生成摘要"""
    return Task(
        description="""汇总所有模块内容，生成简要摘要。

请整理各模块汇报要点，形成向省级领导的一页纸汇报摘要。""",
        expected_output="汇报摘要",
        agent=agent,
        context=context_tasks,  # 等待所有并行任务完成
        async_execution=False,  # 同步执行
    )


# ============================================================================
# 兼容旧代码
# ============================================================================
def create_basic_disaster_task(agent: Agent) -> Task:
    """兼容旧代码"""
    return create_disaster_briefing_task(agent, async_exec=False)
