"""CrewAI Crew 组装：设备分配专家子系统

组装设备筛选和任务分配的 Crew，执行智能设备分配。
"""
import json
import logging
from typing import Any

from crewai import Crew, LLM, Process

from src.agents.reconnaissance.crewai.agents import (
    create_device_screener,
    create_mission_planner,
)
from src.agents.reconnaissance.crewai.tasks import (
    create_device_screening_task,
    create_device_assignment_task,
    DeviceScreeningOutput,
    DeviceAssignmentOutput,
)
from src.agents.reconnaissance.state import DeviceAssignment, DeviceInfo

logger = logging.getLogger(__name__)


class DeviceAssignmentError(Exception):
    """设备分配过程出错"""
    pass


class DeviceAssignmentCrew:
    """设备分配专家 Crew
    
    封装 CrewAI Crew 的创建和执行，提供简单的 API。
    """
    
    def __init__(self, llm: LLM | None = None):
        """初始化 Crew
        
        Args:
            llm: 语言模型实例。如果为 None，使用默认配置。
        """
        if llm is None:
            import os
            # vLLM返回的model id是完整路径，如"/models/openai/gpt-oss-120b"
            # LiteLLM需要格式: openai/<vllm_model_id>
            llm_model = os.getenv("LLM_MODEL", "/models/openai/gpt-oss-120b")
            openai_base_url = os.getenv("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
            openai_api_key = os.getenv("OPENAI_API_KEY", "dummy_key")
            
            if llm_model.startswith("openai/"):
                model = llm_model
            else:
                model = f"openai/{llm_model}"
            
            llm = LLM(
                model=model,
                base_url=openai_base_url,
                api_key=openai_api_key,
                temperature=0.3,
                timeout=180,
            )
        
        self.llm = llm
        self._crew: Crew | None = None
    
    def _build_crew(self) -> Crew:
        """构建 Crew"""
        screener = create_device_screener(self.llm)
        planner = create_mission_planner(self.llm)
        
        screening_task = create_device_screening_task(screener)
        assignment_task = create_device_assignment_task(planner, context_task=screening_task)
        
        return Crew(
            agents=[screener, planner],
            tasks=[screening_task, assignment_task],
            process=Process.sequential,
            verbose=True,
        )
    
    async def run(
        self,
        devices: list[dict[str, Any]],
        targets: list[dict[str, Any]],
        disaster_type: str = "earthquake",
    ) -> tuple[list[DeviceInfo], list[DeviceAssignment], str]:
        """执行设备分配
        
        Args:
            devices: 全部可用设备列表
            targets: 侦察目标列表（已排序）
            disaster_type: 当前灾害类型
            
        Returns:
            (筛选后的设备列表, 分配结果列表, 解释文本)
        """
        if not devices:
            return [], [], "无可用设备"
        
        if not targets:
            return [], [], "无侦察目标"
        
        # 准备输入数据
        devices_json = json.dumps(devices, ensure_ascii=False, indent=2)
        targets_json = json.dumps(
            [
                {
                    "target_id": t.get("target_id"),
                    "name": t.get("name"),
                    "priority": t.get("priority"),
                    "score": t.get("score"),
                    "features": t.get("features", {}),
                    "_target_type": t.get("_target_type"),
                    "_area_type": t.get("_area_type"),
                }
                for t in targets
            ],
            ensure_ascii=False,
            indent=2,
        )
        
        inputs = {
            "devices_data": devices_json,
            "targets_data": targets_json,
            "disaster_type": disaster_type,
        }
        
        # 构建并执行 Crew
        crew = self._build_crew()
        
        try:
            logger.info("[DeviceAssignmentCrew] Starting crew execution")
            result = await crew.kickoff_async(inputs=inputs)
            logger.info("[DeviceAssignmentCrew] Crew execution completed")
        except Exception as e:
            logger.exception("[DeviceAssignmentCrew] Crew execution failed")
            raise DeviceAssignmentError(f"Crew 执行失败: {e}") from e
        
        # 解析结果
        return self._parse_result(result)
    
    def _parse_result(
        self,
        crew_output: Any,
    ) -> tuple[list[DeviceInfo], list[DeviceAssignment], str]:
        """解析 Crew 输出"""
        try:
            tasks_output = getattr(crew_output, "tasks_output", [])
            
            if len(tasks_output) < 2:
                raise DeviceAssignmentError(
                    f"Expected 2 task outputs, got {len(tasks_output)}"
                )
            
            # 解析设备筛选结果
            screening_output = self._extract_task_output(tasks_output[0], DeviceScreeningOutput)
            
            # 解析设备分配结果
            assignment_output = self._extract_task_output(tasks_output[1], DeviceAssignmentOutput)
            
            # 转换为内部数据结构
            recon_devices: list[DeviceInfo] = []
            for d in screening_output.recon_devices:
                recon_devices.append(
                    DeviceInfo(
                        device_id=d.device_id,
                        code=d.code,
                        name=d.name,
                        device_type=d.device_type,
                        in_vehicle_id=None,
                        status="available",
                    )
                )
            
            assignments: list[DeviceAssignment] = []
            for a in assignment_output.assignments:
                assignments.append(
                    DeviceAssignment(
                        device_id=a.device_id,
                        device_name=a.device_name,
                        device_type=a.device_type,
                        target_id=a.target_id,
                        target_name=a.target_name,
                        priority=a.priority,
                        reason=a.reason,
                    )
                )
            
            explanation = assignment_output.explanation
            
            return recon_devices, assignments, explanation
            
        except DeviceAssignmentError:
            raise
        except Exception as e:
            logger.exception("[DeviceAssignmentCrew] Failed to parse crew output")
            raise DeviceAssignmentError(f"解析 Crew 输出失败: {e}") from e
    
    def _extract_task_output(self, task_output: Any, model_class: type) -> Any:
        """从 task output 中提取结构化数据"""
        if hasattr(task_output, "pydantic") and task_output.pydantic is not None:
            return task_output.pydantic
        
        if hasattr(task_output, "json_dict") and task_output.json_dict is not None:
            return model_class.model_validate(task_output.json_dict)
        
        if hasattr(task_output, "raw"):
            raw = task_output.raw
            if isinstance(raw, dict):
                return model_class.model_validate(raw)
            return model_class.model_validate_json(self._clean_json_string(str(raw)))
        
        return model_class.model_validate_json(self._clean_json_string(str(task_output)))
    
    def _clean_json_string(self, text: str) -> str:
        """清理可能包含 markdown 代码块的 JSON 字符串"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start_idx = 1 if lines[0].startswith("```") else 0
            end_idx = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.startswith("```"):
                    end_idx = i
                    break
            text = "\n".join(lines[start_idx:end_idx])
        return text


async def run_device_assignment_crew(
    devices: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    disaster_type: str = "earthquake",
    llm: LLM | None = None,
) -> tuple[list[DeviceInfo], list[DeviceAssignment], str]:
    """便捷函数：执行设备分配 Crew
    
    Args:
        devices: 全部可用设备列表
        targets: 侦察目标列表
        disaster_type: 灾害类型
        llm: 语言模型实例（可选）
        
    Returns:
        (筛选后的设备列表, 分配结果列表, 解释文本)
    """
    crew = DeviceAssignmentCrew(llm=llm)
    return await crew.run(devices, targets, disaster_type)
