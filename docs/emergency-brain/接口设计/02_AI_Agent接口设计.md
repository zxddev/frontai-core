# 应急救灾AI大脑 - AI Agent接口设计

> 版本: 1.0  
> 创建时间: 2025-11-25  
> 状态: 设计中

---

## 一、AI Agent模块总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Agent 服务层                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │ EventAnalysis │  │ SchemeGenerate│  │ResourceMatch  │  │TaskDispatch │  │
│  │    Agent      │  │    Agent      │  │    Agent      │  │   Agent     │  │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └──────┬──────┘  │
│          │                  │                  │                 │          │
│          └──────────────────┼──────────────────┼─────────────────┘          │
│                             ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    LangGraph 编排层 (Orchestrator)                   │   │
│  │   scene_decomposition → rule_application → capability_extraction    │   │
│  │          → resource_matching → planning_optimization → evaluation   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                             ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       算法层 (Algorithms)                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │Assessment│ │ Matching │ │ Routing  │ │Arbitration│ │Simulation│   │   │
│  │  │ 灾情评估 │ │ 资源匹配 │ │ 路径规划 │ │ 冲突仲裁 │ │ 仿真评估 │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 核心Agent职责

| Agent | 职责 | 调用算法 |
|-------|------|---------|
| EventAnalysisAgent | 事件分类、严重度评估、影响范围估算、次生灾害预测 | DisasterAssessment, SecondaryHazardPredictor, LossEstimator |
| SchemeGenerationAgent | 需求分析、方案生成、多方案优化 | PymooOptimizer, MCTSPlanner |
| ResourceMatchingAgent | 能力匹配、资源评分、推荐理由生成 | RescueTeamSelector, CapabilityMatcher, SceneArbitrator |
| TaskDispatchAgent | 任务拆解、执行者分配、路径规划 | TaskScheduler, VehicleRoutingPlanner, OffroadEngine |

---

## 二、接口详细设计

### 2.1 事件分析接口 (异步)

#### POST `/api/v2/ai/analyze-event`

**功能**: 异步分析事件，评估灾情等级、影响范围、次生灾害风险，**计算确认评分并决定事件状态流转**

**执行模式**: **异步** - 立即返回task_id，通过WebSocket推送结果或轮询查询

**请求体**:
```json
{
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "disaster_type": "earthquake",
    "location": {
        "longitude": 104.0657,
        "latitude": 30.5728
    },
    "source_system": "110",
    "source_trust_level": 0.95,
    "initial_data": {
        "magnitude": 5.5,
        "depth_km": 10,
        "occurred_at": "2025-11-25T10:30:00Z",
        "estimated_victims": 20,
        "is_urgent": true
    },
    "context": {
        "population_density": 5000,
        "building_types": ["residential", "commercial"],
        "infrastructure": ["hospital", "school"]
    },
    "analysis_options": {
        "include_secondary_hazard": true,
        "include_loss_estimation": true,
        "confidence_threshold": 0.7
    }
}
```

**立即响应体** (异步任务已提交):
```json
{
    "success": true,
    "task_id": "task-550e8400-e29b-41d4-a716-446655440000",
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "message": "分析任务已提交，预计完成时间2秒",
    "created_at": "2025-11-25T10:30:05Z"
}
```

#### GET `/api/v2/ai/analyze-event/{task_id}`

**功能**: 查询异步分析任务状态和结果

**响应体** (任务完成后):
```json
{
    "success": true,
    "task_id": "task-550e8400-e29b-41d4-a716-446655440000",
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    
    "analysis_result": {
        "disaster_level": "III",
        "disaster_level_color": "黄色",
        "response_level": "市级",
        "ai_confidence": 0.85,
        
        "assessment": {
            "intensity": 7.2,
            "affected_radius_km": 15.0,
            "affected_area_km2": 706.86,
            "building_damage_rate": 0.15,
            "estimated_casualties": {
                "deaths": 5,
                "injuries": 50,
                "trapped": 20
            }
        },
        
        "secondary_hazards": [
            {
                "type": "fire",
                "probability": 0.35,
                "risk_level": "medium",
                "predicted_locations": [
                    {"longitude": 104.068, "latitude": 30.575, "risk_score": 0.42}
                ]
            }
        ],
        
        "loss_estimation": {
            "direct_economic_loss_yuan": 50000000,
            "infrastructure_damage": {
                "roads_km": 5.2,
                "bridges": 2,
                "power_lines_km": 8.5
            }
        },
        
        "urgency_score": 0.82,
        "recommended_actions": [
            "立即启动III级应急响应",
            "派遣地震救援队(USAR)",
            "派遣医疗急救队"
        ]
    },
    
    "confirmation_decision": {
        "confirmation_score": 0.88,
        "score_breakdown": {
            "ai_confidence": {"value": 0.85, "weight": 0.6, "contribution": 0.51},
            "rule_match": {"value": 0.90, "weight": 0.3, "contribution": 0.27},
            "source_trust": {"value": 0.95, "weight": 0.1, "contribution": 0.095}
        },
        "matched_auto_confirm_rules": ["AC-003", "AC-004"],
        "recommended_status": "confirmed",
        "auto_confirmed": true,
        "rationale": "来源为110系统(可信度0.95)，标记紧急，且有被困人员(20人)，AI置信度0.85，满足自动确认条件AC-003和AC-004"
    },
    
    "event_status_update": {
        "previous_status": "pending",
        "new_status": "confirmed",
        "auto_confirmed": true,
        "pre_confirmation": null
    },
    
    "trace": {
        "algorithms_used": ["DisasterAssessment", "SecondaryHazardPredictor", "LossEstimator", "ConfirmationScorer"],
        "auto_confirm_rules_checked": ["AC-001", "AC-002", "AC-003", "AC-004"],
        "execution_time_ms": 1560,
        "model_version": "v2.0"
    },
    
    "created_at": "2025-11-25T10:30:05Z",
    "completed_at": "2025-11-25T10:30:07Z"
}
```

**算法调用链**:
```
1. DisasterAssessment.assess_earthquake()
   - 烈度衰减模型: I = 1.5M - 1.5log(R) - 0.003R + 3.0
   - 影响范围估算
   - 建筑损毁率计算
   - 伤亡估算

2. SecondaryHazardPredictor.predict()
   - 火灾概率: P(fire) = 1 - exp(-λ * risk_score)
   - 滑坡预测: 安全系数FS计算
   - 余震预测: Omori法则

3. LossEstimator.estimate()
   - 人员伤亡估算
   - 建筑损毁估算(脆弱性曲线)
   - 基础设施损失

4. ConfirmationScorer.calculate() [新增]
   - 计算确认评分 = AI置信度×0.6 + 规则匹配度×0.3 + 来源可信度×0.1
   - 检查自动确认硬规则(AC-001~AC-004)
   - 决定状态流转: confirmed/pre_confirmed/pending
```

#### 自动确认硬规则 (AC Rules)

| 规则ID | 规则名称 | 触发条件 | 动作 |
|--------|---------|---------|------|
| AC-001 | 多源交叉验证 | 同位置(500m内)30分钟内≥2个不同来源上报 | 自动确认 |
| AC-002 | 传感器+AI双触发 | 来源=传感器告警 且 AI置信度≥0.8 | 自动确认 |
| AC-003 | 官方系统紧急 | 来源∈{110,119,120} 且 is_urgent=true | 自动确认 |
| AC-004 | 明确被困人员 | estimated_victims≥1 且 AI置信度≥0.7 | 自动确认 |

#### 确认评分与状态流转

```
确认评分计算:
confirmation_score = ai_confidence × 0.6 + rule_match × 0.3 + source_trust × 0.1

状态流转规则:
┌─────────────────────────────────────────────────────────────────────────────┐
│ IF 满足任一AC硬规则 (AC-001 ~ AC-004)                                        │
│    → status = 'confirmed', auto_confirmed = true                            │
│    → 自动触发方案生成                                                        │
│    → WebSocket通知: "事件已自动确认，请复核"                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ ELIF confirmation_score >= 0.85                                             │
│    → status = 'confirmed', auto_confirmed = true                            │
│    → 同上                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ ELIF 0.6 <= confirmation_score < 0.85 OR priority ∈ {critical, high}        │
│    → status = 'pre_confirmed'                                               │
│    → 启动30分钟倒计时 (countdown_expires_at)                                │
│    → 启动资源预锁定 (pre_allocated_resources)                               │
│    → 启动方案预生成 (草案状态)                                              │
│    → WebSocket通知: "事件预确认，请30分钟内复核"                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ ELSE (confirmation_score < 0.6)                                             │
│    → status = 'pending'                                                     │
│    → WebSocket通知: "新事件待人工确认"                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### pre_confirmed状态响应示例

当事件进入pre_confirmed状态时，响应包含预确认信息：

```json
{
    "confirmation_decision": {
        "confirmation_score": 0.72,
        "recommended_status": "pre_confirmed",
        "auto_confirmed": false,
        "rationale": "AI置信度0.75，来源可信度0.6(群众上报)，综合评分0.72，建议预确认等待人工复核"
    },
    
    "event_status_update": {
        "previous_status": "pending",
        "new_status": "pre_confirmed",
        "auto_confirmed": false,
        "pre_confirmation": {
            "countdown_expires_at": "2025-11-25T11:00:07Z",
            "countdown_minutes": 30,
            "pre_allocated_resources": [
                {"resource_id": "team-usar-001", "lock_type": "soft", "expires_at": "2025-11-25T11:00:07Z"}
            ],
            "pre_generated_scheme_id": "scheme-draft-001",
            "auto_escalate_if_timeout": true,
            "auto_escalate_condition": "priority = critical"
        }
    }
}
```

---

### 2.2 方案生成接口

#### POST `/api/v2/ai/generate-scheme`

**功能**: 基于事件分析结果，生成救援方案

**请求体**:
```json
{
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "scenario_id": "scenario-uuid",
    "generation_mode": "auto",
    "constraints": {
        "max_response_time_min": 30,
        "max_teams": 10,
        "reserve_ratio": 0.2,
        "priority_zones": ["zone_a", "zone_b"]
    },
    "optimization_objectives": {
        "minimize_response_time": 0.35,
        "maximize_coverage": 0.30,
        "minimize_cost": 0.15,
        "minimize_risk": 0.20
    },
    "options": {
        "generate_alternatives": 3,
        "include_rationale": true
    }
}
```

**响应体**:
```json
{
    "success": true,
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "schemes": [
        {
            "scheme_id": "scheme-001",
            "rank": 1,
            "score": 0.92,
            "name": "快速响应方案",
            
            "objectives_score": {
                "response_time": 0.95,
                "coverage": 0.88,
                "cost": 0.85,
                "risk": 0.90
            },
            
            "tasks": [
                {
                    "task_id": "T001",
                    "name": "废墟搜救",
                    "phase": "immediate",
                    "priority": 1,
                    "required_capabilities": ["废墟搜救", "生命探测"]
                },
                {
                    "task_id": "T002",
                    "name": "伤员救治",
                    "phase": "immediate",
                    "priority": 1,
                    "required_capabilities": ["现场急救", "伤员转运"]
                },
                {
                    "task_id": "T003",
                    "name": "灾情侦察",
                    "phase": "immediate",
                    "priority": 2,
                    "required_capabilities": ["空中侦察", "热成像"]
                }
            ],
            
            "resource_allocations": [
                {
                    "task_id": "T001",
                    "resource_id": "team-usar-001",
                    "resource_name": "地震救援队A组",
                    "resource_type": "team",
                    "role": "主搜救力量",
                    "ai_recommendation": {
                        "score": 92.5,
                        "rank": 1,
                        "rationale": "该队伍具备专业地震搜救资质，拥有生命探测仪和破拆设备，距离事件点2.8km，预计到达时间8分钟，当前处于待命状态。",
                        "score_breakdown": {
                            "capability_match": 0.95,
                            "distance": 0.90,
                            "availability": 1.0,
                            "equipment": 0.88,
                            "history": 0.92
                        }
                    },
                    "alternatives": [
                        {
                            "resource_id": "team-fire-003",
                            "resource_name": "消防救援站-3中队",
                            "score": 87.3
                        }
                    ]
                }
            ],
            
            "groupings": [
                {
                    "grouping_id": "GROUP-EM-001",
                    "pattern": "搜救+医疗",
                    "definition": "1搜救队 + 1医疗队",
                    "members": ["team-usar-001", "team-medical-001"]
                }
            ],
            
            "triggered_rules": [
                {
                    "rule_id": "TRR-EM-001",
                    "rule_name": "地震人员搜救规则",
                    "rationale": "建筑倒塌后72小时是救援黄金期，需立即派遣专业搜救力量"
                }
            ],
            
            "estimated_metrics": {
                "total_response_time_min": 12,
                "coverage_rate": 0.95,
                "estimated_rescued": 18,
                "total_cost_yuan": 150000
            },
            
            "rationale": "该方案优先保障生命救援，在12分钟内可覆盖95%的受灾区域。采用搜救+医疗编组模式，发现即救治。同时部署侦察无人机持续监控灾情变化。"
        }
    ],
    
    "pareto_solutions": [
        {
            "id": "pareto-1",
            "objectives": {
                "response_time": 12,
                "coverage": 0.95,
                "cost": 150000,
                "risk": 0.08
            }
        },
        {
            "id": "pareto-2", 
            "objectives": {
                "response_time": 18,
                "coverage": 0.98,
                "cost": 200000,
                "risk": 0.05
            }
        }
    ],
    
    "trace": {
        "algorithms_used": ["PymooOptimizer", "MCTSPlanner", "RescueTeamSelector"],
        "trr_rules_matched": ["TRR-EM-001", "TRR-EM-006"],
        "hard_rules_checked": ["HR-EM-001", "HR-EM-003"],
        "optimization_generations": 50,
        "execution_time_ms": 892
    },
    
    "created_at": "2025-11-25T10:32:00Z"
}
```

**算法调用链**:
```
1. apply_trr_rules() - 触发规则匹配
   - 匹配场景触发条件
   - 推导任务需求

2. RescueTeamSelector.select()
   - 灾情特征提取(向量化)
   - 能力需求推断(规则引擎)
   - 队伍-需求匹配评分

3. CapabilityMatcher.match()
   - CSP约束满足求解(OR-Tools)
   - 能力覆盖、距离、容量约束

4. PymooOptimizer.optimize()
   - NSGA-II/III多目标优化
   - Pareto最优解集

5. filter_by_hard_rules() - 硬规则过滤
   - 安全红线检查
   - 时效性检查
   - 资源可用性检查

6. score_candidates() - 软评分排序
   - TOPSIS多准则决策
```

---

### 2.3 资源匹配接口

#### POST `/api/v2/ai/match-resources`

**功能**: 为指定任务匹配最优资源，生成详细推荐理由

**请求体**:
```json
{
    "scenario_id": "scenario-uuid",
    "task": {
        "task_id": "T001",
        "name": "废墟搜救",
        "location": {
            "longitude": 104.0657,
            "latitude": 30.5728
        },
        "required_capabilities": ["废墟搜救", "生命探测", "重型破拆"],
        "urgency": "critical",
        "estimated_duration_min": 120
    },
    "available_resources": ["team-usar-001", "team-usar-002", "team-fire-003"],
    "constraints": {
        "max_distance_km": 20,
        "max_response_time_min": 30,
        "exclude_resources": []
    },
    "options": {
        "top_n": 3,
        "include_alternatives": true,
        "generate_rationale": true
    }
}
```

**响应体**:
```json
{
    "success": true,
    "task_id": "T001",
    "recommendations": [
        {
            "rank": 1,
            "resource_id": "team-usar-001",
            "resource_name": "蓝天救援队-A组",
            "resource_type": "team",
            "total_score": 92.5,
            
            "score_breakdown": {
                "capability_match": {
                    "score": 0.95,
                    "weight": 0.35,
                    "detail": "具备全部3项所需能力: 废墟搜救(专业级)、生命探测(2台设备)、重型破拆(液压设备)"
                },
                "distance": {
                    "score": 0.90,
                    "weight": 0.25,
                    "detail": "距离事件点2.8km，预计到达时间8分钟，是最近的专业搜救队伍"
                },
                "availability": {
                    "score": 1.0,
                    "weight": 0.20,
                    "detail": "当前状态: 待命，无正在执行的任务，可立即出动"
                },
                "equipment": {
                    "score": 0.88,
                    "weight": 0.10,
                    "detail": "配备生命探测仪2台、液压破拆设备1套、热成像无人机1架"
                },
                "history": {
                    "score": 0.92,
                    "weight": 0.10,
                    "detail": "近30天完成任务8次，成功率100%，平均响应时间6分钟"
                }
            },
            
            "rationale": "蓝天救援队-A组是执行本次废墟搜救任务的最优选择。该队伍具备专业地震搜救资质，拥有完整的生命探测和破拆设备，距离事件点仅2.8km，可在8分钟内到达现场。当前处于待命状态，无其他任务冲突。该队伍近期任务完成率100%，表现优异。",
            
            "estimated_arrival_min": 8,
            "team_size": 12,
            "equipment_list": ["生命探测仪x2", "液压破拆设备x1", "热成像无人机x1", "急救包x4"]
        },
        {
            "rank": 2,
            "resource_id": "team-fire-003",
            "resource_name": "消防救援站-3中队",
            "resource_type": "team",
            "total_score": 87.3,
            "rationale": "备选方案，距离稍远(4.5km)但具备重型破拆能力...",
            "estimated_arrival_min": 12
        }
    ],
    
    "conflict_check": {
        "has_conflict": false,
        "conflicts": []
    },
    
    "trace": {
        "algorithms_used": ["RescueTeamSelector", "CapabilityMatcher"],
        "candidates_evaluated": 3,
        "execution_time_ms": 45
    }
}
```

**评分算法详解**:
```python
# 资源匹配评分模型 - 动态权重版

def get_weights(disaster_type: str) -> dict:
    """根据灾害类型动态选择权重"""
    scenario_weights = {
        # 地震/建筑倒塌: 时间就是生命
        "earthquake": {"distance": 0.40, "capability": 0.30, "availability": 0.15, "equipment": 0.10, "history": 0.05},
        "building_collapse": {"distance": 0.40, "capability": 0.30, "availability": 0.15, "equipment": 0.10, "history": 0.05},
        # 化工泄漏: 专业能力最重要
        "hazmat_leak": {"capability": 0.50, "equipment": 0.20, "distance": 0.15, "availability": 0.10, "history": 0.05},
        # 火灾: 响应速度和专业能力并重
        "fire": {"distance": 0.35, "capability": 0.35, "availability": 0.15, "equipment": 0.10, "history": 0.05},
        # 洪水/滑坡: 装备适配性重要
        "flood": {"equipment": 0.30, "capability": 0.30, "distance": 0.25, "availability": 0.10, "history": 0.05},
        "landslide": {"equipment": 0.30, "capability": 0.30, "distance": 0.25, "availability": 0.10, "history": 0.05},
    }
    # 默认权重
    default = {"capability": 0.35, "distance": 0.25, "availability": 0.20, "equipment": 0.10, "history": 0.10}
    return scenario_weights.get(disaster_type, default)

def calculate_score(resource: dict, task: dict, disaster_type: str) -> float:
    """计算资源匹配评分"""
    weights = get_weights(disaster_type)
    
    # 可用性门槛检查 - availability=0直接排除
    if resource["availability"] < 0.1:
        return 0  # 直接排除，不参与评分
    
    scores = {
        "capability": calc_capability_score(resource, task),  # 能力覆盖度 × 专业等级系数
        "distance": calc_distance_score(resource, task),      # 1 - min(distance_km/max_distance, 1)
        "availability": resource["availability"],              # 状态系数 × 任务冲突系数
        "equipment": calc_equipment_score(resource, task),    # 装备覆盖度 × 装备状态系数
        "history": calc_history_score(resource),              # 成功率 × 响应时间系数
    }
    
    total = sum(weights[k] * scores[k] for k in weights)
    return round(total * 100, 2)  # 转换为百分制
```

---

### 2.4 任务调度接口

#### POST `/api/v2/ai/dispatch-tasks`

**功能**: 将方案拆解为具体任务，分配执行者，规划路径

**请求体**:
```json
{
    "scheme_id": "scheme-001",
    "scenario_id": "scenario-uuid",
    "dispatch_options": {
        "strategy": "priority_first",
        "enable_path_planning": true,
        "enable_time_optimization": true
    },
    "routing_config": {
        "prefer_road": true,
        "avoid_damaged_roads": true,
        "vehicle_capability": {
            "slope_deg": 25,
            "wading_depth_m": 0.5
        }
    }
}
```

**响应体**:
```json
{
    "success": true,
    "scheme_id": "scheme-001",
    "dispatch_result": {
        "tasks": [
            {
                "task_id": "task-001",
                "name": "A区废墟搜救",
                "status": "assigned",
                "priority": 1,
                "phase": "immediate",
                
                "assignment": {
                    "assignee_id": "team-usar-001",
                    "assignee_name": "蓝天救援队-A组",
                    "assignee_type": "team",
                    "assigned_at": "2025-11-25T10:35:00Z"
                },
                
                "route": {
                    "mode": "road",
                    "distance_m": 2850,
                    "estimated_time_min": 8,
                    "waypoints": [
                        {"lng": 104.060, "lat": 30.570, "name": "起点-救援站"},
                        {"lng": 104.063, "lat": 30.572, "name": "途经点1"},
                        {"lng": 104.066, "lat": 30.573, "name": "目标点-A区"}
                    ],
                    "road_conditions": [
                        {"segment": "0-1", "status": "normal", "speed_limit": 60},
                        {"segment": "1-2", "status": "damaged", "speed_limit": 30}
                    ],
                    "alternative_route": {
                        "mode": "offroad",
                        "distance_m": 3200,
                        "estimated_time_min": 12,
                        "reason": "如主路不通，可走越野路线"
                    }
                },
                
                "time_window": {
                    "earliest_start": "2025-11-25T10:35:00Z",
                    "latest_start": "2025-11-25T10:45:00Z",
                    "deadline": "2025-11-25T14:35:00Z"
                },
                
                "dependencies": [],
                
                "subtasks": [
                    {
                        "subtask_id": "task-001-1",
                        "name": "生命探测",
                        "sequence": 1,
                        "estimated_duration_min": 30
                    },
                    {
                        "subtask_id": "task-001-2", 
                        "name": "破拆救援",
                        "sequence": 2,
                        "estimated_duration_min": 60,
                        "depends_on": "task-001-1"
                    }
                ]
            }
        ],
        
        "schedule": {
            "gantt_data": [
                {
                    "task_id": "task-001",
                    "resource": "team-usar-001",
                    "start_min": 0,
                    "end_min": 98,
                    "type": "execution"
                }
            ],
            "makespan_min": 240,
            "resource_utilization": 0.85,
            "critical_path": ["task-001", "task-003"]
        },
        
        "vrp_solution": {
            "vehicles": [
                {
                    "vehicle_id": "v-001",
                    "depot": "救援站A",
                    "route": ["task-001", "task-004"],
                    "total_distance_km": 8.5,
                    "total_time_min": 45
                }
            ],
            "total_distance_km": 25.3,
            "objective_value": 0.92
        }
    },
    
    "trace": {
        "algorithms_used": ["TaskScheduler", "VehicleRoutingPlanner", "RoadNetworkEngine", "OffroadEngine"],
        "scheduling_strategy": "critical_path",
        "vrp_iterations": 100,
        "execution_time_ms": 234
    }
}
```

**路径规划算法**:
```
1. RoadNetworkEngine.plan_segment()
   - 基于OSM路网的A*搜索
   - 道路等级权重: 高速1.0 → 小路2.5
   - 障碍物(损毁道路)过滤

2. 如路网不通，切换:
   OffroadEngine.plan()
   - 基于DEM的越野A*
   - 坡度约束、水域规避
   - 车辆能力约束

3. VehicleRoutingPlanner.solve()
   - OR-Tools VRP求解
   - CVRP容量约束
   - VRPTW时间窗约束
```

---

### 2.5 AI问答接口

#### POST `/api/v2/ai/chat`

**功能**: 通用AI助手，支持应急知识问答、态势查询、指令交互

**请求体**:
```json
{
    "scenario_id": "scenario-uuid",
    "session_id": "session-uuid",
    "message": "当前灾情最新情况是什么？",
    "context": {
        "user_role": "综合指挥席",
        "current_view": "灾情态势图"
    },
    "options": {
        "stream": false,
        "include_sources": true
    }
}
```

**响应体**:
```json
{
    "success": true,
    "session_id": "session-uuid",
    "response": {
        "message": "当前想定中共有3个活跃事件:\n\n1. **A区建筑倒塌** (危急)\n   - 位置: 成都市武侯区xxx路\n   - 被困人员: 约20人\n   - 已派遣: 地震救援队A组、医疗急救队\n   - 状态: 搜救进行中\n\n2. **B区火灾** (紧急)\n   - 位置: 成都市武侯区xxx街\n   - 状态: 已控制，无人员伤亡\n\n3. **C区道路中断** (一般)\n   - 已派遣工程抢修队\n   - 预计2小时恢复通行",
        
        "intent": "query_situation",
        "entities": [
            {"type": "event", "ids": ["event-001", "event-002", "event-003"]}
        ],
        
        "suggested_actions": [
            {
                "action": "view_event_detail",
                "label": "查看A区事件详情",
                "params": {"event_id": "event-001"}
            },
            {
                "action": "generate_report",
                "label": "生成态势报告",
                "params": {}
            }
        ],
        
        "sources": [
            {"type": "database", "table": "events_v2"},
            {"type": "realtime", "channel": "telemetry"}
        ]
    },
    
    "created_at": "2025-11-25T10:40:00Z"
}
```

---

### 2.6 AI决策日志查询接口

#### GET `/api/v2/ai/decision-logs`

**功能**: 查询AI决策历史记录，支持追溯和审计

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| scenario_id | string | 是 | 想定ID |
| event_id | string | 否 | 事件ID |
| scheme_id | string | 否 | 方案ID |
| agent_type | string | 否 | Agent类型 |
| start_time | string | 否 | 开始时间 |
| end_time | string | 否 | 结束时间 |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

**响应体**:
```json
{
    "success": true,
    "total": 15,
    "page": 1,
    "page_size": 10,
    "logs": [
        {
            "log_id": "log-001",
            "agent_type": "EventAnalysisAgent",
            "action": "analyze_event",
            "event_id": "event-001",
            
            "input_summary": {
                "disaster_type": "earthquake",
                "magnitude": 5.5,
                "location": "成都市武侯区"
            },
            
            "output_summary": {
                "disaster_level": "III",
                "confidence": 0.85,
                "recommended_actions": 4
            },
            
            "algorithms_used": ["DisasterAssessment", "SecondaryHazardPredictor"],
            "rules_matched": ["TRR-EM-001"],
            "execution_time_ms": 156,
            
            "decision_rationale": "基于震级5.5、震源深度10km，判定为III级地震。结合人口密度和建筑类型，预估被困人员约20人，建议立即启动搜救行动。",
            
            "created_at": "2025-11-25T10:31:00Z",
            "created_by": "system"
        }
    ]
}
```

---

## 三、Agent实现架构

### 3.1 Agent基类

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    data: Dict[str, Any]
    trace: Dict[str, Any]
    rationale: str
    execution_time_ms: float

class BaseAgent(ABC):
    """Agent基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.algorithms = {}  # 注入的算法实例
        
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """执行Agent逻辑"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, str]:
        """验证输入"""
        pass
    
    def log_decision(self, input_data: Dict, result: AgentResult):
        """记录决策日志到 ai_decision_logs_v2"""
        pass
```

### 3.2 EventAnalysisAgent实现

```python
class EventAnalysisAgent(BaseAgent):
    """事件分析Agent - 包含确认评分和状态流转逻辑"""
    
    # 自动确认硬规则
    AUTO_CONFIRM_RULES = {
        "AC-001": "多源交叉验证",
        "AC-002": "传感器+AI双触发",
        "AC-003": "官方系统紧急",
        "AC-004": "明确被困人员"
    }
    
    def __init__(self, config):
        super().__init__(config)
        self.disaster_assessment = DisasterAssessment()
        self.secondary_predictor = SecondaryHazardPredictor()
        self.loss_estimator = LossEstimator()
        self.confirmation_scorer = ConfirmationScorer()  # 新增
    
    async def execute(self, input_data: Dict) -> AgentResult:
        event = input_data["event"]
        options = input_data.get("options", {})
        
        # 1. 灾情评估
        assessment = self.disaster_assessment.run({
            "type": event["disaster_type"],
            "magnitude": event.get("magnitude"),
            "location": event["location"],
            "context": input_data.get("context", {})
        })
        
        # 2. 次生灾害预测(可选)
        secondary_hazards = []
        if options.get("include_secondary_hazard", True):
            prediction = self.secondary_predictor.run({
                "primary_disaster": assessment.solution,
                "terrain": input_data.get("terrain"),
                "weather": input_data.get("weather")
            })
            secondary_hazards = prediction.solution
        
        # 3. 损失估算(可选)
        loss = None
        if options.get("include_loss_estimation", True):
            loss_result = self.loss_estimator.run({
                "assessment": assessment.solution,
                "infrastructure": input_data.get("infrastructure")
            })
            loss = loss_result.solution
        
        # 4. 生成推荐行动
        recommended_actions = self._generate_recommendations(
            assessment.solution, secondary_hazards
        )
        
        # 5. 计算确认评分和状态流转 [新增]
        confirmation_decision = await self._calculate_confirmation(
            event=event,
            ai_confidence=assessment.solution.get("confidence", 0.5),
            source_trust=input_data.get("source_trust_level", 0.5)
        )
        
        # 6. 执行状态流转 [新增]
        status_update = await self._update_event_status(
            event_id=event["event_id"],
            confirmation_decision=confirmation_decision
        )
        
        # 7. 构建返回结果
        result = AgentResult(
            success=True,
            data={
                "disaster_level": assessment.solution["level"],
                "assessment": assessment.solution,
                "secondary_hazards": secondary_hazards,
                "loss_estimation": loss,
                "recommended_actions": recommended_actions,
                "confirmation_decision": confirmation_decision,  # 新增
                "event_status_update": status_update  # 新增
            },
            trace={
                "algorithms_used": ["DisasterAssessment", "SecondaryHazardPredictor", 
                                   "LossEstimator", "ConfirmationScorer"],
                "auto_confirm_rules_checked": list(self.AUTO_CONFIRM_RULES.keys()),
                "execution_time_ms": assessment.time_ms
            },
            rationale=self._generate_rationale(assessment.solution),
            execution_time_ms=assessment.time_ms
        )
        
        # 8. 记录决策日志
        self.log_decision(input_data, result)
        
        return result
    
    async def _calculate_confirmation(
        self, event: Dict, ai_confidence: float, source_trust: float
    ) -> Dict:
        """计算确认评分和推荐状态"""
        
        # 检查自动确认硬规则
        matched_rules = []
        
        # AC-001: 多源交叉验证
        if await self._check_multi_source(event):
            matched_rules.append("AC-001")
        
        # AC-002: 传感器+AI双触发
        if event.get("source_type") == "sensor" and ai_confidence >= 0.8:
            matched_rules.append("AC-002")
        
        # AC-003: 官方系统紧急
        if event.get("source_system") in ["110", "119", "120"] and event.get("is_urgent"):
            matched_rules.append("AC-003")
        
        # AC-004: 明确被困人员
        if event.get("estimated_victims", 0) >= 1 and ai_confidence >= 0.7:
            matched_rules.append("AC-004")
        
        # 计算综合评分
        rule_match_score = 1.0 if matched_rules else 0.5
        confirmation_score = (
            ai_confidence * 0.6 + 
            rule_match_score * 0.3 + 
            source_trust * 0.1
        )
        
        # 决定推荐状态
        if matched_rules or confirmation_score >= 0.85:
            recommended_status = "confirmed"
            auto_confirmed = True
        elif confirmation_score >= 0.6 or event.get("priority") in ["critical", "high"]:
            recommended_status = "pre_confirmed"
            auto_confirmed = False
        else:
            recommended_status = "pending"
            auto_confirmed = False
        
        return {
            "confirmation_score": round(confirmation_score, 3),
            "score_breakdown": {
                "ai_confidence": {"value": ai_confidence, "weight": 0.6},
                "rule_match": {"value": rule_match_score, "weight": 0.3},
                "source_trust": {"value": source_trust, "weight": 0.1}
            },
            "matched_auto_confirm_rules": matched_rules,
            "recommended_status": recommended_status,
            "auto_confirmed": auto_confirmed,
            "rationale": self._generate_confirmation_rationale(
                matched_rules, confirmation_score, recommended_status
            )
        }
```

### 3.3 LangGraph编排流程

```python
from langgraph.graph import StateGraph, START, END

class EmergencyPlanningGraph:
    """应急规划LangGraph流程"""
    
    def build(self) -> StateGraph:
        graph = StateGraph(PlanningState)
        
        # 注册节点
        graph.add_node("event_analysis", self._event_analysis_node)
        graph.add_node("rule_application", self._rule_application_node)
        graph.add_node("scheme_generation", self._scheme_generation_node)
        graph.add_node("resource_matching", self._resource_matching_node)
        graph.add_node("task_dispatch", self._task_dispatch_node)
        graph.add_node("evaluation", self._evaluation_node)
        
        # 定义流程
        graph.add_edge(START, "event_analysis")
        graph.add_edge("event_analysis", "rule_application")
        graph.add_edge("rule_application", "scheme_generation")
        graph.add_edge("scheme_generation", "resource_matching")
        graph.add_edge("resource_matching", "task_dispatch")
        graph.add_edge("task_dispatch", "evaluation")
        graph.add_edge("evaluation", END)
        
        return graph
```

---

## 四、算法模块映射

| API接口 | Agent | 调用算法 | 算法文件 |
|--------|-------|---------|---------|
| analyze-event | EventAnalysisAgent | DisasterAssessment | assessment/disaster_assessment.py |
| | | SecondaryHazardPredictor | assessment/secondary_hazard.py |
| | | LossEstimator | assessment/loss_estimation.py |
| generate-scheme | SchemeGenerationAgent | PymooOptimizer | optimization/pymoo_optimizer.py |
| | | MCTSPlanner | optimization/mcts_planner.py |
| | | SceneArbitrator | arbitration/scene_arbitrator.py |
| match-resources | ResourceMatchingAgent | RescueTeamSelector | matching/rescue_team_selector.py |
| | | CapabilityMatcher | matching/capability_matcher.py |
| | | ConflictResolver | arbitration/conflict_resolver.py |
| dispatch-tasks | TaskDispatchAgent | TaskScheduler | scheduling/task_scheduler.py |
| | | VehicleRoutingPlanner | routing/vehicle_routing.py |
| | | RoadNetworkEngine | routing/road_engine.py |
| | | OffroadEngine | routing/offroad_engine.py |

---

## 五、规则引擎集成

### 5.1 触发规则(TRR)应用

```python
def apply_trr_rules(event_data: Dict, rules: List[TRRRule]) -> List[str]:
    """
    匹配TRR触发规则，返回触发的规则ID列表
    
    规则示例:
    TRR-EM-001: 地震人员搜救规则
    IF: 灾害类型=地震 AND 建筑倒塌=是 AND 被困人员>=1
    THEN: 派遣地震救援队(USAR) + 医疗急救队(MEDICAL)
    """
    matched = []
    for rule in rules:
        if evaluate_conditions(rule.conditions, event_data):
            matched.append(rule.id)
    return matched
```

### 5.2 硬约束规则过滤

```python
def filter_by_hard_rules(candidates: List[Dict], hard_rules: List[HardRule]) -> List[Dict]:
    """
    硬约束一票否决过滤
    
    硬约束示例:
    HR-EM-001: 人员安全红线 - 伤亡概率>10%则否决
    HR-EM-003: 救援时效性 - 执行时间>黄金救援时间则否决
    """
    kept = []
    for candidate in candidates:
        passed = True
        for rule in hard_rules:
            if not evaluate_hard_rule(rule, candidate):
                passed = False
                break
        if passed:
            kept.append(candidate)
    return kept
```

---

## 六、配置文件

### 6.1 AI Agent配置

```yaml
# config/ai_agents.yaml
agents:
  event_analysis:
    enabled: true
    confidence_threshold: 0.7
    auto_confirm_threshold: 0.85
    algorithms:
      - DisasterAssessment
      - SecondaryHazardPredictor
      - LossEstimator
      
  scheme_generation:
    enabled: true
    max_alternatives: 3
    optimization:
      population_size: 50
      generations: 100
    algorithms:
      - PymooOptimizer
      - MCTSPlanner
      
  resource_matching:
    enabled: true
    # 默认权重 (通用场景)
    default_weights:
      capability_match: 0.35
      distance: 0.25
      availability: 0.20
      equipment: 0.10
      history: 0.10
    
    # 场景差异化权重 - 根据灾害类型动态调整
    scenario_weights:
      # 地震/建筑倒塌: 时间就是生命，距离权重最高
      earthquake:
        distance: 0.40
        capability_match: 0.30
        availability: 0.15
        equipment: 0.10
        history: 0.05
      building_collapse:
        distance: 0.40
        capability_match: 0.30
        availability: 0.15
        equipment: 0.10
        history: 0.05
      
      # 化工泄漏: 专业能力最重要
      hazmat_leak:
        capability_match: 0.50
        equipment: 0.20
        distance: 0.15
        availability: 0.10
        history: 0.05
      
      # 火灾: 响应速度和专业能力并重
      fire:
        distance: 0.35
        capability_match: 0.35
        availability: 0.15
        equipment: 0.10
        history: 0.05
      
      # 洪水/滑坡: 装备适配性重要(需要冲锋舟/挖掘机等)
      flood:
        equipment: 0.30
        capability_match: 0.30
        distance: 0.25
        availability: 0.10
        history: 0.05
      landslide:
        equipment: 0.30
        capability_match: 0.30
        distance: 0.25
        availability: 0.10
        history: 0.05
    
    # 可用性门槛 - availability=0直接排除，不参与加权
    availability_threshold: 0.1
    
    algorithms:
      - RescueTeamSelector
      - CapabilityMatcher
      
  task_dispatch:
    enabled: true
    routing:
      prefer_road: true
      offroad_fallback: true
    algorithms:
      - TaskScheduler
      - VehicleRoutingPlanner
      - RoadNetworkEngine
      - OffroadEngine
```

### 6.2 决策权重配置

```yaml
# config/decision_weights.yaml
decision_weights:
  scheme_evaluation:
    life_safety: 0.40
    time_efficiency: 0.25
    resource_cost: 0.15
    success_rate: 0.15
    secondary_risk: 0.05
    
  scene_priority:
    life_threat: 0.35
    time_urgency: 0.25
    affected_people: 0.20
    success_prob: 0.20
```

---

## 七、错误处理

### 7.1 错误码定义

| 错误码 | HTTP状态 | 说明 |
|-------|---------|------|
| AI_ANALYSIS_FAILED | 500 | AI分析失败 |
| INSUFFICIENT_DATA | 400 | 输入数据不足 |
| NO_FEASIBLE_SOLUTION | 422 | 无可行方案 |
| ALGORITHM_TIMEOUT | 504 | 算法执行超时 |
| RESOURCE_CONFLICT | 409 | 资源冲突 |
| RULE_VIOLATION | 422 | 违反硬约束规则 |

### 7.2 错误响应格式

```json
{
    "success": false,
    "error_code": "NO_FEASIBLE_SOLUTION",
    "message": "当前约束条件下无可行救援方案",
    "details": {
        "violated_constraints": ["max_response_time_min"],
        "suggestion": "建议放宽响应时间约束或增加可用资源"
    },
    "trace": {
        "algorithms_tried": ["PymooOptimizer"],
        "iterations": 100
    },
    "request_id": "req-uuid"
}
```

---

## 八、性能要求

| 接口 | 超时时间 | 预期响应时间 |
|-----|---------|-------------|
| analyze-event | 30s | <2s |
| generate-scheme | 60s | <5s |
| match-resources | 10s | <500ms |
| dispatch-tasks | 30s | <3s |
| chat | 30s | <2s |

---

## 九、数据库表

| 表名 | 说明 |
|------|------|
| ai_decision_logs_v2 | AI决策日志 |
| events_v2 | 事件表(关联分析结果) |
| schemes_v2 | 方案表(关联生成结果) |
| scheme_resource_allocations_v2 | 资源分配(含AI推荐理由) |
| tasks_v2 | 任务表(关联调度结果) |
