"""
驻扎点选址常量配置

基于中国国家标准和国际研究的安全距离与评估权重配置。

参考标准:
- GB 21734-2008 地震应急避难场所 场址及配套设施
- GB 51143-2015 防灾避难场所设计规范（2021年修订版）
- GB 50011-2010 建筑抗震设计规范
- GB 50201-2014 防洪标准
- 公路泥石流防治工程设计规范
- 滑坡防治设计规范
- GIS-AHP-TOPSIS 多准则决策方法

安全距离依据:
- GB 51143-2015 规定建筑物倒塌安全距离为建筑高度的1.5倍
- 重要建筑距活动断裂带至少3km（国家标准项目-活动断层避让）
- 涉及危险物质的工程距活动断裂带至少6km
"""
from __future__ import annotations

from typing import Dict


# ============== 灾害类型安全距离配置 ==============
# 单位: 米 (m)
# 基于中国国家标准确定的最小安全距离

HAZARD_SAFE_DISTANCES: Dict[str, int] = {
    # 地震烈度相关（依据GB 51143-2015和活动断层避让标准）
    # 红区(IX度以上)：距活动断裂带至少3km，考虑余震和次生灾害风险
    # 橙区(VII-VIII度)：中等烈度区，建筑损坏风险高
    # 黄区(VI度)：轻度影响区，仍需保持安全距离
    "seismic_red": 5000,        # 高烈度核心区(IX度以上)，5km安全距离
    "seismic_orange": 3000,     # 中烈度影响区(VII-VIII度)，3km安全距离
    "seismic_yellow": 1000,     # 低烈度影响区(VI度)，1km安全距离

    # 次生灾害 - 地质灾害
    "landslide": 1000,          # 滑坡区，参考滑坡防治设计规范
    "debris_flow": 500,         # 泥石流区，参考公路泥石流防治工程设计规范
    "liquefaction": 800,        # 液化区，地基不稳定

    # 次生灾害 - 水文灾害
    "flooded": 800,             # 洪水区，参考 GB 50201-2014 防洪标准
    "dammed_lake": 3000,        # 堰塞湖影响区，溃决风险极高

    # 次生灾害 - 其他
    "fire": 500,                # 火灾区，热辐射安全距离
    "contaminated": 1000,       # 污染区（化工泄漏等）

    # 通用危险区
    "danger_zone": 500,         # 通用危险区
    "blocked": 300,             # 封锁区（道路不通，但无直接危险）
    "collapsed": 500,           # 坍塌区，建筑倒塌风险

    # 默认值
    "default": 500,
}


# ============== 灾害类型中文名称映射 ==============

HAZARD_TYPE_NAMES: Dict[str, str] = {
    # 地震烈度相关
    "seismic_red": "高烈度核心区",
    "seismic_orange": "中烈度影响区",
    "seismic_yellow": "低烈度影响区",

    # 次生灾害 - 地质灾害
    "landslide": "滑坡区",
    "debris_flow": "泥石流区",
    "liquefaction": "液化区",

    # 次生灾害 - 水文灾害
    "flooded": "洪水区",
    "dammed_lake": "堰塞湖影响区",

    # 次生灾害 - 其他
    "fire": "火灾区",
    "contaminated": "污染区",

    # 通用危险区
    "danger_zone": "危险区",
    "blocked": "封锁区",
    "collapsed": "坍塌区",
}


# ============== 评估维度权重配置 ==============
# 基于 GIS-AHP-TOPSIS 多准则决策方法
# 总权重 = 1.0
# 安全第一原则：灾害风险权重最高

EVALUATION_WEIGHTS: Dict[str, float] = {
    "hazard_risk": 0.50,        # 灾害风险评分 - 最重要，直接关系生命安全（提高到50%）
    "terrain": 0.20,            # 地形安全评分 - 坡度、稳定性、高程
    "accessibility": 0.15,      # 可达性评分 - 距离、道路、补给、医疗
    "facility": 0.10,           # 设施条件评分 - 水电、直升机、面积
    "communication": 0.05,      # 通信质量评分 - 网络类型、信号质量
}


# ============== 子维度权重配置 ==============

# 灾害风险子维度权重（各类灾害的相对重要性）
HAZARD_RISK_WEIGHTS: Dict[str, float] = {
    # 地震烈度区域（最高风险）
    "seismic_red": 1.0,         # 高烈度核心区，风险最高
    "seismic_orange": 0.9,      # 中烈度影响区
    "seismic_yellow": 0.7,      # 低烈度影响区
    # 次生灾害
    "dammed_lake": 1.0,         # 堰塞湖风险最高，溃决后果严重
    "landslide": 0.9,           # 滑坡风险高
    "debris_flow": 0.85,        # 泥石流风险高
    "flooded": 0.8,             # 洪水风险
    "fire": 0.7,                # 火灾风险
    "collapsed": 0.6,           # 坍塌风险
    "liquefaction": 0.6,        # 液化风险
    "contaminated": 0.5,        # 污染风险
    "danger_zone": 0.5,         # 通用危险区
    "blocked": 0.3,             # 封锁区（主要影响通行）
}

# 地形安全子维度权重
TERRAIN_WEIGHTS: Dict[str, float] = {
    "slope": 0.40,              # 坡度
    "ground_stability": 0.40,   # 地面稳定性
    "elevation": 0.20,          # 高程（避免过低或过高）
}

# 可达性子维度权重
ACCESSIBILITY_WEIGHTS: Dict[str, float] = {
    "distance_to_center": 0.30,     # 距搜索中心距离
    "nearest_road": 0.30,           # 距道路距离
    "nearest_supply": 0.20,         # 距补给点距离
    "nearest_medical": 0.20,        # 距医疗点距离
}

# 设施条件子维度权重
FACILITY_WEIGHTS: Dict[str, float] = {
    "water_supply": 0.30,       # 水源
    "power_supply": 0.25,       # 电源
    "helicopter": 0.20,         # 直升机起降
    "area": 0.25,               # 面积
}


# ============== 评分阈值配置 ==============

# 坡度评分阈值（度）
SLOPE_THRESHOLDS: Dict[str, float] = {
    "excellent": 5.0,           # ≤5° 满分
    "good": 10.0,               # ≤10° 良好
    "acceptable": 15.0,         # ≤15° 可接受
    "poor": 25.0,               # ≤25° 较差
    "max": 35.0,                # >35° 不可用
}

# 地面稳定性评分映射
GROUND_STABILITY_SCORES: Dict[str, float] = {
    "excellent": 1.0,
    "good": 0.8,
    "moderate": 0.5,
    "poor": 0.2,
    "unknown": 0.4,             # 未知时给予中等偏低分数
}

# 网络类型评分映射
NETWORK_TYPE_SCORES: Dict[str, float] = {
    "5g": 1.0,
    "4g_lte": 0.85,
    "satellite": 0.7,           # 卫星通信可靠但延迟高
    "mesh": 0.6,                # 自组网
    "3g": 0.5,
    "shortwave": 0.4,           # 短波通信
    "none": 0.0,
}

# 信号质量修正系数
SIGNAL_QUALITY_MULTIPLIERS: Dict[str, float] = {
    "excellent": 1.0,
    "good": 0.9,
    "fair": 0.7,
    "poor": 0.4,
    "unknown": 0.6,
}

# 面积评分阈值（平方米）
AREA_THRESHOLDS: Dict[str, float] = {
    "excellent": 5000.0,        # ≥5000m² 满分
    "good": 3000.0,             # ≥3000m² 良好
    "acceptable": 2000.0,       # ≥2000m² 可接受
    "minimum": 1000.0,          # ≥1000m² 最低要求
}


# ============== 距离评分配置 ==============

# 距离评分的参考值（超过此值得分为0）
DISTANCE_REFERENCE_VALUES: Dict[str, float] = {
    "search_radius": 30000.0,       # 搜索半径参考值 30km
    "nearest_road": 500.0,          # 距道路参考值 500m
    "nearest_supply": 10000.0,      # 距补给点参考值 10km
    "nearest_medical": 5000.0,      # 距医疗点参考值 5km
}


# ============== 风险提示阈值配置 ==============

# 风险提示的距离阈值倍数
RISK_WARNING_THRESHOLDS: Dict[str, float] = {
    "critical": 1.0,            # 低于安全距离 - 严重警告
    "warning": 1.5,             # 1-1.5倍安全距离 - 警告
    "caution": 2.0,             # 1.5-2倍安全距离 - 注意
}

# 坡度风险提示阈值
SLOPE_WARNING_THRESHOLDS: Dict[str, float] = {
    "warning": 12.0,            # >12° 警告
    "caution": 8.0,             # >8° 注意
}
