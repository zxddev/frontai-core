# EmergencyAI 前端调用指南

## 1. API 调用

### 1.1 发起分析请求

```http
POST /api/v2/ai/emergency-analyze
Content-Type: application/json

{
  "event_id": "550e8400-e29b-41d4-a716-446655440001",
  "scenario_id": "182c4b66-f368-4763-84a1-84b44c2439d9",
  "disaster_description": "四川省阿坝州茂县发生6.5级地震，震中位于茂县凤仪镇，震源深度20公里。多处房屋倒塌，道路阻断，估计被困群众约50人。",
  "structured_input": {
    "location": {
      "longitude": 103.85,
      "latitude": 31.68
    }
  },
  "constraints": {
    "max_response_time_hours": 2
  }
}
```

**响应** (立即返回):
```json
{
  "success": true,
  "task_id": "emergency-550e8400-e29b-41d4-a716-446655440001",
  "status": "processing",
  "message": "应急AI分析任务已提交，预计完成时间5-15秒"
}
```

### 1.2 轮询获取结果

```http
GET /api/v2/ai/emergency-analyze/{task_id}
```

**轮询策略**: 每3秒查询一次，直到 `status === "completed"` 或 `status === "failed"`

---

## 2. 返回数据结构

### 2.1 完整响应结构

```typescript
interface EmergencyAnalyzeResult {
  success: boolean;
  event_id: string;
  scenario_id: string;
  status: "processing" | "completed" | "failed";
  completed_at: string;
  execution_time_ms: number;
  errors: string[];
  
  // 各阶段结果
  understanding: UnderstandingResult;
  reasoning: ReasoningResult;
  htn_decomposition: HTNResult;
  strategic: StrategicResult;        // 新增：战略层
  matching: MatchingResult;
  optimization: OptimizationResult;
  
  // 最终方案
  recommended_scheme: RecommendedScheme;
  scheme_explanation: string;
}
```

### 2.2 战略层结构 (strategic)

```typescript
interface StrategicResult {
  // 任务域分类
  active_domains: string[];           // ["life_rescue", "engineering", "evacuation"]
  
  // 灾害阶段
  disaster_phase: string;             // "initial" | "golden" | "sustained" | "recovery"
  disaster_phase_name: string;        // "初期响应"
  
  // 优先级排序
  domain_priorities: DomainPriority[];
  
  // 推荐模块
  recommended_modules: RecommendedModule[];
  
  // 运力检查
  transport_plans: TransportPlan[];
  transport_warnings: string[];
  
  // 安全规则
  safety_violations: SafetyViolation[];
  
  // 生成报告
  generated_reports: {
    initial?: string;    // 灾情初报
    update?: string;     // 灾情续报
    daily?: string;      // 救援日报
  };
}

interface DomainPriority {
  domain_id: string;      // "life_rescue"
  name: string;           // "生命救护"
  description: string;
  priority: number;       // 1, 2, 3...
}

interface RecommendedModule {
  module_id: string;              // "ruins_search"
  module_name: string;            // "废墟搜救模块"
  personnel: number;              // 15
  dogs: number;                   // 4
  vehicles: number;               // 3
  match_score: number;            // 0.167
  provided_capabilities: string[];
  equipment_list: Equipment[];
}
```

### 2.3 HTN任务序列 (htn_decomposition)

```typescript
interface HTNResult {
  scene_codes: string[];          // ["S1"]
  task_sequence: TaskNode[];
  parallel_tasks: ParallelGroup[];
}

interface TaskNode {
  task_id: string;        // "EM01"
  task_name: string;      // "无人机广域侦察"
  sequence: number;       // 执行顺序 1, 2, 3...
  depends_on: string[];   // 依赖的任务ID ["EM02"]
  golden_hour: number | null;  // 黄金救援时间(分钟)
  phase: string;          // "search" | "rescue" | "medical"
  is_parallel: boolean;
  parallel_group_id: string | null;
}
```

### 2.4 推荐方案 (recommended_scheme)

```typescript
interface RecommendedScheme {
  scheme_id: string;
  allocations: ResourceAllocation[];
  total_score: number;
  response_time_min: number;
  coverage_rate: number;
  resource_scale: number;
  requires_reinforcement: boolean;
  reinforcement_level: string;      // "市级" | "省级"
  capacity_warning: string;
}

interface ResourceAllocation {
  resource_id: string;
  resource_name: string;            // "茂县消防救援大队"
  resource_type: string;            // "FIRE_RESCUE"
  assigned_capabilities: string[];  // ["STRUCTURAL_RESCUE", "LIFE_DETECTION"]
  match_score: number;
  distance_km: number;
  eta_minutes: number;
  rescue_capacity: number;
}
```

---

## 3. 前端展示建议

### 3.1 方案总览卡片

```
┌─────────────────────────────────────────────────────────┐
│  救援方案总览                            [成功] 52.8秒  │
├─────────────────────────────────────────────────────────┤
│  灾害阶段: 初期响应 (initial)                           │
│  任务域: 生命救护 > 工程抢险 > 群众转移                  │
│  调度队伍: 3支    覆盖率: 100%    预计响应: 219分钟     │
├─────────────────────────────────────────────────────────┤
│  ⚠️ 道路受损，大巴车运输受限                            │
│  ⚠️ 道路受损，公路运输车运输受限                        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 队伍任务分配表

```
┌──────────────────────────────────────────────────────────────────┐
│  队伍任务分配                                                     │
├──────────────────┬────────────┬──────────────────────────────────┤
│  队伍名称         │  到达时间   │  分配任务                        │
├──────────────────┼────────────┼──────────────────────────────────┤
│  茂县消防救援大队  │  1分钟     │  EM01 无人机广域侦察              │
│                  │            │  EM03 建筑倒塌区域识别            │
│                  │            │  EM06 埋压人员生命探测            │
│                  │            │  EM11 废墟挖掘与破拆              │
├──────────────────┼────────────┼──────────────────────────────────┤
│  茂县住建局抢险队  │  1分钟     │  道路抢通（支援）                 │
├──────────────────┼────────────┼──────────────────────────────────┤
│  华西医院医疗队    │  219分钟   │  EM10 被困人员救援               │
│                  │            │  EM14 伤员现场急救               │
│                  │            │  EM15 伤员转运后送               │
└──────────────────┴────────────┴──────────────────────────────────┘
```

### 3.3 任务->队伍映射逻辑 (前端实现)

```typescript
// 能力->任务映射表
const TASK_CAPABILITY_MAP: Record<string, string[]> = {
  'EM01': ['LIFE_DETECTION'],
  'EM03': ['LIFE_DETECTION'],
  'EM06': ['LIFE_DETECTION'],
  'EM10': ['MEDICAL_TRIAGE', 'EMERGENCY_TREATMENT'],
  'EM11': ['STRUCTURAL_RESCUE'],
  'EM14': ['PATIENT_TRANSPORT'],
  'EM15': ['MEDICAL_TRIAGE'],
};

// 生成队伍任务分配
function generateTeamTasks(result: EmergencyAnalyzeResult) {
  const tasks = result.htn_decomposition.task_sequence;
  const allocations = result.recommended_scheme.allocations;
  
  return allocations.map(alloc => {
    const teamCaps = new Set(alloc.assigned_capabilities);
    
    const assignedTasks = tasks.filter(task => {
      const taskCaps = TASK_CAPABILITY_MAP[task.task_id] || [];
      return taskCaps.some(cap => teamCaps.has(cap));
    }).sort((a, b) => a.sequence - b.sequence);
    
    return {
      team_id: alloc.resource_id,
      team_name: alloc.resource_name,
      eta_minutes: alloc.eta_minutes,
      capabilities: alloc.assigned_capabilities,
      tasks: assignedTasks.map(t => ({
        task_id: t.task_id,
        task_name: t.task_name,
        sequence: t.sequence,
        depends_on: t.depends_on,
      })),
    };
  });
}
```

### 3.4 推荐模块展示

```
┌─────────────────────────────────────────────────────────┐
│  推荐救援模块                                            │
├─────────────────────────────────────────────────────────┤
│  📦 废墟搜救模块                        匹配度: 16.7%   │
│     人员: 15人  搜救犬: 4只  车辆: 3辆                   │
│     能力: 生命探测                                       │
│     装备: 蛇眼探测仪×3, 支撑器材×10, 照明设备×6          │
├─────────────────────────────────────────────────────────┤
│  📦 医疗前突模块                        匹配度: 16.7%   │
│     人员: 8人   搜救犬: 0只  车辆: 2辆                   │
│     能力: 医疗分诊                                       │
│     装备: 急救包×20, 担架×10                             │
└─────────────────────────────────────────────────────────┘
```

### 3.5 任务流程图 (可选)

使用 HTN 任务序列的 `depends_on` 字段绘制 DAG 图:

```
EM02 地震监测数据分析
  │
  ▼
EM01 无人机广域侦察
  │
  ├──────────────┐
  ▼              ▼
EM03 区域识别   EM04 灾情评估
  │              │
  ▼              ├──────┐
EM06 生命探测   EM05   EM07
  │              次生    力量
  ▼              研判    调度
EM11 废墟破拆
  │
  ▼
EM10 伤员救治 ──▶ EM14 急救 ──▶ EM15 转运
```

---

## 4. 完整调用示例 (TypeScript/React)

```typescript
import { useState, useEffect } from 'react';

interface AnalyzeRequest {
  event_id: string;
  scenario_id: string;
  disaster_description: string;
  structured_input: {
    location: { longitude: number; latitude: number };
  };
}

export function useEmergencyAnalyze() {
  const [result, setResult] = useState<EmergencyAnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = async (request: AnalyzeRequest) => {
    setLoading(true);
    setError(null);
    
    try {
      // 1. 提交分析任务
      const submitRes = await fetch('/api/v2/ai/emergency-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      const { task_id } = await submitRes.json();
      
      // 2. 轮询获取结果
      let attempts = 0;
      const maxAttempts = 30; // 最多90秒
      
      while (attempts < maxAttempts) {
        await new Promise(r => setTimeout(r, 3000));
        
        const pollRes = await fetch(`/api/v2/ai/emergency-analyze/${task_id}`);
        const data = await pollRes.json();
        
        if (data.status === 'completed') {
          setResult(data);
          setLoading(false);
          return data;
        }
        
        if (data.status === 'failed') {
          throw new Error(data.errors?.join(', ') || '分析失败');
        }
        
        attempts++;
      }
      
      throw new Error('分析超时');
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  };

  return { analyze, result, loading, error };
}

// 使用示例
function EmergencyPanel() {
  const { analyze, result, loading } = useEmergencyAnalyze();
  
  const handleAnalyze = () => {
    analyze({
      event_id: crypto.randomUUID(),
      scenario_id: '182c4b66-f368-4763-84a1-84b44c2439d9',
      disaster_description: '茂县发生6.5级地震...',
      structured_input: {
        location: { longitude: 103.85, latitude: 31.68 }
      }
    });
  };
  
  if (loading) return <div>分析中... (预计45-60秒)</div>;
  
  if (result) {
    const teamTasks = generateTeamTasks(result);
    
    return (
      <div>
        {/* 方案总览 */}
        <OverviewCard 
          phase={result.strategic.disaster_phase_name}
          domains={result.strategic.domain_priorities}
          warnings={result.strategic.transport_warnings}
        />
        
        {/* 队伍任务表 */}
        <TeamTaskTable teams={teamTasks} />
        
        {/* 推荐模块 */}
        <ModuleList modules={result.strategic.recommended_modules} />
        
        {/* 方案说明 */}
        <SchemeExplanation text={result.scheme_explanation} />
      </div>
    );
  }
  
  return <button onClick={handleAnalyze}>开始分析</button>;
}
```

---

## 5. 字段中文映射

```typescript
const PHASE_NAMES: Record<string, string> = {
  'initial': '初期响应',
  'golden': '黄金救援',
  'sustained': '持续救援',
  'recovery': '恢复重建',
};

const DOMAIN_NAMES: Record<string, string> = {
  'life_rescue': '生命救护',
  'engineering': '工程抢险',
  'evacuation': '群众转移',
  'hazmat': '危化处置',
  'support': '综合保障',
};

const CAPABILITY_NAMES: Record<string, string> = {
  'STRUCTURAL_RESCUE': '结构救援',
  'LIFE_DETECTION': '生命探测',
  'MEDICAL_TRIAGE': '医疗分诊',
  'EMERGENCY_TREATMENT': '紧急救治',
  'PATIENT_TRANSPORT': '伤员转运',
  'ROAD_CLEARANCE': '道路抢通',
  'HAZMAT_RESPONSE': '危化处置',
};
```

---

## 6. 注意事项

1. **轮询间隔**: 建议3秒，避免过于频繁
2. **超时处理**: 建议90秒超时，LLM调用可能较慢
3. **错误展示**: 检查 `errors` 数组，可能包含警告信息
4. **增援提示**: 当 `requires_reinforcement=true` 时，显示增援建议
5. **运力警告**: `transport_warnings` 非空时需要醒目提示
