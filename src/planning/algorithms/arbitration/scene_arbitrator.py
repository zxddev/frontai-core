"""
多场景优先级仲裁算法

业务逻辑:
=========
1. 场景类型:
   - 主灾场景: 地震、洪涝等主要灾害
   - 次生场景: 火灾、滑坡、堰塞湖等衍生灾害
   - 并发场景: 同时发生的多个灾害

2. 优先级维度:
   - 生命威胁: 受威胁人数、危险程度
   - 时间紧迫: 救援黄金时间、灾害发展速度
   - 资源匹配: 可用资源与需求的匹配度
   - 成功概率: 救援成功的可能性

3. 仲裁规则:
   - 生命优先: 生命威胁高的场景优先
   - 时效优先: 即将错过黄金时间的优先
   - 效益优先: 救援成功概率高的优先
   - 均衡策略: 综合考虑多维度

4. 资源分配:
   - 预留机制: 为高优先级场景预留资源
   - 动态调整: 根据场景发展实时调整

算法实现:
=========
- 多准则决策分析 (MCDA)
- 层次分析法 (AHP) 权重确定
- TOPSIS综合评分
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
import math

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


@dataclass
class SceneInfo:
    """场景信息"""
    id: str
    name: str
    scene_type: str  # primary/secondary/concurrent
    
    # 评估指标
    affected_population: int
    life_threat_level: float  # 0-1
    golden_time_remaining_min: int
    disaster_spread_rate: float  # 0-1, 扩散速度
    rescue_difficulty: float  # 0-1
    success_probability: float  # 0-1
    
    # 资源需求
    resource_requirements: Dict[str, int]
    
    # 位置
    lat: float = 0
    lng: float = 0


@dataclass
class ScenePriority:
    """场景优先级结果"""
    scene_id: str
    scene_name: str
    priority_score: float
    rank: int
    dimension_scores: Dict[str, float]
    resource_allocation: Dict[str, int]
    rationale: str


class SceneArbitrator(AlgorithmBase):
    """
    多场景优先级仲裁器
    
    使用示例:
    ```python
    arbitrator = SceneArbitrator()
    result = arbitrator.run({
        "scenes": [
            {
                "id": "S1",
                "name": "居民楼坍塌",
                "scene_type": "primary",
                "affected_population": 50,
                "life_threat_level": 0.9,
                "golden_time_remaining_min": 45,
                "disaster_spread_rate": 0.1,
                "rescue_difficulty": 0.7,
                "success_probability": 0.6,
                "resource_requirements": {"rescue_team": 3, "medical_team": 2}
            },
            {
                "id": "S2",
                "name": "化工厂泄漏",
                "scene_type": "secondary",
                "affected_population": 200,
                "life_threat_level": 0.7,
                "golden_time_remaining_min": 120,
                "disaster_spread_rate": 0.8,
                "rescue_difficulty": 0.5,
                "success_probability": 0.8,
                "resource_requirements": {"hazmat_team": 2, "medical_team": 1}
            }
        ],
        "available_resources": {
            "rescue_team": 5,
            "medical_team": 4,
            "hazmat_team": 2
        },
        "weights": {
            "life_threat": 0.35,
            "time_urgency": 0.25,
            "population": 0.20,
            "success_rate": 0.20
        }
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "weights": {
                "life_threat": 0.35,
                "time_urgency": 0.25,
                "population": 0.20,
                "success_rate": 0.20,
            },
            "golden_time_threshold_min": 60,
            "critical_population_threshold": 100,
            "min_resource_ratio": 0.3,  # 最低资源分配比例
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "scenes" not in problem or not problem["scenes"]:
            return False, "缺少 scenes"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行场景仲裁"""
        scenes = self._parse_scenes(problem["scenes"])
        available_resources = problem.get("available_resources", {})
        weights = problem.get("weights", self.params["weights"])
        
        # 1. 计算各维度得分
        dimension_scores = self._compute_dimension_scores(scenes)
        
        # 2. TOPSIS综合评分
        priority_scores = self._topsis_ranking(scenes, dimension_scores, weights)
        
        # 3. 资源分配
        allocations = self._allocate_resources(scenes, priority_scores, available_resources)
        
        # 4. 生成结果
        priorities = []
        for i, (scene_id, score) in enumerate(sorted(priority_scores.items(), 
                                                      key=lambda x: x[1], reverse=True)):
            scene = next(s for s in scenes if s.id == scene_id)
            priorities.append(ScenePriority(
                scene_id=scene_id,
                scene_name=scene.name,
                priority_score=round(score, 4),
                rank=i + 1,
                dimension_scores=dimension_scores[scene_id],
                resource_allocation=allocations.get(scene_id, {}),
                rationale=self._generate_rationale(scene, dimension_scores[scene_id])
            ))
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=[{
                "scene_id": p.scene_id,
                "scene_name": p.scene_name,
                "priority_score": p.priority_score,
                "rank": p.rank,
                "dimension_scores": p.dimension_scores,
                "resource_allocation": p.resource_allocation,
                "rationale": p.rationale,
            } for p in priorities],
            metrics={
                "scene_count": len(scenes),
                "top_priority": priorities[0].scene_id if priorities else None,
            },
            trace={
                "weights": weights,
            },
            time_ms=0
        )
    
    def _parse_scenes(self, data: List[Dict]) -> List[SceneInfo]:
        """解析场景"""
        return [SceneInfo(
            id=d["id"],
            name=d.get("name", ""),
            scene_type=d.get("scene_type", "primary"),
            affected_population=d.get("affected_population", 0),
            life_threat_level=d.get("life_threat_level", 0.5),
            golden_time_remaining_min=d.get("golden_time_remaining_min", 120),
            disaster_spread_rate=d.get("disaster_spread_rate", 0.1),
            rescue_difficulty=d.get("rescue_difficulty", 0.5),
            success_probability=d.get("success_probability", 0.5),
            resource_requirements=d.get("resource_requirements", {}),
            lat=d.get("lat", 0),
            lng=d.get("lng", 0)
        ) for d in data]
    
    def _compute_dimension_scores(self, scenes: List[SceneInfo]) -> Dict[str, Dict[str, float]]:
        """计算各维度标准化得分"""
        scores = {}
        
        # 提取各维度值
        populations = [s.affected_population for s in scenes]
        life_threats = [s.life_threat_level for s in scenes]
        golden_times = [s.golden_time_remaining_min for s in scenes]
        success_rates = [s.success_probability for s in scenes]
        
        # 标准化 (min-max)
        def normalize(values, higher_better=True):
            min_v, max_v = min(values), max(values)
            if max_v == min_v:
                return [0.5] * len(values)
            if higher_better:
                return [(v - min_v) / (max_v - min_v) for v in values]
            else:
                return [(max_v - v) / (max_v - min_v) for v in values]
        
        norm_pop = normalize(populations, higher_better=True)
        norm_threat = normalize(life_threats, higher_better=True)
        norm_time = normalize(golden_times, higher_better=False)  # 时间少更紧急
        norm_success = normalize(success_rates, higher_better=True)
        
        for i, scene in enumerate(scenes):
            scores[scene.id] = {
                "population": norm_pop[i],
                "life_threat": norm_threat[i],
                "time_urgency": norm_time[i],
                "success_rate": norm_success[i],
            }
        
        return scores
    
    def _topsis_ranking(self, scenes: List[SceneInfo],
                        dimension_scores: Dict[str, Dict[str, float]],
                        weights: Dict[str, float]) -> Dict[str, float]:
        """
        TOPSIS综合评分
        
        Technique for Order of Preference by Similarity to Ideal Solution
        """
        n = len(scenes)
        if n == 0:
            return {}
        
        # 加权标准化矩阵
        weighted_matrix = {}
        for scene_id, scores in dimension_scores.items():
            weighted_matrix[scene_id] = {
                dim: scores[dim] * weights.get(dim, 0.25)
                for dim in scores
            }
        
        # 理想解和负理想解
        dims = list(next(iter(weighted_matrix.values())).keys())
        ideal = {dim: max(wm[dim] for wm in weighted_matrix.values()) for dim in dims}
        anti_ideal = {dim: min(wm[dim] for wm in weighted_matrix.values()) for dim in dims}
        
        # 计算到理想解的距离
        def distance(scores, target):
            return math.sqrt(sum((scores[d] - target[d])**2 for d in dims))
        
        final_scores = {}
        for scene_id, scores in weighted_matrix.items():
            d_plus = distance(scores, ideal)
            d_minus = distance(scores, anti_ideal)
            
            if d_plus + d_minus == 0:
                final_scores[scene_id] = 0.5
            else:
                final_scores[scene_id] = d_minus / (d_plus + d_minus)
        
        return final_scores
    
    def _allocate_resources(self, scenes: List[SceneInfo],
                            priority_scores: Dict[str, float],
                            available_resources: Dict[str, int]) -> Dict[str, Dict[str, int]]:
        """按优先级分配资源"""
        allocations = {s.id: {} for s in scenes}
        remaining = dict(available_resources)
        
        # 按优先级排序
        sorted_scenes = sorted(scenes, key=lambda s: priority_scores[s.id], reverse=True)
        
        for scene in sorted_scenes:
            allocation = {}
            for res_type, needed in scene.resource_requirements.items():
                available = remaining.get(res_type, 0)
                allocate = min(needed, available)
                
                if allocate > 0:
                    allocation[res_type] = allocate
                    remaining[res_type] = available - allocate
            
            allocations[scene.id] = allocation
        
        return allocations
    
    def _generate_rationale(self, scene: SceneInfo, 
                            dim_scores: Dict[str, float]) -> str:
        """生成优先级决策说明"""
        reasons = []
        
        if dim_scores.get("life_threat", 0) > 0.7:
            reasons.append(f"生命威胁程度高({scene.life_threat_level:.0%})")
        
        if dim_scores.get("time_urgency", 0) > 0.7:
            reasons.append(f"救援时间紧迫(剩余{scene.golden_time_remaining_min}分钟)")
        
        if dim_scores.get("population", 0) > 0.7:
            reasons.append(f"影响人口众多({scene.affected_population}人)")
        
        if dim_scores.get("success_rate", 0) > 0.7:
            reasons.append(f"救援成功率较高({scene.success_probability:.0%})")
        
        if not reasons:
            reasons.append("综合评估结果")
        
        return "；".join(reasons)
    
    def compute_ahp_weights(self, comparison_matrix: List[List[float]]) -> List[float]:
        """
        使用AHP计算权重
        
        comparison_matrix: 成对比较矩阵
        返回: 各准则的权重
        """
        n = len(comparison_matrix)
        
        # 计算特征向量 (简化: 列归一化后取均值)
        col_sums = [sum(comparison_matrix[i][j] for i in range(n)) for j in range(n)]
        
        normalized = []
        for i in range(n):
            row = []
            for j in range(n):
                row.append(comparison_matrix[i][j] / col_sums[j] if col_sums[j] > 0 else 0)
            normalized.append(row)
        
        weights = [sum(row) / n for row in normalized]
        
        # 归一化
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        
        return weights
