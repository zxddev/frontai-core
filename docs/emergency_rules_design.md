# 应急救灾协同决策系统 - 规则设计文档

> 版本: v1.0  
> 最后更新: 2025-11-25  
> 状态: **设计中**

---

## 一、规则体系总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           规则层 (Rule Layer)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  灾害分类   │  │  力量派遣   │  │  疏散安置   │  │  资源约束   │     │
│  │  Classification│ Dispatch    │  │  Evacuation │  │  Constraints │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │              │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐     │
│  │ 灾害类型    │  │ 队伍选择    │  │ 安全地点    │  │ 硬约束      │     │
│  │ 灾害等级    │  │ 无人设备    │  │ 疏散路线    │  │ 软约束      │     │
│  │ 次生灾害    │  │ 编组规则    │  │ 人群管理    │  │ 优先级权重  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │  触发规则   │  │  仲裁规则   │  │  否决规则   │                       │
│  │  TRR Rules  │  │  Arbitration │  │  Hard Rules │                       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                       │
│         │                 │                 │                                │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐                       │
│  │ IF-THEN触发 │  │ 场景优先级  │  │ 一票否决    │                       │
│  │ 条件匹配    │  │ 冲突消解    │  │ 安全红线    │                       │
│  │ 动作生成    │  │ TOPSIS仲裁 │  │ 资源底线    │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **生命优先**: 人员安全是第一优先级，所有规则以此为基准
2. **可解释性**: 每条规则必须有明确的触发条件和执行理由
3. **层次化**: 硬约束 > 软约束 > 优化偏好
4. **动态调整**: 支持根据灾情发展实时调整规则参数

---

## 二、灾害类型与等级分类

### 2.1 灾害类型定义

| 类型代码 | 灾害类型 | 子类型 | 典型场景 |
|----------|----------|--------|----------|
| EQ | 地震 | 主震、余震 | 建筑倒塌、人员被埋 |
| FL | 洪涝 | 暴雨内涝、江河洪水、山洪 | 城市积水、人员被困 |
| FI | 火灾 | 建筑火灾、森林火灾、化工火灾 | 人员疏散、灭火救援 |
| HM | 危化品 | 泄漏、爆炸、中毒 | 有毒气体扩散、污染区域 |
| LS | 地质灾害 | 滑坡、泥石流、崩塌 | 道路中断、村庄掩埋 |
| TY | 台风 | 强风、暴雨、风暴潮 | 建筑损坏、人员转移 |
| EP | 公共卫生 | 传染病、中毒事件 | 隔离转运、医疗救治 |

### 2.2 灾害等级划分

```yaml
# 灾害响应等级定义 (参照国家标准)
disaster_levels:
  I:   # 特别重大
    color: "红色"
    response_level: "国家级"
    criteria:
      casualties: ">= 30人死亡 或 >= 100人重伤"
      affected_population: ">= 10万人"
      direct_loss: ">= 1亿元"
      secondary_hazard: "可能引发特别严重次生灾害"
    
  II:  # 重大
    color: "橙色"
    response_level: "省级"
    criteria:
      casualties: ">= 10人死亡 或 >= 50人重伤"
      affected_population: ">= 5万人"
      direct_loss: ">= 5000万元"
      secondary_hazard: "可能引发严重次生灾害"
    
  III: # 较大
    color: "黄色"
    response_level: "市级"
    criteria:
      casualties: ">= 3人死亡 或 >= 10人重伤"
      affected_population: ">= 1万人"
      direct_loss: ">= 1000万元"
      secondary_hazard: "可能引发一般次生灾害"
    
  IV:  # 一般
    color: "蓝色"
    response_level: "区县级"
    criteria:
      casualties: "< 3人死亡"
      affected_population: "< 1万人"
      direct_loss: "< 1000万元"
      secondary_hazard: "次生灾害风险较低"
```

### 2.3 各类灾害等级判定细则

#### 地震等级判定

| 等级 | 震级(M) | 烈度(I) | 人口密集区 | 建筑脆弱性 |
|------|---------|---------|------------|------------|
| I级  | M >= 7.0 | I >= 9 | 是 | 高 |
| II级 | 6.0 <= M < 7.0 | 7 <= I < 9 | 是 | 中-高 |
| III级 | 5.0 <= M < 6.0 | 6 <= I < 7 | 是/否 | 任意 |
| IV级 | 4.0 <= M < 5.0 | I < 6 | 否 | 低 |

#### 洪涝等级判定

| 等级 | 积水深度 | 影响面积 | 受困人数 | 交通中断 |
|------|----------|----------|----------|----------|
| I级  | >= 2.0m | >= 50km² | >= 1000人 | 主干道全部 |
| II级 | 1.0-2.0m | 20-50km² | 500-1000人 | 主干道部分 |
| III级 | 0.5-1.0m | 5-20km² | 100-500人 | 次干道 |
| IV级 | < 0.5m | < 5km² | < 100人 | 支路 |

#### 危化品泄漏等级判定

| 等级 | 泄漏量 | 毒性等级 | 影响半径 | 风向人口 |
|------|--------|----------|----------|----------|
| I级  | >= 10吨 | 剧毒 | >= 5km | >= 10000人 |
| II级 | 1-10吨 | 高毒 | 1-5km | 1000-10000人 |
| III级 | 0.1-1吨 | 中毒 | 0.5-1km | 100-1000人 |
| IV级 | < 0.1吨 | 低毒 | < 0.5km | < 100人 |

---

## 三、救援力量分类与能力定义

### 3.1 救援队伍类型

```yaml
rescue_teams:
  # 专业救援队伍
  professional:
    - id: "RT-001"
      name: "消防救援队"
      code: "FIRE"
      capabilities: ["灭火", "搜救", "破拆", "高空救援", "水域救援"]
      equipment: ["消防车", "云梯车", "破拆工具", "生命探测仪"]
      response_time_min: 10
      capacity: 20  # 人
      
    - id: "RT-002"
      name: "医疗急救队"
      code: "MEDICAL"
      capabilities: ["现场急救", "伤员转运", "医疗分类", "心肺复苏"]
      equipment: ["救护车", "急救包", "担架", "AED"]
      response_time_min: 15
      capacity: 8
      
    - id: "RT-003"
      name: "危化品处置队"
      code: "HAZMAT"
      capabilities: ["化学品识别", "泄漏封堵", "洗消", "气体监测"]
      equipment: ["防化服", "堵漏器材", "洗消车", "气体检测仪"]
      response_time_min: 30
      capacity: 12
      
    - id: "RT-004"
      name: "地震救援队"
      code: "USAR"
      capabilities: ["废墟搜救", "生命探测", "重型破拆", "狭小空间救援"]
      equipment: ["搜救犬", "生命探测仪", "液压破拆", "支撑设备"]
      response_time_min: 60
      capacity: 30
      
    - id: "RT-005"
      name: "水上救援队"
      code: "WATER"
      capabilities: ["水域搜救", "船艇操作", "潜水救援", "抗洪抢险"]
      equipment: ["冲锋舟", "救生衣", "潜水设备", "抽水泵"]
      response_time_min: 20
      capacity: 15
      
    - id: "RT-006"
      name: "电力抢修队"
      code: "POWER"
      capabilities: ["电力抢修", "发电保障", "线路巡检"]
      equipment: ["发电车", "抢修工具", "绝缘设备"]
      response_time_min: 30
      capacity: 10
      
    - id: "RT-007"
      name: "通信保障队"
      code: "COMM"
      capabilities: ["通信恢复", "应急通信", "信号覆盖"]
      equipment: ["卫星通信车", "移动基站", "对讲机"]
      response_time_min: 45
      capacity: 8

  # 志愿者队伍
  volunteer:
    - id: "VT-001"
      name: "社区志愿者"
      code: "COMMUNITY"
      capabilities: ["人员疏散引导", "物资搬运", "信息登记", "心理安抚"]
      response_time_min: 5
      capacity: 50
      
    - id: "VT-002"
      name: "蓝天救援队"
      code: "BLUE_SKY"
      capabilities: ["山地搜救", "城市搜救", "水域救援", "应急培训"]
      response_time_min: 30
      capacity: 20
```

### 3.2 无人设备类型

```yaml
unmanned_equipment:
  # 无人机
  uav:
    - id: "UAV-001"
      name: "侦察无人机"
      type: "reconnaissance"
      capabilities: ["高空侦察", "热成像", "实时视频", "地图测绘"]
      specs:
        flight_time_min: 45
        range_km: 10
        payload_kg: 2
        altitude_m: 500
      suitable_scenarios: ["灾情侦察", "人员搜索", "火点监控"]
      
    - id: "UAV-002"
      name: "喊话无人机"
      type: "broadcast"
      capabilities: ["语音喊话", "警示灯", "紧急通知"]
      specs:
        flight_time_min: 30
        range_km: 5
        sound_db: 120
      suitable_scenarios: ["疏散引导", "紧急通知", "人群管控"]
      
    - id: "UAV-003"
      name: "物资投送无人机"
      type: "delivery"
      capabilities: ["物资空投", "精准投放", "夜间作业"]
      specs:
        flight_time_min: 20
        range_km: 8
        payload_kg: 10
      suitable_scenarios: ["孤岛投送", "药品投放", "食品投送"]
      
    - id: "UAV-004"
      name: "消防无人机"
      type: "firefighting"
      capabilities: ["灭火弹投放", "火情监控", "热点定位"]
      specs:
        flight_time_min: 15
        range_km: 3
        payload_kg: 20
      suitable_scenarios: ["高层火灾", "森林火灾", "化工火灾"]

  # 无人车
  ugv:
    - id: "UGV-001"
      name: "侦察机器人"
      type: "reconnaissance"
      capabilities: ["狭小空间侦察", "有毒环境侦察", "视频传输"]
      specs:
        battery_hours: 4
        speed_kmh: 5
        size: "0.5m x 0.3m x 0.2m"
      suitable_scenarios: ["建筑倒塌", "危化品泄漏", "矿难救援"]
      
    - id: "UGV-002"
      name: "搜救机器人"
      type: "search_rescue"
      capabilities: ["生命探测", "语音通话", "物品递送"]
      specs:
        battery_hours: 6
        payload_kg: 5
      suitable_scenarios: ["废墟搜救", "被困人员联络"]
      
    - id: "UGV-003"
      name: "消防机器人"
      type: "firefighting"
      capabilities: ["远程灭火", "侦察探测", "排烟"]
      specs:
        water_flow_l_min: 80
        range_m: 100
      suitable_scenarios: ["危险火场", "石化火灾", "隧道火灾"]

  # 无人船
  usv:
    - id: "USV-001"
      name: "救援无人船"
      type: "rescue"
      capabilities: ["水面搜救", "救生圈投放", "拖带救援"]
      specs:
        speed_knots: 15
        range_km: 20
        capacity_persons: 3
      suitable_scenarios: ["溺水救援", "洪涝转移", "水面搜索"]
```

---

## 四、力量派遣规则 (TRR - Trigger-Response Rules)

### 4.1 救援队伍派遣触发规则

```json
{
  "version": "emergency-2025-11-25",
  "rules": [
    {
      "id": "TRR-EM-001",
      "name": "地震人员搜救规则",
      "if": [
        "灾害类型 = 地震",
        "建筑倒塌 = 是",
        "被困人员 >= 1",
        "黄金72小时内 = 是"
      ],
      "then": [
        "派遣队伍: 地震救援队(USAR)",
        "派遣队伍: 医疗急救队(MEDICAL)",
        "优先级: 最高",
        "携带装备: 生命探测仪、液压破拆、医疗急救包"
      ],
      "rationale": "建筑倒塌后72小时是救援黄金期，需立即派遣专业搜救力量"
    },
    {
      "id": "TRR-EM-002",
      "name": "火灾扑救规则",
      "if": [
        "灾害类型 = 火灾",
        "火势等级 >= 中",
        "有人员被困风险 = 是"
      ],
      "then": [
        "派遣队伍: 消防救援队(FIRE)",
        "派遣数量: 根据火势等级 (中=2车, 大=4车, 特大=8车)",
        "派遣队伍: 医疗急救队(MEDICAL)",
        "优先级: 最高"
      ],
      "rationale": "火灾蔓延迅速，需快速响应并配备医疗力量"
    },
    {
      "id": "TRR-EM-003",
      "name": "危化品泄漏规则",
      "if": [
        "灾害类型 = 危化品",
        "泄漏状态 = 持续",
        "化学品毒性 >= 中"
      ],
      "then": [
        "派遣队伍: 危化品处置队(HAZMAT)",
        "设立警戒区: 根据扩散模型计算",
        "派遣队伍: 医疗急救队(MEDICAL) 待命于安全区",
        "通知: 环保部门、气象部门"
      ],
      "rationale": "危化品需专业处置，普通救援人员禁止进入"
    },
    {
      "id": "TRR-EM-004",
      "name": "洪涝转移规则",
      "if": [
        "灾害类型 = 洪涝",
        "积水深度 >= 0.5m",
        "受困人员 >= 1",
        "水位趋势 = 上涨"
      ],
      "then": [
        "派遣队伍: 水上救援队(WATER)",
        "携带装备: 冲锋舟、救生衣",
        "设立转移点: 地势高处、安全建筑",
        "优先转移: 老幼病残孕"
      ],
      "rationale": "水位上涨时需优先转移弱势群体"
    },
    {
      "id": "TRR-EM-005",
      "name": "高层建筑救援规则",
      "if": [
        "灾害类型 ∈ [火灾, 地震]",
        "建筑高度 >= 50m",
        "电梯不可用 = 是",
        "被困人员位于高层 = 是"
      ],
      "then": [
        "派遣队伍: 消防救援队(FIRE) + 云梯车",
        "启用无人机: 侦察无人机(UAV-001)",
        "备选方案: 直升机救援",
        "优先级: 最高"
      ],
      "rationale": "高层救援需要专用设备和无人机配合"
    },
    {
      "id": "TRR-EM-006",
      "name": "夜间搜救规则",
      "if": [
        "时间段 = 夜间(18:00-06:00)",
        "搜救任务 = 进行中",
        "可见度 < 100m"
      ],
      "then": [
        "启用设备: 热成像无人机(UAV-001)",
        "配备照明: 移动照明车",
        "增派人员: 夜间作业经验丰富的队伍"
      ],
      "rationale": "夜间搜救需热成像设备提高效率"
    },
    {
      "id": "TRR-EM-007",
      "name": "道路抢通规则",
      "if": [
        "道路中断 = 是",
        "中断原因 ∈ [塌方, 积水, 落石]",
        "该道路为救援必经之路 = 是"
      ],
      "then": [
        "派遣队伍: 工程抢修队",
        "携带装备: 挖掘机、装载机",
        "先行侦察: 无人机勘察路况",
        "制定绕行方案: 如抢通时间 > 2小时"
      ],
      "rationale": "生命通道必须优先打通"
    },
    {
      "id": "TRR-EM-008",
      "name": "大规模疏散规则",
      "if": [
        "需疏散人数 >= 1000",
        "疏散时限 <= 2小时",
        "疏散区域面积 >= 1km²"
      ],
      "then": [
        "启用: 喊话无人机(UAV-002) 多架次",
        "派遣: 社区志愿者(VT-001)",
        "设立: 多个疏散引导点",
        "协调: 交通管制、公交转运"
      ],
      "rationale": "大规模疏散需立体化引导"
    }
  ]
}
```

### 4.2 无人设备派遣规则

```json
{
  "version": "emergency-uav-2025-11-25",
  "rules": [
    {
      "id": "UAV-RULE-001",
      "name": "灾情侦察优先规则",
      "if": [
        "灾情态势 = 不明",
        "人员进入风险 = 高",
        "侦察无人机可用 = 是"
      ],
      "then": [
        "立即起飞: 侦察无人机(UAV-001)",
        "任务: 全景侦察 + 热成像搜索",
        "实时回传: 指挥中心",
        "禁止: 人员先行进入"
      ],
      "rationale": "人员进入前必须先用无人机侦察"
    },
    {
      "id": "UAV-RULE-002",
      "name": "被困人员定位规则",
      "if": [
        "有被困人员报警 = 是",
        "具体位置 = 不明确",
        "通信中断 = 是"
      ],
      "then": [
        "起飞: 侦察无人机(UAV-001) 热成像模式",
        "起飞: 喊话无人机(UAV-002) 喊话定位",
        "搜索模式: 网格化搜索",
        "定位后: 标记GPS坐标传给救援队"
      ],
      "rationale": "无人机可快速定位被困人员位置"
    },
    {
      "id": "UAV-RULE-003",
      "name": "孤岛物资投送规则",
      "if": [
        "受困区域 = 孤岛/被围困",
        "地面通道 = 不可达",
        "受困人员急需物资 = 是"
      ],
      "then": [
        "起飞: 物资投送无人机(UAV-003)",
        "投送物资优先级: 药品 > 饮水 > 食品 > 通信设备",
        "投放精度: GPS定位 + 视觉引导",
        "多架次轮换: 确保持续投送"
      ],
      "rationale": "无人机是孤岛物资投送最快捷方式"
    },
    {
      "id": "UAV-RULE-004",
      "name": "危险区域侦察规则",
      "if": [
        "区域类型 ∈ [危化品污染区, 辐射区, 高温区]",
        "人员进入 = 严禁"
      ],
      "then": [
        "起飞: 侦察无人机(UAV-001) + 气体检测载荷",
        "起飞: 侦察机器人(UGV-001) 地面配合",
        "数据采集: 浓度、温度、辐射值",
        "划定: 安全边界"
      ],
      "rationale": "危险区域必须用无人设备先行侦察"
    },
    {
      "id": "UAV-RULE-005",
      "name": "水面救援规则",
      "if": [
        "灾害类型 ∈ [洪涝, 溺水]",
        "水面有落水人员 = 是",
        "救援船艇未到达 = 是"
      ],
      "then": [
        "起飞: 侦察无人机(UAV-001) 定位跟踪",
        "起飞: 物资无人机(UAV-003) 投放救生圈",
        "启动: 救援无人船(USV-001) 前往救援",
        "持续喊话: 稳定情绪"
      ],
      "rationale": "无人设备可先于有人船艇到达"
    },
    {
      "id": "UAV-RULE-006",
      "name": "火场侦察规则",
      "if": [
        "灾害类型 = 火灾",
        "火场面积 >= 1000m²",
        "烟雾浓度 = 高"
      ],
      "then": [
        "起飞: 侦察无人机(UAV-001) 热成像",
        "任务: 定位火点、寻找被困人员、监控蔓延",
        "起飞: 消防无人机(UAV-004) 高层灭火",
        "持续监控: 直至明火扑灭"
      ],
      "rationale": "无人机可穿透烟雾进行热成像侦察"
    },
    {
      "id": "UAV-RULE-007",
      "name": "废墟搜救规则",
      "if": [
        "灾害类型 ∈ [地震, 爆炸]",
        "建筑倒塌 = 是",
        "废墟空间狭小 = 是"
      ],
      "then": [
        "部署: 搜救机器人(UGV-002)",
        "任务: 狭小空间侦察、生命探测、语音联络",
        "配合: 生命探测仪定位",
        "递送: 水、通信设备给被困者"
      ],
      "rationale": "搜救机器人可进入人员无法到达的狭小空间"
    }
  ]
}
```

---

## 五、安全地点与疏散规则

### 5.1 安全地点选择标准

```yaml
safe_shelter_criteria:
  # 必要条件 (全部满足)
  mandatory:
    - id: "SC-001"
      name: "结构安全"
      rule: "建筑抗震设防 >= 当地烈度 + 1度"
      check: "建筑安全鉴定合格"
      
    - id: "SC-002"
      name: "位置安全"
      rule: "距灾害源安全距离 >= 安全半径"
      examples:
        flood: "高于历史最高水位 2m"
        hazmat: "位于上风向 + 距离 >= 扩散半径 * 2"
        fire: "距火场 >= 500m + 有隔离带"
        
    - id: "SC-003"
      name: "道路通达"
      rule: "至少有 2 条可用道路连接"
      check: "道路未中断、可通行大型车辆"
      
    - id: "SC-004"
      name: "容量充足"
      rule: "人均面积 >= 2m²"
      check: "总容量 >= 计划疏散人数 * 1.2"

  # 优选条件 (尽量满足)
  preferred:
    - id: "SP-001"
      name: "配套设施"
      items: ["供水", "供电", "卫生间", "通信"]
      
    - id: "SP-002"
      name: "医疗条件"
      rule: "有医疗点或距医院 < 5km"
      
    - id: "SP-003"
      name: "物资储备"
      items: ["饮用水", "食品", "帐篷", "被褥"]
      
    - id: "SP-004"
      name: "停车场地"
      rule: "可停放救援车辆 >= 10辆"
```

### 5.2 疏散路线规划规则

```yaml
evacuation_route_rules:
  # 路线选择原则
  selection_principles:
    - id: "ER-001"
      name: "远离危险源"
      rule: "路线与危险源最小距离 >= 安全距离"
      
    - id: "ER-002"
      name: "道路条件"
      rule: "优先选择宽度 >= 6m 的主干道"
      
    - id: "ER-003"
      name: "路程最短"
      rule: "在满足安全前提下选择最短路径"
      
    - id: "ER-004"
      name: "避免拥堵"
      rule: "单一路线容量不超过设计容量的 80%"
      
    - id: "ER-005"
      name: "备用路线"
      rule: "每个疏散方向至少规划 2 条路线"

  # 人群流量控制
  flow_control:
    walking_speed_m_s:
      normal: 1.2
      elderly: 0.8
      with_luggage: 0.9
      panic: 0.6  # 恐慌状态下降低
      
    road_capacity_person_m_min:
      sidewalk: 80    # 人行道
      road_lane: 120  # 机动车道步行
      stairway: 50    # 楼梯
      
    bottleneck_rules:
      - "瓶颈口宽度每减少1m，通过能力下降约30%"
      - "转弯处通过能力为直道的70%"
      - "上坡通过能力为平地的80%"
```

### 5.3 人群疏散优先级

```yaml
evacuation_priority:
  # 人员分类优先级 (1最高, 5最低)
  priority_groups:
    1: 
      name: "重伤员"
      description: "需要担架或急救的伤员"
      transport: "救护车优先"
      
    2:
      name: "弱势群体A"
      description: "婴幼儿、孕妇、重症患者"
      transport: "专车接送"
      
    3:
      name: "弱势群体B"
      description: "老年人(≥70岁)、残疾人、行动不便者"
      transport: "安排志愿者协助"
      
    4:
      name: "一般人员"
      description: "健康成年人"
      transport: "步行或公共交通"
      
    5:
      name: "机动人员"
      description: "青壮年志愿者"
      transport: "最后撤离，协助他人"

  # 区域疏散优先级
  zone_priority:
    - "危险区核心 → 危险区边缘 → 缓冲区 → 安全区"
    - "下风向 → 上风向 (危化品)"
    - "低洼区 → 高地 (洪涝)"
    - "高层 → 低层 (火灾，无电梯时相反)"
```

---

## 六、硬约束规则 (一票否决)

```json
{
  "version": "emergency-hard-rules-2025-11-25",
  "rules": [
    {
      "id": "HR-EM-001",
      "name": "人员安全红线",
      "if": "方案导致救援人员伤亡概率 > 10%",
      "then": "一票否决",
      "description": "救援人员安全是底线，高风险方案需调整或换人员为无人设备"
    },
    {
      "id": "HR-EM-002",
      "name": "二次伤害禁止",
      "if": "方案可能导致被困人员二次伤害",
      "then": "一票否决",
      "description": "如不稳定结构下的强行破拆、有毒环境下无防护进入"
    },
    {
      "id": "HR-EM-003",
      "name": "救援时效性",
      "if": "方案执行时间 > 黄金救援时间",
      "then": "一票否决",
      "description": "地震72h、溺水6min、火灾逃生3min等关键时限"
    },
    {
      "id": "HR-EM-004",
      "name": "资源可用性",
      "if": "方案所需资源 > 实际可用资源",
      "then": "一票否决",
      "description": "不能超出现有资源能力进行规划"
    },
    {
      "id": "HR-EM-005",
      "name": "道路可达性",
      "if": "救援路线不可通行且无替代路线",
      "then": "一票否决",
      "description": "必须保证救援力量能够到达现场"
    },
    {
      "id": "HR-EM-006",
      "name": "危险区域管控",
      "if": "方案让无防护人员进入高危区域",
      "then": "一票否决",
      "description": "危化品核心区、高辐射区、高温区等必须有防护"
    },
    {
      "id": "HR-EM-007",
      "name": "气象条件限制",
      "if": "风力 > 6级 且 方案需要无人机作业",
      "then": "一票否决",
      "description": "恶劣气象条件下禁止无人机起飞"
    },
    {
      "id": "HR-EM-008",
      "name": "通信保障",
      "if": "方案区域无任何通信手段",
      "then": "一票否决 或 先建立通信",
      "description": "没有通信联络的救援行动禁止执行"
    }
  ]
}
```

---

## 七、软约束与优化权重

### 7.1 决策权重配置

```yaml
decision_weights:
  # 方案评估维度权重
  evaluation_dimensions:
    life_safety:      0.40  # 生命安全
    time_efficiency:  0.25  # 时间效率
    resource_cost:    0.15  # 资源消耗
    success_rate:     0.15  # 成功概率
    secondary_risk:   0.05  # 次生风险
    
  # 场景优先级仲裁权重 (TOPSIS)
  scene_priority:
    life_threat:      0.35  # 生命威胁程度
    time_urgency:     0.25  # 时间紧迫性
    affected_people:  0.20  # 影响人数
    success_prob:     0.20  # 救援成功率
    
  # 资源分配偏好
  resource_preference:
    professional_first: 0.7  # 优先使用专业队伍
    local_first:        0.6  # 优先使用就近资源
    reserve_ratio:      0.2  # 保留20%资源应对次生灾害
```

### 7.2 约束松弛规则

```yaml
constraint_relaxation:
  # 当硬约束无法满足时的松弛策略
  relaxation_rules:
    - id: "RELAX-001"
      constraint: "响应时间"
      original: "< 30分钟"
      relaxed: "< 60分钟"
      condition: "所有就近资源已派出"
      compensation: "派遣更多远距资源"
      
    - id: "RELAX-002"
      constraint: "专业队伍"
      original: "必须派遣专业队伍"
      relaxed: "志愿者+远程专业指导"
      condition: "专业队伍全部占用"
      compensation: "视频连线专业人员指导"
      
    - id: "RELAX-003"
      constraint: "无人机数量"
      original: ">= 3架"
      relaxed: ">= 1架"
      condition: "无人机资源不足"
      compensation: "增加地面侦察力量"
```

---

## 八、编组规则

### 8.1 救援力量编组模式

```json
{
  "version": "emergency-grouping-2025-11-25",
  "grouping_rules": [
    {
      "id": "GROUP-EM-001",
      "pattern": "搜救+医疗",
      "definition": "1搜救队 + 1医疗队 (生命救援小组)",
      "roles": {
        "rescue_team": "搜索定位、破拆救出",
        "medical_team": "现场急救、伤员转运"
      },
      "features": "搜救医疗一体化，发现即救治",
      "scenarios": ["地震搜救", "建筑倒塌", "矿难救援"]
    },
    {
      "id": "GROUP-EM-002",
      "pattern": "消防+医疗+通信",
      "definition": "2消防车 + 1救护车 + 1通信车 (标准火灾编组)",
      "roles": {
        "fire_team": "灭火、人员疏散",
        "medical_team": "伤员救治",
        "comm_team": "现场通信保障"
      },
      "features": "功能完整的火灾处置单元",
      "scenarios": ["建筑火灾", "工厂火灾"]
    },
    {
      "id": "GROUP-EM-003",
      "pattern": "侦察无人机+搜救机器人+指挥车",
      "definition": "2无人机 + 1机器人 + 1指挥车 (无人协同编组)",
      "roles": {
        "uav": "空中侦察、定位标记",
        "ugv": "地面侦察、狭小空间探测",
        "command": "远程操控、数据汇聚"
      },
      "features": "先无人后有人，降低人员风险",
      "scenarios": ["危化品侦察", "高危区域探测", "废墟搜索"]
    },
    {
      "id": "GROUP-EM-004",
      "pattern": "危化品处置全编组",
      "definition": "1危化队 + 1消防队 + 1医疗队 + 1环保监测",
      "roles": {
        "hazmat": "堵漏、洗消",
        "fire": "警戒、稀释",
        "medical": "中毒救治",
        "monitor": "环境监测"
      },
      "features": "多专业协同处置",
      "scenarios": ["化学品泄漏", "毒气扩散"]
    },
    {
      "id": "GROUP-EM-005",
      "pattern": "水域救援编组",
      "definition": "2冲锋舟 + 1无人船 + 1无人机 + 1救护车",
      "roles": {
        "boats": "人员转运、水面搜救",
        "usv": "远距侦察、物资投送",
        "uav": "空中定位、指挥引导",
        "medical": "岸边待命救治"
      },
      "features": "水陆空立体救援",
      "scenarios": ["洪涝救援", "溺水救援"]
    }
  ]
}
```

---

## 九、与算法模块的对接

### 9.1 规则-算法映射关系

| 规则类型 | 对应算法模块 | 输入 | 输出 |
|----------|--------------|------|------|
| 灾害等级判定 | `DisasterAssessment` | 灾害参数 | 等级、影响范围 |
| 队伍选择规则 | `RescueTeamSelector` | 灾情画像、可用资源 | 推荐队伍列表 |
| 编组规则 | `CapabilityMatcher` | 能力需求、资源池 | 编组方案 |
| 全地形路径 | `OffroadEngine` + `RoadNetworkEngine` | 起终点、DEM、路网、障碍物 | 最优路线(道路优先+越野兜底) |
| 多车辆调度 | `VehicleRoutingPlanner` | 任务点、车队、约束 | VRP最优路径 |
| 场景优先级 | `SceneArbitrator` | 多场景参数 | 优先级排序 |
| 资源分配 | `ConflictResolver` | 资源冲突 | 分配方案 |
| 方案优化 | `PymooOptimizer` | 决策权重、约束 | Pareto最优解 |
| 方案仿真 | `DiscreteEventSimulator` | 方案、随机参数 | 成功率、耗时 |

### 9.2 规则配置加载示例

```python
from src.planning.config_loader import load_emergency_rules

# 加载规则配置
rules = load_emergency_rules()

# 获取硬约束规则
hard_rules = rules.get_hard_rules()

# 获取触发规则
trr_rules = rules.get_trr_rules(disaster_type="earthquake")

# 获取编组规则
grouping = rules.get_grouping_rules(scenario="建筑倒塌")

# 获取决策权重
weights = rules.get_decision_weights()
```

### 9.3 全地形路径规划示例

```python
from pathlib import Path
from src.planning.algorithms.routing import (
    OffroadEngine, OffroadConfig,
    RoadNetworkEngine, RoadEngineConfig,
    load_routing_resources,
    Point, CapabilityMetrics, Obstacle
)

# 加载地理数据资源
resources = load_routing_resources(
    dem_path=Path("data/四川省.tif"),
    roads_path=Path("data/roads/gis_osm_roads_free_1.shp"),
    water_path=Path("data/roads/gis_osm_water_a_free_1.shp")
)

# 创建路网引擎和越野引擎
road_engine = RoadNetworkEngine(
    roads_path=str(resources.roads_path),
    dem=resources.dem_dataset,
    config=RoadEngineConfig(resolution_m=80.0)
)
offroad_engine = OffroadEngine(
    dem=resources.dem_dataset,
    water_polygons=resources.water_polygons,
    config=OffroadConfig(resolution_m=80.0)
)

# 定义起终点和车辆能力
start = Point(lon=103.5, lat=30.5)
end = Point(lon=103.8, lat=30.7)
capability = CapabilityMetrics(slope_deg=25.0, range_km=100.0)

# 路网优先规划，不通则越野
result = road_engine.plan_segment(start, end, obstacles=[], hard_req=set(), soft_req=set(), capability=capability)
if result is None:
    result = offroad_engine.plan(start, end, obstacles=[], hard_req=set(), soft_req=set(), capability=capability)

print(f"路径距离: {result.distance_m:.0f}m, 模式: {result.metadata['mode']}")
```

---

## 十、配置文件清单

```
config/emergency/
├── disaster_types.yaml          # 灾害类型与等级定义
├── rescue_teams.yaml            # 救援队伍能力库
├── unmanned_equipment.yaml      # 无人设备能力库
├── trr_rules.json              # 触发规则
├── hard_rules.json             # 硬约束规则
├── grouping_rules.json         # 编组规则
├── evacuation_rules.yaml       # 疏散规则
├── safe_shelter_criteria.yaml  # 安全地点标准
└── decision_weights.yaml       # 决策权重配置
```

---

## 附录：规则ID命名规范

| 前缀 | 含义 | 示例 |
|------|------|------|
| TRR-EM-xxx | 应急触发规则 | TRR-EM-001 地震搜救规则 |
| HR-EM-xxx | 应急硬约束 | HR-EM-001 人员安全红线 |
| GROUP-EM-xxx | 应急编组规则 | GROUP-EM-001 搜救医疗编组 |
| UAV-RULE-xxx | 无人机派遣规则 | UAV-RULE-001 灾情侦察优先 |
| ER-xxx | 疏散路线规则 | ER-001 远离危险源 |
| SC-xxx | 安全地点标准 | SC-001 结构安全 |
