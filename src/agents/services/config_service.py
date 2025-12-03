"""
配置服务：从数据库获取配置数据

提供硬规则、评估权重、枚举映射等配置的统一访问接口。
"""
from __future__ import annotations

import logging
import operator
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import text

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类型定义
# ============================================================================

@dataclass
class HardRuleConfig:
    """硬规则配置"""
    rule_id: str
    name: str
    field: str
    operator: str
    threshold: float
    message: str
    is_active: bool = True
    
    def check(self, scheme: Dict[str, Any]) -> bool:
        """执行规则检查"""
        value = scheme.get(self.field, 0)
        ops: Dict[str, Callable[[float, float], bool]] = {
            '<=': operator.le,
            '>=': operator.ge,
            '<': operator.lt,
            '>': operator.gt,
            '==': operator.eq,
        }
        op_func = ops.get(self.operator, operator.le)
        return op_func(float(value), self.threshold)


@dataclass
class EvaluationWeights:
    """5维评估权重"""
    disaster_type: str
    success_rate: float
    response_time: float
    coverage_rate: float
    risk: float
    redundancy: float
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典格式"""
        return {
            'success_rate': self.success_rate,
            'response_time': self.response_time,
            'coverage_rate': self.coverage_rate,
            'risk': self.risk,
            'redundancy': self.redundancy,
        }


@dataclass
class EnumMapping:
    """枚举映射"""
    category: str
    code: str
    display_name: Optional[str]
    score: Optional[float]
    sort_order: int = 0


# ============================================================================
# 配置服务
# ============================================================================

class ConfigService:
    """配置服务：统一管理数据库配置数据的访问"""
    
    @staticmethod
    async def get_hard_rules() -> List[HardRuleConfig]:
        """
        从PostgreSQL获取硬规则配置
        
        Returns:
            硬规则配置列表
            
        Raises:
            RuntimeError: 数据库查询失败
        """
        from src.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text('''
                SELECT rule_id, name, field, operator, threshold, message, is_active
                FROM config.hard_rules
                WHERE is_active = TRUE
                ORDER BY rule_id
            '''))
            rows = result.fetchall()
            
            if not rows:
                raise RuntimeError("config.hard_rules表无数据，请先执行v21_config_tables.sql")
            
            rules: List[HardRuleConfig] = []
            for row in rows:
                rules.append(HardRuleConfig(
                    rule_id=row[0],
                    name=row[1],
                    field=row[2],
                    operator=row[3],
                    threshold=float(row[4]),
                    message=row[5],
                    is_active=row[6],
                ))
            
            logger.debug(f"从数据库加载{len(rules)}条硬规则")
            return rules
    
    @staticmethod
    async def get_evaluation_weights(disaster_type: str) -> EvaluationWeights:
        """
        从PostgreSQL获取评估权重配置
        
        Args:
            disaster_type: 灾害类型（earthquake, fire, flood, hazmat, default）
            
        Returns:
            权重配置
            
        Raises:
            RuntimeError: 数据库查询失败或配置不存在
        """
        from src.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            # 先尝试精确匹配，再回退到default
            result = await session.execute(text('''
                SELECT disaster_type, success_rate, response_time, coverage_rate, risk, redundancy
                FROM config.evaluation_weights
                WHERE disaster_type = :dtype OR disaster_type = 'default'
                ORDER BY CASE WHEN disaster_type = :dtype THEN 0 ELSE 1 END
                LIMIT 1
            '''), {'dtype': disaster_type})
            row = result.fetchone()
            
            if not row:
                raise RuntimeError(f"config.evaluation_weights表无数据，请先执行v21_config_tables.sql")
            
            weights = EvaluationWeights(
                disaster_type=row[0],
                success_rate=float(row[1]),
                response_time=float(row[2]),
                coverage_rate=float(row[3]),
                risk=float(row[4]),
                redundancy=float(row[5]),
            )
            
            logger.debug(f"获取权重配置: {disaster_type} -> {weights.disaster_type}")
            return weights
    
    @staticmethod
    async def get_enum_mappings(category: str) -> Dict[str, EnumMapping]:
        """
        从PostgreSQL获取枚举映射配置
        
        Args:
            category: 分类（severity, priority）
            
        Returns:
            code到EnumMapping的映射字典
            
        Raises:
            RuntimeError: 数据库查询失败
        """
        from src.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text('''
                SELECT category, code, display_name, score, sort_order
                FROM config.enum_mappings
                WHERE category = :cat
                ORDER BY sort_order
            '''), {'cat': category})
            rows = result.fetchall()
            
            if not rows:
                raise RuntimeError(f"config.enum_mappings表无{category}分类数据")
            
            mappings: Dict[str, EnumMapping] = {}
            for row in rows:
                em = EnumMapping(
                    category=row[0],
                    code=row[1],
                    display_name=row[2],
                    score=float(row[3]) if row[3] is not None else None,
                    sort_order=row[4],
                )
                mappings[em.code] = em
            
            logger.debug(f"获取枚举映射: {category} -> {len(mappings)}项")
            return mappings
    
    @staticmethod
    async def get_severity_display_map() -> Dict[str, str]:
        """获取严重程度code→中文名映射"""
        mappings = await ConfigService.get_enum_mappings('severity')
        return {code: em.display_name or code for code, em in mappings.items()}
    
    @staticmethod
    async def get_priority_display_map() -> Dict[str, str]:
        """获取优先级code→中文名映射"""
        mappings = await ConfigService.get_enum_mappings('priority')
        return {code: em.display_name or code for code, em in mappings.items()}
    
    @staticmethod
    async def get_severity_score_map() -> Dict[str, float]:
        """获取严重程度code→评分映射"""
        mappings = await ConfigService.get_enum_mappings('severity')
        return {code: em.score or 0.5 for code, em in mappings.items()}
    
    @staticmethod
    def get_task_type_mapping() -> Dict[str, str]:
        """
        从Neo4j获取任务别名→ID映射
        
        构建从任务名称/别名到任务ID的映射，用于方案解析。
        
        Returns:
            别名→任务ID的映射字典
            
        Raises:
            RuntimeError: Neo4j查询失败
        """
        from src.agents.emergency_ai.tools.kg_tools import _get_neo4j_driver
        
        driver = _get_neo4j_driver()
        
        with driver.session() as session:
            result = session.run('''
                MATCH (m:MetaTask)
                RETURN m.id AS task_id, m.name AS name, m.aliases AS aliases
            ''')
            
            mapping: Dict[str, str] = {}
            for record in result:
                task_id: str = record['task_id']
                name: str = record['name']
                aliases: Optional[List[str]] = record['aliases']
                
                # 主名称映射
                mapping[name] = task_id
                
                # 别名映射
                if aliases:
                    for alias in aliases:
                        mapping[alias] = task_id
            
            if not mapping:
                raise RuntimeError("Neo4j中无MetaTask数据")
            
            logger.debug(f"从Neo4j加载任务映射: {len(mapping)}项")
            return mapping


# ============================================================================
# 同步版本（用于非异步上下文）
# ============================================================================

class ConfigServiceSync:
    """配置服务同步版本"""
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_hard_rules() -> List[HardRuleConfig]:
        """同步获取硬规则（带缓存）"""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            ConfigService.get_hard_rules()
        )
    
    @staticmethod
    def get_evaluation_weights(disaster_type: str) -> EvaluationWeights:
        """同步获取权重配置"""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            ConfigService.get_evaluation_weights(disaster_type)
        )
    
    @staticmethod
    @lru_cache(maxsize=10)
    def get_enum_mappings(category: str) -> Dict[str, EnumMapping]:
        """同步获取枚举映射（带缓存）"""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            ConfigService.get_enum_mappings(category)
        )
