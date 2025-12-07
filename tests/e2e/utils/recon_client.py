"""
ReconScheduler API客户端

封装侦察调度API的调用，简化测试代码
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ReconScheduleResponse:
    """调度响应"""
    task_id: str
    status: str
    success: bool
    flight_plans: List[Dict[str, Any]]
    execution_package: Optional[Dict[str, Any]]
    validation_results: Optional[Dict[str, Any]]
    breaker_state: str
    approval_status: Optional[str]
    degradation_options: List[str]
    progress_percent: float
    current_phase: Optional[str]
    retry_count: int
    warnings: List[str]
    errors: List[str]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReconScheduleResponse":
        return cls(
            task_id=data.get("task_id", ""),
            status=data.get("status", "unknown"),
            success=data.get("success", False),
            flight_plans=data.get("flight_plans", []),
            execution_package=data.get("execution_package"),
            validation_results=data.get("validation_results"),
            breaker_state=data.get("breaker_state", "closed"),
            approval_status=data.get("approval_status"),
            degradation_options=data.get("degradation_options", []),
            progress_percent=data.get("progress_percent", 0.0),
            current_phase=data.get("current_phase"),
            retry_count=data.get("retry_count", 0),
            warnings=data.get("warnings", []),
            errors=data.get("errors", []),
        )


class ReconSchedulerClient:
    """
    ReconScheduler API客户端
    
    用法:
        client = ReconSchedulerClient(httpx_client, "/api/v2/ai")
        
        # 提交任务
        task_id = await client.schedule(request)
        
        # 等待完成
        result = await client.schedule_and_wait(request, max_wait=120)
        
        # 审批
        await client.approve(task_id, "reduce_altitude")
    """
    
    def __init__(self, http_client: httpx.AsyncClient, api_prefix: str):
        self.client = http_client
        self.prefix = api_prefix
    
    async def schedule(
        self,
        event_id: str,
        scenario_id: str,
        recon_request: str,
        target_area: Optional[Dict[str, Any]] = None,
        disaster_context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        提交调度任务
        
        Returns:
            task_id
        """
        payload = {
            "event_id": event_id,
            "scenario_id": scenario_id,
            "recon_request": recon_request,
        }
        if target_area:
            payload["target_area"] = target_area
        if disaster_context:
            payload["disaster_context"] = disaster_context
        if config:
            payload["config"] = config
        
        resp = await self.client.post(f"{self.prefix}/recon-schedule", json=payload)
        resp.raise_for_status()
        
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"提交失败: {data.get('message')}")
        
        return data["task_id"]
    
    async def get_result(self, task_id: str) -> ReconScheduleResponse:
        """获取任务结果"""
        resp = await self.client.get(f"{self.prefix}/recon-schedule/{task_id}")
        resp.raise_for_status()
        
        return ReconScheduleResponse.from_dict(resp.json())
    
    async def schedule_and_wait(
        self,
        event_id: str,
        scenario_id: str,
        recon_request: str,
        target_area: Optional[Dict[str, Any]] = None,
        disaster_context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        max_wait: int = 120,
        poll_interval: float = 2.0,
    ) -> ReconScheduleResponse:
        """
        提交任务并等待完成
        
        Args:
            max_wait: 最大等待时间(秒)
            poll_interval: 轮询间隔(秒)
            
        Returns:
            ReconScheduleResponse
        """
        task_id = await self.schedule(
            event_id=event_id,
            scenario_id=scenario_id,
            recon_request=recon_request,
            target_area=target_area,
            disaster_context=disaster_context,
            config=config,
        )
        
        elapsed = 0.0
        while elapsed < max_wait:
            result = await self.get_result(task_id)
            
            if result.status in ("completed", "failed", "awaiting_approval"):
                return result
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        # 超时，返回最后状态
        return await self.get_result(task_id)
    
    async def approve(
        self,
        task_id: str,
        degradation_option: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        人工审批
        
        Args:
            task_id: 任务ID
            degradation_option: 降级选项
            comment: 审批备注
            
        Returns:
            响应数据
        """
        payload = {"approved_degradation": degradation_option}
        if comment:
            payload["comment"] = comment
        
        resp = await self.client.post(
            f"{self.prefix}/recon-schedule/{task_id}/approve",
            json=payload
        )
        resp.raise_for_status()
        
        return resp.json()
    
    async def checkpoint(self, task_id: str) -> Dict[str, Any]:
        """
        保存检查点
        
        Returns:
            检查点响应
        """
        resp = await self.client.post(f"{self.prefix}/recon-schedule/{task_id}/checkpoint")
        resp.raise_for_status()
        
        return resp.json()
    
    async def resume(self, task_id: str, force: bool = False) -> Dict[str, Any]:
        """
        恢复任务
        
        Returns:
            恢复响应
        """
        payload = {"force": force}
        resp = await self.client.post(
            f"{self.prefix}/recon-schedule/{task_id}/resume",
            json=payload
        )
        resp.raise_for_status()
        
        return resp.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        resp = await self.client.get(f"{self.prefix}/health")
        resp.raise_for_status()
        return resp.json()


__all__ = ["ReconSchedulerClient", "ReconScheduleResponse"]
