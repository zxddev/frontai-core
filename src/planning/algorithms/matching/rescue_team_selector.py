"""
救援队伍智能选择算法

业务逻辑:
=========
1. 灾情特征提取:
   - 从灾情画像中提取特征向量
   - 特征包括: 灾害类型、是否有倒塌、是否有被困、地形、可达性等

2. 能力需求推断:
   - 基于规则/模型从特征推断所需能力
   - 能力包括: 生命探测、破拆、重型机械、危化品处置等
   - 每个能力有优先级(critical/high/medium/low)和数量需求

3. 队伍-需求匹配:
   - 计算每个队伍与需求的匹配分数
   - 考虑: 能力覆盖、专业匹配度、距离、可用性

4. 组合优化:
   - 加权集合覆盖问题
   - 目标: 最少队伍覆盖所有关键能力，最小化总响应时间

算法实现:
=========
- 特征提取: 规则映射 + 向量化
- 能力推断: 规则引擎 / 决策树 / 数据库映射
- 匹配评分: score = Σ(能力权重 * 匹配度) * 距离衰减 * 专业度加成
- 组合优化: 贪心算法 + 局部搜索优化

数据源:
=======
- 优先从 operational_v2.capability_requirements_v2 表读取能力映射
- 无数据库连接时使用内置的 FALLBACK_CAPABILITY_MAP
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import numpy as np

from ..base import (
    AlgorithmBase, AlgorithmResult, AlgorithmStatus, 
    Location, haversine_distance, estimate_travel_time
)

logger = logging.getLogger(__name__)


@dataclass
class CapabilityRequirement:
    """能力需求"""
    capability_id: str
    priority: str  # critical/high/medium/low
    quantity: int = 1
    
    @property
    def weight(self) -> float:
        """优先级权重"""
        return {"critical": 4.0, "high": 2.0, "medium": 1.0, "low": 0.5}.get(self.priority, 1.0)


@dataclass
class TeamProfile:
    """队伍画像"""
    id: str
    name: str
    type: str
    capabilities: List[str]
    specialty: str  # 专业领域
    location: Location
    personnel: int
    equipment_level: str  # basic/standard/advanced
    status: str  # available/busy/offline
    response_time_min: int = 0  # 预计响应时间
    
    @classmethod
    def from_dict(cls, d: Dict) -> "TeamProfile":
        loc = d.get("location", {})
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            type=d.get("type", ""),
            capabilities=d.get("capabilities", []),
            specialty=d.get("specialty", "general"),
            location=Location(lat=loc.get("lat", 0), lng=loc.get("lng", 0)),
            personnel=d.get("personnel", 10),
            equipment_level=d.get("equipment_level", "standard"),
            status=d.get("status", "available"),
        )


@dataclass
class TeamSelection:
    """队伍选择结果"""
    team: TeamProfile
    score: float
    assigned_capabilities: List[str]
    eta_minutes: int
    priority_order: int


class CapabilityMappingProvider:
    """
    能力映射数据提供者
    
    支持从数据库或内存fallback获取灾害类型→能力需求映射
    """
    
    # 内置fallback映射（无数据库时使用）
    FALLBACK_DISASTER_MAP = {
        "earthquake": {
            "SEARCH_LIFE_DETECT": "critical",
            "RESCUE_STRUCTURAL": "critical",
            "RESCUE_CONFINED": "high",
            "ENG_DEMOLITION": "high",
            "MEDICAL_TRIAGE": "critical",
            "MEDICAL_FIRST_AID": "critical",
        },
        "fire": {
            "FIRE_SUPPRESS": "critical",
            "FIRE_SUPPLY_WATER": "critical",
            "RESCUE_HIGH_ANGLE": "high",
            "MEDICAL_FIRST_AID": "high",
        },
        "hazmat": {
            "HAZMAT_DETECT": "critical",
            "HAZMAT_CONTAIN": "critical",
            "HAZMAT_DECON": "high",
            "MEDICAL_FIRST_AID": "high",
        },
        "flood": {
            "RESCUE_WATER_FLOOD": "critical",
            "RESCUE_WATER_SWIFT": "high",
            "MEDICAL_FIRST_AID": "high",
        },
        "landslide": {
            "SEARCH_LIFE_DETECT": "critical",
            "RESCUE_STRUCTURAL": "critical",
            "ENG_HEAVY_MACHINE": "critical",
            "GEO_MONITOR": "high",
        },
    }
    
    FALLBACK_FEATURE_MAP = {
        "has_collapse": {"ENG_DEMOLITION": "high", "RESCUE_STRUCTURAL": "critical"},
        "has_trapped": {"SEARCH_LIFE_DETECT": "critical", "RESCUE_CONFINED": "high"},
        "has_fire": {"FIRE_SUPPRESS": "critical"},
        "has_hazmat": {"HAZMAT_CONTAIN": "critical", "HAZMAT_DETECT": "critical"},
        "high_rise": {"RESCUE_HIGH_ANGLE": "critical"},
        "water_area": {"RESCUE_WATER_FLOOD": "critical"},
    }
    
    def __init__(self, db_conn=None):
        """
        Args:
            db_conn: 数据库连接（可选），支持psycopg2/asyncpg
        """
        self._conn = db_conn
        self._cache: Dict[str, Dict[str, str]] = {}
        self._cache_loaded = False
    
    def _load_from_database(self) -> bool:
        """从数据库加载能力映射"""
        if self._conn is None:
            return False
        
        try:
            sql = """
                SELECT 
                    disaster_type,
                    event_subtype,
                    required_capability_code,
                    CASE 
                        WHEN priority >= 90 THEN 'critical'
                        WHEN priority >= 70 THEN 'high'
                        WHEN priority >= 50 THEN 'medium'
                        ELSE 'low'
                    END AS priority_level,
                    min_teams
                FROM operational_v2.capability_requirements_v2
                ORDER BY disaster_type, priority DESC
            """
            
            cursor = self._conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning("capability_requirements_v2表为空，使用fallback映射")
                return False
            
            for row in rows:
                disaster_type = row[0]
                event_subtype = row[1]
                capability_code = row[2]
                priority_level = row[3]
                
                # 主键: disaster_type 或 disaster_type:event_subtype
                key = disaster_type
                if event_subtype:
                    subkey = f"{disaster_type}:{event_subtype}"
                    if subkey not in self._cache:
                        self._cache[subkey] = {}
                    self._cache[subkey][capability_code] = priority_level
                
                # 同时写入主类型（取最高优先级）
                if key not in self._cache:
                    self._cache[key] = {}
                if capability_code not in self._cache[key]:
                    self._cache[key][capability_code] = priority_level
            
            logger.info(f"从数据库加载能力映射: {len(self._cache)} 种灾害类型")
            self._cache_loaded = True
            return True
            
        except Exception as e:
            logger.warning(f"从数据库加载能力映射失败: {e}，使用fallback")
            return False
    
    def get_disaster_capability_map(self, disaster_type: str, event_subtype: Optional[str] = None) -> Dict[str, str]:
        """
        获取灾害类型对应的能力需求映射
        
        Args:
            disaster_type: 灾害类型 (earthquake/flood/fire/hazmat等)
            event_subtype: 事件子类型 (building_collapse/people_trapped等)
            
        Returns:
            {capability_code: priority_level} 字典
        """
        if not self._cache_loaded:
            self._load_from_database()
        
        # 优先使用数据库缓存
        if self._cache:
            # 先查子类型
            if event_subtype:
                subkey = f"{disaster_type}:{event_subtype}"
                if subkey in self._cache:
                    return self._cache[subkey].copy()
            # 再查主类型
            if disaster_type in self._cache:
                return self._cache[disaster_type].copy()
        
        # fallback到内置映射
        return self.FALLBACK_DISASTER_MAP.get(disaster_type, {}).copy()
    
    def get_feature_capability_map(self, feature: str) -> Dict[str, str]:
        """
        获取特征对应的附加能力需求
        
        Args:
            feature: 特征名称 (has_collapse/has_trapped等)
            
        Returns:
            {capability_code: priority_level} 字典
        """
        # 特征映射暂时只用内置的，后续可扩展到数据库
        return self.FALLBACK_FEATURE_MAP.get(feature, {}).copy()


class RescueTeamSelector(AlgorithmBase):
    """
    救援队伍智能选择器
    
    使用示例:
    ```python
    # 方式1: 使用数据库能力映射
    selector = RescueTeamSelector(db_conn=conn)
    
    # 方式2: 使用内置fallback映射
    selector = RescueTeamSelector()
    
    result = selector.run({
        "disaster_profile": {
            "type": "earthquake",
            "subtype": "building_collapse",  # 可选，用于更精确的能力匹配
            "level": "I",
            "location": {"lat": 31.23, "lng": 121.47},
            "features": {
                "has_collapse": True,
                "has_trapped": True,
                "has_fire": False,
                "terrain": "urban"
            }
        },
        "available_teams": [...],
        "constraints": {
            "max_response_time": 60,
            "max_teams": 10
        }
    })
    ```
    """
    
    def __init__(self, db_conn=None, **kwargs):
        """
        Args:
            db_conn: 数据库连接（可选），用于从capability_requirements_v2读取映射
        """
        super().__init__(**kwargs)
        self._mapping_provider = CapabilityMappingProvider(db_conn)
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "max_teams": 15,
            "max_response_time_min": 120,
            "distance_decay_factor": 0.02,
            "specialty_bonus": 0.3,
            "coverage_threshold": 0.9,  # 关键能力覆盖率要求
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "disaster_profile" not in problem:
            return False, "缺少 disaster_profile"
        if "available_teams" not in problem:
            return False, "缺少 available_teams"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行队伍选择"""
        disaster_profile = problem["disaster_profile"]
        available_teams = problem["available_teams"]
        constraints = problem.get("constraints", {})
        
        # 1. 解析队伍
        teams = [TeamProfile.from_dict(t) for t in available_teams]
        teams = [t for t in teams if t.status == "available"]
        
        if not teams:
            return AlgorithmResult(
                status=AlgorithmStatus.INFEASIBLE,
                solution=[],
                metrics={},
                trace={"error": "无可用队伍"},
                time_ms=0,
                message="无可用队伍"
            )
        
        # 2. 提取灾情特征
        features = self._extract_disaster_features(disaster_profile)
        
        # 3. 推断能力需求
        requirements = self._infer_capability_requirements(disaster_profile, features)
        
        # 4. 获取灾害位置
        loc = disaster_profile.get("location", {})
        disaster_location = Location(lat=loc.get("lat", 0), lng=loc.get("lng", 0))
        
        # 5. 计算每个队伍的得分和ETA
        team_scores = []
        for team in teams:
            distance = haversine_distance(team.location, disaster_location)
            eta = estimate_travel_time(distance)
            
            # 检查时间约束
            max_time = constraints.get("max_response_time", self.params["max_response_time_min"])
            if eta > max_time:
                continue
            
            score = self._compute_team_score(team, requirements, distance, disaster_profile)
            team.response_time_min = eta
            team_scores.append((team, score, eta))
        
        if not team_scores:
            return AlgorithmResult(
                status=AlgorithmStatus.INFEASIBLE,
                solution=[],
                metrics={},
                trace={"error": "无队伍满足时间约束"},
                time_ms=0,
                message="无队伍能在规定时间内到达"
            )
        
        # 6. 组合优化 - 选择最优队伍组合
        max_teams = constraints.get("max_teams", self.params["max_teams"])
        selected = self._optimize_team_combination(team_scores, requirements, max_teams)
        
        # 7. 计算覆盖率
        covered_caps = set()
        for sel in selected:
            covered_caps.update(sel.assigned_capabilities)
        
        critical_caps = {r.capability_id for r in requirements if r.priority == "critical"}
        critical_coverage = len(covered_caps & critical_caps) / len(critical_caps) if critical_caps else 1.0
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=[{
                "team_id": s.team.id,
                "team_name": s.team.name,
                "score": s.score,
                "eta_minutes": s.eta_minutes,
                "assigned_capabilities": s.assigned_capabilities,
                "priority_order": s.priority_order,
            } for s in selected],
            metrics={
                "selected_count": len(selected),
                "total_score": sum(s.score for s in selected),
                "critical_coverage": critical_coverage,
                "avg_eta": sum(s.eta_minutes for s in selected) / len(selected) if selected else 0,
            },
            trace={
                "requirements": [{"id": r.capability_id, "priority": r.priority} for r in requirements],
                "total_candidates": len(team_scores),
            },
            time_ms=0
        )
    
    def _extract_disaster_features(self, profile: Dict) -> Dict[str, bool]:
        """提取灾情特征"""
        features = profile.get("features", {})
        
        # 标准化特征
        return {
            "has_collapse": features.get("has_collapse", False),
            "has_trapped": features.get("has_trapped", False),
            "has_fire": features.get("has_fire", False),
            "has_hazmat": features.get("has_hazmat", False),
            "high_rise": features.get("high_rise", False),
            "water_area": features.get("water_area", False),
            "confined_space": features.get("confined_space", False),
            "night_time": features.get("night_time", False),
        }
    
    def _infer_capability_requirements(self, profile: Dict, features: Dict) -> List[CapabilityRequirement]:
        """推断能力需求（优先从数据库读取，fallback到内置映射）"""
        requirements = {}
        
        # 1. 基于灾害类型的基础需求（从数据库或fallback获取）
        disaster_type = profile.get("type", "earthquake")
        event_subtype = profile.get("subtype")  # 支持更精确的子类型匹配
        base_caps = self._mapping_provider.get_disaster_capability_map(disaster_type, event_subtype)
        
        for cap_id, priority in base_caps.items():
            requirements[cap_id] = CapabilityRequirement(
                capability_id=cap_id,
                priority=priority,
                quantity=1
            )
        
        # 2. 基于特征的附加需求
        for feature, has_feature in features.items():
            if has_feature:
                feature_caps = self._mapping_provider.get_feature_capability_map(feature)
                for cap_id, priority in feature_caps.items():
                    if cap_id in requirements:
                        # 提升优先级
                        current = requirements[cap_id]
                        if self._priority_level(priority) > self._priority_level(current.priority):
                            requirements[cap_id] = CapabilityRequirement(
                                capability_id=cap_id,
                                priority=priority,
                                quantity=current.quantity + 1
                            )
                    else:
                        requirements[cap_id] = CapabilityRequirement(
                            capability_id=cap_id,
                            priority=priority,
                            quantity=1
                        )
        
        # 3. 基于灾情等级调整数量
        level = profile.get("level", "III")
        quantity_multiplier = {"I": 3, "II": 2, "III": 1, "IV": 1}.get(level, 1)
        
        for req in requirements.values():
            if req.priority in ["critical", "high"]:
                req.quantity = max(1, req.quantity * quantity_multiplier)
        
        return list(requirements.values())
    
    def _priority_level(self, priority: str) -> int:
        """优先级转数值"""
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(priority, 0)
    
    def _compute_team_score(self, team: TeamProfile, requirements: List[CapabilityRequirement],
                            distance_km: float, profile: Dict) -> float:
        """
        计算队伍匹配分数
        
        score = Σ(能力权重 * 匹配度) * 距离衰减 * 专业度加成
        """
        score = 0.0
        team_caps = set(team.capabilities)
        
        # 1. 能力覆盖得分
        for req in requirements:
            if req.capability_id in team_caps:
                score += req.weight * 10  # 基础分
        
        # 2. 距离衰减
        decay_factor = self.params["distance_decay_factor"]
        distance_penalty = 1 / (1 + decay_factor * distance_km)
        score *= distance_penalty
        
        # 3. 专业度加成
        disaster_type = profile.get("type", "")
        specialty_match = self._check_specialty_match(team.specialty, disaster_type)
        if specialty_match:
            score *= (1 + self.params["specialty_bonus"])
        
        # 4. 装备等级加成
        equipment_bonus = {"advanced": 1.2, "standard": 1.0, "basic": 0.8}.get(team.equipment_level, 1.0)
        score *= equipment_bonus
        
        # 5. 人员数量因子
        personnel_factor = min(1.5, team.personnel / 10)
        score *= personnel_factor
        
        return round(score, 2)
    
    def _check_specialty_match(self, specialty: str, disaster_type: str) -> bool:
        """检查专业匹配"""
        specialty_map = {
            "earthquake": ["earthquake_rescue", "building_collapse", "search_rescue"],
            "fire": ["firefighting", "hazmat", "industrial_fire"],
            "hazmat": ["hazmat", "chemical", "nuclear"],
            "flood": ["water_rescue", "flood", "maritime"],
            "landslide": ["geological", "mountain_rescue", "search_rescue"],
        }
        matching_specialties = specialty_map.get(disaster_type, [])
        return specialty.lower() in matching_specialties or specialty.lower() == "general"
    
    def _optimize_team_combination(self, team_scores: List[Tuple[TeamProfile, float, int]],
                                    requirements: List[CapabilityRequirement],
                                    max_teams: int) -> List[TeamSelection]:
        """
        组合优化 - 加权集合覆盖问题
        
        使用贪心算法 + 局部优化
        目标: 选择最优队伍组合覆盖所有关键能力
        """
        selected = []
        uncovered = {r.capability_id: r for r in requirements}
        covered_count = {}  # 能力已覆盖次数
        
        # 按分数排序
        sorted_teams = sorted(team_scores, key=lambda x: -x[1])
        used_teams = set()
        
        # 贪心选择
        priority_order = 0
        while uncovered and len(selected) < max_teams and sorted_teams:
            best_team = None
            best_value = -1
            best_idx = -1
            
            for idx, (team, score, eta) in enumerate(sorted_teams):
                if team.id in used_teams:
                    continue
                
                # 计算边际价值: 能覆盖多少未覆盖的关键能力
                team_caps = set(team.capabilities)
                marginal_value = 0
                
                for cap_id, req in uncovered.items():
                    if cap_id in team_caps:
                        marginal_value += req.weight
                
                # 综合价值 = 边际价值 * 分数
                combined_value = marginal_value * score
                
                if combined_value > best_value:
                    best_value = combined_value
                    best_team = (team, score, eta)
                    best_idx = idx
            
            if best_team is None:
                break
            
            team, score, eta = best_team
            used_teams.add(team.id)
            
            # 确定分配的能力
            team_caps = set(team.capabilities)
            assigned = []
            to_remove = []
            
            for cap_id, req in uncovered.items():
                if cap_id in team_caps:
                    assigned.append(cap_id)
                    covered_count[cap_id] = covered_count.get(cap_id, 0) + 1
                    # 如果已满足数量需求，移除
                    if covered_count[cap_id] >= req.quantity:
                        to_remove.append(cap_id)
            
            for cap_id in to_remove:
                del uncovered[cap_id]
            
            priority_order += 1
            selected.append(TeamSelection(
                team=team,
                score=score,
                assigned_capabilities=assigned,
                eta_minutes=eta,
                priority_order=priority_order
            ))
        
        return selected
