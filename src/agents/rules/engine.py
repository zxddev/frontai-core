"""
TRR规则引擎

提供规则匹配和硬规则检查功能
参考军事版Rete算法设计，简化为条件匹配引擎
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .models import (
    TRRRule,
    MatchedRule,
    HardRule,
    HardRuleResult,
    Condition,
    ConditionOperator,
    ConditionLogic,
    HardRuleAction,
)
from .loader import RuleLoader

logger = logging.getLogger(__name__)


class TRRRuleEngine:
    """
    TRR触发规则引擎
    
    基于YAML规则库进行条件匹配，输出触发的规则列表
    
    使用示例:
    ```python
    engine = TRRRuleEngine()
    context = {
        "disaster_type": "earthquake",
        "has_trapped": True,
        "magnitude": 6.0,
    }
    matched = engine.evaluate(context)
    for rule in matched:
        print(f"{rule.rule_id}: {rule.actions.task_types}")
    ```
    """
    
    def __init__(
        self,
        trr_rules_path: Optional[str] = None,
        hard_rules_path: Optional[str] = None,
    ) -> None:
        """
        初始化规则引擎
        
        Args:
            trr_rules_path: TRR规则文件路径
            hard_rules_path: 硬规则文件路径
        """
        self._trr_rules: List[TRRRule] = []
        self._hard_rules: List[HardRule] = []
        self._trr_rules_path = trr_rules_path
        self._hard_rules_path = hard_rules_path
        self._loaded = False
    
    def _ensure_loaded(self) -> None:
        """确保规则已加载"""
        if not self._loaded:
            self._trr_rules = RuleLoader.load_trr_rules(self._trr_rules_path)
            self._hard_rules = RuleLoader.load_hard_rules(self._hard_rules_path)
            self._loaded = True
            logger.info(
                f"规则引擎初始化完成: TRR规则{len(self._trr_rules)}条, "
                f"硬规则{len(self._hard_rules)}条"
            )
    
    def evaluate(self, context: Dict[str, Any]) -> List[MatchedRule]:
        """
        评估上下文，返回匹配的TRR规则
        
        Args:
            context: 事件上下文，包含disaster_type, has_trapped等字段
            
        Returns:
            按权重降序排列的匹配规则列表
        """
        self._ensure_loaded()
        
        matched: List[MatchedRule] = []
        
        logger.info(f"开始规则匹配，上下文字段: {list(context.keys())}")
        
        for rule in self._trr_rules:
            is_match, matched_conditions = self._check_trigger(rule, context)
            
            if is_match:
                matched_rule = MatchedRule(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    actions=rule.actions,
                    priority=rule.priority,
                    weight=rule.weight,
                    matched_conditions=matched_conditions,
                )
                matched.append(matched_rule)
                logger.info(f"规则匹配: {rule.id} - {rule.name}")
        
        # 按权重降序排列
        matched.sort(key=lambda r: r.weight, reverse=True)
        
        logger.info(f"规则匹配完成: 共匹配{len(matched)}条规则")
        return matched
    
    def _check_trigger(
        self, rule: TRRRule, context: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        检查规则触发条件
        
        Returns:
            (是否触发, 匹配的条件描述列表)
        """
        trigger = rule.trigger
        results: List[bool] = []
        matched_conditions: List[str] = []
        
        for condition in trigger.conditions:
            is_match = self._check_condition(condition, context)
            results.append(is_match)
            
            if is_match:
                desc = f"{condition.field} {condition.operator.value} {condition.value}"
                matched_conditions.append(desc)
        
        # 根据逻辑组合结果
        if trigger.logic == ConditionLogic.AND:
            return all(results), matched_conditions
        else:  # OR
            return any(results), matched_conditions
    
    def _check_condition(
        self, condition: Condition, context: Dict[str, Any]
    ) -> bool:
        """检查单个条件"""
        field = condition.field
        operator = condition.operator
        expected = condition.value
        
        # 获取实际值，支持嵌套字段（如location.lat）
        actual = self._get_nested_value(context, field)
        
        if actual is None:
            # 字段不存在，条件不满足
            return False
        
        return self._compare(actual, operator, expected)
    
    def _get_nested_value(self, data: Dict[str, Any], field: str) -> Any:
        """获取嵌套字段值，支持点号分隔"""
        parts = field.split(".")
        value = data
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _compare(
        self, actual: Any, operator: ConditionOperator, expected: Any
    ) -> bool:
        """执行比较操作"""
        try:
            if operator == ConditionOperator.EQ:
                return actual == expected
            
            elif operator == ConditionOperator.NE:
                return actual != expected
            
            elif operator == ConditionOperator.GT:
                return float(actual) > float(expected)
            
            elif operator == ConditionOperator.GTE:
                return float(actual) >= float(expected)
            
            elif operator == ConditionOperator.LT:
                return float(actual) < float(expected)
            
            elif operator == ConditionOperator.LTE:
                return float(actual) <= float(expected)
            
            elif operator == ConditionOperator.IN:
                return actual in expected
            
            elif operator == ConditionOperator.NOT_IN:
                return actual not in expected
            
            elif operator == ConditionOperator.CONTAINS:
                if isinstance(actual, str):
                    return expected in actual
                elif isinstance(actual, (list, tuple)):
                    return expected in actual
                return False
            
            elif operator == ConditionOperator.REGEX:
                if isinstance(actual, str) and isinstance(expected, str):
                    return bool(re.match(expected, actual))
                return False
            
            else:
                logger.warning(f"未知操作符: {operator}")
                return False
                
        except (TypeError, ValueError) as e:
            logger.warning(f"比较失败: {actual} {operator} {expected} - {e}")
            return False
    
    def check_hard_rules(
        self, scheme_data: Dict[str, Any]
    ) -> List[HardRuleResult]:
        """
        检查硬约束规则
        
        Args:
            scheme_data: 方案数据，包含各项指标
            
        Returns:
            所有硬规则的检查结果列表
        """
        self._ensure_loaded()
        
        results: List[HardRuleResult] = []
        
        logger.info(f"开始硬规则检查，方案字段: {list(scheme_data.keys())}")
        
        for rule in self._hard_rules:
            result = self._check_hard_rule(rule, scheme_data)
            results.append(result)
            
            if not result.passed:
                log_fn = logger.warning if result.action == HardRuleAction.WARN else logger.error
                log_fn(f"硬规则未通过: {rule.id} - {result.message}")
        
        passed_count = sum(1 for r in results if r.passed)
        reject_count = sum(
            1 for r in results 
            if not r.passed and r.action == HardRuleAction.REJECT
        )
        warn_count = sum(
            1 for r in results 
            if not r.passed and r.action == HardRuleAction.WARN
        )
        
        logger.info(
            f"硬规则检查完成: 通过{passed_count}, 否决{reject_count}, 警告{warn_count}"
        )
        
        return results
    
    def _check_hard_rule(
        self, rule: HardRule, data: Dict[str, Any]
    ) -> HardRuleResult:
        """检查单条硬规则"""
        # 检查前置条件
        if rule.condition is not None:
            condition_met = self._compare(
                self._get_nested_value(data, rule.condition.field),
                rule.condition.operator,
                rule.condition.value,
            )
            if not condition_met:
                # 前置条件不满足，规则不适用，直接通过
                return HardRuleResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    passed=True,
                    action=rule.action,
                    message=f"前置条件不满足，规则不适用",
                    severity=rule.severity,
                )
        
        # 获取检查值
        check = rule.check
        actual = self._get_nested_value(data, check.field)
        
        # 获取阈值（支持动态阈值）
        if check.threshold_field:
            threshold = self._get_nested_value(data, check.threshold_field)
        else:
            threshold = check.threshold
        
        # 如果字段不存在，根据规则类型处理
        if actual is None:
            return HardRuleResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,  # 字段不存在，跳过检查
                action=rule.action,
                message=f"字段{check.field}不存在，跳过检查",
                severity=rule.severity,
            )
        
        # 执行比较
        # 注意：硬规则的check定义的是"违规条件"，满足条件说明违规
        violated = self._compare(actual, check.operator, threshold)
        passed = not violated
        
        # 格式化消息
        message = rule.message.format(
            value=actual,
            threshold=threshold,
        ) if not passed else f"规则检查通过"
        
        return HardRuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            action=rule.action,
            message=message,
            severity=rule.severity,
            checked_value=actual,
            threshold_value=threshold,
        )
    
    def get_rejected_rules(
        self, results: List[HardRuleResult]
    ) -> List[HardRuleResult]:
        """筛选出否决方案的规则"""
        return [
            r for r in results 
            if not r.passed and r.action == HardRuleAction.REJECT
        ]
    
    def get_warning_rules(
        self, results: List[HardRuleResult]
    ) -> List[HardRuleResult]:
        """筛选出警告的规则"""
        return [
            r for r in results 
            if not r.passed and r.action == HardRuleAction.WARN
        ]
    
    def is_scheme_feasible(self, results: List[HardRuleResult]) -> bool:
        """判断方案是否可行（无否决规则触发）"""
        return len(self.get_rejected_rules(results)) == 0
    
    @property
    def trr_rules_count(self) -> int:
        """TRR规则数量"""
        self._ensure_loaded()
        return len(self._trr_rules)
    
    @property
    def hard_rules_count(self) -> int:
        """硬规则数量"""
        self._ensure_loaded()
        return len(self._hard_rules)
