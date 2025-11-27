"""
救援队驻扎点 ORM 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from src.core.database import Base


class RescueStagingSite(Base):
    """救援队驻扎点表"""
    
    __tablename__ = "rescue_staging_sites_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    scenario_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    site_code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    site_type = Column(String(50), nullable=False, default="open_ground")
    
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    boundary = Column(Geometry("POLYGON", srid=4326), nullable=True)
    address = Column(Text, nullable=True)
    
    area_m2 = Column(Numeric(12, 2), nullable=True)
    
    elevation_m = Column(Numeric(8, 2), nullable=True)
    slope_degree = Column(Numeric(5, 2), nullable=True)
    terrain_type = Column(String(50), nullable=True)
    ground_stability = Column(String(20), default="unknown")
    
    max_vehicles = Column(Integer, nullable=True)
    max_personnel = Column(Integer, nullable=True)
    max_weight_kg = Column(Numeric(12, 2), nullable=True)
    
    has_water_supply = Column(Boolean, default=False)
    water_supply_capacity_l = Column(Numeric(10, 2), nullable=True)
    has_power_supply = Column(Boolean, default=False)
    power_capacity_kw = Column(Numeric(8, 2), nullable=True)
    has_sanitation = Column(Boolean, default=False)
    has_shelter_structure = Column(Boolean, default=False)
    
    can_helicopter_land = Column(Boolean, default=False)
    helipad_diameter_m = Column(Numeric(6, 2), nullable=True)
    
    primary_network_type = Column(String(20), default="none")
    signal_quality = Column(String(20), nullable=True)
    has_backup_comm = Column(Boolean, default=False)
    
    nearest_road_distance_m = Column(Numeric(10, 2), nullable=True)
    road_access_width_m = Column(Numeric(6, 2), nullable=True)
    can_heavy_vehicle_access = Column(Boolean, default=True)
    
    nearest_supply_depot_m = Column(Numeric(10, 2), nullable=True)
    nearest_medical_point_m = Column(Numeric(10, 2), nullable=True)
    nearest_command_post_m = Column(Numeric(10, 2), nullable=True)
    
    safety_score = Column(Numeric(5, 2), nullable=True)
    last_safety_assessment_at = Column(DateTime(timezone=True), nullable=True)
    
    status = Column(String(20), default="available")
    occupied_by_team_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    managing_organization = Column(String(200), nullable=True)
    contact_person = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
    notes = Column(Text, nullable=True)
    properties = Column(JSONB, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
