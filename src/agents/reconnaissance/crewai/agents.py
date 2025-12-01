"""CrewAI Agent 定义：设备分配专家

包含两个专家 Agent：
1. 设备能力分析师：根据 base_capabilities 判断设备是否具备侦察能力
2. 任务分配专家：根据灾害类型和目标特征选择最合适的设备组合
"""
from typing import Any

from crewai import Agent


# 侦察相关能力标签（来自 devices_v2.base_capabilities）
RECON_CAPABILITIES = {
    "aerial_recon",      # 空中侦察
    "ground_recon",      # 地面侦察
    "water_recon",       # 水面侦察
    "3d_mapping",        # 3D建模
    "video_stream",      # 实时视频
    "thermal_imaging",   # 热成像
    "life_detection",    # 生命探测
    "environment_analysis",  # 环境分析
}

# 非侦察能力（这些设备不应用于侦察任务）
NON_RECON_CAPABILITIES = {
    "cargo_delivery",    # 物资投送
    "cargo_transport",   # 货物运输
    "medical_delivery",  # 医疗投送
    "water_rescue",      # 水上救援
    "search_rescue",     # 搜救（救援为主，非侦察）
    "communication_relay",  # 通讯组网
}


def create_device_screener(llm: Any) -> Agent:
    """创建设备筛选专家 Agent
    
    职责：根据设备能力判断哪些设备适合执行侦察任务
    """
    return Agent(
        role="设备能力分析师",
        goal="筛选出具备侦察能力的无人设备，排除物资投送、救援等非侦察用途设备",
        backstory="""你是应急指挥中心的设备能力分析师，精通各类无人装备的技术参数和作战能力。

你的核心职责：
1. 分析设备的 base_capabilities（基础能力标签）
2. 识别具备侦察能力的设备：aerial_recon（空中侦察）、ground_recon（地面侦察）、
   water_recon（水面侦察）、3d_mapping（3D建模）、video_stream（实时视频）、
   thermal_imaging（热成像）、life_detection（生命探测）、environment_analysis（环境分析）
3. 排除非侦察设备：cargo_delivery（物资投送）、medical_delivery（医疗投送）、
   water_rescue（水上救援）、communication_relay（通讯组网）

关键原则：
- 物资投送无人机是送物资的，不能用于侦察
- 人员搜救设备是救人的，不适合初期侦察
- 只有具备侦察/探测/成像能力的设备才能执行侦察任务

你熟悉军用和民用无人装备体系。""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def create_mission_planner(llm: Any) -> Agent:
    """创建任务分配专家 Agent
    
    职责：根据灾害类型和目标特征，为每个侦察目标选择最合适的设备
    """
    return Agent(
        role="侦察任务分配专家",
        goal="为每个侦察目标匹配最适合的无人设备，生成合理的任务分配方案",
        backstory="""你是应急指挥中心的侦察任务规划专家，擅长根据灾情特点进行资源调配。

你的核心职责：
1. 分析每个侦察目标的特征（灾害类型、地形、风险等级）
2. 根据设备能力和作业环境进行匹配
3. 生成人类可读的分配理由

【关键】环境类型匹配规则：
- air（无人机）：万能，可侦察陆地和水域目标
- land（机器狗）：只能侦察陆地目标，不能下水
- sea（无人艇）：只能侦察水域目标（淹没区、水库、河流等）

匹配原则：
- 滑坡/地震废墟（陆地）：无人机航拍 + 机器狗进入复杂地形
- 淹没区域（水域）：无人机航拍 + 无人艇水面侦察
- 化工厂/污染区（陆地）：优先无人机远程侦察
- 建筑内部（陆地）：机器狗可进入狭小空间
- 水库/河流（水域）：无人机 + 无人艇配合

你需要考虑：
1. 设备的 env_type（作业环境）必须与目标环境兼容
2. 设备的 applicable_disasters（适用灾害类型）
3. 设备的 forbidden_disasters（禁止使用场景）
4. 目标的优先级（critical > high > medium > low）

你熟悉ICS事故指挥系统和无人装备战术运用。""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
