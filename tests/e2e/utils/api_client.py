"""
API客户端封装

提供类型安全的API调用方法。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from uuid import UUID

import httpx


@dataclass
class AnalyzeResult:
    """分析结果"""
    success: bool
    status: str
    task_id: str
    recommended_scheme: Optional[Dict[str, Any]] = None
    scheme_explanation: Optional[str] = None
    pareto_solutions: Optional[List[Dict[str, Any]]] = None
    trace: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    execution_time_ms: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None


class EmergencyAIClient:
    """EmergencyAI API客户端"""
    
    def __init__(self, client: httpx.AsyncClient, prefix: str = "/api/v2/ai"):
        self.client = client
        self.prefix = prefix
    
    async def submit_analyze(
        self,
        event_id: str,
        scenario_id: str,
        disaster_description: str,
        structured_input: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """提交分析任务"""
        payload = {
            "event_id": event_id,
            "scenario_id": scenario_id,
            "disaster_description": disaster_description,
        }
        if structured_input:
            payload["structured_input"] = structured_input
        if constraints:
            payload["constraints"] = constraints
        
        resp = await self.client.post(f"{self.prefix}/emergency-analyze", json=payload)
        resp.raise_for_status()
        return resp.json()
    
    async def get_result(self, task_id: str) -> Dict[str, Any]:
        """获取分析结果"""
        resp = await self.client.get(f"{self.prefix}/emergency-analyze/{task_id}")
        resp.raise_for_status()
        return resp.json()
    
    async def get_result_by_event(self, event_id: str) -> Dict[str, Any]:
        """通过事件ID获取分析结果"""
        resp = await self.client.get(f"{self.prefix}/emergency-analyze/by-event/{event_id}")
        resp.raise_for_status()
        return resp.json()
    
    async def poll_result(
        self,
        task_id: str,
        max_wait: int = 60,
        interval: float = 2.0,
    ) -> AnalyzeResult:
        """轮询分析结果"""
        import time
        start = time.time()
        
        while time.time() - start < max_wait:
            try:
                result = await self.get_result(task_id)
                status = result.get("status", "processing")
                
                if status in ("completed", "failed", "interrupted"):
                    return AnalyzeResult(
                        success=result.get("success", False),
                        status=status,
                        task_id=task_id,
                        recommended_scheme=result.get("recommended_scheme"),
                        scheme_explanation=result.get("scheme_explanation"),
                        pareto_solutions=result.get("pareto_solutions"),
                        trace=result.get("trace"),
                        errors=result.get("errors"),
                        execution_time_ms=result.get("execution_time_ms"),
                        raw=result,
                    )
            except httpx.HTTPStatusError:
                pass
            
            await asyncio.sleep(interval)
        
        return AnalyzeResult(
            success=False,
            status="timeout",
            task_id=task_id,
            errors=["轮询超时"],
        )
    
    async def analyze_and_wait(
        self,
        event_id: str,
        scenario_id: str,
        disaster_description: str,
        structured_input: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        max_wait: int = 60,
    ) -> AnalyzeResult:
        """提交分析并等待结果"""
        submit_resp = await self.submit_analyze(
            event_id=event_id,
            scenario_id=scenario_id,
            disaster_description=disaster_description,
            structured_input=structured_input,
            constraints=constraints,
        )
        task_id = submit_resp.get("task_id")
        if not task_id:
            return AnalyzeResult(
                success=False,
                status="submit_failed",
                task_id="",
                errors=["提交失败，无task_id"],
            )
        
        return await self.poll_result(task_id, max_wait=max_wait)
    
    async def confirm_scheme(
        self,
        task_id: str,
        team_ids: Optional[List[str]] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """确认部署方案"""
        payload: Dict[str, Any] = {}
        if team_ids:
            payload["team_ids"] = team_ids
        if event_id:
            payload["event_id"] = event_id
        
        resp = await self.client.post(
            f"{self.prefix}/emergency-analyze/{task_id}/confirm",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        resp = await self.client.get(f"{self.prefix}/health")
        resp.raise_for_status()
        return resp.json()


class FrontendAPIClient:
    """前端API客户端"""
    
    def __init__(self, client: httpx.AsyncClient, prefix: str = "/api/v1"):
        self.client = client
        self.prefix = prefix
    
    async def get_entities(
        self,
        layer_code: Optional[str] = None,
        entity_type: Optional[str] = None,
        scenario_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取实体列表"""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if layer_code:
            params["layerCode"] = layer_code
        if entity_type:
            params["type"] = entity_type
        if scenario_id:
            params["scenarioId"] = scenario_id
        
        resp = await self.client.get(f"{self.prefix}/entities", params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def get_layers(self) -> Dict[str, Any]:
        """获取图层列表"""
        resp = await self.client.get(f"{self.prefix}/layers")
        resp.raise_for_status()
        return resp.json()
    
    async def get_units(
        self,
        scenario_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取队伍列表"""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if scenario_id:
            params["scenarioId"] = scenario_id
        
        resp = await self.client.get(f"{self.prefix}/units", params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def get_cars(
        self,
        scenario_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取车辆列表"""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if scenario_id:
            params["scenarioId"] = scenario_id
        
        resp = await self.client.get(f"{self.prefix}/cars", params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def get_overall_plan_modules(self) -> Dict[str, Any]:
        """获取总体方案模块"""
        resp = await self.client.get(f"{self.prefix}/overall-plan/modules")
        resp.raise_for_status()
        return resp.json()
    
    async def get_pending_actions(
        self,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取待处理事件"""
        params: Dict[str, Any] = {}
        if scenario_id:
            params["scenarioId"] = scenario_id
        
        resp = await self.client.get(f"{self.prefix}/pending-actions", params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def get_tasks(
        self,
        scenario_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取任务列表"""
        params: Dict[str, Any] = {}
        if scenario_id:
            params["scenarioId"] = scenario_id
        if status:
            params["status"] = status
        
        resp = await self.client.get(f"{self.prefix}/tasks", params=params)
        resp.raise_for_status()
        return resp.json()
