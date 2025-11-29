"""
资源模块报告的Jinja2模板

每个模板组合:
1. SPHERE标准计算的数值（确定性）
2. LLM生成的建议（通过Instructor结构化）

模板输出格式符合ICS应急管理标准。
"""

from typing import Any

from jinja2 import Environment, StrictUndefined


def _format_number(value: int | float) -> str:
    """格式化数字，添加千位分隔符"""
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


MODULE_1_TEMPLATE = """## 一、应急救援力量部署

### （一）救援力量需求
根据被困人员数量（{{ trapped_count }}人），按照每50人配置1支专业救援队的标准，需调派：
- 专业救援队伍：{{ rescue_teams }}支
- 搜救犬：{{ search_dogs }}只
- 救援人员：{{ rescue_personnel }}人

### （二）队伍来源建议
{% for source in team_sources %}
- {{ source }}
{% endfor %}

### （三）分阶段部署计划
{% for phase in deployment_phases %}
{{ loop.index }}. {{ phase }}
{% endfor %}

### （四）重点救援区域
{% for area in priority_areas %}
- {{ area }}
{% endfor %}

### （五）协调配合
{{ coordination_suggestions }}

### （六）特殊装备配置
{% for equipment in special_equipment %}
- {{ equipment }}
{% endfor %}
"""

MODULE_2_TEMPLATE = """## 二、医疗救护部署

### （一）医疗资源需求
根据伤亡人数（伤员{{ injured_count }}人，其中重伤{{ serious_injury_count }}人），需配置：
- 医护人员：{{ medical_staff }}人（按每20名伤员配置1名医护）
- 担架：{{ stretchers }}副
- 救护车：{{ ambulances }}辆
{% if field_hospitals > 0 %}
- 野战医院：{{ field_hospitals }}所
{% endif %}

### （二）伤员分诊方案
{{ triage_plan }}

### （三）医院协调
{% for hospital in hospital_coordination %}
- {{ hospital }}
{% endfor %}

### （四）医疗物资优先配置
{% for supply in medical_supply_priorities %}
- {{ supply }}
{% endfor %}

### （五）临时医疗点选址
{% for criteria in field_hospital_location_criteria %}
- {{ criteria }}
{% endfor %}

### （六）伤员转运通道
{{ evacuation_routes }}
"""

MODULE_3_TEMPLATE = """## 三、基础设施抢修

### （一）损毁情况统计
- 倒塌建筑：{{ buildings_collapsed }}栋
- 受损建筑：{{ buildings_damaged }}栋
- 损毁道路：{{ roads_damaged_km }}公里
- 损毁桥梁：{{ bridges_damaged }}座
- 停电户数：{{ power_outage_households }}户

### （二）抢修力量需求
- 结构工程队：{{ structural_engineering_teams }}支
- 道路抢修队：{{ road_repair_teams }}支
- 桥梁抢修队：{{ bridge_repair_teams }}支
- 电力抢修队：{{ power_restoration_teams }}支
- 工程人员总计：{{ total_personnel }}人
- 挖掘机等大型机械：{{ excavators }}台

### （三）抢修优先级
{% for priority in repair_priorities %}
{{ loop.index }}. {{ priority }}
{% endfor %}

### （四）临时通道方案
{% for solution in temporary_solutions %}
- {{ solution }}
{% endfor %}

### （五）危险建筑排查
{{ safety_inspection_plan }}

### （六）设备部署
{% for deployment in equipment_deployment %}
- {{ deployment }}
{% endfor %}

### （七）电力恢复方案
{{ power_restoration_plan }}
"""

MODULE_4_TEMPLATE = """## 四、临时安置与生活保障

### （一）安置规模
根据SPHERE国际人道主义标准，需安置受灾群众{{ affected_population | format_number }}人，安置期{{ days }}天。

### （二）物资需求
| 物资类型 | 数量 | 标准依据 |
|---------|------|----------|
| 救灾帐篷 | {{ tents | format_number }}顶 | 每顶容纳5人 |
| 棉被 | {{ blankets | format_number }}床 | 每人2床 |
| 睡垫 | {{ sleeping_mats | format_number }}张 | 每人1张 |
| 饮用水 | {{ water_liters | format_number }}升 | 每人每天20升×{{ days }}天 |
| 应急食品 | {{ food_kg | format_number }}公斤 | 每人每天0.5公斤×{{ days }}天 |

### （三）安置点选址标准
{% for criteria in site_selection_criteria %}
- {{ criteria }}
{% endfor %}

### （四）特殊群体照护
{{ special_groups_care }}

### （五）卫生设施配置
{% for facility in sanitation_facilities %}
- {{ facility }}
{% endfor %}

### （六）饮水供应方案
{{ water_supply_plan }}

### （七）食品发放方案
{{ food_distribution_plan }}

### （八）扩展预案
{{ expansion_considerations }}
"""

MODULE_6_TEMPLATE = """## 六、通信与信息保障

### （一）通信设备需求
根据救援队伍数量（{{ rescue_teams }}支）和受灾人口（{{ affected_population | format_number }}人），需配置：
- 卫星电话：{{ satellite_phones }}部
- 移动基站车：{{ mobile_base_stations }}辆
- 便携式电台：{{ portable_radios }}部
- 通信保障发电机：{{ generators_for_communication }}台

### （二）网络恢复方案
{{ network_restoration_plan }}

### （三）指挥通信保障
{% for measure in command_communication %}
- {{ measure }}
{% endfor %}

### （四）信息发布与舆情监控
{{ public_information }}

### （五）通信冗余方案
{{ redundancy_plan }}

### （六）频率协调
{{ frequency_coordination }}
"""

MODULE_7_TEMPLATE = """## 七、物资调拨与运输保障

### （一）运输需求
根据受灾人口（{{ affected_population | format_number }}人）和安置期（{{ days }}天），需配置：
- 运输车辆：{{ transport_trucks }}辆
- 物资分发点：{{ distribution_points }}个
- 叉车：{{ forklifts }}辆
- 水车：{{ water_tankers }}辆
- 医疗转运车：{{ medical_transport_vehicles }}辆

### （二）物资来源
{% for source in supply_sources %}
- {{ source }}
{% endfor %}

### （三）运输通道规划
{% for route in transport_routes %}
- {{ route }}
{% endfor %}

### （四）物资分发方案
{{ distribution_plan }}

### （五）物资追踪管理
{{ tracking_system }}

### （六）道路中断替代方案
{{ alternative_routes }}
"""

MODULE_8_TEMPLATE = """## 八、救援力量自身保障

### （一）救援人员规模
- 救援人员：{{ total_rescue_personnel }}人
- 医护人员：{{ total_medical_staff }}人
- 工程人员：{{ total_engineering_personnel }}人
- **总计：{{ total_responders }}人**

### （二）保障物资需求（{{ days }}天）
| 物资类型 | 数量 | 标准依据 |
|---------|------|----------|
| 救援人员帐篷 | {{ responder_tents }}顶 | 每顶容纳4人 |
| 餐食 | {{ responder_food_kg | format_number }}公斤 | 每人每天0.6公斤 |
| 饮用水 | {{ responder_water_liters | format_number }}升 | 每人每天25升 |
| 野战厨房 | {{ field_kitchens }}个 | 每200人1个 |
| 休息区 | {{ rest_areas }}处 | 每100人1处 |

### （三）驻扎安排
{{ camp_arrangement }}

### （四）轮换制度
{{ shift_rotation }}

### （五）健康监测
{{ health_monitoring }}

### （六）安全防护装备
{% for equipment in safety_equipment %}
- {{ equipment }}
{% endfor %}

### （七）心理支持
{{ mental_health_support }}
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
