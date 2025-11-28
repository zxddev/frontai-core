"""
态势标绘工具

供Agent调用的LangChain Tools，封装PlottingService。
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PlotPointArgs(BaseModel):
    """标绘点参数"""
    scenario_id: str = Field(description="Scenario ID (UUID format)")
    plotting_type: str = Field(
        description="Plot type: event_point / rescue_target / situation_point / resettle_point / resource_point"
    )
    name: str = Field(description="Name of the plot")
    longitude: float = Field(description="Longitude")
    latitude: float = Field(description="Latitude")
    description: Optional[str] = Field(None, description="Description text")
    level: Optional[int] = Field(None, description="Severity level 1-5 (only for rescue_target)")


class PlotCircleArgs(BaseModel):
    """标绘圆形区域参数"""
    scenario_id: str = Field(description="Scenario ID (UUID format)")
    plotting_type: str = Field(
        description="Type: danger_area (orange) / safety_area (green) / command_post_candidate (blue)"
    )
    name: str = Field(description="Area name")
    center_longitude: float = Field(description="Center longitude")
    center_latitude: float = Field(description="Center latitude")
    radius_m: float = Field(default=500.0, description="Radius in meters, default 500")
    description: Optional[str] = Field(None, description="Description text")


@tool(args_schema=PlotPointArgs)
async def plot_point(
    scenario_id: str,
    plotting_type: str,
    name: str,
    longitude: float,
    latitude: float,
    description: Optional[str] = None,
    level: Optional[int] = None,
) -> str:
    """
    Plot a point on the map.
    
    Types:
    - event_point: Event marker icon
    - rescue_target: Rescue target with ripple animation
    - situation_point: Text label
    - resettle_point: Resettlement point
    - resource_point: Resource point
    """
    from src.domains.plotting.service import PlottingService
    from src.domains.plotting.schemas import PlottingType, PlotPointRequest
    
    if not scenario_id:
        return "Error: scenario_id is required"
    
    try:
        ptype = PlottingType(plotting_type)
    except ValueError:
        valid_types = [t.value for t in PlottingType if t.value.endswith("_point") or t.value == "rescue_target"]
        return f"Error: Invalid type '{plotting_type}'. Valid types: {valid_types}"
    
    try:
        result = await PlottingService.plot_point(PlotPointRequest(
            scenario_id=UUID(scenario_id),
            plotting_type=ptype,
            name=name,
            longitude=longitude,
            latitude=latitude,
            description=description,
            level=level,
        ))
        
        logger.info(f"Tool plot_point: {result.message}, entity_id={result.entity_id}")
        return f"{result.message}, ID: {result.entity_id}"
        
    except Exception as e:
        logger.error(f"Tool plot_point failed: {e}")
        return f"Error: {str(e)}"


@tool(args_schema=PlotCircleArgs)
async def plot_circle(
    scenario_id: str,
    plotting_type: str,
    name: str,
    center_longitude: float,
    center_latitude: float,
    radius_m: float = 500.0,
    description: Optional[str] = None,
) -> str:
    """
    Plot a circular area on the map.
    
    Types:
    - danger_area: Danger zone (orange color)
    - safety_area: Safety zone (green color)
    - command_post_candidate: Command post candidate (blue color)
    """
    from src.domains.plotting.service import PlottingService
    from src.domains.plotting.schemas import PlottingType, PlotCircleRequest
    
    if not scenario_id:
        return "Error: scenario_id is required"
    
    try:
        ptype = PlottingType(plotting_type)
    except ValueError:
        valid_types = ["danger_area", "safety_area", "command_post_candidate"]
        return f"Error: Invalid type '{plotting_type}'. Valid types: {valid_types}"
    
    try:
        result = await PlottingService.plot_circle(PlotCircleRequest(
            scenario_id=UUID(scenario_id),
            plotting_type=ptype,
            name=name,
            center_longitude=center_longitude,
            center_latitude=center_latitude,
            radius_m=radius_m,
            description=description,
        ))
        
        logger.info(f"Tool plot_circle: {result.message}, entity_id={result.entity_id}")
        return f"{result.message}, ID: {result.entity_id}"
        
    except Exception as e:
        logger.error(f"Tool plot_circle failed: {e}")
        return f"Error: {str(e)}"


@tool
async def geocode(address: str) -> str:
    """
    Convert address to coordinates (geocoding).
    
    Use this tool when user provides an address instead of coordinates.
    
    Args:
        address: Address text, e.g. "北京市朝阳区", "上海市浦东新区"
    
    Returns:
        Coordinates string with longitude and latitude
    """
    from src.infra.clients.amap.geocode import amap_geocode_async
    
    try:
        result = await amap_geocode_async(address)
        if result:
            return f"Address '{address}' coordinates: longitude {result['longitude']}, latitude {result['latitude']}"
        return f"Cannot resolve address: {address}"
    except Exception as e:
        logger.error(f"Tool geocode failed: {e}")
        return f"Error: {str(e)}"


@tool
async def delete_plot(entity_id: str) -> str:
    """
    Delete a plot from the map.
    
    Args:
        entity_id: The entity ID to delete
    """
    from src.domains.plotting.service import PlottingService
    
    try:
        result = await PlottingService.delete_plot(UUID(entity_id))
        logger.info(f"Tool delete_plot: {result.message}")
        return result.message
    except Exception as e:
        logger.error(f"Tool delete_plot failed: {e}")
        return f"Error: {str(e)}"
