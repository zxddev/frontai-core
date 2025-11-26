"""
基于 pymoo 的多目标优化器

pymoo 是成熟的多目标优化库，提供:
- NSGA-II: 适用于2-3个目标
- NSGA-III: 适用于3个以上目标 (使用参考点关联)
- MOEA/D, RVEA 等其他算法

优势:
- 学术验证，广泛使用
- 完整的参考点关联实现
- 内置可视化
- 支持约束处理
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Callable, Optional
from dataclasses import dataclass
import numpy as np

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


@dataclass
class ParetoSolution:
    """Pareto解"""
    id: str
    variables: List[float]
    objectives: Dict[str, float]


class PymooOptimizer(AlgorithmBase):
    """
    基于 pymoo 的多目标优化器
    
    自动选择算法:
    - 2-3个目标: NSGA-II
    - >3个目标: NSGA-III
    
    使用示例:
    ```python
    from pymoo.core.problem import ElementwiseProblem
    
    # 定义问题
    class EmergencyPlanProblem(ElementwiseProblem):
        def __init__(self):
            super().__init__(
                n_var=10,      # 决策变量数
                n_obj=3,       # 目标数: 时间、成本、覆盖率
                n_constr=2,    # 约束数
                xl=np.zeros(10),
                xu=np.ones(10)
            )
        
        def _evaluate(self, x, out, *args, **kwargs):
            # 目标函数
            out["F"] = [
                self.calc_time(x),
                self.calc_cost(x),
                -self.calc_coverage(x)  # 最大化转最小化
            ]
            # 约束 (<=0 表示满足)
            out["G"] = [
                self.resource_constraint(x),
                self.time_constraint(x)
            ]
    
    # 优化
    optimizer = PymooOptimizer()
    result = optimizer.run({
        "problem": EmergencyPlanProblem(),
        "n_generations": 100,
        "pop_size": 100
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "pop_size": 100,
            "n_generations": 100,
            "algorithm": "auto",  # auto/nsga2/nsga3
            "n_partitions": 12,   # NSGA-III 参考点划分
            "seed": None,
            "verbose": False,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "problem" not in problem and "evaluate_func" not in problem:
            return False, "需要提供 problem (pymoo Problem) 或 evaluate_func"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行优化"""
        try:
            from pymoo.optimize import minimize
            from pymoo.algorithms.moo.nsga2 import NSGA2
            from pymoo.algorithms.moo.nsga3 import NSGA3
            from pymoo.util.ref_dirs import get_reference_directions
        except ImportError:
            return AlgorithmResult(
                status=AlgorithmStatus.ERROR,
                solution=[],
                metrics={},
                trace={"error": "pymoo 未安装，请运行: pip install pymoo"},
                time_ms=0,
                message="pymoo 未安装"
            )
        
        # 获取或创建 pymoo Problem
        pymoo_problem = problem.get("problem")
        if pymoo_problem is None:
            pymoo_problem = self._create_problem_from_func(problem)
        
        n_obj = pymoo_problem.n_obj
        pop_size = problem.get("pop_size", self.params["pop_size"])
        n_gen = problem.get("n_generations", self.params["n_generations"])
        
        # 自动选择算法
        algo_name = problem.get("algorithm", self.params["algorithm"])
        if algo_name == "auto":
            algo_name = "nsga3" if n_obj > 3 else "nsga2"
        
        if algo_name == "nsga3":
            # NSGA-III 需要参考点
            n_partitions = problem.get("n_partitions", self.params["n_partitions"])
            ref_dirs = get_reference_directions("das-dennis", n_obj, n_partitions=n_partitions)
            algorithm = NSGA3(pop_size=pop_size, ref_dirs=ref_dirs)
        else:
            algorithm = NSGA2(pop_size=pop_size)
        
        # 执行优化
        res = minimize(
            pymoo_problem,
            algorithm,
            ("n_gen", n_gen),
            seed=problem.get("seed", self.params["seed"]),
            verbose=problem.get("verbose", self.params["verbose"])
        )
        
        # 解析结果
        objective_names = problem.get("objective_names", [f"f{i}" for i in range(n_obj)])
        solutions = []
        
        if res.F is not None:
            for i, (x, f) in enumerate(zip(res.X, res.F)):
                obj_dict = {name: float(val) for name, val in zip(objective_names, f)}
                solutions.append(ParetoSolution(
                    id=f"SOL-{i+1:03d}",
                    variables=x.tolist() if isinstance(x, np.ndarray) else list(x),
                    objectives=obj_dict
                ))
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=[{
                "id": s.id,
                "variables": s.variables,
                "objectives": s.objectives,
            } for s in solutions],
            metrics={
                "pareto_size": len(solutions),
                "generations": n_gen,
                "algorithm": algo_name,
            },
            trace={
                "n_objectives": n_obj,
                "n_variables": pymoo_problem.n_var,
            },
            time_ms=0
        )
    
    def _create_problem_from_func(self, problem: Dict) -> Any:
        """从评估函数创建 pymoo Problem"""
        from pymoo.core.problem import ElementwiseProblem
        
        evaluate_func = problem["evaluate_func"]
        n_var = problem["n_variables"]
        n_obj = problem["n_objectives"]
        bounds = problem.get("bounds", [(0, 1)] * n_var)
        
        xl = np.array([b[0] for b in bounds])
        xu = np.array([b[1] for b in bounds])
        
        class CustomProblem(ElementwiseProblem):
            def __init__(self):
                super().__init__(n_var=n_var, n_obj=n_obj, xl=xl, xu=xu)
            
            def _evaluate(self, x, out, *args, **kwargs):
                out["F"] = evaluate_func(x)
        
        return CustomProblem()


class EmergencyPlanProblem:
    """
    应急方案优化问题示例
    
    决策变量: 资源分配比例 (0-1)
    目标:
    - 最小化响应时间
    - 最小化总成本  
    - 最大化覆盖率 (转为最小化负值)
    - 最小化风险
    """
    
    @staticmethod
    def create(n_resources: int = 10, n_tasks: int = 5):
        """创建应急方案优化问题"""
        from pymoo.core.problem import ElementwiseProblem
        
        class Problem(ElementwiseProblem):
            def __init__(self):
                # 决策变量: 每个资源分配给每个任务的比例
                n_var = n_resources * n_tasks
                super().__init__(
                    n_var=n_var,
                    n_obj=4,  # 时间、成本、覆盖率、风险
                    n_constr=2,  # 资源容量、时间窗
                    xl=np.zeros(n_var),
                    xu=np.ones(n_var)
                )
                self.n_resources = n_resources
                self.n_tasks = n_tasks
            
            def _evaluate(self, x, out, *args, **kwargs):
                # 重塑为矩阵 [resources x tasks]
                allocation = x.reshape(self.n_resources, self.n_tasks)
                
                # 目标1: 响应时间 (假设与资源分散程度相关)
                time_obj = np.sum(np.var(allocation, axis=0))
                
                # 目标2: 成本 (资源使用量)
                cost_obj = np.sum(allocation)
                
                # 目标3: 覆盖率 (负值，因为要最大化)
                coverage = np.mean(np.max(allocation, axis=0))
                coverage_obj = -coverage
                
                # 目标4: 风险 (资源过度集中)
                risk_obj = np.max(np.sum(allocation, axis=1))
                
                out["F"] = [time_obj, cost_obj, coverage_obj, risk_obj]
                
                # 约束1: 每个资源总分配不超过1
                g1 = np.max(np.sum(allocation, axis=1)) - 1.0
                
                # 约束2: 每个任务至少有一定覆盖
                g2 = 0.1 - np.min(np.sum(allocation, axis=0))
                
                out["G"] = [g1, g2]
        
        return Problem()
