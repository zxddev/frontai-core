"""
硬规则引擎单元测试

测试 TRRRuleEngine 的核心功能：
- 硬规则分类（reject/break_glass/warn）
- 条件求值
- 规则通过判定

作者：Claude Code
日期：2025-12-11
"""
import os
import sys
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
import pytest

# 添加项目根目录到路径
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.rules.engine import TRRRuleEngine
from src.agents.rules.models import (
    HardRule,
    HardRuleCheck,
    HardRuleCondition,
    HardRuleAction,
    HardRuleSeverity,
    HardRuleResult,
    ConditionOperator,
)


# ============================================================================
# 测试辅助函数
# ============================================================================

def _make_hard_rule(
    rule_id: str,
    name: str,
    check_field: str,
    check_operator: ConditionOperator,
    threshold: float,
    action: HardRuleAction,
    message: str = "规则违反: {value} vs {threshold}",
    severity: HardRuleSeverity = HardRuleSeverity.HIGH,
    condition: HardRuleCondition = None,
) -> HardRule:
    """
    构造测试用的硬规则

    Args:
        rule_id: 规则ID
        name: 规则名称
        check_field: 检查字段
        check_operator: 比较操作符
        threshold: 阈值
        action: 执行动作
        message: 消息模板
        severity: 严重程度
        condition: 前置条件

    Returns:
        HardRule 对象
    """
    return HardRule(
        id=rule_id,
        name=name,
        description=f"测试规则: {name}",
        check=HardRuleCheck(
            field=check_field,
            operator=check_operator,
            threshold=threshold,
        ),
        condition=condition,
        action=action,
        message=message,
        severity=severity,
    )


def _make_engine_with_rules(rules: List[HardRule]) -> TRRRuleEngine:
    """
    创建带有指定规则的引擎（绕过文件加载）

    Args:
        rules: 硬规则列表

    Returns:
        配置好的 TRRRuleEngine
    """
    engine = TRRRuleEngine()
    engine._hard_rules = rules
    engine._trr_rules = []
    engine._loaded = True
    return engine


# ============================================================================
# 测试用例 1: 硬规则 reject 分类
# ============================================================================

class TestHardRuleRejectClassification:
    """测试 reject 类规则分类"""

    def test_hard_rule_reject_classification(self):
        """
        测试用例1: 违反 reject 类规则的方案

        输入：coverage_rate < 0.8（违反最低覆盖率规则）
        期望：classification["reject"] 非空
        """
        # Arrange - 创建一条 reject 规则
        rule = _make_hard_rule(
            rule_id="HR-TEST-001",
            name="最低覆盖率",
            check_field="coverage_rate",
            check_operator=ConditionOperator.LT,  # 违规条件：< 0.8
            threshold=0.8,
            action=HardRuleAction.REJECT,
            message="覆盖率{value}低于最低要求{threshold}",
        )
        engine = _make_engine_with_rules([rule])

        # 方案数据：覆盖率 0.5 < 0.8，违反规则
        scheme_data = {
            "coverage_rate": 0.5,
            "response_time_min": 30,
        }

        # Act
        result = engine.check_hard_rules(scheme_data, with_classification=True)

        # Assert
        classification = result["classification"]
        assert len(classification["reject"]) > 0, "应有 reject 类违规"
        assert classification["reject"][0].rule_id == "HR-TEST-001"
        assert classification["reject"][0].passed is False

    def test_hard_rule_reject_blocks_scheme(self):
        """
        测试用例1b: reject 规则阻断方案

        输入：违反 reject 规则
        期望：is_scheme_feasible 返回 False
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-002",
            name="最大响应时间",
            check_field="response_time_min",
            check_operator=ConditionOperator.GT,  # 违规条件：> 60
            threshold=60,
            action=HardRuleAction.REJECT,
        )
        engine = _make_engine_with_rules([rule])

        scheme_data = {"response_time_min": 90}  # 90 > 60，违规

        # Act
        results = engine.check_hard_rules(scheme_data)
        feasible = engine.is_scheme_feasible(results)

        # Assert
        assert feasible is False, "违反 reject 规则的方案应不可行"


# ============================================================================
# 测试用例 2: 硬规则 break_glass 分类
# ============================================================================

class TestHardRuleBreakGlassClassification:
    """测试 break_glass 类规则分类"""

    def test_hard_rule_break_glass_classification(self):
        """
        测试用例2: 违反 break_glass 类规则的方案

        输入：risk_level > 0.7（高风险需确认）
        期望：classification["break_glass"] 非空
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-003",
            name="高风险确认",
            check_field="risk_level",
            check_operator=ConditionOperator.GT,  # 违规条件：> 0.7
            threshold=0.7,
            action=HardRuleAction.BREAK_GLASS,
            message="风险等级{value}超过阈值{threshold}，需指挥员确认",
        )
        engine = _make_engine_with_rules([rule])

        scheme_data = {"risk_level": 0.85}  # 0.85 > 0.7，触发 break_glass

        # Act
        result = engine.check_hard_rules(scheme_data, with_classification=True)

        # Assert
        classification = result["classification"]
        assert len(classification["break_glass"]) > 0, "应有 break_glass 类违规"
        assert classification["break_glass"][0].rule_id == "HR-TEST-003"
        assert classification["break_glass"][0].requires_audit is True

    def test_hard_rule_break_glass_requires_confirmation(self):
        """
        测试用例2b: break_glass 规则需要确认

        输入：违反 break_glass 规则
        期望：requires_break_glass 返回 True
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-004",
            name="跨区域调度确认",
            check_field="cross_region",
            check_operator=ConditionOperator.EQ,  # 违规条件：== True
            threshold=True,
            action=HardRuleAction.BREAK_GLASS,
        )
        engine = _make_engine_with_rules([rule])

        scheme_data = {"cross_region": True}  # 跨区域，需确认

        # Act
        results = engine.check_hard_rules(scheme_data)
        requires_confirm = engine.requires_break_glass(results)

        # Assert
        assert requires_confirm is True, "break_glass 规则应要求确认"


# ============================================================================
# 测试用例 3: 硬规则 warn 分类
# ============================================================================

class TestHardRuleWarnClassification:
    """测试 warn 类规则分类"""

    def test_hard_rule_warn_classification(self):
        """
        测试用例3: 违反 warn 类规则的方案

        输入：redundancy_rate < 0.5（冗余性不足警告）
        期望：classification["warn"] 非空
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-005",
            name="冗余性警告",
            check_field="redundancy_rate",
            check_operator=ConditionOperator.LT,  # 违规条件：< 0.5
            threshold=0.5,
            action=HardRuleAction.WARN,
            message="冗余性{value}较低，建议增加备份资源",
            severity=HardRuleSeverity.MEDIUM,
        )
        engine = _make_engine_with_rules([rule])

        scheme_data = {"redundancy_rate": 0.3}  # 0.3 < 0.5，触发警告

        # Act
        result = engine.check_hard_rules(scheme_data, with_classification=True)

        # Assert
        classification = result["classification"]
        assert len(classification["warn"]) > 0, "应有 warn 类违规"
        assert classification["warn"][0].rule_id == "HR-TEST-005"

    def test_hard_rule_warn_does_not_block(self):
        """
        测试用例3b: warn 规则不阻断方案

        输入：仅违反 warn 规则
        期望：is_scheme_feasible 返回 True
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-006",
            name="成本警告",
            check_field="estimated_cost",
            check_operator=ConditionOperator.GT,  # 违规条件：> 100000
            threshold=100000,
            action=HardRuleAction.WARN,
        )
        engine = _make_engine_with_rules([rule])

        scheme_data = {"estimated_cost": 150000}  # 超预算，但只是警告

        # Act
        results = engine.check_hard_rules(scheme_data)
        feasible = engine.is_scheme_feasible(results)

        # Assert
        assert feasible is True, "仅 warn 规则不应阻断方案"


# ============================================================================
# 测试用例 4: 所有规则通过
# ============================================================================

class TestHardRulePassAll:
    """测试所有规则通过的情况"""

    def test_hard_rule_pass_all(self):
        """
        测试用例4: 符合所有规则的方案

        输入：所有指标都在阈值范围内
        期望：所有分类为空
        """
        # Arrange - 创建多条规则
        rules = [
            _make_hard_rule(
                rule_id="HR-TEST-007",
                name="覆盖率检查",
                check_field="coverage_rate",
                check_operator=ConditionOperator.LT,
                threshold=0.8,
                action=HardRuleAction.REJECT,
            ),
            _make_hard_rule(
                rule_id="HR-TEST-008",
                name="风险检查",
                check_field="risk_level",
                check_operator=ConditionOperator.GT,
                threshold=0.7,
                action=HardRuleAction.BREAK_GLASS,
            ),
            _make_hard_rule(
                rule_id="HR-TEST-009",
                name="冗余性检查",
                check_field="redundancy_rate",
                check_operator=ConditionOperator.LT,
                threshold=0.3,
                action=HardRuleAction.WARN,
            ),
        ]
        engine = _make_engine_with_rules(rules)

        # 方案数据：所有指标都合格
        scheme_data = {
            "coverage_rate": 0.95,    # > 0.8，通过
            "risk_level": 0.3,        # < 0.7，通过
            "redundancy_rate": 0.6,   # > 0.3，通过
        }

        # Act
        result = engine.check_hard_rules(scheme_data, with_classification=True)

        # Assert
        classification = result["classification"]
        assert len(classification["reject"]) == 0, "不应有 reject 违规"
        assert len(classification["break_glass"]) == 0, "不应有 break_glass 违规"
        assert len(classification["warn"]) == 0, "不应有 warn 违规"

        # 所有结果都应该是 passed=True
        for r in result["results"]:
            assert r.passed is True, f"规则 {r.rule_id} 应该通过"


# ============================================================================
# 测试用例 5: 条件求值
# ============================================================================

class TestHardRuleConditionEvaluation:
    """测试硬规则条件求值"""

    def test_hard_rule_condition_evaluation_lt(self):
        """
        测试用例5: 小于条件求值

        输入：coverage_rate = 0.6, 阈值 0.8
        期望：0.6 < 0.8 为 True，规则违反
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-010",
            name="覆盖率下限",
            check_field="coverage_rate",
            check_operator=ConditionOperator.LT,
            threshold=0.8,
            action=HardRuleAction.REJECT,
        )
        engine = _make_engine_with_rules([rule])

        # Act
        results = engine.check_hard_rules({"coverage_rate": 0.6})

        # Assert
        assert results[0].passed is False, "0.6 < 0.8 应触发违规"
        assert results[0].checked_value == 0.6
        assert results[0].threshold_value == 0.8

    def test_hard_rule_condition_evaluation_gte(self):
        """
        测试用例5b: 大于等于条件求值

        输入：response_time = 60, 阈值 60
        期望：60 >= 60 为 True，规则违反
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-011",
            name="响应时间上限",
            check_field="response_time_min",
            check_operator=ConditionOperator.GTE,
            threshold=60,
            action=HardRuleAction.WARN,
        )
        engine = _make_engine_with_rules([rule])

        # Act
        results = engine.check_hard_rules({"response_time_min": 60})

        # Assert
        assert results[0].passed is False, "60 >= 60 应触发违规"

    def test_hard_rule_condition_with_precondition(self):
        """
        测试用例5c: 带前置条件的规则

        输入：disaster_type=earthquake 时检查 magnitude
        期望：前置条件满足时才检查主条件
        """
        # Arrange - 仅地震时检查震级
        rule = _make_hard_rule(
            rule_id="HR-TEST-012",
            name="地震震级检查",
            check_field="magnitude",
            check_operator=ConditionOperator.GTE,
            threshold=7.0,
            action=HardRuleAction.REJECT,
            condition=HardRuleCondition(
                field="disaster_type",
                operator=ConditionOperator.EQ,
                value="earthquake",
            ),
        )
        engine = _make_engine_with_rules([rule])

        # Case 1: 地震且震级高 -> 违规
        results1 = engine.check_hard_rules({
            "disaster_type": "earthquake",
            "magnitude": 7.5,
        })
        assert results1[0].passed is False, "地震7.5级应违规"

        # Case 2: 非地震 -> 规则不适用，通过
        results2 = engine.check_hard_rules({
            "disaster_type": "flood",
            "magnitude": 8.0,  # 即使震级高，但不是地震
        })
        assert results2[0].passed is True, "非地震时规则不适用"

    def test_hard_rule_nested_field_evaluation(self):
        """
        测试用例5d: 嵌套字段求值

        输入：location.risk_level = 0.9（嵌套字段）
        期望：正确解析嵌套字段
        """
        # Arrange - 使用数值类型阈值（HardRuleCheck.threshold 只支持 float|int|bool）
        rule = _make_hard_rule(
            rule_id="HR-TEST-013",
            name="高风险区域检查",
            check_field="location.risk_level",
            check_operator=ConditionOperator.GT,
            threshold=0.7,
            action=HardRuleAction.BREAK_GLASS,
        )
        engine = _make_engine_with_rules([rule])

        # Act
        results = engine.check_hard_rules({
            "location": {
                "risk_level": 0.9,  # 0.9 > 0.7，触发违规
                "lat": 30.5,
                "lng": 104.0,
            }
        })

        # Assert
        assert results[0].passed is False, "高风险区域应触发 break_glass"
        assert results[0].checked_value == 0.9

    def test_hard_rule_missing_field_skipped(self):
        """
        测试用例5e: 缺失字段跳过检查

        输入：方案数据中缺少检查字段
        期望：规则跳过，返回通过
        """
        # Arrange
        rule = _make_hard_rule(
            rule_id="HR-TEST-014",
            name="可选字段检查",
            check_field="optional_metric",
            check_operator=ConditionOperator.LT,
            threshold=0.5,
            action=HardRuleAction.WARN,
        )
        engine = _make_engine_with_rules([rule])

        # Act - 方案中没有 optional_metric 字段
        results = engine.check_hard_rules({"coverage_rate": 0.9})

        # Assert
        assert results[0].passed is True, "缺失字段应跳过检查"
        assert "不存在" in results[0].message


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
