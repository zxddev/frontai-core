"""
CrewAI Crew组装 - 侦察调度增强

组装两个专家Crew：
1. DisasterAnalysisCrew - 灾情理解
2. PlanPresentationCrew - 计划呈报

无fallback：LLM调用失败直接抛异常暴露问题
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from crewai import Crew, LLM, Process

from .agents import create_disaster_analyst, create_plan_presenter
from .tasks import (
    create_disaster_analysis_task,
    create_plan_presentation_task,
    DisasterAnalysisOutput,
    PlanPresentationOutput,
)

logger = logging.getLogger(__name__)


class CrewAIError(Exception):
    """CrewAI执行错误，不降级直接暴露"""
    pass


def get_default_llm() -> LLM:
    """获取默认LLM配置，从环境变量读取"""
    llm_model: str = os.getenv("LLM_MODEL", "/models/openai/gpt-oss-120b")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "dummy_key")
    
    model: str = llm_model if llm_model.startswith("openai/") else f"openai/{llm_model}"
    
    logger.info(f"[CrewAI] 初始化LLM: model={model}, base_url={openai_base_url}")
    
    return LLM(
        model=model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0.3,
        timeout=180,
    )


class DisasterAnalysisCrew:
    """
    灾情分析Crew - 从自然语言描述中提取结构化灾情信息
    
    无fallback：LLM失败直接抛CrewAIError
    """
    
    def __init__(self, llm: LLM | None = None) -> None:
        self.llm: LLM = llm if llm is not None else get_default_llm()
    
    def _build_crew(self) -> Crew:
        """构建Crew实例"""
        analyst = create_disaster_analyst(self.llm)
        analysis_task = create_disaster_analysis_task(analyst)
        
        return Crew(
            agents=[analyst],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True,
        )
    
    async def analyze(
        self,
        recon_request: str,
        target_area: dict[str, Any] | None = None,
    ) -> DisasterAnalysisOutput:
        """
        执行灾情分析
        
        Args:
            recon_request: 自然语言侦察需求描述
            target_area: 目标区域GeoJSON
            
        Returns:
            结构化的灾情分析结果
            
        Raises:
            CrewAIError: LLM调用或解析失败时抛出
        """
        target_area_info: str = ""
        if target_area and target_area.get("type") == "Polygon":
            coords = target_area.get("coordinates", [[]])[0]
            if coords:
                center_lat: float = sum(c[1] for c in coords) / len(coords)
                center_lng: float = sum(c[0] for c in coords) / len(coords)
                target_area_info = f"目标区域中心：({center_lat:.4f}, {center_lng:.4f})"
        
        inputs: dict[str, str] = {
            "recon_request": recon_request,
            "target_area_info": target_area_info or "未提供具体区域",
        }
        
        crew = self._build_crew()
        
        logger.info(f"[DisasterAnalysisCrew] 开始LLM分析: {recon_request[:80]}...")
        
        result = await crew.kickoff_async(inputs=inputs)
        
        logger.info("[DisasterAnalysisCrew] LLM调用完成，解析结果")
        
        return self._parse_result(result)
    
    def _parse_result(self, crew_output: Any) -> DisasterAnalysisOutput:
        """
        解析Crew输出为结构化对象
        
        Raises:
            CrewAIError: 解析失败时抛出
        """
        tasks_output = getattr(crew_output, "tasks_output", [])
        
        if not tasks_output:
            raise CrewAIError("Crew输出为空，无tasks_output")
        
        task_output = tasks_output[0]
        
        if hasattr(task_output, "pydantic") and task_output.pydantic is not None:
            logger.info("[DisasterAnalysisCrew] 使用pydantic输出")
            return task_output.pydantic
        
        if hasattr(task_output, "json_dict") and task_output.json_dict is not None:
            logger.info("[DisasterAnalysisCrew] 使用json_dict输出")
            return DisasterAnalysisOutput.model_validate(task_output.json_dict)
        
        if hasattr(task_output, "raw"):
            raw = task_output.raw
            logger.info(f"[DisasterAnalysisCrew] 使用raw输出: type={type(raw)}")
            if isinstance(raw, dict):
                return DisasterAnalysisOutput.model_validate(raw)
            cleaned: str = self._clean_json_string(str(raw))
            return DisasterAnalysisOutput.model_validate_json(cleaned)
        
        raise CrewAIError(f"无法解析Crew输出: {type(task_output)}")
    
    def _clean_json_string(self, text: str) -> str:
        """清理可能包含markdown代码块的JSON字符串"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start_idx: int = 1 if lines[0].startswith("```") else 0
            end_idx: int = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.startswith("```"):
                    end_idx = i
                    break
            text = "\n".join(lines[start_idx:end_idx])
        return text


class PlanPresentationCrew:
    """
    计划呈报Crew - 将技术性侦察计划转化为指挥员级别的报告
    
    无fallback：LLM失败直接抛CrewAIError
    """
    
    def __init__(self, llm: LLM | None = None) -> None:
        self.llm: LLM = llm if llm is not None else get_default_llm()
    
    def _build_crew(self) -> Crew:
        """构建Crew实例"""
        presenter = create_plan_presenter(self.llm)
        presentation_task = create_plan_presentation_task(presenter)
        
        return Crew(
            agents=[presenter],
            tasks=[presentation_task],
            process=Process.sequential,
            verbose=True,
        )
    
    async def present(
        self,
        recon_plan: dict[str, Any],
    ) -> PlanPresentationOutput:
        """
        生成指挥员简报
        
        Args:
            recon_plan: 完整的侦察计划数据
            
        Returns:
            指挥员简报
            
        Raises:
            CrewAIError: LLM调用或解析失败时抛出
        """
        disaster_analysis: dict[str, Any] = recon_plan.get("disaster_analysis", {})
        timeline: dict[str, Any] = recon_plan.get("timeline", {})
        flight_plans: list[dict[str, Any]] = recon_plan.get("flight_plans", [])
        risk_assessment: dict[str, Any] = recon_plan.get("risk_assessment", {})
        
        disaster_type: str = disaster_analysis.get("disaster_type", "unknown")
        total_duration: float = timeline.get("total_duration_min", 0)
        risk_level: str = risk_assessment.get("overall_risk_level", "medium")
        
        simplified_plan: dict[str, Any] = {
            "mission_phases": recon_plan.get("mission_phases", []),
            "flight_plans": [
                {
                    "task_name": fp.get("task_name"),
                    "device_name": fp.get("device_name"),
                    "scan_pattern": fp.get("scan_pattern"),
                    "altitude_m": fp.get("flight_parameters", {}).get("altitude_m"),
                    "duration_min": fp.get("statistics", {}).get("total_duration_min"),
                }
                for fp in flight_plans
            ],
            "milestones": timeline.get("milestones", []),
            "contingency_plans": risk_assessment.get("contingency_plans", [])[:3],
        }
        
        inputs: dict[str, Any] = {
            "recon_plan_data": json.dumps(simplified_plan, ensure_ascii=False, indent=2),
            "disaster_type": disaster_type,
            "total_duration_min": total_duration,
            "flight_count": len(flight_plans),
            "risk_level": risk_level,
        }
        
        crew = self._build_crew()
        
        logger.info(f"[PlanPresentationCrew] 开始生成简报: {len(flight_plans)}条航线")
        
        result = await crew.kickoff_async(inputs=inputs)
        
        logger.info("[PlanPresentationCrew] LLM调用完成，解析结果")
        
        return self._parse_result(result)
    
    def _parse_result(self, crew_output: Any) -> PlanPresentationOutput:
        """
        解析Crew输出为结构化对象
        
        Raises:
            CrewAIError: 解析失败时抛出
        """
        tasks_output = getattr(crew_output, "tasks_output", [])
        
        if not tasks_output:
            raise CrewAIError("Crew输出为空，无tasks_output")
        
        task_output = tasks_output[0]
        
        if hasattr(task_output, "pydantic") and task_output.pydantic is not None:
            logger.info("[PlanPresentationCrew] 使用pydantic输出")
            return task_output.pydantic
        
        if hasattr(task_output, "json_dict") and task_output.json_dict is not None:
            logger.info("[PlanPresentationCrew] 使用json_dict输出")
            return PlanPresentationOutput.model_validate(task_output.json_dict)
        
        if hasattr(task_output, "raw"):
            raw = task_output.raw
            logger.info(f"[PlanPresentationCrew] 使用raw输出: type={type(raw)}")
            if isinstance(raw, dict):
                return PlanPresentationOutput.model_validate(raw)
            cleaned: str = self._clean_json_string(str(raw))
            return PlanPresentationOutput.model_validate_json(cleaned)
        
        raise CrewAIError(f"无法解析Crew输出: {type(task_output)}")
    
    def _clean_json_string(self, text: str) -> str:
        """清理可能包含markdown代码块的JSON字符串"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start_idx: int = 1 if lines[0].startswith("```") else 0
            end_idx: int = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.startswith("```"):
                    end_idx = i
                    break
            text = "\n".join(lines[start_idx:end_idx])
        return text


class ReconSchedulerCrew:
    """
    侦察调度Crew集成 - 整合灾情分析和计划呈报
    
    无fallback：任何失败直接抛出异常
    """
    
    def __init__(self, llm: LLM | None = None) -> None:
        self.llm: LLM = llm if llm is not None else get_default_llm()
        self.disaster_crew: DisasterAnalysisCrew = DisasterAnalysisCrew(self.llm)
        self.presentation_crew: PlanPresentationCrew = PlanPresentationCrew(self.llm)
    
    async def analyze_disaster(
        self,
        recon_request: str,
        target_area: dict[str, Any] | None = None,
    ) -> DisasterAnalysisOutput:
        """灾情分析，失败直接抛异常"""
        return await self.disaster_crew.analyze(recon_request, target_area)
    
    async def present_plan(
        self,
        recon_plan: dict[str, Any],
    ) -> PlanPresentationOutput:
        """计划呈报，失败直接抛异常"""
        return await self.presentation_crew.present(recon_plan)
