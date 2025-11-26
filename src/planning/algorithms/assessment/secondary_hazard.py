"""
次生灾害风险预测算法

业务逻辑:
=========
1. 地震后火灾预测:
   - 燃气管网破损概率 = f(烈度, 管网密度, 管道年限)
   - 电气短路概率 = f(烈度, 建筑类型)
   - 综合火灾风险 = 1 - (1-P_gas)*(1-P_elec)

2. 滑坡/泥石流预测:
   - 基于降雨阈值模型: 累计雨量 vs 临界雨量
   - 考虑: 坡度、土壤饱和度、植被覆盖
   - 稳定性分析: FS = 抗滑力/下滑力

3. 余震预测:
   - Modified Omori法则: n(t) = K / (t + c)^p
   - Bath定律: 最大余震震级 ≈ 主震震级 - 1.2

4. 堰塞湖风险:
   - 基于滑坡体积和河道特征
   - 溃坝风险评估

算法实现:
=========
- 火灾: P = 1 - exp(-λ * I * ρ_pipe * age_factor)
- 滑坡: FS = (c + (γ-γw)*z*cos²β*tanφ) / (γ*z*sinβ*cosβ)
- 余震频率: n(t) = K*(t+c)^(-p), 典型值 p≈1.0-1.4
"""
from __future__ import annotations

import math
import logging
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus, Location

logger = logging.getLogger(__name__)


@dataclass
class SecondaryHazardRisk:
    """次生灾害风险结果"""
    hazard_type: str       # fire/landslide/aftershock/dam_break
    probability: float     # 发生概率 0-1
    severity: str          # low/medium/high/critical
    affected_area_km2: float
    time_window_hours: float  # 预测时间窗口
    risk_factors: Dict[str, float]  # 各因素贡献
    recommendations: List[str]  # 建议措施


class SecondaryHazardPredictor(AlgorithmBase):
    """
    次生灾害风险预测器
    
    使用示例:
    ```python
    predictor = SecondaryHazardPredictor()
    result = predictor.run({
        "primary_disaster": "earthquake",
        "params": {
            "intensity": 8,  # 烈度
            "gas_pipeline_density": 0.5,  # 管网密度 km/km²
            "building_age_years": 20,
        },
        "hazard_types": ["fire", "aftershock"]
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "prediction_window_hours": 24,
            "confidence_threshold": 0.3,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "primary_disaster" not in problem:
            return False, "缺少 primary_disaster 字段"
        if "params" not in problem:
            return False, "缺少 params 字段"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """预测次生灾害风险"""
        primary = problem["primary_disaster"]
        params = problem["params"]
        hazard_types = problem.get("hazard_types", ["fire", "landslide", "aftershock"])
        
        risks = []
        
        for hazard_type in hazard_types:
            if hazard_type == "fire":
                risk = self._predict_fire_risk(primary, params)
            elif hazard_type == "landslide":
                risk = self._predict_landslide_risk(params)
            elif hazard_type == "aftershock":
                risk = self._predict_aftershock(params)
            elif hazard_type == "dam_break":
                risk = self._predict_dam_break_risk(params)
            else:
                continue
            
            if risk:
                risks.append(risk)
        
        # 按风险概率排序
        risks.sort(key=lambda r: -r.probability)
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=risks,
            metrics={
                "total_risks": len(risks),
                "high_risks": sum(1 for r in risks if r.severity in ["high", "critical"]),
                "max_probability": max((r.probability for r in risks), default=0),
            },
            trace={"primary_disaster": primary, "analyzed_types": hazard_types},
            time_ms=0
        )
    
    def _predict_fire_risk(self, primary: str, params: Dict) -> SecondaryHazardRisk:
        """
        预测次生火灾风险
        
        模型: P(fire) = 1 - exp(-λ * risk_score)
        risk_score = intensity_factor * pipeline_factor * age_factor
        """
        intensity = params.get("intensity", 6)
        pipeline_density = params.get("gas_pipeline_density", 0.3)
        building_age = params.get("building_age_years", 15)
        
        # 烈度因子 (烈度>=7显著增加)
        intensity_factor = max(0, (intensity - 5) / 3) ** 2
        
        # 管网密度因子
        pipeline_factor = pipeline_density * 2
        
        # 建筑年限因子 (老旧建筑风险更高)
        age_factor = min(2.0, building_age / 20)
        
        # 综合风险分数
        risk_score = intensity_factor * (1 + pipeline_factor) * age_factor
        
        # 转换为概率
        lambda_param = 0.15
        probability = 1 - math.exp(-lambda_param * risk_score)
        probability = min(0.95, max(0.01, probability))
        
        # 确定严重程度
        if probability >= 0.6:
            severity = "critical"
        elif probability >= 0.4:
            severity = "high"
        elif probability >= 0.2:
            severity = "medium"
        else:
            severity = "low"
        
        # 估算影响范围
        affected_area = params.get("affected_area_km2", 5) * probability * 0.3
        
        return SecondaryHazardRisk(
            hazard_type="fire",
            probability=round(probability, 3),
            severity=severity,
            affected_area_km2=round(affected_area, 2),
            time_window_hours=24,
            risk_factors={
                "intensity": round(intensity_factor, 2),
                "pipeline": round(pipeline_factor, 2),
                "building_age": round(age_factor, 2),
            },
            recommendations=self._get_fire_recommendations(severity)
        )
    
    def _predict_landslide_risk(self, params: Dict) -> SecondaryHazardRisk:
        """
        预测滑坡/泥石流风险
        
        模型: 基于安全系数 FS (Factor of Safety)
        FS < 1.0: 不稳定
        FS = 1.0-1.3: 临界稳定
        FS > 1.3: 稳定
        
        简化公式: FS = (c' + σ'*tanφ') / τ
        """
        rainfall_mm = params.get("rainfall_accumulated_mm", 0)
        slope_angle = params.get("slope_angle_deg", 20)
        soil_saturation = params.get("soil_saturation", 0.5)
        vegetation_cover = params.get("vegetation_cover", 0.5)
        
        # 临界雨量 (mm) - 随坡度增加而降低
        critical_rainfall = 150 - slope_angle * 2
        
        # 降雨触发因子
        rainfall_factor = rainfall_mm / critical_rainfall if critical_rainfall > 0 else 2
        
        # 坡度因子 (>30度显著增加风险)
        slope_factor = max(0, (slope_angle - 15) / 20)
        
        # 土壤饱和度因子
        saturation_factor = soil_saturation ** 2
        
        # 植被保护因子 (降低风险)
        vegetation_protection = 1 - vegetation_cover * 0.4
        
        # 综合风险
        risk_score = (rainfall_factor * slope_factor * saturation_factor * vegetation_protection)
        
        # 安全系数估算
        fs = 1.5 / (1 + risk_score) if risk_score > 0 else 2.0
        
        # 转换为概率
        if fs < 1.0:
            probability = 0.8 + (1 - fs) * 0.2
        elif fs < 1.3:
            probability = 0.3 + (1.3 - fs) * 1.67
        else:
            probability = max(0.05, 0.3 - (fs - 1.3) * 0.3)
        
        probability = min(0.95, max(0.01, probability))
        
        # 严重程度
        if probability >= 0.6:
            severity = "critical"
        elif probability >= 0.4:
            severity = "high"
        elif probability >= 0.2:
            severity = "medium"
        else:
            severity = "low"
        
        return SecondaryHazardRisk(
            hazard_type="landslide",
            probability=round(probability, 3),
            severity=severity,
            affected_area_km2=params.get("slope_area_km2", 1),
            time_window_hours=48,
            risk_factors={
                "rainfall": round(rainfall_factor, 2),
                "slope": round(slope_factor, 2),
                "saturation": round(saturation_factor, 2),
                "safety_factor": round(fs, 2),
            },
            recommendations=self._get_landslide_recommendations(severity)
        )
    
    def _predict_aftershock(self, params: Dict) -> SecondaryHazardRisk:
        """
        预测余震
        
        模型: Modified Omori Law
        n(t) = K * (t + c)^(-p)
        
        Bath定律: 最大余震 ≈ 主震 - 1.2
        """
        main_magnitude = params.get("magnitude", 6.0)
        hours_since_main = params.get("hours_since_main", 1)
        
        # Omori参数 (经验值)
        K = 10 ** (main_magnitude - 4)  # 与主震震级相关
        c = 0.1  # 时间偏移 (天)
        p = 1.1  # 衰减指数
        
        # 预测未来24小时余震数量
        t_days = hours_since_main / 24
        t_end = t_days + 1  # 未来1天
        
        # 积分计算余震数
        if p != 1:
            n_aftershocks = K * ((t_end + c)**(1-p) - (t_days + c)**(1-p)) / (1-p)
        else:
            n_aftershocks = K * math.log((t_end + c) / (t_days + c))
        
        # 最大余震震级 (Bath定律)
        max_aftershock_mag = main_magnitude - 1.2
        
        # 有感余震概率 (>=4级)
        prob_felt = min(0.95, n_aftershocks * 0.1) if max_aftershock_mag >= 4 else 0.1
        
        # 强余震概率 (>=5级)
        prob_strong = prob_felt * 0.3 if max_aftershock_mag >= 5 else 0.05
        
        # 使用有感余震概率作为主要指标
        probability = prob_felt
        
        if prob_strong >= 0.3:
            severity = "critical"
        elif prob_strong >= 0.15:
            severity = "high"
        elif prob_felt >= 0.3:
            severity = "medium"
        else:
            severity = "low"
        
        return SecondaryHazardRisk(
            hazard_type="aftershock",
            probability=round(probability, 3),
            severity=severity,
            affected_area_km2=params.get("affected_area_km2", 100),
            time_window_hours=24,
            risk_factors={
                "expected_count": round(n_aftershocks, 1),
                "max_magnitude": round(max_aftershock_mag, 1),
                "prob_strong_aftershock": round(prob_strong, 3),
                "omori_K": round(K, 2),
            },
            recommendations=self._get_aftershock_recommendations(severity, max_aftershock_mag)
        )
    
    def _predict_dam_break_risk(self, params: Dict) -> SecondaryHazardRisk:
        """预测堰塞湖/溃坝风险"""
        landslide_volume_m3 = params.get("landslide_volume_m3", 0)
        river_flow_m3s = params.get("river_flow_m3s", 10)
        dam_height_m = params.get("dam_height_m", 0)
        
        if landslide_volume_m3 == 0 or dam_height_m == 0:
            return SecondaryHazardRisk(
                hazard_type="dam_break",
                probability=0.05,
                severity="low",
                affected_area_km2=0,
                time_window_hours=72,
                risk_factors={},
                recommendations=["持续监测"]
            )
        
        # 堰塞体稳定性估算
        # 体积越大、水流越急，风险越高
        volume_factor = min(2.0, landslide_volume_m3 / 1e6)
        flow_factor = min(2.0, river_flow_m3s / 50)
        
        # 溃坝概率
        probability = min(0.9, 0.1 + volume_factor * flow_factor * 0.3)
        
        if probability >= 0.5:
            severity = "critical"
        elif probability >= 0.3:
            severity = "high"
        elif probability >= 0.15:
            severity = "medium"
        else:
            severity = "low"
        
        # 下游影响范围估算
        affected_area = dam_height_m * river_flow_m3s * 0.01
        
        return SecondaryHazardRisk(
            hazard_type="dam_break",
            probability=round(probability, 3),
            severity=severity,
            affected_area_km2=round(affected_area, 2),
            time_window_hours=72,
            risk_factors={
                "volume_factor": round(volume_factor, 2),
                "flow_factor": round(flow_factor, 2),
            },
            recommendations=self._get_dam_break_recommendations(severity)
        )
    
    def _get_fire_recommendations(self, severity: str) -> List[str]:
        """获取火灾风险应对建议"""
        base = ["关闭燃气总阀", "切断非必要电源"]
        if severity in ["critical", "high"]:
            return base + ["预置消防力量", "清理易燃物", "设立隔离带"]
        elif severity == "medium":
            return base + ["加强巡查", "备好灭火器材"]
        return base
    
    def _get_landslide_recommendations(self, severity: str) -> List[str]:
        """获取滑坡风险应对建议"""
        if severity == "critical":
            return ["立即撤离危险区", "设置警戒线", "持续监测", "准备应急通道"]
        elif severity == "high":
            return ["疏散危险区人员", "加强监测频率", "预置救援力量"]
        elif severity == "medium":
            return ["发布预警", "加强巡查", "准备疏散方案"]
        return ["常规监测", "关注天气变化"]
    
    def _get_aftershock_recommendations(self, severity: str, max_mag: float) -> List[str]:
        """获取余震风险应对建议"""
        base = ["远离危险建筑", "保持通信畅通"]
        if severity in ["critical", "high"]:
            return base + [
                f"警惕{max_mag:.1f}级左右余震",
                "暂停危险区域作业",
                "加固临时安置点"
            ]
        elif severity == "medium":
            return base + ["注意建筑安全", "制定撤离预案"]
        return base
    
    def _get_dam_break_recommendations(self, severity: str) -> List[str]:
        """获取堰塞湖风险应对建议"""
        if severity == "critical":
            return [
                "下游居民立即撤离",
                "24小时监测水位",
                "准备泄洪/爆破方案",
                "通知下游所有村镇"
            ]
        elif severity == "high":
            return ["加强水位监测", "制定撤离方案", "预置救援力量"]
        elif severity == "medium":
            return ["定时监测", "评估排险方案"]
        return ["常规监测"]
