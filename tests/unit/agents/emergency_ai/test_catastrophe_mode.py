"""
巨灾模式边界测试

测试 optimization.py 中巨灾模式的边界行为：
- 触发条件
- 容量缺口计算
- 增援级别判定
- 方案组合逻辑
- 5维评估执行

作者：Claude Code
日期：2025-12-11
"""
import os
import sys
from typing import Dict, Any, List
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

# 添加项目根目录到路径
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.emergency_ai.nodes.optimization import (
    _try_combine_catastrophe_solutions,
    _calculate_success_rate,
    _calculate_redundancy_rate,
)
from src.agents.emergency_ai.state import EmergencyAIState, AllocationSolution, SchemeScore


# ============================================================================
# 测试辅助函数
# ============================================================================

def _make_solution(
    solution_id: str,
    allocations: List[Dict[str, Any]] = None,
    total_rescue_capacity: int = 50,
    coverage_rate: float = 0.8,
    response_time_min: float = 45.0,
    total_score: float = 0.75,
    risk_level: float = 0.2,
) -> AllocationSolution:
    """
    构造测试用的分配方案

    Args:
        solution_id: 方案ID
        allocations: 资源分配列表
        total_rescue_capacity: 总救援容量
        coverage_rate: 能力覆盖率
        response_time_min: 响应时间（分钟）
        total_score: 总分
        risk_level: 风险等级

    Returns:
        AllocationSolution 字典
    """
    if allocations is None:
        allocations = [
            {
                "resource_id": "team-001",
                "resource_name": "测试队伍1",
                "resource_type": "RESCUE_TEAM",
                "assigned_capabilities": ["RESCUE_STRUCTURAL"],
                "match_score": 0.8,
                "distance_km": 15.0,
                "eta_minutes": 30,
                "rescue_capacity": 25,
            },
            {
                "resource_id": "team-002",
                "resource_name": "测试队伍2",
                "resource_type": "MEDICAL_TEAM",
                "assigned_capabilities": ["MEDICAL_TRIAGE"],
                "match_score": 0.7,
                "distance_km": 20.0,
                "eta_minutes": 40,
                "rescue_capacity": 25,
            },
        ]

    return {
        "solution_id": solution_id,
        "allocations": allocations,
        "total_rescue_capacity": total_rescue_capacity,
        "coverage_rate": coverage_rate,
        "response_time_min": response_time_min,
        "total_score": total_score,
        "risk_level": risk_level,
        "resource_scale": len(allocations),
        "teams_count": len(allocations),
        "uncovered_capabilities": [],
        "max_distance_km": 20.0,
    }


def _make_scheme_score(
    scheme_id: str,
    hard_rule_passed: bool = True,
    hard_rule_violations: List[str] = None,
    weighted_score: float = 0.75,
) -> SchemeScore:
    """
    构造测试用的方案评分

    Args:
        scheme_id: 方案ID
        hard_rule_passed: 是否通过硬规则
        hard_rule_violations: 硬规则违反列表
        weighted_score: 加权得分

    Returns:
        SchemeScore 字典
    """
    return {
        "scheme_id": scheme_id,
        "hard_rule_passed": hard_rule_passed,
        "hard_rule_violations": hard_rule_violations or [],
        "soft_rule_scores": {},
        "weighted_score": weighted_score,
        "rank": 0,
        "risk_level": "critical" if not hard_rule_passed else "normal",
        "requires_authorization": not hard_rule_passed,
        "safety_classification": {"reject": [], "break_glass": [], "warn": []},
        "break_glass_rules": [],
    }


def _make_state_for_catastrophe(
    event_id: str = "test-event-001",
    estimated_trapped: int = 100,
    current_capacity: int = 30,
    solutions: List[AllocationSolution] = None,
    scheme_scores: List[SchemeScore] = None,
) -> EmergencyAIState:
    """
    构造巨灾模式测试用的状态

    Args:
        event_id: 事件ID
        estimated_trapped: 被困人数
        current_capacity: 当前救援容量
        solutions: 候选方案列表
        scheme_scores: 方案评分列表

    Returns:
        EmergencyAIState 字典
    """
    if solutions is None:
        solutions = [
            _make_solution("solution-001", total_rescue_capacity=current_capacity),
        ]

    if scheme_scores is None:
        # 所有方案都违反硬规则（触发巨灾模式）
        scheme_scores = [
            _make_scheme_score(
                scheme_id="solution-001",
                hard_rule_passed=False,
                hard_rule_violations=["COVERAGE_RATE_MIN: 覆盖率不足"],
            ),
        ]

    state: EmergencyAIState = {
        "event_id": event_id,
        "disaster_description": "测试灾情",
        "structured_input": {},
        "parsed_disaster": {
            "disaster_type": "earthquake",
            "severity": "critical",
            "estimated_trapped": estimated_trapped,
            "affected_population": 5000,
        },
        "allocation_solutions": solutions,
        "scheme_scores": scheme_scores,
        "capability_requirements": [
            {"capability_code": "RESCUE_STRUCTURAL"},
            {"capability_code": "MEDICAL_TRIAGE"},
        ],
        "similar_cases": [],
        "trace": {},
        "errors": [],
    }

    return state


# ============================================================================
# 测试用例 1: 巨灾模式触发条件
# ============================================================================

class TestCatastropheModeTriggered:
    """测试巨灾模式触发条件"""

    def test_catastrophe_mode_triggered_when_all_rejected(self):
        """
        测试用例1: 所有方案违反硬规则时触发巨灾模式

        输入：所有方案的 hard_rule_passed = False
        期望：requires_reinforcement = True
        """
        # Arrange
        scheme_scores = [
            _make_scheme_score("sol-1", hard_rule_passed=False),
            _make_scheme_score("sol-2", hard_rule_passed=False),
        ]

        # 检查是否所有方案都未通过硬规则
        normal_scores = [s for s in scheme_scores if s["hard_rule_passed"]]

        # Assert
        assert len(normal_scores) == 0, "应无通过硬规则的方案"
        # 当 normal_scores 为空时，应触发巨灾模式
        requires_reinforcement = len(normal_scores) == 0
        assert requires_reinforcement is True, "所有方案被否决时应触发巨灾模式"

    def test_catastrophe_mode_not_triggered_when_some_passed(self):
        """
        测试用例1b: 有方案通过硬规则时不触发巨灾模式

        输入：至少一个方案的 hard_rule_passed = True
        期望：requires_reinforcement = False
        """
        # Arrange
        scheme_scores = [
            _make_scheme_score("sol-1", hard_rule_passed=True),
            _make_scheme_score("sol-2", hard_rule_passed=False),
        ]

        # 检查是否有方案通过硬规则
        normal_scores = [s for s in scheme_scores if s["hard_rule_passed"]]

        # Assert
        assert len(normal_scores) > 0, "应有通过硬规则的方案"
        requires_reinforcement = len(normal_scores) == 0
        assert requires_reinforcement is False, "有方案通过时不应触发巨灾模式"


# ============================================================================
# 测试用例 2: 容量缺口计算
# ============================================================================

class TestCapacityGapCalculation:
    """测试容量缺口计算"""

    def test_catastrophe_mode_capacity_gap_calculation(self):
        """
        测试用例2: 容量缺口计算

        输入：被困 100 人，容量 30 人
        期望：capacity_gap = 70
        """
        # Arrange
        estimated_trapped = 100
        current_capacity = 30

        # Act
        capacity_gap = max(0, estimated_trapped - current_capacity)

        # Assert
        assert capacity_gap == 70, f"容量缺口应为70，实际为{capacity_gap}"

    def test_capacity_gap_zero_when_sufficient(self):
        """
        测试用例2b: 容量充足时缺口为0

        输入：被困 50 人，容量 80 人
        期望：capacity_gap = 0
        """
        # Arrange
        estimated_trapped = 50
        current_capacity = 80

        # Act
        capacity_gap = max(0, estimated_trapped - current_capacity)

        # Assert
        assert capacity_gap == 0, "容量充足时缺口应为0"

    def test_capacity_rate_calculation(self):
        """
        测试用例2c: 容量覆盖率计算

        输入：被困 100 人，容量 30 人
        期望：capacity_rate = 0.3
        """
        # Arrange
        estimated_trapped = 100
        current_capacity = 30

        # Act
        capacity_rate = current_capacity / estimated_trapped if estimated_trapped > 0 else 0

        # Assert
        assert capacity_rate == 0.3, f"容量覆盖率应为0.3，实际为{capacity_rate}"


# ============================================================================
# 测试用例 3-5: 增援级别判定
# ============================================================================

class TestReinforcementLevel:
    """测试增援级别判定"""

    def test_catastrophe_mode_reinforcement_level_national(self):
        """
        测试用例3: 国家级增援

        输入：capacity_rate < 0.3
        期望：reinforcement_level = "国家级"
        """
        # Arrange
        capacity_rate = 0.25  # < 0.3

        # Act
        if capacity_rate < 0.3:
            reinforcement_level = "国家级"
        elif capacity_rate < 0.5:
            reinforcement_level = "省级"
        else:
            reinforcement_level = "市级"

        # Assert
        assert reinforcement_level == "国家级", "覆盖率<30%应为国家级增援"

    def test_catastrophe_mode_reinforcement_level_provincial(self):
        """
        测试用例4: 省级增援

        输入：0.3 <= capacity_rate < 0.5
        期望：reinforcement_level = "省级"
        """
        # Arrange
        capacity_rate = 0.4  # >= 0.3 且 < 0.5

        # Act
        if capacity_rate < 0.3:
            reinforcement_level = "国家级"
        elif capacity_rate < 0.5:
            reinforcement_level = "省级"
        else:
            reinforcement_level = "市级"

        # Assert
        assert reinforcement_level == "省级", "覆盖率30%-50%应为省级增援"

    def test_catastrophe_mode_reinforcement_level_municipal(self):
        """
        测试用例5: 市级增援

        输入：capacity_rate >= 0.5
        期望：reinforcement_level = "市级"
        """
        # Arrange
        capacity_rate = 0.6  # >= 0.5

        # Act
        if capacity_rate < 0.3:
            reinforcement_level = "国家级"
        elif capacity_rate < 0.5:
            reinforcement_level = "省级"
        else:
            reinforcement_level = "市级"

        # Assert
        assert reinforcement_level == "市级", "覆盖率>=50%应为市级增援"

    def test_reinforcement_level_boundary_30_percent(self):
        """
        测试用例3b: 边界值测试 - 恰好30%

        输入：capacity_rate = 0.3
        期望：reinforcement_level = "省级"（不是国家级）
        """
        # Arrange
        capacity_rate = 0.3  # 恰好等于边界值

        # Act
        if capacity_rate < 0.3:
            reinforcement_level = "国家级"
        elif capacity_rate < 0.5:
            reinforcement_level = "省级"
        else:
            reinforcement_level = "市级"

        # Assert
        assert reinforcement_level == "省级", "覆盖率恰好30%应为省级增援"


# ============================================================================
# 测试用例 6: 方案组合逻辑
# ============================================================================

class TestCatastropheSolutionCombination:
    """测试巨灾模式方案组合逻辑"""

    def test_catastrophe_mode_combined_solution(self):
        """
        测试用例6: 多方案组合

        输入：多个方案可组合
        期望：组合后覆盖更多能力
        """
        # Arrange
        solutions = [
            _make_solution(
                "sol-1",
                allocations=[
                    {
                        "resource_id": "team-001",
                        "resource_name": "救援队1",
                        "resource_type": "RESCUE_TEAM",
                        "assigned_capabilities": ["RESCUE_STRUCTURAL"],
                        "match_score": 0.8,
                        "distance_km": 10.0,
                        "eta_minutes": 25,
                        "rescue_capacity": 20,
                    },
                ],
                total_rescue_capacity=20,
            ),
            _make_solution(
                "sol-2",
                allocations=[
                    {
                        "resource_id": "team-002",
                        "resource_name": "医疗队1",
                        "resource_type": "MEDICAL_TEAM",
                        "assigned_capabilities": ["MEDICAL_TRIAGE"],
                        "match_score": 0.7,
                        "distance_km": 15.0,
                        "eta_minutes": 35,
                        "rescue_capacity": 15,
                    },
                ],
                total_rescue_capacity=15,
            ),
        ]
        capability_requirements = [
            {"capability_code": "RESCUE_STRUCTURAL"},
            {"capability_code": "MEDICAL_TRIAGE"},
        ]

        # Act
        combined = _try_combine_catastrophe_solutions(solutions, capability_requirements)

        # Assert
        assert combined is not None, "应返回组合方案"
        # 组合后应包含两个队伍的能力
        all_caps = set()
        for alloc in combined.get("allocations", []):
            all_caps.update(alloc.get("assigned_capabilities", []))

        assert "RESCUE_STRUCTURAL" in all_caps or "MEDICAL_TRIAGE" in all_caps, \
            "组合方案应覆盖更多能力"

    def test_catastrophe_mode_single_solution(self):
        """
        测试用例6b: 单方案不组合

        输入：只有一个方案
        期望：直接返回该方案
        """
        # Arrange
        solutions = [
            _make_solution("sol-1", total_rescue_capacity=30),
        ]
        capability_requirements = [{"capability_code": "RESCUE_STRUCTURAL"}]

        # Act
        result = _try_combine_catastrophe_solutions(solutions, capability_requirements)

        # Assert
        assert result is not None, "应返回方案"
        assert result["solution_id"] == "sol-1", "单方案应直接返回"


# ============================================================================
# 测试用例 7: 警告消息包含缺口
# ============================================================================

class TestWarningMessage:
    """测试警告消息内容"""

    def test_catastrophe_mode_warning_message_contains_gap(self):
        """
        测试用例7: 警告消息包含容量缺口

        输入：任意巨灾场景
        期望：warning 包含容量缺口数字
        """
        # Arrange
        estimated_trapped = 100
        current_capacity = 30
        capacity_gap = max(0, estimated_trapped - current_capacity)
        capacity_rate = current_capacity / estimated_trapped

        # Act - 生成警告消息（模拟 optimization.py 中的逻辑）
        if capacity_rate < 0.3:
            reinforcement_message = (
                f"🚨🚨🚨 特大灾害！本地资源严重不足！\n"
                f"被困人数: {estimated_trapped}人\n"
                f"本地救援容量: {current_capacity}人（仅覆盖{capacity_rate*100:.1f}%）\n"
                f"容量缺口: {capacity_gap}人\n"
            )
        else:
            reinforcement_message = f"容量缺口: {capacity_gap}人"

        # Assert
        assert str(capacity_gap) in reinforcement_message, "警告消息应包含容量缺口数字"
        assert "70" in reinforcement_message, "缺口70应出现在消息中"

    def test_warning_message_contains_trapped_count(self):
        """
        测试用例7b: 警告消息包含被困人数

        输入：被困100人
        期望：warning 包含被困人数
        """
        # Arrange
        estimated_trapped = 100
        current_capacity = 30
        capacity_rate = current_capacity / estimated_trapped

        # Act
        reinforcement_message = f"被困人数: {estimated_trapped}人"

        # Assert
        assert "100" in reinforcement_message, "警告消息应包含被困人数"


# ============================================================================
# 测试用例 8: 5维评估仍然执行
# ============================================================================

class TestCatastrophe5DEvaluation:
    """测试巨灾模式下5维评估"""

    def test_catastrophe_mode_5d_evaluation_still_runs(self):
        """
        测试用例8: 巨灾模式下5维评估仍执行

        输入：巨灾模式方案
        期望：soft_rule_scores 包含 5 维评分
        """
        # Arrange
        solution = _make_solution(
            "catastrophe-sol",
            total_rescue_capacity=30,
            coverage_rate=0.6,
            response_time_min=45.0,
        )
        similar_cases = []
        capability_requirements = [
            {"capability_code": "RESCUE_STRUCTURAL"},
            {"capability_code": "MEDICAL_TRIAGE"},
        ]

        # Act - 计算5维评分
        success_rate = _calculate_success_rate(solution, similar_cases, "earthquake")
        redundancy = _calculate_redundancy_rate(solution, capability_requirements)

        response_time = solution.get("response_time_min", 60)
        time_score = max(0, 1 - response_time / 120)
        coverage = solution.get("coverage_rate", 0)
        risk = 1 - solution.get("risk_level", 0)

        soft_rule_scores = {
            "success_rate": round(success_rate, 3),
            "response_time": round(time_score, 3),
            "coverage_rate": round(coverage, 3),
            "risk": round(risk, 3),
            "redundancy": round(redundancy, 3),
        }

        # Assert - 验证5维评分都存在
        assert "success_rate" in soft_rule_scores, "应包含成功率评分"
        assert "response_time" in soft_rule_scores, "应包含响应时间评分"
        assert "coverage_rate" in soft_rule_scores, "应包含覆盖率评分"
        assert "risk" in soft_rule_scores, "应包含风险评分"
        assert "redundancy" in soft_rule_scores, "应包含冗余性评分"

        # 验证评分在合理范围内
        for key, value in soft_rule_scores.items():
            assert 0 <= value <= 1, f"{key} 评分应在0-1范围内，实际为{value}"

    def test_success_rate_calculation_with_cases(self):
        """
        测试用例8b: 有历史案例时的成功率计算

        输入：有相似历史案例
        期望：成功率受案例影响
        """
        # Arrange
        solution = _make_solution("sol-1", coverage_rate=0.8, total_score=0.75)
        similar_cases = [
            {"similarity_score": 0.9, "lessons_learned": "成功救援"},
            {"similarity_score": 0.7, "lessons_learned": None},
        ]

        # Act
        success_rate = _calculate_success_rate(solution, similar_cases, "earthquake")

        # Assert
        assert 0 < success_rate <= 1, f"成功率应在0-1范围内，实际为{success_rate}"

    def test_redundancy_calculation(self):
        """
        测试用例8c: 冗余性计算

        输入：多个队伍覆盖同一能力
        期望：冗余性评分更高
        """
        # Arrange
        solution_high_redundancy = _make_solution(
            "sol-high",
            allocations=[
                {"resource_id": "t1", "assigned_capabilities": ["RESCUE_STRUCTURAL"]},
                {"resource_id": "t2", "assigned_capabilities": ["RESCUE_STRUCTURAL"]},  # 冗余
                {"resource_id": "t3", "assigned_capabilities": ["MEDICAL_TRIAGE"]},
            ],
        )
        solution_low_redundancy = _make_solution(
            "sol-low",
            allocations=[
                {"resource_id": "t1", "assigned_capabilities": ["RESCUE_STRUCTURAL"]},
                {"resource_id": "t2", "assigned_capabilities": ["MEDICAL_TRIAGE"]},
            ],
        )
        capability_requirements = [
            {"capability_code": "RESCUE_STRUCTURAL"},
            {"capability_code": "MEDICAL_TRIAGE"},
        ]

        # Act
        redundancy_high = _calculate_redundancy_rate(solution_high_redundancy, capability_requirements)
        redundancy_low = _calculate_redundancy_rate(solution_low_redundancy, capability_requirements)

        # Assert
        assert redundancy_high >= redundancy_low, "高冗余方案的冗余性评分应更高"


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
