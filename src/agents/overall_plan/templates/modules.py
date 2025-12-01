"""
资源模块报告的Jinja2模板

业务场景：向省级指挥大厅/省委书记汇报态势并请求资源调拨

每个模块包含三部分：
1. 【已确认情况】：系统收集到的事实数据
2. 【初步估算】：基于已知数据的合理推算（明确标注"待核实"）
3. 【资源需求请求】：需要上级批准调拨的资源清单

模板输出格式符合ICS应急管理标准和政府公文汇报风格。
"""

from typing import Any

from jinja2 import Environment, StrictUndefined


def _format_number(value: int | float) -> str:
    """格式化数字，添加千位分隔符"""
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def _format_or_pending(value: int | float) -> str:
    """格式化数字，0值显示为【】让指挥员填写"""
    if value == 0 or value is None:
        return "【】"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def _format_list(items: list[str], prefix: str = "- ") -> str:
    """格式化列表项，添加前缀"""
    return "\n".join(f"{prefix}{item}" for item in items)


# 创建Jinja2环境，启用严格未定义检查
_env = Environment(undefined=StrictUndefined)
_env.filters["format_number"] = _format_number
_env.filters["format_list"] = _format_list
_env.filters["or_pending"] = _format_or_pending  # 0值显示【】


MODULE_1_TEMPLATE = """## 一、应急救援力量态势与需求

### （一）当前态势
- **已确认被困人员**：{{ trapped_count | or_pending }}人
- **已派出救援力量**：【】
- **救援进展**：【】

### （二）资源需求测算
{% if trapped_count > 0 %}
根据SPHERE国际人道主义标准（每50名被困人员配置1支专业救援队），测算需求如下：

| 资源类型 | 需求数量 | 测算依据 | 优先级 |
|---------|---------|---------|-------|
| 专业救援队 | {{ rescue_teams }}支 | 被困{{ trapped_count }}人÷50人/队 | **紧急** |
| 搜救犬 | {{ search_dogs }}只 | 每队配置2只 | **紧急** |
| 救援人员 | {{ rescue_personnel }}人 | 每队30人 | **紧急** |
{% else %}
（被困人数待确认后测算）
{% endif %}

### （三）拟请求调派力量
【请填写拟调派的救援队伍】

### （四）重点救援区域
【请填写重点救援区域】

### （五）请求事项
1. 请求批准调派【】支专业救援队伍
2. 请求协调【】名救援人员及【】只搜救犬
3. 请求明确救援力量指挥关系和协调机制
"""

MODULE_2_TEMPLATE = """## 二、医疗救护态势与需求

### （一）当前态势
- **已确认伤员**：{{ injured_count | or_pending }}人
- **其中重伤**：{{ serious_injury_count | or_pending }}人
- **医疗救治进展**：【】

### （二）资源需求测算
{% if injured_count > 0 %}
根据SPHERE医疗救护标准，测算需求如下：

| 资源类型 | 需求数量 | 测算依据 | 优先级 |
|---------|---------|---------|-------|
| 医护人员 | {{ medical_staff }}人 | 每20名伤员配1名医护 | **紧急** |
| 担架 | {{ stretchers }}副 | 重伤员人数 | **紧急** |
| 救护车 | {{ ambulances }}辆 | 每10名伤员1辆 | **紧急** |
{% if field_hospitals > 0 %}| 野战医院 | {{ field_hospitals }}所 | 每500伤员1所 | **紧急** |{% endif %}
{% else %}
（伤亡人数待确认后测算）
{% endif %}

### （三）拟协调医疗资源
【请填写拟协调的医院和医疗资源】

### （四）医疗物资需求清单
【请填写医疗物资需求】

### （五）请求事项
1. 请求卫健委协调【】名医护人员支援
2. 请求调拨【】辆救护车
3. 请求协调定点医院开辟绿色通道
"""

MODULE_3_TEMPLATE = """## 三、基础设施损毁态势与抢修需求

### （一）损毁情况统计
| 损毁类型 | 数量 | 数据来源 |
|---------|------|---------|
| 倒塌建筑 | {{ buildings_collapsed | or_pending }}栋 | 【】 |
| 受损建筑 | {{ buildings_damaged | or_pending }}栋 | 【】 |
| 损毁道路 | {{ roads_damaged_km | or_pending }}公里 | 【】 |
| 损毁桥梁 | {{ bridges_damaged | or_pending }}座 | 【】 |
| 停电户数 | {{ power_outage_households | or_pending }}户 | 【】 |

### （二）抢修力量需求测算
（待损毁情况确认后测算）

### （三）抢修优先级建议
【请填写抢修优先级】

### （四）请求事项
1. 请求住建厅协调【】支结构工程队
2. 请求交通厅协调【】支道路抢修队
3. 请求电力公司调派【】支抢修队伍
4. 请求调拨【】台大型机械设备
"""

MODULE_4_TEMPLATE = """## 四、受灾群众安置态势与物资需求

### （一）安置规模
- **预计需安置人口**：{{ affected_population | or_pending }}人
- **安置期限**：{{ days }}天（应急响应期）

### （二）物资需求测算
{% if affected_population > 0 %}
根据SPHERE国际人道主义标准测算：

| 物资类型 | 需求数量 | 测算依据 | 优先级 |
|---------|---------|---------|-------|
| 救灾帐篷 | {{ tents | format_number }}顶 | 每顶容纳5人 | **紧急** |
| 棉被 | {{ blankets | format_number }}床 | 每人2床 | **紧急** |
| 睡垫 | {{ sleeping_mats | format_number }}张 | 每人1张 | **紧急** |
| 饮用水 | {{ water_liters | format_number }}升 | 每人每天20升×{{ days }}天 | **紧急** |
| 应急食品 | {{ food_kg | format_number }}公斤 | 每人每天0.5公斤×{{ days }}天 | **紧急** |
{% else %}
（受灾人口待确认后测算）
{% endif %}

### （三）安置点选址要求
【请填写安置点选址要求】

### （四）特殊群体照护需求
【请填写特殊群体照护需求】

### （五）请求事项
1. 请求民政厅调拨【】顶救灾帐篷
2. 请求调拨【】床棉被、【】张睡垫
3. 请求协调【】升饮用水供应
4. 请求调拨【】公斤应急食品
5. 请求协调安置点卫生设施配置
"""

MODULE_6_TEMPLATE = """## 五、通信保障态势与需求

### （一）通信设备需求测算
（待救援队伍和受灾规模确认后测算）

### （二）指挥通信保障措施
【请填写指挥通信保障措施】

### （三）请求事项
1. 请求通信管理局协调【】部卫星电话
2. 请求调派【】辆移动基站车
3. 请求调拨【】部便携式电台
4. 请求协调应急通信频率
"""

MODULE_7_TEMPLATE = """## 六、物资调配与运输保障需求

### （一）运输保障需求测算
（待受灾规模确认后测算）

### （二）拟调用物资来源
【请填写拟调用物资来源】

### （三）运输通道规划
【请填写运输通道规划】

### （四）请求事项
1. 请求交通厅协调【】辆运输车辆
2. 请求协调【】辆水车
3. 请求开辟救灾物资运输绿色通道
4. 请求协调物资中转站和分发点设置
"""

MODULE_8_TEMPLATE = """## 七、救援力量自身保障需求

### （一）救援人员规模汇总
| 人员类型 | 数量 | 来源 |
|---------|------|------|
| 救援人员 | 【】人 | 【】 |
| 医护人员 | 【】人 | 【】 |
| 工程人员 | 【】人 | 【】 |
| **合计** | **【】人** | - |

### （二）后勤保障物资需求（{{ days }}天）
（待救援人员规模确认后测算）

### （三）安全防护装备需求
【请填写安全防护装备需求】

### （四）请求事项
1. 请求保障【】名救援人员的食宿
2. 请求调拨【】顶救援人员帐篷
3. 请求协调【】公斤餐食和【】升饮用水
4. 请求配置野战厨房【】个
5. 请求协调救援人员安全防护装备
"""

MODULE_TEMPLATES: dict[str, str] = {
    "module_1": MODULE_1_TEMPLATE,
    "module_2": MODULE_2_TEMPLATE,
    "module_3": MODULE_3_TEMPLATE,
    "module_4": MODULE_4_TEMPLATE,
    "module_6": MODULE_6_TEMPLATE,
    "module_7": MODULE_7_TEMPLATE,
    "module_8": MODULE_8_TEMPLATE,
}

# 模块加载时预编译模板，提升性能
_COMPILED_TEMPLATES = {
    key: _env.from_string(tpl) for key, tpl in MODULE_TEMPLATES.items()
}


def render_module_template(
    module_key: str,
    context: dict[str, Any],
) -> str:
    """
    使用给定上下文渲染模块模板

    Args:
        module_key: 模板键（如 "module_1", "module_4"）
        context: 模板上下文，包含计算值和LLM生成的建议

    Returns:
        渲染后的模块文本

    Raises:
        KeyError: 模板键不存在时抛出
        jinja2.UndefinedError: 缺少必需的上下文变量时抛出
    """
    compiled = _COMPILED_TEMPLATES.get(module_key)
    if compiled is None:
        raise KeyError(f"未知的模块模板: {module_key}")

    return compiled.render(**context)
