"""
端到端规划流程测试。
模拟完整的场景规划：
1. 意图 -> 场景 (S1)
2. 场景 -> 任务 (MT01...)
3. 任务 -> 能力 (S1-M1...)
4. 能力 -> 资源 (J-20...)
5. 评分

注意：本测试依赖外部 `planning` 库（AFSIM 风格规划引擎），
在当前工程未集成该库时会整体跳过，仅作为集成示例保留。
"""
import json
import logging
import os
import importlib.util
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


try:
    _planning_spec = importlib.util.find_spec("planning.agent")
except ModuleNotFoundError:
    _planning_spec = None

if _planning_spec is None:
    pytest.skip(
        "external 'planning.agent' package not available; skipping planning integration test",
        allow_module_level=True,
    )

from planning.agent import build_agent
from planning.graph import PlanningGraphBuilder, run_planning
from planning.config_loader import ConfigLoader
from planning.state import PlanningState
from infra.db.postgres_dao import PostgresDao
from planning.afsim_types import validate_afsim_payload

# 设置日志
logging.basicConfig(level=logging.INFO)

class MockNeo4j:
    def read(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # Mock rules query
        if "HAS_RULE" in cypher:
            return [{"id": "R-001", "name": "反隐身空战"}]
        return []

class MockRag:
    def similarity_search(self, query: str) -> List[Any]:
        # Return S1 scene
        meta = {"scene_id": "S1"}
        return [("content", 0.9, meta)]

class MockDao(PostgresDao):
    def __init__(self):
        pass # skip db connect
        
    def fetch_tasks(self, scene_id: str) -> List[Dict[str, Any]]:
        return [
            {"id": "MT01", "name": "Task1", "phase": "detect", "required_capabilities": ["S1-M1"]},
            {"id": "MT02", "name": "Task2", "phase": "engage", "required_capabilities": ["S1-M22"]}
        ]
        
    def fetch_resources(self, scene_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "resource_id": "J-20_01", 
                "type": "J-20_LIKE",
                "capabilities": ["S1-M1"],
                "risk": 0.1,
                "status": "ready"
            },
            {
                "resource_id": "UAV_01",
                "type": "UAV_F_8",
                "capabilities": ["S1-M22"],
                "risk": 0.2,
                "status": "ready"
            }
        ]
        
    def fetch_rules(self, scene_id: str) -> List[Dict[str, Any]]:
        return [
            {"id": "R-001", "name": "Rule1", "priority": 100}
        ]

def test_planning_flow():
    """测试完整的规划图流程。"""
    # 1. Setup
    config = ConfigLoader().load()
    rag = MockRag()
    kg = MockNeo4j()
    dao = MockDao()
    settings = MagicMock()
    afsim_payload = validate_afsim_payload(
        {
            "air_units": [
                {
                    "unit_id": "BLUE-AIR-001",
                    "type": "F-15EX",
                    "subtype": "fighter",
                    "formation": "4-ship",
                    "position": "121.0,31.0",
                    "altitude_m": 10000,
                    "heading_deg": 90,
                    "speed_kmh": 900,
                    "radar_status": "scan",
                    "datalink_status": "on",
                    "rcs_m2": 3.0,
                    "threat_level": "high",
                    "confidence": 0.95
                }
            ],
            "sea_units": [],
            "ground_units": [],
            "environment": {"weather": "clear", "em_env": "normal"}
        }
    )

    # 2. Run Planning
    result = run_planning(
        intent="打击敌方隐身战机",
        afsim_payload=afsim_payload,
        config=config,
        rag=rag,
        kg=kg,
        dao=dao,
        settings=settings
    )
    
    # 3. Assertions
    assert result["scene"] == "S1"
    assert "MT01" in result["tasks"]
    assert "S1-M1" in result["capabilities"] 
    assert "S1-M22" in result["capabilities"]
    
    # Check resource allocation (CSP / Optimization)
    # S1-M1 -> J-20_01, S1-M22 -> UAV_01
    allocation = result["resource_allocation"]
    # Optimization might return a list of IDs if using fallback or values if using pareto
    # AdvancedOptimizer returns list of resource IDs in "allocation" (values of dict)
    # graph.py extracts values: final_allocation = list(best_sol["allocation"].values())
    
    assert len(allocation) > 0
    
    # Check pareto solutions
    assert "pareto_solutions" in result
    # Note: optimization might fail if population size is small or random seed, but with valid resources it should produce something
    # If it fails, it falls back to simple allocation, so pareto_solutions might be empty or we check if score exists
    
    if result["pareto_solutions"]:
        print(f"Pareto Solutions Found: {len(result['pareto_solutions'])}")
        first_sol = result["pareto_solutions"][0]
        print(f"First Solution Metrics: {first_sol['metrics']}")
    
    # Check rules
    assert "R-001" in result["rules"]
    
    # Check score
    assert result["score"] > 0.0
    
    print("\nPlan Result Summary:")
    print(f"Scene: {result['scene']}")
    print(f"Tasks: {len(result['tasks'])}")
    print(f"Resources: {len(result['resource_allocation'])}")
    print(f"Score: {result['score']}")

if __name__ == "__main__":
    # Allow running directly without pytest
    test_planning_flow()
