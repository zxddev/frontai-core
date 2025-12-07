import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.rules.engine import TRRRuleEngine
from src.agents.rules.models import (
    HardRule,
    HardRuleCheck,
    HardRuleAction,
    HardRuleSeverity,
    ConditionOperator,
)


def _build_rule(action: HardRuleAction, threshold: float = 50.0) -> HardRule:
    return HardRule(
        id="TEST",
        name="电量检查",
        description="电量不足风险",
        check=HardRuleCheck(field="battery", operator=ConditionOperator.LT, threshold=threshold),
        condition=None,
        action=action,
        message="电量{value}%不足（需{threshold}%）",
        severity=HardRuleSeverity.HIGH,
    )


def test_break_glass_rule_returns_audit_flag_and_risk():
    engine = TRRRuleEngine()
    engine._hard_rules = [_build_rule(HardRuleAction.BREAK_GLASS, threshold=30)]
    engine._loaded = True

    result = engine.check_hard_rules({"battery": 20}, with_classification=True)

    results = result["results"]
    classification = result["classification"]

    assert len(results) == 1
    r = results[0]
    assert r.passed is False
    assert r.requires_audit is True
    assert r.risk_description == "电量不足风险"

    assert "break_glass" in classification
    assert len(classification["break_glass"]) == 1
