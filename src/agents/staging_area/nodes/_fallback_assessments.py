from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from src.agents.staging_area.state import (
    SafetyAssessment,
    TerrainAssessment,
    CommunicationAssessment,
)
from src.planning.algorithms.base import haversine_distance, Location


def _uuid(site: Dict[str, Any]) -> UUID:
    raw = site.get("site_id") or site.get("id") or ""
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))


def _name(site: Dict[str, Any]) -> str:
    return str(site.get("name") or site.get("site_name") or "未知")


def fallback_safety_assessments(
    sites: List[Dict[str, Any]],
    *,
    epicenter_lon: Optional[float],
    epicenter_lat: Optional[float],
) -> List[SafetyAssessment]:
    out: List[SafetyAssessment] = []
    for site in sites:
        dist_danger = site.get("distance_to_danger_m")
        slope = site.get("slope_degree")
        lon = site.get("longitude")
        lat = site.get("latitude")

        level = "moderate_risk"
        warnings: List[str] = []
        hazards: List[str] = []

        if isinstance(dist_danger, (int, float)):
            if dist_danger < 200:
                level = "dangerous"
                warnings.append("距离危险区过近（<200m）")
            elif dist_danger < 500:
                level = "high_risk"
                warnings.append("距离危险区偏近（<500m）")
            elif dist_danger < 1000:
                level = "moderate_risk"
            else:
                level = "safe"

        if isinstance(slope, (int, float)) and slope > 15:
            hazards.append("坡度较大，存在滑坡/滚石风险")
            if level == "safe":
                level = "moderate_risk"

        aftershock = "余震影响未知"
        if isinstance(epicenter_lon, (int, float)) and isinstance(epicenter_lat, (int, float)) and isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            dist_km = haversine_distance(Location(epicenter_lat, epicenter_lon), Location(lat, lon))
            if dist_km < 5:
                aftershock = f"距震中约{dist_km:.1f}km，余震影响较高"
            elif dist_km < 15:
                aftershock = f"距震中约{dist_km:.1f}km，余震影响中等"
            else:
                aftershock = f"距震中约{dist_km:.1f}km，余震影响相对较低"

        evac = "撤离可行性未知（建议预设至少2条撤离路线）"
        if level in ("high_risk", "dangerous"):
            evac = "建议提前规划撤离路线并准备应急撤离方案"

        out.append(
            SafetyAssessment(
                site_id=_uuid(site),
                site_name=_name(site),
                safety_level=level,
                secondary_hazard_risks=hazards,
                aftershock_impact=aftershock,
                evacuation_feasibility=evac,
                safety_warnings=warnings,
                confidence=0.4,
            )
        )
    return out


def fallback_terrain_assessments(sites: List[Dict[str, Any]]) -> List[TerrainAssessment]:
    out: List[TerrainAssessment] = []
    for site in sites:
        slope = site.get("slope_degree")
        area = site.get("area_m2")
        stability = str(site.get("ground_stability") or "unknown").lower()

        risks: List[str] = []
        suitability = "fair"

        if isinstance(slope, (int, float)):
            if slope < 10:
                suitability = "good"
            elif slope <= 15:
                suitability = "fair"
            else:
                suitability = "poor"
                risks.append("坡度>15°，不利于重型装备展开")
        else:
            risks.append("缺少坡度数据")

        if isinstance(area, (int, float)):
            if area >= 5000:
                suitability = "excellent" if suitability in ("good", "fair") else suitability
            elif area < 2000:
                risks.append("面积可能不足（<2000m²）")
                suitability = "poor"
        else:
            risks.append("缺少面积数据")

        if stability in ("poor",):
            risks.append("地面稳定性较差")
            suitability = "poor"
        elif stability in ("excellent", "good") and suitability == "fair":
            suitability = "good"

        out.append(
            TerrainAssessment(
                site_id=_uuid(site),
                site_name=_name(site),
                terrain_suitability=suitability,
                slope_assessment=f"坡度={slope}°" if slope is not None else "坡度未知",
                stability_assessment=f"稳定性={stability}",
                expansion_space=f"面积={area}m²" if area is not None else "面积未知",
                terrain_risks=risks,
                confidence=0.4,
            )
        )
    return out


def fallback_communication_assessments(sites: List[Dict[str, Any]]) -> List[CommunicationAssessment]:
    out: List[CommunicationAssessment] = []
    for site in sites:
        network = str(site.get("network_type") or site.get("primary_network_type") or "none").lower()
        signal = str(site.get("signal_quality") or "unknown").lower()

        quality = "none"
        if network in ("5g", "4g_lte"):
            quality = "excellent" if signal == "excellent" else "good" if signal in ("good", "fair") else "fair"
        elif network in ("3g",):
            quality = "fair"
        elif network in ("satellite", "shortwave", "mesh"):
            quality = "fair"

        backup = ["卫星电话", "短波电台"]
        equipment = ["北斗卫星终端", "短波电台"]
        risks: List[str] = []
        if quality in ("poor", "none"):
            risks.append("主用通信不足，需加强备用通信")
        if signal in ("poor", "unknown"):
            risks.append("信号质量不稳定")

        out.append(
            CommunicationAssessment(
                site_id=_uuid(site),
                site_name=_name(site),
                primary_network_quality=quality,
                backup_options=backup,
                communication_risks=risks,
                recommended_equipment=equipment,
                confidence=0.4,
            )
        )
    return out

