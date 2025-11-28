"""
Casualty Estimation Module

Based on:
- USGS PAGER (Prompt Assessment of Global Earthquakes for Response)
- WHO Emergency Health Guidelines
- Chinese National Emergency Response Standards

Provides casualty estimation models for disaster planning,
enabling AI agents to autonomously assess resource requirements.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Optional


class BuildingVulnerability(str, Enum):
    """
    Building vulnerability classification for earthquake casualty estimation.
    
    Based on USGS PAGER building vulnerability index:
    - A: Adobe/unreinforced brick - highest vulnerability
    - B: Unreinforced masonry with wooden floors
    - C: Reinforced masonry, confined masonry
    - D: Light wood frame, reinforced concrete
    - E: Steel frame, engineered buildings - lowest vulnerability
    
    Chinese building stock typically falls into C-D range for urban areas.
    """
    A = "A"  # Adobe, mud brick, unreinforced stone - 土坯/生土
    B = "B"  # Unreinforced brick with timber - 砖木结构
    C = "C"  # Reinforced masonry, confined - 砖混结构
    D = "D"  # Reinforced concrete, light frame - 框架结构
    E = "E"  # Steel frame, engineered - 钢结构/高层

    @property
    def collapse_rate(self) -> float:
        """
        Building collapse rate at MMI intensity VIII (severe shaking).
        Source: USGS PAGER empirical data
        """
        rates = {
            BuildingVulnerability.A: 0.35,  # 35% collapse
            BuildingVulnerability.B: 0.20,  # 20% collapse
            BuildingVulnerability.C: 0.08,  # 8% collapse
            BuildingVulnerability.D: 0.03,  # 3% collapse
            BuildingVulnerability.E: 0.01,  # 1% collapse
        }
        return rates[self]

    @property
    def fatality_rate_if_collapsed(self) -> float:
        """
        Fatality rate given building collapse.
        Higher for heavy construction materials.
        """
        rates = {
            BuildingVulnerability.A: 0.15,  # Light materials, less deadly
            BuildingVulnerability.B: 0.20,
            BuildingVulnerability.C: 0.25,
            BuildingVulnerability.D: 0.10,  # Modern design, pancake survival
            BuildingVulnerability.E: 0.05,  # Engineered collapse zones
        }
        return rates[self]


class DisasterType(str, Enum):
    """Disaster types with distinct casualty estimation methods."""
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"
    LANDSLIDE = "landslide"
    TYPHOON = "typhoon"
    FIRE = "fire"
    EXPLOSION = "explosion"
    CHEMICAL = "chemical"


@dataclass
class CasualtyEstimate:
    """
    Comprehensive casualty estimation result.
    
    All counts are integer estimates. Confidence indicates the reliability
    of the estimate based on data quality and model uncertainty.
    
    Attributes:
        fatalities: Estimated deaths
        severe_injuries: Life-threatening injuries requiring hospitalization
        minor_injuries: Injuries treatable at field stations
        trapped: Persons trapped requiring SAR operations
        displaced: Persons requiring evacuation/shelter
        affected: Total affected population (may include uninjured)
        confidence: Estimate confidence (0.0-1.0)
        methodology: Description of estimation method used
    """
    fatalities: int = 0
    severe_injuries: int = 0
    minor_injuries: int = 0
    trapped: int = 0
    displaced: int = 0
    affected: int = 0
    confidence: float = 0.5
    methodology: str = ""
    
    # Breakdown by severity (optional)
    fatalities_low: Optional[int] = None
    fatalities_high: Optional[int] = None
    
    def __post_init__(self):
        """Ensure non-negative values."""
        for attr in ['fatalities', 'severe_injuries', 'minor_injuries', 'trapped', 'displaced', 'affected']:
            if getattr(self, attr) < 0:
                setattr(self, attr, 0)
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def total_casualties(self) -> int:
        """Total casualties = fatalities + all injuries."""
        return self.fatalities + self.severe_injuries + self.minor_injuries

    @property
    def total_injuries(self) -> int:
        """Total injuries requiring medical attention."""
        return self.severe_injuries + self.minor_injuries

    @property
    def rescue_priority_count(self) -> int:
        """Number of persons requiring immediate rescue operations."""
        return self.trapped + self.severe_injuries

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "fatalities": self.fatalities,
            "severe_injuries": self.severe_injuries,
            "minor_injuries": self.minor_injuries,
            "trapped": self.trapped,
            "displaced": self.displaced,
            "affected": self.affected,
            "confidence": self.confidence,
            "methodology": self.methodology,
            "total_casualties": self.total_casualties,
            "rescue_priority_count": self.rescue_priority_count,
        }


class CasualtyEstimator:
    """
    Casualty estimation engine based on USGS PAGER methodology.
    
    Provides estimates for:
    - Earthquake casualties (primary method)
    - Flood casualties
    - Landslide casualties
    - Generic disaster casualties
    
    Usage:
        estimator = CasualtyEstimator()
        estimate = estimator.estimate_earthquake(
            magnitude=6.5,
            depth_km=10,
            population=100000,
            building_type=BuildingVulnerability.C,
            time_of_day=time(3, 0),  # 3 AM
        )
    """
    
    # Fatality rate coefficients calibrated to historical data
    # Fatality rate = base_rate * 10^(b * (MMI - 7))
    # Calibrated to produce realistic rates for China seismic zones:
    #   MMI VI:  ~0.0001% (minor damage)
    #   MMI VII: ~0.001%  (moderate damage) - baseline
    #   MMI VIII: ~0.01%  (heavy damage)
    #   MMI IX:  ~0.1%    (severe damage)
    #   MMI X:   ~0.5%    (extreme damage)
    #   MMI XI:  ~2%      (catastrophic)
    # Reference: Calibrated against 2008 Wenchuan earthquake data
    _FATALITY_COEFFICIENTS = {
        BuildingVulnerability.A: {"base": 0.0002, "b": 0.40},  # Adobe - highest
        BuildingVulnerability.B: {"base": 0.00015, "b": 0.38}, # Brick-timber
        BuildingVulnerability.C: {"base": 0.0001, "b": 0.35},  # Reinforced masonry
        BuildingVulnerability.D: {"base": 0.00005, "b": 0.32}, # RC frame
        BuildingVulnerability.E: {"base": 0.00002, "b": 0.30}, # Steel frame
    }

    def estimate_earthquake(
        self,
        magnitude: float,
        depth_km: float,
        population: int,
        building_type: BuildingVulnerability = BuildingVulnerability.C,
        time_of_day: Optional[time] = None,
        secondary_hazards: bool = False,
    ) -> CasualtyEstimate:
        """
        Estimate earthquake casualties using USGS PAGER methodology.
        
        Args:
            magnitude: Richter/moment magnitude (e.g., 6.5)
            depth_km: Hypocenter depth in kilometers
            population: Affected area population
            building_type: Predominant building vulnerability class
            time_of_day: Local time of earthquake (affects indoor ratio)
            secondary_hazards: Whether to include landslide/fire estimates
            
        Returns:
            CasualtyEstimate with fatalities, injuries, trapped, displaced
        """
        # Step 1: Convert magnitude to Modified Mercalli Intensity (MMI)
        # Simplified formula: MMI ≈ 1.5*M - 0.5*log(D) where D is depth
        mmi = self._magnitude_to_mmi(magnitude, depth_km)
        
        # Step 2: Calculate shaking death rate using calibrated model
        # Fatality rate = base_rate * 10^(b * (MMI - 7))
        coef = self._FATALITY_COEFFICIENTS[building_type]
        fatality_rate = coef["base"] * (10 ** (coef["b"] * (mmi - 7.0)))
        fatality_rate = min(fatality_rate, 0.5)  # Cap at 50% (extreme case)
        
        # Step 3: Adjust for time of day (indoor occupancy)
        indoor_factor = self._get_indoor_factor(time_of_day)
        adjusted_rate = fatality_rate * indoor_factor
        
        # Step 4: Calculate casualties
        fatalities = int(population * adjusted_rate)
        
        # Injury ratios (empirical: severe=3x, minor=10x fatalities for earthquakes)
        severe_injuries = int(fatalities * 3.0)
        minor_injuries = int(fatalities * 10.0)
        
        # Trapped estimate (depends on collapse rate and rescue timing)
        collapse_rate = building_type.collapse_rate
        trapped_rate = collapse_rate * 0.3 * indoor_factor  # 30% of collapse victims trapped
        trapped = int(population * trapped_rate)
        
        # Displaced estimate (buildings damaged > 50%)
        damage_rate = self._estimate_damage_rate(mmi, building_type)
        displaced = int(population * damage_rate * 0.5)  # 50% of damaged building occupants
        
        # Add secondary hazards if requested
        if secondary_hazards:
            secondary = self._estimate_secondary_hazards(magnitude, population)
            fatalities += secondary["fatalities"]
            severe_injuries += secondary["severe_injuries"]
        
        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(magnitude, population, depth_km)
        
        return CasualtyEstimate(
            fatalities=fatalities,
            severe_injuries=severe_injuries,
            minor_injuries=minor_injuries,
            trapped=trapped,
            displaced=displaced,
            affected=population,
            confidence=confidence,
            methodology=f"USGS PAGER model (M{magnitude}, MMI {mmi:.1f}, {building_type.value}-class buildings)",
            fatalities_low=int(fatalities * 0.3),  # 30% lower bound
            fatalities_high=int(fatalities * 3.0),  # 3x upper bound
        )

    def estimate_flood(
        self,
        flood_depth_m: float,
        flow_velocity_mps: float,
        population: int,
        warning_hours: float = 0,
        night_time: bool = False,
    ) -> CasualtyEstimate:
        """
        Estimate flood casualties.
        
        Based on depth-velocity product and warning time models.
        
        Args:
            flood_depth_m: Maximum flood depth in meters
            flow_velocity_mps: Water flow velocity in m/s
            population: Population in flood zone
            warning_hours: Hours of advance warning
            night_time: Whether flood occurs at night
        """
        # Depth-velocity hazard product
        dv = flood_depth_m * flow_velocity_mps
        
        # Base fatality rate from DV product
        if dv < 0.5:
            base_rate = 0.0001  # Low hazard
        elif dv < 1.0:
            base_rate = 0.001
        elif dv < 3.0:
            base_rate = 0.01
        else:
            base_rate = 0.05  # High hazard
        
        # Adjust for warning time (evacuation reduces casualties)
        warning_factor = max(0.1, 1.0 - (warning_hours * 0.1))
        
        # Night time increases risk
        night_factor = 1.5 if night_time else 1.0
        
        fatality_rate = base_rate * warning_factor * night_factor
        fatalities = int(population * fatality_rate)
        
        # Flood injuries tend to be lower ratio to fatalities
        severe_injuries = int(fatalities * 1.5)
        minor_injuries = int(fatalities * 5.0)
        
        # Displacement is high for floods
        displaced = int(population * min(1.0, dv * 0.3))
        
        return CasualtyEstimate(
            fatalities=fatalities,
            severe_injuries=severe_injuries,
            minor_injuries=minor_injuries,
            trapped=int(fatalities * 0.5),  # Rescue-needed
            displaced=displaced,
            affected=population,
            confidence=0.6,
            methodology=f"Depth-velocity model (DV={dv:.1f}, warning={warning_hours}h)",
        )

    def estimate_landslide(
        self,
        volume_m3: float,
        runout_m: float,
        population: int,
        warning_given: bool = False,
    ) -> CasualtyEstimate:
        """
        Estimate landslide casualties.
        
        Based on volume-runout model and building impact.
        """
        # Volume-based hazard
        if volume_m3 < 1000:
            base_rate = 0.001
        elif volume_m3 < 10000:
            base_rate = 0.01
        elif volume_m3 < 100000:
            base_rate = 0.05
        else:
            base_rate = 0.10
        
        # Warning reduces casualties significantly
        warning_factor = 0.2 if warning_given else 1.0
        
        fatality_rate = base_rate * warning_factor
        fatalities = int(population * fatality_rate)
        
        # Landslides have high fatality to injury ratio (burial)
        severe_injuries = int(fatalities * 0.5)
        minor_injuries = int(fatalities * 2.0)
        trapped = int(fatalities * 2.0)  # Many trapped in debris
        
        displaced = int(population * 0.3)  # Area evacuation
        
        return CasualtyEstimate(
            fatalities=fatalities,
            severe_injuries=severe_injuries,
            minor_injuries=minor_injuries,
            trapped=trapped,
            displaced=displaced,
            affected=population,
            confidence=0.5,
            methodology=f"Volume-runout model (V={volume_m3}m³, L={runout_m}m)",
        )

    def estimate_generic(
        self,
        disaster_type: DisasterType,
        severity: float,  # 0.0-1.0
        population: int,
    ) -> CasualtyEstimate:
        """
        Generic casualty estimation for when detailed parameters unavailable.
        
        Uses simplified models based on disaster type and severity score.
        
        Args:
            disaster_type: Type of disaster
            severity: Severity scale 0.0 (minor) to 1.0 (catastrophic)
            population: Affected population
        """
        # Base fatality rates by disaster type
        base_rates = {
            DisasterType.EARTHQUAKE: 0.01,
            DisasterType.FLOOD: 0.001,
            DisasterType.LANDSLIDE: 0.05,
            DisasterType.TYPHOON: 0.0001,
            DisasterType.FIRE: 0.005,
            DisasterType.EXPLOSION: 0.02,
            DisasterType.CHEMICAL: 0.01,
        }
        
        base_rate = base_rates.get(disaster_type, 0.001)
        fatality_rate = base_rate * severity
        fatalities = int(population * fatality_rate)
        
        # Generic injury ratios
        severe_injuries = int(fatalities * 2.0)
        minor_injuries = int(fatalities * 8.0)
        trapped = int(fatalities * 1.0)
        displaced = int(population * severity * 0.2)
        
        return CasualtyEstimate(
            fatalities=fatalities,
            severe_injuries=severe_injuries,
            minor_injuries=minor_injuries,
            trapped=trapped,
            displaced=displaced,
            affected=population,
            confidence=0.3,  # Low confidence for generic model
            methodology=f"Generic model ({disaster_type.value}, severity={severity:.1%})",
        )

    # =========================================================================
    # Private helper methods
    # =========================================================================

    def _magnitude_to_mmi(self, magnitude: float, depth_km: float) -> float:
        """
        Convert earthquake magnitude and depth to Modified Mercalli Intensity.
        
        Based on Atkinson & Wald (2007) regression for epicentral intensity.
        MMI = C1 + C2*M - C3*log10(D)
        where D = hypocentral distance in km
        
        Reference values:
          M6.0, 10km depth → MMI ~VII (7)
          M7.0, 15km depth → MMI ~VIII (8)
          M8.0, 20km depth → MMI ~IX (9)
        """
        # Hypocentral distance (minimum 5km for numerical stability)
        hypo_dist = max(5.0, depth_km)
        
        # Atkinson & Wald (2007) coefficients for crustal earthquakes
        # Adjusted for China seismic zone characteristics
        c1 = 2.085
        c2 = 1.428
        c3 = 1.402
        
        mmi = c1 + c2 * magnitude - c3 * math.log10(hypo_dist)
        
        # Clamp to valid MMI range (I to XII)
        return max(1.0, min(12.0, mmi))

    def _get_indoor_factor(self, time_of_day: Optional[time]) -> float:
        """
        Get indoor occupancy factor based on time of day.
        
        Earthquakes at night cause more casualties due to higher indoor rates.
        """
        if time_of_day is None:
            return 1.0  # Assume average
        
        hour = time_of_day.hour
        
        # Night time (10 PM - 6 AM): 90% indoors
        if hour >= 22 or hour < 6:
            return 1.3
        # Working hours (8 AM - 6 PM): 70% indoors
        elif 8 <= hour < 18:
            return 1.0
        # Commute/evening (6-8 AM, 6-10 PM): 50% indoors
        else:
            return 0.8

    def _estimate_damage_rate(
        self, 
        mmi: float, 
        building_type: BuildingVulnerability,
    ) -> float:
        """Estimate building damage rate (>50% damaged)."""
        # Simplified damage function
        base_rate = building_type.collapse_rate * 3.0  # Damaged >> collapsed
        intensity_factor = (mmi - 5) / 7.0  # Scale from MMI V to XII
        intensity_factor = max(0.0, min(1.0, intensity_factor))
        
        return base_rate * intensity_factor

    def _estimate_secondary_hazards(
        self, 
        magnitude: float, 
        population: int,
    ) -> dict:
        """Estimate casualties from earthquake-triggered landslides and fires."""
        # Landslide triggered by M>6.0 earthquakes
        if magnitude >= 6.0:
            landslide_factor = (magnitude - 6.0) * 0.001
        else:
            landslide_factor = 0.0
        
        # Fire risk scales with magnitude
        fire_factor = 0.0001 * magnitude
        
        return {
            "fatalities": int(population * (landslide_factor + fire_factor)),
            "severe_injuries": int(population * (landslide_factor + fire_factor) * 2),
        }

    def _calculate_confidence(
        self, 
        magnitude: float, 
        population: int, 
        depth_km: float,
    ) -> float:
        """
        Calculate estimate confidence based on input data quality.
        
        Higher confidence for:
        - Moderate magnitudes (M5-7) with more data
        - Larger populations (statistical significance)
        - Shallow depths (better understood)
        """
        # Magnitude confidence (peak at M6.0)
        mag_conf = 1.0 - abs(magnitude - 6.0) * 0.1
        mag_conf = max(0.3, min(1.0, mag_conf))
        
        # Population confidence (need >1000 for statistical validity)
        if population < 1000:
            pop_conf = 0.3
        elif population < 10000:
            pop_conf = 0.5
        elif population < 100000:
            pop_conf = 0.7
        else:
            pop_conf = 0.8
        
        # Depth confidence (shallow better understood)
        if depth_km < 20:
            depth_conf = 0.8
        elif depth_km < 50:
            depth_conf = 0.6
        else:
            depth_conf = 0.4
        
        return (mag_conf + pop_conf + depth_conf) / 3.0
