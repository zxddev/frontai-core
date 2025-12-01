"""Unit tests for PriorityScoringEngine.

These tests focus on deterministic parts of the scoring logic:
- Dimension normalization
- Hard rule application and priority bucketing
"""
from __future__ import annotations

from typing import Any, Dict

from src.agents.rules.models import ConditionOperator
from src.agents.shared.priority_scoring import (
    EntityType,
    HardRuleConditionExpr,
    HardRuleConfig,
    PriorityBucket,
    PriorityScoringEngine,
    ScoringContext,
    ScoringDimension,
    ScoringRuleSet,
)


class _DummyConfigService:
    async def get_or_raise(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - not used here
        raise RuntimeError("not used in these unit tests")


def _build_test_ruleset() -> ScoringRuleSet:
    """Construct a minimal in-memory rule set for tests."""

    dims = [
        ScoringDimension(
            name="risk_level",
            weight=0.5,
            source="features.risk_level",
            scale="0-10",
        ),
        ScoringDimension(
            name="info_gap",
            weight=0.5,
            source="features.info_age_hours",
            max=24,
        ),
    ]

    hard_rules = [
        HardRuleConfig(
            id="CRITICAL_RISK_LEVEL",
            **{
                "if": HardRuleConditionExpr(
                    field="features.risk_level",
                    operator=ConditionOperator.GTE,
                    value=9,
                ),
                "set_priority": "critical",
                "min_score": 0.9,
            },
        ),
    ]

    buckets = [
        PriorityBucket(name="critical", min_score=0.8),
        PriorityBucket(name="high", min_score=0.6),
        PriorityBucket(name="medium", min_score=0.3),
        PriorityBucket(name="low", min_score=0.0),
    ]

    return ScoringRuleSet(
        entity_type="test_entity",
        dimensions=dims,
        hard_rules=hard_rules,
        priority_buckets=buckets,
    )


def test_normal_case_uses_weighted_dimensions() -> None:
    """Moderate inputs should map into medium priority via weighted dimensions."""

    engine = PriorityScoringEngine(config_service=_DummyConfigService())
    ruleset = _build_test_ruleset()

    ctx: ScoringContext = {
        "scenario_id": "scn-1",
        "event_id": "evt-1",
        "entity_type": EntityType.RECON_TARGET,
        "entity_id": "risk-1",
        "features": {
            "risk_level": 5.0,  # 中等风险
            "info_age_hours": 12.0,
        },
        "texts": [],
        "tags": {},
    }

    result = engine._score_single(ctx, ruleset, ai_residual_value=0.0)

    # 风险等级 5/10=0.5 * 0.5 权重 = 0.25
    # 信息时效 12/24=0.5 * 0.5 权重 = 0.25
    # 总分 0.5 → medium 桶
    assert 0.49 <= result["score"] <= 0.51
    assert result["priority"] == "medium"


def test_hard_rule_raises_score_and_priority() -> None:
    """High risk level should trigger hard rule and force critical priority."""

    engine = PriorityScoringEngine(config_service=_DummyConfigService())
    ruleset = _build_test_ruleset()

    ctx: ScoringContext = {
        "scenario_id": "scn-1",
        "event_id": "evt-1",
        "entity_type": EntityType.RECON_TARGET,
        "entity_id": "risk-critical",
        "features": {
            "risk_level": 10.0,  # 触发硬规则
            "info_age_hours": 1.0,
        },
        "texts": [],
        "tags": {},
    }

    result = engine._score_single(ctx, ruleset, ai_residual_value=0.0)

    assert "CRITICAL_RISK_LEVEL" in result["hard_rules_triggered"]
    assert result["priority"] == "critical"
    # 硬规则要求最小分数 0.9
    assert result["score"] >= 0.9
