"""
蒙特卡洛树搜索 (MCTS) 任务规划器

业务逻辑:
=========
1. 任务序列优化:
   - 给定一组任务，找最优执行顺序
   - 考虑任务依赖、资源约束

2. 状态空间:
   - 节点: 已完成的任务集合
   - 动作: 选择下一个任务

3. 评估函数:
   - 模拟到终态的累积收益
   - 收益 = 完成任务数 - 时间惩罚 - 风险惩罚

算法实现:
=========
MCTS四阶段:
1. Selection: UCB1选择最优子节点
2. Expansion: 扩展新节点
3. Simulation: 随机模拟到终态
4. Backpropagation: 回传更新统计
"""
from __future__ import annotations

import random
import math
import logging
from typing import Any, Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


@dataclass
class TaskState:
    """任务状态"""
    task_id: str
    duration: int
    reward: float
    predecessors: List[str] = field(default_factory=list)
    risk: float = 0.0


@dataclass
class MCTSNode:
    """MCTS节点"""
    state: Set[str]  # 已完成任务集合
    parent: Optional['MCTSNode'] = None
    action: Optional[str] = None  # 导致此状态的任务
    children: Dict[str, 'MCTSNode'] = field(default_factory=dict)
    visits: int = 0
    total_reward: float = 0.0
    
    @property
    def avg_reward(self) -> float:
        return self.total_reward / self.visits if self.visits > 0 else 0.0
    
    def ucb1(self, exploration: float = 1.414) -> float:
        """UCB1值"""
        if self.visits == 0:
            return float('inf')
        if self.parent is None or self.parent.visits == 0:
            return self.avg_reward
        
        exploitation = self.avg_reward
        exploration_term = exploration * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration_term


class MCTSPlanner(AlgorithmBase):
    """
    MCTS任务规划器
    
    使用示例:
    ```python
    planner = MCTSPlanner()
    result = planner.run({
        "tasks": [
            {"id": "T1", "duration": 30, "reward": 10, "predecessors": [], "risk": 0.1},
            {"id": "T2", "duration": 45, "reward": 15, "predecessors": ["T1"], "risk": 0.2},
            {"id": "T3", "duration": 20, "reward": 8, "predecessors": [], "risk": 0.05},
        ],
        "time_budget": 120,
        "n_iterations": 1000
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "n_iterations": 1000,
            "exploration_constant": 1.414,
            "simulation_depth": 50,
            "risk_penalty": 10,
            "time_penalty": 0.1,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "tasks" not in problem or not problem["tasks"]:
            return False, "缺少 tasks"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行MCTS搜索"""
        tasks = self._parse_tasks(problem["tasks"])
        time_budget = problem.get("time_budget", float('inf'))
        n_iterations = problem.get("n_iterations", self.params["n_iterations"])
        
        # 创建根节点
        root = MCTSNode(state=set())
        
        # MCTS主循环
        for _ in range(n_iterations):
            # 1. Selection
            node = self._select(root, tasks, time_budget)
            
            # 2. Expansion
            if not self._is_terminal(node, tasks, time_budget):
                node = self._expand(node, tasks, time_budget)
            
            # 3. Simulation
            reward = self._simulate(node, tasks, time_budget)
            
            # 4. Backpropagation
            self._backpropagate(node, reward)
        
        # 提取最优路径
        best_sequence = self._extract_best_sequence(root, tasks, time_budget)
        
        # 计算统计
        total_reward = sum(tasks[t].reward for t in best_sequence)
        total_duration = sum(tasks[t].duration for t in best_sequence)
        total_risk = sum(tasks[t].risk for t in best_sequence)
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution={
                "task_sequence": best_sequence,
                "total_reward": total_reward,
                "total_duration": total_duration,
                "avg_risk": total_risk / len(best_sequence) if best_sequence else 0,
            },
            metrics={
                "sequence_length": len(best_sequence),
                "total_tasks": len(tasks),
                "iterations": n_iterations,
                "tree_nodes": self._count_nodes(root),
            },
            trace={
                "root_visits": root.visits,
                "root_avg_reward": root.avg_reward,
            },
            time_ms=0
        )
    
    def _parse_tasks(self, data: List[Dict]) -> Dict[str, TaskState]:
        """解析任务"""
        return {
            d["id"]: TaskState(
                task_id=d["id"],
                duration=d.get("duration", 0),
                reward=d.get("reward", 1),
                predecessors=d.get("predecessors", []),
                risk=d.get("risk", 0)
            )
            for d in data
        }
    
    def _get_available_actions(self, state: Set[str], tasks: Dict[str, TaskState],
                               time_budget: float, current_time: float = 0) -> List[str]:
        """获取可执行的任务"""
        available = []
        for task_id, task in tasks.items():
            if task_id in state:
                continue
            
            # 检查前置任务
            if not all(p in state for p in task.predecessors):
                continue
            
            # 检查时间预算
            if current_time + task.duration > time_budget:
                continue
            
            available.append(task_id)
        
        return available
    
    def _select(self, node: MCTSNode, tasks: Dict[str, TaskState],
                time_budget: float) -> MCTSNode:
        """Selection阶段: UCB1选择"""
        current_time = sum(tasks[t].duration for t in node.state)
        
        while node.children:
            # 检查是否有未探索的动作
            available = self._get_available_actions(node.state, tasks, time_budget, current_time)
            unexplored = [a for a in available if a not in node.children]
            
            if unexplored:
                return node  # 需要扩展
            
            if not available:
                return node  # 终态
            
            # UCB1选择
            best_child = max(node.children.values(), key=lambda c: c.ucb1(self.params["exploration_constant"]))
            node = best_child
            current_time = sum(tasks[t].duration for t in node.state)
        
        return node
    
    def _expand(self, node: MCTSNode, tasks: Dict[str, TaskState],
                time_budget: float) -> MCTSNode:
        """Expansion阶段: 扩展新节点"""
        current_time = sum(tasks[t].duration for t in node.state)
        available = self._get_available_actions(node.state, tasks, time_budget, current_time)
        unexplored = [a for a in available if a not in node.children]
        
        if not unexplored:
            return node
        
        # 随机选择一个未探索的动作
        action = random.choice(unexplored)
        new_state = node.state | {action}
        
        child = MCTSNode(
            state=new_state,
            parent=node,
            action=action
        )
        node.children[action] = child
        
        return child
    
    def _simulate(self, node: MCTSNode, tasks: Dict[str, TaskState],
                  time_budget: float) -> float:
        """Simulation阶段: 随机模拟"""
        state = set(node.state)
        current_time = sum(tasks[t].duration for t in state)
        total_reward = sum(tasks[t].reward for t in state)
        total_risk = sum(tasks[t].risk for t in state)
        
        depth = 0
        max_depth = self.params["simulation_depth"]
        
        while depth < max_depth:
            available = self._get_available_actions(state, tasks, time_budget, current_time)
            
            if not available:
                break
            
            # 随机选择
            action = random.choice(available)
            task = tasks[action]
            
            state.add(action)
            current_time += task.duration
            total_reward += task.reward
            total_risk += task.risk
            depth += 1
        
        # 计算最终收益
        risk_penalty = total_risk * self.params["risk_penalty"]
        time_penalty = max(0, current_time - time_budget) * self.params["time_penalty"]
        
        return total_reward - risk_penalty - time_penalty
    
    def _backpropagate(self, node: MCTSNode, reward: float):
        """Backpropagation阶段: 回传更新"""
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent
    
    def _is_terminal(self, node: MCTSNode, tasks: Dict[str, TaskState],
                     time_budget: float) -> bool:
        """判断是否终态"""
        current_time = sum(tasks[t].duration for t in node.state)
        available = self._get_available_actions(node.state, tasks, time_budget, current_time)
        return len(available) == 0
    
    def _extract_best_sequence(self, root: MCTSNode, tasks: Dict[str, TaskState],
                               time_budget: float) -> List[str]:
        """提取最优任务序列"""
        sequence = []
        node = root
        
        while node.children:
            # 选择访问次数最多的子节点
            best_child = max(node.children.values(), key=lambda c: c.visits)
            sequence.append(best_child.action)
            node = best_child
        
        return sequence
    
    def _count_nodes(self, node: MCTSNode) -> int:
        """统计树节点数"""
        count = 1
        for child in node.children.values():
            count += self._count_nodes(child)
        return count
