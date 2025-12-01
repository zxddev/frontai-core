"""Hard rules check node for FrontlineRescueAgent.

This node loads HARD_RULES_FRONTLINE_V1 from the DB-backed
config.algorithm_parameters table and applies them to a
global solution summary aggregated from event_allocations.

If any rule with action=="reject" is violated, the state is
marked as failed and an error message is appended.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.agents.frontline_rescue.state import FrontlineRescueState
from src.agents.rules.models import (
    ConditionOperator,
    HardRuleAction,
    HardRuleResult,
    HardRuleSeverity,
)
from src.core.database import AsyncSessionLocal
from src.infra.config.algorithm_config_service import AlgorithmConfigService


logger = logging.getLogger(__name__)


def _get_nested_value(data: Dict[str, Any], field: str) -> Any:
    """Get nested value from dict using dot-separated path."""

    parts = field.split(".")
    value: Any = data
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return value


def _compare(actual: Any, operator: ConditionOperator, expected: Any) -> bool:
    """Compare two values using TRR-style operators.

    This mirrors TRRRuleEngine._compare for basic numeric operators.
    """

    if operator == ConditionOperator.EQ:
        return actual == expected
    if operator == ConditionOperator.NE:
        return actual != expected
    if operator == ConditionOperator.GT:
        return float(actual) > float(expected)
    if operator == ConditionOperator.GTE:
        return float(actual) >= float(expected)
    if operator == ConditionOperator.LT:
        return float(actual) < float(expected)
    if operator == ConditionOperator.LTE:
        return float(actual) <= float(expected)

    # For IN/NOT_IN/CONTAINS/REGEX we do not expect usage in
    # HARD_RULES_FRONTLINE_V1; treat as non-match to be safe.
    logger.warning("Unsupported operator in frontline hard rules: %s", operator)
    return False


async def hard_rules_check_node(state: FrontlineRescueState) -> Dict[str, Any]:
    """Apply HARD_RULES_FRONTLINE_V1 to the aggregated allocation solution.

    Aggregation strategy:
    - solution.max_eta_minutes: max of max_eta_minutes across feasible events
    - solution.coverage_rate: min of coverage_rate across feasible events
    If no event is feasible, fall back to all allocations.
    """

    # 如果前序节点已经失败，直接跳过
    if state.get("status") == "failed":
        return {}

    allocations = state.get("event_allocations") or []
    if not allocations:
        logger.info("[Frontline] No event_allocations, skip hard_rules_check")
        return {
            "hard_rule_results": [],
            "current_phase": "hard_rules_skipped",
        }

    feasible = [a for a in allocations if a.get("is_feasible")]
    base = feasible or allocations

    try:
        max_eta = max(float(a.get("max_eta_minutes") or 0.0) for a in base)
    except ValueError:
        max_eta = 0.0

    try:
        coverage_values = [float(a.get("coverage_rate") or 0.0) for a in base]
        coverage_rate = min(coverage_values) if coverage_values else 0.0
    except ValueError:
        coverage_rate = 0.0

    solution_data: Dict[str, Any] = {
        "solution": {
            "max_eta_minutes": max_eta,
            "coverage_rate": coverage_rate,
        }
    }

    logger.info(
        "[Frontline] Global solution summary for hard-rules: max_eta=%.1f, min_coverage=%.3f",
        max_eta,
        coverage_rate,
    )

    async with AsyncSessionLocal() as session:
        config_service = AlgorithmConfigService(session)
        params = await config_service.get_or_raise(
            category="scoring",
            code="HARD_RULES_FRONTLINE_V1",
        )

    raw_rules = params.get("rules") or []
    results: List[HardRuleResult] = []
    any_reject_violation = False

    for raw in raw_rules:
        rule_id = str(raw.get("id") or raw.get("rule_id") or "HR_FRONTLINE")
        name = str(raw.get("name") or rule_id)
        field = str(raw.get("field") or "")
        if not field:
            logger.warning("[Frontline] Hard rule %s missing field, skip", rule_id)
            continue

        op_str = str(raw.get("operator") or "gt")
        try:
            operator = ConditionOperator(op_str)
        except ValueError:
            logger.warning("[Frontline] Unknown operator %s in rule %s", op_str, rule_id)
            continue

        threshold = raw.get("threshold")
        actual = _get_nested_value(solution_data, field)

        if actual is None:
            passed = False
        else:
            try:
                passed = _compare(actual, operator, threshold)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Frontline] Hard rule %s compare failed: %s", rule_id, exc)
                passed = False

        action = HardRuleAction(str(raw.get("action") or "reject"))
        severity = HardRuleSeverity(str(raw.get("severity") or "high"))
        message = str(raw.get("message") or "Frontline hard rule check failed")

        if not passed and action == HardRuleAction.REJECT:
            any_reject_violation = True

        result = HardRuleResult(
            rule_id=rule_id,
            rule_name=name,
            passed=passed,
            action=action,
            message=message,
            severity=severity,
            checked_value=actual,
            threshold_value=threshold,
        )
        results.append(result)

    update: Dict[str, Any] = {
        "hard_rule_results": [r.model_dump() for r in results],
        "current_phase": "hard_rules_passed" if not any_reject_violation else "hard_rules_rejected",
    }

    if any_reject_violation:
        violations = [
            r.message
            for r in results
            if (not r.passed) and r.action == HardRuleAction.REJECT
        ]
        errors = list(state.get("errors", []))
        if violations:
            errors.append("hard_rules_violation: " + "；".join(violations))
        else:
            errors.append("hard_rules_violation")
        update["errors"] = errors
        update["status"] = "failed"

    return update


__all__ = ["hard_rules_check_node"]
