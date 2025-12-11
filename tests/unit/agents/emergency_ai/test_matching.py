"""
matching.py 单元测试

测试资源匹配模块的核心函数，包括：
- 事件位置提取
- 灾害等级判断
- 匹配分数计算
- 能力覆盖计算
- 贪心策略生成
- NSGA优化

作者：Claude Code
日期：2025-12-11
"""
import os
import sys
from typing import Dict, Any, List, Set
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# 添加项目根目录到路径
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.emergency_ai.nodes.matching import (
    _extract_event_location,
    _determine_disaster_scale,
    _get_covered_capabilities,
    _calculate_match_scores,
    _generate_greedy_solution,
    _map_team_type,
    VehicleProfile,
    TEAM_VEHICLE_PROFILES,
    DEFAULT_VEHICLE_PROFILE,
)
from src.agents.emergency_ai.state import EmergencyAIState


# ============================================================================
# 测试辅助函数
# ============================================================================

def _make_state(
    event_id: str = "test-event-001",
    location: Dict[str, Any] = None,
    parsed_disaster: Dict[str, Any] = None,
) -> EmergencyAIState:
    """
    构造测试用的 EmergencyAIState

    Args:
        event_id: 事件ID
        location: 位置信息 {latitude, longitude}
        parsed_disaster: 灾情解析结果

    Returns:
        EmergencyAIState 字典
    """
    state: EmergencyAIState = {
        "event_id": event_id,
        "disaster_description": "测试灾情描述",
        "structured_input": {},
        "errors": [],
        "trace": {},
    }

    if location:
        state["structured_input"]["location"] = location

    if parsed_disaster:
        state["parsed_disaster"] = parsed_disaster

    return state


def _make_team(
    team_id: str,
    name: str,
    team_type: str,
    capabilities: List[str],
    distance_km: float = 10.0,
    rescue_capacity: int = 10,
    vehicle_speed_kmh: int = 60,
    vehicle_is_all_terrain: bool = False,
    capability_level: int = 3,
    response_time_minutes: int = 5,
) -> Dict[str, Any]:
    """
    构造测试用的队伍数据

    Args:
        team_id: 队伍ID
        name: 队伍名称
        team_type: 队伍类型
        capabilities: 能力列表
        distance_km: 距离（公里）
        rescue_capacity: 救援容量
        vehicle_speed_kmh: 车辆速度
        vehicle_is_all_terrain: 是否全地形
        capability_level: 能力等级 (1-5)
        response_time_minutes: 响应时间（分钟）

    Returns:
        队伍字典
    """
    return {
        "id": team_id,
        "name": name,
        "team_type": team_type,
        "capabilities": capabilities,
        "distance_km": distance_km,
        "distance_m": distance_km * 1000,
        "rescue_capacity": rescue_capacity,
        "vehicle_speed_kmh": vehicle_speed_kmh,
        "vehicle_is_all_terrain": vehicle_is_all_terrain,
        "capability_level": capability_level,
        "response_time_minutes": response_time_minutes,
        "base_lat": 30.0,
        "base_lng": 120.0,
        "base_address": "测试地址",
        "available_personnel": 20,
        "total_personnel": 30,
    }


# ============================================================================
# 测试用例 1: test_extract_event_location_valid_coordinates
# ============================================================================

class TestExtractEventLocation:
    """测试事件位置提取函数"""

    def test_extract_event_location_valid_coordinates(self):
        """
        测试用例1: 有效坐标提取

        输入：有效的 lat/lng 坐标（中国范围内）
        期望：返回 (lat, lng) 元组
        """
        # Arrange - 准备测试数据
        state = _make_state(
            location={"latitude": 30.5, "longitude": 120.3}
        )

        # Act - 执行被测函数
        result = _extract_event_location(state)

        # Assert - 验证结果
        assert result is not None, "有效坐标应返回非空结果"
        assert isinstance(result, tuple), "返回值应为元组"
        assert len(result) == 2, "元组应包含2个元素"
        assert result[0] == 30.5, "纬度应为30.5"
        assert result[1] == 120.3, "经度应为120.3"

    def test_extract_event_location_invalid_coordinates_out_of_range(self):
        """
        测试用例2: 超出范围的坐标

        输入：超出有效范围的坐标（如 lat=200）
        期望：返回 None
        """
        # Arrange - 纬度超出范围 (-90 到 90)
        state = _make_state(
            location={"latitude": 200, "longitude": 120.3}
        )

        # Act
        result = _extract_event_location(state)

        # Assert
        assert result is None, "超出范围的纬度应返回None"

    def test_extract_event_location_invalid_longitude_out_of_range(self):
        """
        测试用例2b: 经度超出范围

        输入：经度超出有效范围（如 lng=300）
        期望：返回 None
        """
        # Arrange - 经度超出范围 (-180 到 180)
        state = _make_state(
            location={"latitude": 30.5, "longitude": 300}
        )

        # Act
        result = _extract_event_location(state)

        # Assert
        assert result is None, "超出范围的经度应返回None"

    def test_extract_event_location_missing_location(self):
        """
        测试用例2c: 缺少位置信息

        输入：structured_input 中无 location 字段
        期望：返回 None
        """
        # Arrange - 无位置信息
        state = _make_state()

        # Act
        result = _extract_event_location(state)

        # Assert
        assert result is None, "缺少位置信息应返回None"

    def test_extract_event_location_alternative_field_names(self):
        """
        测试用例2d: 支持 lat/lng 字段名

        输入：使用 lat/lng 而非 latitude/longitude
        期望：正确解析并返回坐标
        """
        # Arrange - 使用简写字段名
        state = _make_state(
            location={"lat": 31.2, "lng": 121.5}
        )

        # Act
        result = _extract_event_location(state)

        # Assert
        assert result is not None, "lat/lng 字段名应被支持"
        assert result[0] == 31.2, "纬度应为31.2"
        assert result[1] == 121.5, "经度应为121.5"


# ============================================================================
# 测试用例 3-4: test_determine_disaster_scale
# ============================================================================

class TestDetermineDisasterScale:
    """测试灾害等级判断函数"""

    def test_determine_disaster_scale_earthquake_catastrophic(self):
        """
        测试用例3: 地震+大规模人口 -> catastrophic

        输入：地震 + affected_population > 10000
        期望：返回 "catastrophic"
        """
        # Arrange
        state = _make_state(
            parsed_disaster={
                "disaster_type": "earthquake",
                "severity": "critical",
                "affected_population": 15000,
                "estimated_trapped": 200,
            }
        )

        # Act
        result = _determine_disaster_scale(state)

        # Assert
        assert result == "catastrophic", "地震+大规模人口应判定为catastrophic"

    def test_determine_disaster_scale_earthquake_large(self):
        """
        测试用例3b: 地震+中等人口 -> large

        输入：地震 + affected_population < 10000
        期望：返回 "large"
        """
        # Arrange
        state = _make_state(
            parsed_disaster={
                "disaster_type": "earthquake",
                "severity": "high",
                "affected_population": 5000,
                "estimated_trapped": 50,
            }
        )

        # Act
        result = _determine_disaster_scale(state)

        # Assert
        assert result == "large", "地震应至少判定为large"

    def test_determine_disaster_scale_default(self):
        """
        测试用例4: 无灾情数据 -> medium

        输入：无 parsed_disaster
        期望：返回 "medium"
        """
        # Arrange - 无灾情解析结果
        state = _make_state()

        # Act
        result = _determine_disaster_scale(state)

        # Assert
        assert result == "medium", "无灾情数据应默认为medium"

    def test_determine_disaster_scale_by_trapped_count(self):
        """
        测试用例4b: 根据被困人数判断

        输入：被困人数 > 50
        期望：返回 "large"
        """
        # Arrange
        state = _make_state(
            parsed_disaster={
                "disaster_type": "flood",
                "severity": "medium",
                "estimated_trapped": 60,
            }
        )

        # Act
        result = _determine_disaster_scale(state)

        # Assert
        assert result == "large", "被困>50人应判定为large"

    def test_determine_disaster_scale_by_severity(self):
        """
        测试用例4c: 根据严重程度判断

        输入：severity = "low"
        期望：返回 "small"
        """
        # Arrange
        state = _make_state(
            parsed_disaster={
                "disaster_type": "fire",
                "severity": "low",
                "estimated_trapped": 5,
            }
        )

        # Act
        result = _determine_disaster_scale(state)

        # Assert
        assert result == "small", "低严重程度应判定为small"


# ============================================================================
# 测试用例 5-6: test_calculate_match_scores
# ============================================================================

class TestCalculateMatchScores:
    """测试匹配分数计算函数"""

    def test_calculate_match_scores_capability_coverage(self):
        """
        测试用例5: 能力有交集时计算匹配分数

        输入：队伍能力与需求有交集
        期望：match_score > 0
        """
        # Arrange
        teams = [
            _make_team(
                team_id="team-001",
                name="消防特勤一队",
                team_type="fire_rescue",
                capabilities=["RESCUE_STRUCTURAL", "FIRE_SUPPRESS", "SEARCH_LIFE_DETECT"],
                distance_km=15.0,
            ),
        ]
        required_capabilities = {"RESCUE_STRUCTURAL", "FIRE_SUPPRESS"}

        # Act
        candidates = _calculate_match_scores(
            teams=teams,
            required_capabilities=required_capabilities,
            event_lat=30.5,
            event_lng=120.3,
            max_response_hours=2.0,
        )

        # Assert
        assert len(candidates) == 1, "应返回1个候选"
        assert candidates[0]["match_score"] > 0, "匹配分数应大于0"
        assert candidates[0]["resource_name"] == "消防特勤一队"

    def test_calculate_match_scores_no_match(self):
        """
        测试用例6: 能力无交集时过滤

        输入：队伍能力与需求无交集
        期望：队伍被过滤掉
        """
        # Arrange
        teams = [
            _make_team(
                team_id="team-001",
                name="通信保障队",
                team_type="communication",
                capabilities=["LOG_COMM", "LOG_POWER"],  # 无救援能力
                distance_km=10.0,
            ),
        ]
        required_capabilities = {"RESCUE_STRUCTURAL", "MEDICAL_TRIAGE"}  # 需要救援能力

        # Act
        candidates = _calculate_match_scores(
            teams=teams,
            required_capabilities=required_capabilities,
            event_lat=30.5,
            event_lng=120.3,
            max_response_hours=2.0,
        )

        # Assert
        assert len(candidates) == 0, "无匹配能力的队伍应被过滤"

    def test_calculate_match_scores_distance_factor(self):
        """
        测试用例5b: 距离影响匹配分数

        输入：两个能力相同但距离不同的队伍
        期望：距离近的队伍分数更高
        """
        # Arrange
        teams = [
            _make_team(
                team_id="team-near",
                name="近距离队伍",
                team_type="fire_rescue",
                capabilities=["RESCUE_STRUCTURAL"],
                distance_km=5.0,
            ),
            _make_team(
                team_id="team-far",
                name="远距离队伍",
                team_type="fire_rescue",
                capabilities=["RESCUE_STRUCTURAL"],
                distance_km=50.0,
            ),
        ]
        required_capabilities = {"RESCUE_STRUCTURAL"}

        # Act
        candidates = _calculate_match_scores(
            teams=teams,
            required_capabilities=required_capabilities,
            event_lat=30.5,
            event_lng=120.3,
            max_response_hours=2.0,
        )

        # Assert
        assert len(candidates) == 2, "应返回2个候选"
        near_score = next(c["match_score"] for c in candidates if c["resource_id"] == "team-near")
        far_score = next(c["match_score"] for c in candidates if c["resource_id"] == "team-far")
        assert near_score > far_score, "距离近的队伍分数应更高"


# ============================================================================
# 测试用例 7: test_get_covered_capabilities
# ============================================================================

class TestGetCoveredCapabilities:
    """测试能力覆盖计算函数"""

    def test_get_covered_capabilities(self):
        """
        测试用例7: 计算能力并集

        输入：多个队伍的能力列表
        期望：返回能力并集
        """
        # Arrange
        teams = [
            {"capabilities": ["RESCUE_STRUCTURAL", "FIRE_SUPPRESS"]},
            {"capabilities": ["MEDICAL_TRIAGE", "MEDICAL_FIRST_AID"]},
            {"capabilities": ["RESCUE_STRUCTURAL", "SEARCH_LIFE_DETECT"]},  # 有重复
        ]

        # Act
        result = _get_covered_capabilities(teams)

        # Assert
        expected = {
            "RESCUE_STRUCTURAL",
            "FIRE_SUPPRESS",
            "MEDICAL_TRIAGE",
            "MEDICAL_FIRST_AID",
            "SEARCH_LIFE_DETECT",
        }
        assert result == expected, f"能力并集应为{expected}，实际为{result}"

    def test_get_covered_capabilities_empty(self):
        """
        测试用例7b: 空队伍列表

        输入：空列表
        期望：返回空集合
        """
        # Arrange
        teams = []

        # Act
        result = _get_covered_capabilities(teams)

        # Assert
        assert result == set(), "空队伍列表应返回空集合"

    def test_get_covered_capabilities_no_capabilities(self):
        """
        测试用例7c: 队伍无能力字段

        输入：队伍没有 capabilities 字段
        期望：返回空集合
        """
        # Arrange
        teams = [
            {"name": "无能力队伍"},
            {"capabilities": []},
        ]

        # Act
        result = _get_covered_capabilities(teams)

        # Assert
        assert result == set(), "无能力的队伍应返回空集合"


# ============================================================================
# 测试用例 8-9: test_generate_greedy_solution
# ============================================================================

class TestGenerateGreedySolution:
    """测试贪心策略生成函数"""

    def test_generate_greedy_solution_capacity_priority(self):
        """
        测试用例8: 容量优先策略

        输入：strategy="capacity"
        期望：按救援容量降序选择
        """
        # Arrange
        candidates = [
            {
                "resource_id": "team-small",
                "resource_name": "小容量队伍",
                "resource_type": "RESCUE_TEAM",
                "capabilities": ["RESCUE_STRUCTURAL"],
                "distance_km": 10.0,
                "availability_score": 1.0,
                "match_score": 0.8,
                "rescue_capacity": 10,
                "eta_minutes": 30,
                "base_lng": 120.0,
                "base_lat": 30.0,
            },
            {
                "resource_id": "team-large",
                "resource_name": "大容量队伍",
                "resource_type": "RESCUE_TEAM",
                "capabilities": ["RESCUE_STRUCTURAL"],
                "distance_km": 20.0,
                "availability_score": 1.0,
                "match_score": 0.7,
                "rescue_capacity": 50,
                "eta_minutes": 45,
                "base_lng": 120.0,
                "base_lat": 30.0,
            },
        ]
        capability_requirements = [
            {"capability_code": "RESCUE_STRUCTURAL"},
        ]

        # Act
        solution = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="capacity",
            solution_id="test-solution",
            estimated_trapped=30,
            capacity_safety_factor=1.2,
        )

        # Assert
        assert solution is not None, "应生成方案"
        allocations = solution["allocations"]
        # 容量优先策略应先选择大容量队伍
        assert allocations[0]["resource_id"] == "team-large", "应优先选择大容量队伍"

    def test_generate_greedy_solution_redundancy_enhancement(self):
        """
        测试用例9: 冗余性增强

        输入：低冗余能力（只有1个队伍覆盖）
        期望：添加备份队伍
        """
        # Arrange
        candidates = [
            {
                "resource_id": "team-primary",
                "resource_name": "主力队伍",
                "resource_type": "RESCUE_TEAM",
                "capabilities": ["RESCUE_STRUCTURAL", "FIRE_SUPPRESS"],
                "distance_km": 10.0,
                "availability_score": 1.0,
                "match_score": 0.9,
                "rescue_capacity": 20,
                "eta_minutes": 30,
                "base_lng": 120.0,
                "base_lat": 30.0,
            },
            {
                "resource_id": "team-backup",
                "resource_name": "备份队伍",
                "resource_type": "RESCUE_TEAM",
                "capabilities": ["RESCUE_STRUCTURAL"],  # 可为 RESCUE_STRUCTURAL 提供备份
                "distance_km": 15.0,
                "availability_score": 1.0,
                "match_score": 0.7,
                "rescue_capacity": 15,
                "eta_minutes": 40,
                "base_lng": 120.0,
                "base_lat": 30.0,
            },
        ]
        capability_requirements = [
            {"capability_code": "RESCUE_STRUCTURAL"},
            {"capability_code": "FIRE_SUPPRESS"},
        ]

        # Act
        solution = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="match_score",
            solution_id="test-solution",
            estimated_trapped=10,
            capacity_safety_factor=1.2,
        )

        # Assert
        assert solution is not None, "应生成方案"
        allocations = solution["allocations"]
        # 冗余增强阶段应添加备份队伍
        resource_ids = [a["resource_id"] for a in allocations]
        assert "team-backup" in resource_ids, "应添加备份队伍以增强冗余性"


# ============================================================================
# 测试用例 10: test_map_team_type
# ============================================================================

class TestMapTeamType:
    """测试队伍类型映射函数"""

    def test_map_team_type_fire_rescue(self):
        """测试消防救援队伍类型映射"""
        assert _map_team_type("fire_rescue") == "FIRE_TEAM"

    def test_map_team_type_medical(self):
        """测试医疗队伍类型映射"""
        assert _map_team_type("medical") == "MEDICAL_TEAM"

    def test_map_team_type_search_rescue(self):
        """测试搜救队伍类型映射"""
        assert _map_team_type("search_rescue") == "RESCUE_TEAM"

    def test_map_team_type_unknown(self):
        """测试未知队伍类型映射"""
        assert _map_team_type("unknown_type") == "RESCUE_TEAM"  # 默认值


# ============================================================================
# 测试用例: 车辆配置
# ============================================================================

class TestVehicleProfiles:
    """测试车辆参数配置"""

    def test_vehicle_profile_exists_for_common_types(self):
        """测试常见队伍类型都有车辆配置"""
        common_types = ["fire_rescue", "medical", "search_rescue", "hazmat", "engineering"]
        for team_type in common_types:
            assert team_type in TEAM_VEHICLE_PROFILES, f"{team_type} 应有车辆配置"

    def test_default_vehicle_profile(self):
        """测试默认车辆配置"""
        assert DEFAULT_VEHICLE_PROFILE is not None
        assert DEFAULT_VEHICLE_PROFILE.speed_kmh > 0
        assert DEFAULT_VEHICLE_PROFILE.mountain_speed_kmh > 0

    def test_fire_rescue_is_all_terrain(self):
        """测试消防车是全地形"""
        profile = TEAM_VEHICLE_PROFILES["fire_rescue"]
        assert profile.is_all_terrain is True, "消防车应为全地形"


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
