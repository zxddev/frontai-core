"""
空间查询工具

提供位置、距离、区域状态等只读空间查询能力。
供SpatialAgent的LangGraph调用。
"""
from __future__ import annotations

import logging
from typing import Optional, List, Tuple

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from src.core.database import AsyncSessionLocal
from src.agents.db.spatial import SpatialRepository
from ..schemas import EntityLocation, NearestUnitResult, AreaStatus

logger = logging.getLogger(__name__)


def _parse_coordinate_string(coord_str: str) -> Optional[Tuple[float, float]]:
    """
    解析坐标字符串为 (longitude, latitude) 元组
    
    支持格式:
    - "108.9,34.2"
    - "108.9, 34.2"
    - "经度108.9纬度34.2"
    """
    try:
        # 简单的逗号分隔格式
        if "," in coord_str:
            parts = coord_str.replace(" ", "").split(",")
            if len(parts) == 2:
                lon, lat = float(parts[0]), float(parts[1])
                # 验证经纬度范围
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    return (lon, lat)
    except (ValueError, TypeError):
        pass
    return None


@tool
async def find_entity_location(
    entity_name: str,
    entity_type: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """
    查询实体位置
    
    根据实体名称（支持模糊匹配和别名）查询其当前位置。
    
    Args:
        entity_name: 实体名称，如"茂县消防大队"、"一号车"、"搜救犬"
        entity_type: 可选类型过滤，DRONE/ROBOT_DOG/TEAM/VEHICLE
        
    Returns:
        包含位置信息的字典:
        - success: 是否成功
        - entities: 匹配的实体列表
        - count: 匹配数量
    """
    logger.info(f"查询实体位置: name={entity_name}, type={entity_type}")
    
    try:
        async with AsyncSessionLocal() as db:
            repo = SpatialRepository(db)
            
            # 模糊查询实体
            entities = await repo.find_by_name_fuzzy(
                name=entity_name,
                entity_type=entity_type,
                limit=5,
            )
            
            if not entities:
                return {
                    "success": False,
                    "error": f"未找到名为'{entity_name}'的实体",
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "entities": [],
                    "count": 0,
                }
            
            # 为有坐标的实体生成位置描述
            for entity in entities:
                if entity.get("longitude") and entity.get("latitude"):
                    loc_desc = await repo.reverse_geocode(
                        (entity["longitude"], entity["latitude"])
                    )
                    if loc_desc:
                        entity["location_desc"] = loc_desc
            
            return {
                "success": True,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "entities": entities,
                "count": len(entities),
            }
            
    except Exception as e:
        logger.exception(f"查询实体位置失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "entity_name": entity_name,
            "entity_type": entity_type,
        }


@tool
async def find_nearest_unit(
    reference_point: str,
    target_type: str,
    count: int = 1,
    status_filter: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """
    查找最近的单位
    
    根据参考点查找最近的特定类型单位。
    
    Args:
        reference_point: 参考点，可以是:
            - 地名: "着火点"、"东门"、"化工厂"、"茂县消防大队"
            - 坐标字符串: "103.85,31.68"
        target_type: 目标类型，TEAM/VEHICLE（DRONE/ROBOT_DOG暂不支持KNN）
        count: 返回数量，默认1
        status_filter: 状态过滤，如"standby"只查待命单位
        
    Returns:
        包含最近单位列表的字典:
        - success: 是否成功
        - units: 最近单位列表（含距离）
        - reference_coords: 解析后的参考点坐标
    """
    logger.info(f"查找最近单位: ref={reference_point}, type={target_type}, count={count}")
    
    try:
        async with AsyncSessionLocal() as db:
            repo = SpatialRepository(db)
            
            # 解析参考点坐标
            coords = _parse_coordinate_string(reference_point)
            
            if not coords:
                # 尝试地名解析
                coords = await repo.resolve_location_name(reference_point)
                
            if not coords:
                return {
                    "success": False,
                    "error": f"无法解析参考点'{reference_point}'为坐标",
                    "reference_point": reference_point,
                    "target_type": target_type,
                    "units": [],
                }
            
            # KNN查询
            units = await repo.find_nearest_knn(
                point=coords,
                entity_type=target_type,
                limit=count,
                status_filter=status_filter,
            )
            
            if not units:
                return {
                    "success": True,
                    "reference_point": reference_point,
                    "reference_coords": {"longitude": coords[0], "latitude": coords[1]},
                    "target_type": target_type,
                    "units": [],
                    "message": f"未找到类型为{target_type}的单位",
                }
            
            # 格式化距离
            for unit in units:
                if "distance_meters" in unit and unit["distance_meters"]:
                    dist_m = unit["distance_meters"]
                    if dist_m < 1000:
                        unit["distance_text"] = f"{int(dist_m)}米"
                    else:
                        unit["distance_text"] = f"{dist_m/1000:.1f}公里"
            
            return {
                "success": True,
                "reference_point": reference_point,
                "reference_coords": {"longitude": coords[0], "latitude": coords[1]},
                "target_type": target_type,
                "units": units,
                "count": len(units),
            }
            
    except Exception as e:
        logger.exception(f"查找最近单位失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "reference_point": reference_point,
            "target_type": target_type,
        }


@tool
async def get_area_status(
    area_id: str,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """
    查询区域状态
    
    获取指定区域（想定）内的单位分布信息。
    
    Args:
        area_id: 区域/想定ID (UUID格式)
        
    Returns:
        包含区域状态的字典:
        - success: 是否成功
        - area_id: 区域ID
        - units_count: 区域内单位数量
        - units: 区域内单位列表
    """
    logger.info(f"查询区域状态: area_id={area_id}")
    
    try:
        async with AsyncSessionLocal() as db:
            repo = SpatialRepository(db)
            
            # 查询区域内单位
            units = await repo.get_units_in_area(
                area_id=area_id,
                entity_types=["TEAM", "VEHICLE"],
            )
            
            # 按类型统计
            team_count = sum(1 for u in units if u.get("entity_type") == "TEAM")
            vehicle_count = sum(1 for u in units if u.get("entity_type") == "VEHICLE")
            
            return {
                "success": True,
                "area_id": area_id,
                "units_count": len(units),
                "team_count": team_count,
                "vehicle_count": vehicle_count,
                "units": units,
            }
            
    except Exception as e:
        logger.exception(f"查询区域状态失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "area_id": area_id,
        }


# 导出工具列表，供LangGraph使用
SPATIAL_TOOLS = [
    find_entity_location,
    find_nearest_unit,
    get_area_status,
]
