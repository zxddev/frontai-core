"""
CrewAI目标优先级分析与侦察方案生成

为每个侦察目标生成详细的侦察方案：
- 每个目标单独调用LLM（避免输入过长）
- 使用asyncio并发执行（提高效率）
- 单个失败用规则引擎兜底（不影响整体）
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task
from pydantic import BaseModel, Field

from .crew import get_default_llm, CrewAIError

logger = logging.getLogger(__name__)

# 并发配置
MAX_CONCURRENT_LLM_CALLS = 5  # 最大并发数
SINGLE_TARGET_TIMEOUT = 120   # 单目标超时时间（秒）


class ReconMethodDetail(BaseModel):
    """侦察方法详情"""
    method_name: str = Field(..., description="方法名称")
    description: str = Field(..., description="方法描述")
    route_description: str = Field(..., description="路线描述")
    altitude_or_distance: str = Field(..., description="飞行高度或作业距离")
    coverage_pattern: str = Field(..., description="覆盖模式：zigzag/spiral/circular/linear")


class DeviceRecommendation(BaseModel):
    """设备推荐详情"""
    device_type: str = Field(..., description="设备类型：drone/dog/ship")
    reason: str = Field(..., description="为什么推荐使用这种设备")
    capabilities_needed: list[str] = Field(default_factory=list, description="需要的设备能力")


class RiskMitigation(BaseModel):
    """风险规避措施"""
    risk_type: str = Field(..., description="风险类型")
    mitigation_measure: str = Field(..., description="规避措施")


class TargetReconPlan(BaseModel):
    """单个目标的详细侦察方案"""
    target_id: str = Field(..., description="目标ID")
    priority_score: int = Field(..., ge=0, le=100, description="优先级分数0-100")
    priority: str = Field(..., description="优先级：critical/high/medium/low")
    priority_reason: str = Field(..., description="优先级理由")
    recommended_devices: list[DeviceRecommendation] = Field(..., description="推荐设备列表")
    recon_method: ReconMethodDetail = Field(..., description="侦察方法详情")
    recon_focus: list[str] = Field(..., description="侦察重点")
    recon_content: list[str] = Field(..., description="具体侦察内容")
    risk_mitigations: list[RiskMitigation] = Field(default_factory=list, description="风险规避措施")
    safety_notes: list[str] = Field(default_factory=list, description="安全注意事项")
    abort_conditions: list[str] = Field(default_factory=list, description="中止条件")
    estimated_duration_min: float = Field(..., description="预计侦察时长（分钟）")
    coordination_notes: str = Field("", description="协同说明")


class TargetPriorityOutput(BaseModel):
    """目标优先级分析输出"""
    prioritized_targets: list[TargetReconPlan] = Field(..., description="优先级排序后的目标方案")
    analysis_summary: str = Field(..., description="分析摘要")
    total_devices_needed: int = Field(..., description="需要设备总数")
    total_duration_min: float = Field(..., description="预计总时长（分钟）")
    device_breakdown: dict[str, int] = Field(..., description="设备类型分布")
    recommendations: list[str] = Field(default_factory=list, description="总体建议")
    warnings: list[str] = Field(default_factory=list, description="警告")


# 单目标分析的简化prompt
SINGLE_TARGET_PROMPT = """为以下侦察目标制定详细侦察方案。

## 目标信息
{target_json}

## 输出要求
根据目标类型，输出JSON格式侦察方案：

1. **优先级评分**(0-100)：被困人员+30, 时间紧迫+25, 高风险+15
2. **设备推荐**：说明为什么选择这种设备
3. **侦察方法**：具体怎么侦察（路线、高度、模式）
4. **侦察重点**：需要关注什么（3-5项）
5. **风险规避**：识别风险并提出措施（2-3项）
6. **安全注意**：作业安全要求（2-4项）
7. **中止条件**：什么情况中止（2-3项）

## 设备选择指南
- 被困人员搜救：drone(热成像) + dog(废墟搜索)
- 滑坡区域：drone(航拍评估)
- 淹没区域：drone(空中) + ship(水面)
- 地震核心区：drone(航拍)

## 输出JSON格式
{{
    "target_id": "原目标ID",
    "priority_score": 85,
    "priority": "critical",
    "priority_reason": "理由",
    "recommended_devices": [
        {{"device_type": "drone", "reason": "理由", "capabilities_needed": ["thermal_imaging"]}}
    ],
    "recon_method": {{
        "method_name": "方法名",
        "description": "描述",
        "route_description": "路线",
        "altitude_or_distance": "高度",
        "coverage_pattern": "zigzag"
    }},
    "recon_focus": ["重点1", "重点2"],
    "recon_content": ["内容1", "内容2"],
    "risk_mitigations": [
        {{"risk_type": "风险", "mitigation_measure": "措施"}}
    ],
    "safety_notes": ["注意1", "注意2"],
    "abort_conditions": ["条件1", "条件2"],
    "estimated_duration_min": 25,
    "coordination_notes": "协同说明"
}}

只输出JSON，不要其他内容。"""


def _create_single_target_agent(llm: LLM) -> Agent:
    """创建单目标分析Agent"""
    return Agent(
        role="侦察战术专家",
        goal="为单个侦察目标制定详细方案",
        backstory="你是应急救援侦察专家，精通无人机、机器狗、无人艇的战术运用。",
        llm=llm,
        verbose=False,  # 并发时关闭verbose减少日志
    )


class TargetPriorityAnalysisCrew:
    """
    目标优先级分析与方案生成
    
    每个目标单独调用LLM，并发执行提高效率。
    单个失败时用规则引擎兜底。
    """
    
    def __init__(self, llm: LLM | None = None) -> None:
        self.llm: LLM = llm if llm is not None else get_default_llm()
        self._semaphore: asyncio.Semaphore | None = None
    
    async def analyze(
        self,
        targets: list[dict[str, Any]],
    ) -> TargetPriorityOutput:
        """
        并发分析所有目标
        
        每个目标单独调用LLM，使用Semaphore控制并发数。
        单个目标失败时用规则引擎兜底。
        """
        if not targets:
            logger.warning("[TargetAnalysis] 目标列表为空")
            return TargetPriorityOutput(
                prioritized_targets=[],
                analysis_summary="无需分析，目标列表为空",
                total_devices_needed=0,
                total_duration_min=0,
                device_breakdown={},
                recommendations=[],
                warnings=["未发现需要侦察的目标"],
            )
        
        logger.info(f"[TargetAnalysis] 开始并发分析{len(targets)}个目标，并发数={MAX_CONCURRENT_LLM_CALLS}")
        
        # 创建信号量控制并发
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
        
        # 并发执行所有目标分析
        tasks = [self._analyze_with_limit(t) for t in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        plans: list[TargetReconPlan] = []
        failed_count = 0
        warnings: list[str] = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # LLM失败，用规则引擎兜底
                logger.warning(f"[TargetAnalysis] 目标{i}分析失败: {result}，使用规则引擎")
                fallback = _rule_based_single_target(targets[i])
                plans.append(fallback)
                failed_count += 1
            elif isinstance(result, TargetReconPlan):
                plans.append(result)
            else:
                logger.error(f"[TargetAnalysis] 目标{i}返回未知类型: {type(result)}")
                fallback = _rule_based_single_target(targets[i])
                plans.append(fallback)
                failed_count += 1
        
        if failed_count > 0:
            warnings.append(f"{failed_count}个目标LLM分析失败，已用规则引擎补充")
        
        # 按优先级排序
        plans.sort(key=lambda x: x.priority_score, reverse=True)
        
        # 统计设备
        device_count = {"drone": 0, "dog": 0, "ship": 0}
        total_duration = 0.0
        for p in plans:
            for d in p.recommended_devices:
                if d.device_type in device_count:
                    device_count[d.device_type] += 1
            total_duration += p.estimated_duration_min
        
        critical_count = sum(1 for p in plans if p.priority == "critical")
        high_count = sum(1 for p in plans if p.priority == "high")
        
        logger.info(f"[TargetAnalysis] 分析完成: {len(plans)}个目标, 失败{failed_count}个")
        
        return TargetPriorityOutput(
            prioritized_targets=plans,
            analysis_summary=f"分析{len(plans)}个目标，紧急{critical_count}个、高优先{high_count}个。"
                             f"需要drone {device_count['drone']}架、dog {device_count['dog']}台、ship {device_count['ship']}艘。",
            total_devices_needed=sum(device_count.values()),
            total_duration_min=total_duration,
            device_breakdown=device_count,
            recommendations=["建议优先处理紧急目标", "注意设备续航分配"],
            warnings=warnings,
        )
    
    async def _analyze_with_limit(self, target: dict) -> TargetReconPlan:
        """带并发限制的单目标分析"""
        async with self._semaphore:
            return await self._analyze_single_target(target)
    
    async def _analyze_single_target(self, target: dict) -> TargetReconPlan:
        """分析单个目标"""
        target_id = target.get("target_id", "unknown")
        logger.debug(f"[TargetAnalysis] 开始分析: {target_id}")
        
        # 构建简化的目标JSON
        target_json = json.dumps(target, ensure_ascii=False, indent=2)
        
        # 创建Agent和Task
        agent = _create_single_target_agent(self.llm)
        task = Task(
            description=SINGLE_TARGET_PROMPT.format(target_json=target_json),
            expected_output="JSON格式侦察方案",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        
        # 执行（带超时）
        try:
            result = await asyncio.wait_for(
                crew.kickoff_async(inputs={}),
                timeout=SINGLE_TARGET_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise CrewAIError(f"目标{target_id}分析超时({SINGLE_TARGET_TIMEOUT}s)")
        
        # 解析结果
        return self._parse_single_result(result, target_id)
    
    def _parse_single_result(self, crew_output: Any, target_id: str) -> TargetReconPlan:
        """解析单个目标的LLM输出"""
        tasks_output = getattr(crew_output, "tasks_output", [])
        
        if not tasks_output:
            raise CrewAIError(f"目标{target_id}无输出")
        
        task_output = tasks_output[0]
        
        # 尝试从json_dict获取
        if hasattr(task_output, "json_dict") and task_output.json_dict:
            return self._dict_to_plan(task_output.json_dict)
        
        # 尝试从raw获取
        if hasattr(task_output, "raw"):
            raw = task_output.raw
            if isinstance(raw, dict):
                return self._dict_to_plan(raw)
            # 解析JSON字符串
            text = str(raw).strip()
            text = self._clean_json(text)
            data = json.loads(text)
            return self._dict_to_plan(data)
        
        raise CrewAIError(f"目标{target_id}输出格式无法解析")
    
    def _dict_to_plan(self, data: dict) -> TargetReconPlan:
        """将字典转换为TargetReconPlan"""
        devices = [
            DeviceRecommendation(
                device_type=d.get("device_type", "drone"),
                reason=d.get("reason", ""),
                capabilities_needed=d.get("capabilities_needed", []),
            )
            for d in data.get("recommended_devices", [])
        ]
        
        rm = data.get("recon_method", {})
        recon_method = ReconMethodDetail(
            method_name=rm.get("method_name", "侦察"),
            description=rm.get("description", ""),
            route_description=rm.get("route_description", ""),
            altitude_or_distance=rm.get("altitude_or_distance", ""),
            coverage_pattern=rm.get("coverage_pattern", "zigzag"),
        )
        
        mitigations = [
            RiskMitigation(
                risk_type=r.get("risk_type", ""),
                mitigation_measure=r.get("mitigation_measure", ""),
            )
            for r in data.get("risk_mitigations", [])
        ]
        
        return TargetReconPlan(
            target_id=data.get("target_id", ""),
            priority_score=data.get("priority_score", 50),
            priority=data.get("priority", "medium"),
            priority_reason=data.get("priority_reason", ""),
            recommended_devices=devices,
            recon_method=recon_method,
            recon_focus=data.get("recon_focus", []),
            recon_content=data.get("recon_content", []),
            risk_mitigations=mitigations,
            safety_notes=data.get("safety_notes", []),
            abort_conditions=data.get("abort_conditions", []),
            estimated_duration_min=data.get("estimated_duration_min", 15),
            coordination_notes=data.get("coordination_notes", ""),
        )
    
    def _clean_json(self, text: str) -> str:
        """清理JSON字符串"""
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.startswith("```"):
                    end = i
                    break
            text = "\n".join(lines[start:end])
        return text


def _rule_based_single_target(target: dict) -> TargetReconPlan:
    """规则引擎：为单个目标生成方案（LLM失败时的兜底）"""
    score = 50
    
    victims = target.get("estimated_victims", 0) or 0
    if victims > 0:
        score += min(30, victims * 5)
    if target.get("is_time_critical"):
        score += 25
    golden = target.get("golden_hour_remaining_min")
    if golden is not None and golden < 120:
        score += 20
    risk = target.get("risk_level", 5)
    if risk >= 8:
        score += 15
    elif risk >= 6:
        score += 10
    
    score = min(100, score)
    
    if score >= 80:
        priority = "critical"
    elif score >= 60:
        priority = "high"
    elif score >= 40:
        priority = "medium"
    else:
        priority = "low"
    
    area_type = target.get("area_type", "")
    event_type = target.get("event_type", "")
    
    # 被困人员
    if event_type == "trapped_person" or victims > 0:
        devices = [
            DeviceRecommendation(device_type="drone", reason="热成像定位被困人员", capabilities_needed=["thermal_imaging"]),
            DeviceRecommendation(device_type="dog", reason="废墟搜索确认生命迹象", capabilities_needed=["life_detection"]),
        ]
        method = ReconMethodDetail(
            method_name="空地联合搜索",
            description="无人机热成像扫描，机器狗跟进确认",
            route_description="无人机螺旋扫描，机器狗沿安全通道推进",
            altitude_or_distance="无人机50m，机器狗地面",
            coverage_pattern="spiral",
        )
        focus = ["热成像定位被困人员", "评估结构稳定性", "标记安全进入路线"]
        content = ["被困人员位置", "建筑损坏程度", "通行情况"]
        mitigations = [
            RiskMitigation(risk_type="二次坍塌", mitigation_measure="机器狗进入前无人机先评估"),
            RiskMitigation(risk_type="余震", mitigation_measure="保持撤离通道畅通"),
        ]
        safety = ["无人机保持50m高度", "机器狗避开不稳定结构", "电量<30%返航"]
        abort = ["瓦斯泄漏", "新坍塌迹象", "通信中断>60s"]
        duration = 30.0
        coord = "无人机热点坐标传给机器狗"
    
    # 滑坡
    elif area_type == "landslide":
        devices = [DeviceRecommendation(device_type="drone", reason="航拍评估滑坡体", capabilities_needed=["aerial_recon"])]
        method = ReconMethodDetail(
            method_name="滑坡体航拍",
            description="无人机zigzag扫描评估",
            route_description="从下游向上游扫描",
            altitude_or_distance="120m",
            coverage_pattern="zigzag",
        )
        focus = ["滑坡体边界", "稳定性评估", "二次滑坡风险"]
        content = ["滑坡体范围", "裂缝情况", "下游威胁"]
        mitigations = [RiskMitigation(risk_type="二次滑坡", mitigation_measure="保持安全距离")]
        safety = ["保持120m高度", "避免滑坡体上方悬停"]
        abort = ["滑坡体移动", "能见度下降"]
        duration = 25.0
        coord = ""
    
    # 淹没区域
    elif area_type == "flooded":
        devices = [
            DeviceRecommendation(device_type="drone", reason="空中观察水位", capabilities_needed=["aerial_recon"]),
            DeviceRecommendation(device_type="ship", reason="水面搜索", capabilities_needed=["water_recon"]),
        ]
        method = ReconMethodDetail(
            method_name="空水联合侦察",
            description="无人机空中扫描，无人艇水面巡航",
            route_description="无人机zigzag，无人艇沿水域边缘",
            altitude_or_distance="无人机80m，无人艇水面",
            coverage_pattern="zigzag",
        )
        focus = ["被困群众", "水位变化", "可通行路线"]
        content = ["被困人员分布", "水深流速", "撤离路线"]
        mitigations = [RiskMitigation(risk_type="水位上涨", mitigation_measure="设置监测点")]
        safety = ["无人艇避开漩涡", "实时监控水位"]
        abort = ["水位快速上涨", "危险漂浮物"]
        duration = 30.0
        coord = "无人机发现被困人员后引导无人艇"
    
    # 地震核心区
    elif area_type in ("seismic_red", "seismic_orange"):
        devices = [DeviceRecommendation(device_type="drone", reason="航拍评估损坏", capabilities_needed=["aerial_recon", "thermal_imaging"])]
        method = ReconMethodDetail(
            method_name="震区航拍",
            description="无人机zigzag扫描",
            route_description="沿道路和建筑群扫描",
            altitude_or_distance="100m",
            coverage_pattern="zigzag",
        )
        focus = ["建筑倒塌", "道路通行", "被困人员热信号"]
        content = ["建筑损坏分级", "道路阻断点", "潜在被困区"]
        mitigations = [RiskMitigation(risk_type="余震", mitigation_measure="保持安全高度")]
        safety = ["保持100m高度", "余震时爬升"]
        abort = ["强余震", "火灾爆炸风险"]
        duration = 20.0
        coord = ""
    
    # 默认
    else:
        devices = [DeviceRecommendation(device_type="drone", reason="快速获取态势", capabilities_needed=["aerial_recon"])]
        method = ReconMethodDetail(
            method_name="航拍侦察",
            description="无人机高空扫描",
            route_description="zigzag覆盖",
            altitude_or_distance="100m",
            coverage_pattern="zigzag",
        )
        focus = ["整体态势"]
        content = ["区域概况"]
        mitigations = []
        safety = ["电量<30%返航", "信号丢失返航"]
        abort = ["设备故障", "天气恶化"]
        duration = 15.0
        coord = ""
    
    reasons = []
    if victims > 0:
        reasons.append(f"{victims}人被困")
    if target.get("is_time_critical"):
        reasons.append("时间紧迫")
    if risk >= 8:
        reasons.append("高风险区域")
    if not reasons:
        reasons.append("常规目标")
    
    return TargetReconPlan(
        target_id=target.get("target_id", ""),
        priority_score=score,
        priority=priority,
        priority_reason="，".join(reasons),
        recommended_devices=devices,
        recon_method=method,
        recon_focus=focus,
        recon_content=content,
        risk_mitigations=mitigations,
        safety_notes=safety,
        abort_conditions=abort,
        estimated_duration_min=duration,
        coordination_notes=coord,
    )


def rule_based_priority_analysis(targets: list[dict[str, Any]]) -> TargetPriorityOutput:
    """
    纯规则引擎分析（不使用LLM）
    
    当用户选择useCrewAI=false时调用。
    """
    plans = [_rule_based_single_target(t) for t in targets]
    plans.sort(key=lambda x: x.priority_score, reverse=True)
    
    device_count = {"drone": 0, "dog": 0, "ship": 0}
    total_duration = 0.0
    for p in plans:
        for d in p.recommended_devices:
            if d.device_type in device_count:
                device_count[d.device_type] += 1
        total_duration += p.estimated_duration_min
    
    critical_count = sum(1 for p in plans if p.priority == "critical")
    high_count = sum(1 for p in plans if p.priority == "high")
    
    return TargetPriorityOutput(
        prioritized_targets=plans,
        analysis_summary=f"识别{len(targets)}个目标，紧急{critical_count}个、高优先{high_count}个。"
                         f"需要drone {device_count['drone']}架、dog {device_count['dog']}台、ship {device_count['ship']}艘。",
        total_devices_needed=sum(device_count.values()),
        total_duration_min=total_duration,
        device_breakdown=device_count,
        recommendations=["建议优先处理紧急目标", "注意设备续航分配"],
        warnings=[],
    )
