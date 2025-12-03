"""
驻扎点选址前端适配API

接口路径: /staging-area/*
提供安全点位查找接口
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from src.domains.staging_area.repository import StagingAreaRepository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staging-area", tags=["前端-驻扎点选址"])


# ============== 请求/响应模型 ==============

class SafePointConstraintsRequest(BaseModel):
    """安全点位筛选约束"""
    min_buffer_m: float = Field(default=500.0, description="距危险区最小缓冲距离(m)")
    max_slope_deg: float = Field(default=15.0, description="最大坡度(度)")
    min_area_m2: Optional[float] = Field(default=None, description="最小面积要求(m²)")
    require_water_supply: bool = Field(default=False, description="是否要求水源")
    require_power_supply: bool = Field(default=False, description="是否要求电源")
    require_helicopter_landing: bool = Field(default=False, description="是否要求直升机起降")
    require_ground_stability: Optional[str] = Field(default=None, description="地面稳定性要求")
    require_network_type: Optional[str] = Field(default=None, description="通信网络类型要求")
    max_distance_to_supply_m: Optional[float] = Field(default=None, description="距补给点最大距离(m)")
    max_distance_to_medical_m: Optional[float] = Field(default=None, description="距医疗点最大距离(m)")
    site_types: Optional[List[str]] = Field(default=None, description="限定场地类型列表")


class FindSafePointRequestV1(BaseModel):
    """安全点位查找请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    center_lon: float = Field(..., description="搜索中心经度")
    center_lat: float = Field(..., description="搜索中心纬度")
    search_radius_m: float = Field(default=30000.0, description="搜索半径(m)")
    constraints: SafePointConstraintsRequest = Field(default_factory=SafePointConstraintsRequest, description="筛选约束条件")
    top_n: int = Field(default=5, description="返回前N个结果")


class SafePointFacilitiesResponse(BaseModel):
    """安全点位设施信息"""
    hasWater: bool = Field(alias="hasWater")
    hasPower: bool = Field(alias="hasPower")
    canHelicopter: bool = Field(alias="canHelicopter")
    networkType: str = Field(alias="networkType")
    groundStability: str = Field(alias="groundStability")

    class Config:
        populate_by_name = True


class SafePointResultResponse(BaseModel):
    """安全点位结果"""
    siteId: UUID = Field(alias="siteId")
    siteCode: str = Field(alias="siteCode")
    name: str
    longitude: float
    latitude: float
    siteType: str = Field(alias="siteType")
    areaM2: Optional[float] = Field(alias="areaM2")
    slopeDegree: Optional[float] = Field(alias="slopeDegree")
    distanceM: float = Field(alias="distanceM", description="距搜索中心距离(m)")
    distanceToDangerM: Optional[float] = Field(alias="distanceToDangerM", description="距危险区距离(m)")
    score: float = Field(description="综合评分 0-1")
    facilities: SafePointFacilitiesResponse
    nearestSupplyDepotM: Optional[float] = Field(alias="nearestSupplyDepotM")
    nearestMedicalPointM: Optional[float] = Field(alias="nearestMedicalPointM")

    class Config:
        populate_by_name = True


class FindSafePointDataResponse(BaseModel):
    """安全点位查找数据响应"""
    sites: List[SafePointResultResponse]
    totalCandidates: int = Field(alias="totalCandidates")
    elapsedMs: int = Field(alias="elapsedMs")

    class Config:
        populate_by_name = True


# ============== 路由 ==============

@router.post("/find-safe-point", response_model=ApiResponse[FindSafePointDataResponse])
async def find_safe_point(
    request: FindSafePointRequestV1,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    查找安全点位
    
    根据中心坐标和筛选条件，查找符合要求的安全点位。
    
    **筛选条件**：
    - 距危险区最小缓冲距离
    - 最大坡度、最小面积
    - 水源、电源、直升机起降要求
    - 地面稳定性、通信网络类型
    - 距补给点/医疗点最大距离
    - 场地类型限定
    
    **返回**：按距离排序的安全点位列表，附带综合评分
    """
    start_time = time.perf_counter()
    logger.info(f"查找安全点位: scenario={request.scenario_id}, center=({request.center_lon}, {request.center_lat})")
    
    try:
        repo = StagingAreaRepository(db)
        constraints = request.constraints
        
        sites = await repo.find_safe_points(
            scenario_id=request.scenario_id,
            center_lon=request.center_lon,
            center_lat=request.center_lat,
            search_radius_m=request.search_radius_m,
            min_buffer_m=constraints.min_buffer_m,
            max_slope_deg=constraints.max_slope_deg,
            min_area_m2=constraints.min_area_m2,
            require_water=constraints.require_water_supply,
            require_power=constraints.require_power_supply,
            require_helicopter=constraints.require_helicopter_landing,
            require_ground_stability=constraints.require_ground_stability,
            require_network_type=constraints.require_network_type,
            max_distance_to_supply_m=constraints.max_distance_to_supply_m,
            max_distance_to_medical_m=constraints.max_distance_to_medical_m,
            site_types=constraints.site_types,
            top_n=request.top_n,
        )
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        results = [
            SafePointResultResponse(
                siteId=s["site_id"],
                siteCode=s["site_code"],
                name=s["name"],
                longitude=s["longitude"],
                latitude=s["latitude"],
                siteType=s["site_type"],
                areaM2=s["area_m2"],
                slopeDegree=s["slope_degree"],
                distanceM=s["distance_m"],
                distanceToDangerM=s["distance_to_danger_m"],
                score=s["score"],
                facilities=SafePointFacilitiesResponse(
                    hasWater=s["has_water_supply"],
                    hasPower=s["has_power_supply"],
                    canHelicopter=s["can_helicopter_land"],
                    networkType=s["primary_network_type"],
                    groundStability=s["ground_stability"],
                ),
                nearestSupplyDepotM=s["nearest_supply_depot_m"],
                nearestMedicalPointM=s["nearest_medical_point_m"],
            )
            for s in sites
        ]
        
        data = FindSafePointDataResponse(
            sites=results,
            totalCandidates=len(results),
            elapsedMs=elapsed_ms,
        )
        
        return ApiResponse.success(data.model_dump(by_alias=True))
        
    except Exception as e:
        logger.exception(f"查找安全点位失败: {e}")
        return ApiResponse.error(500, f"查找安全点位失败: {str(e)}")
