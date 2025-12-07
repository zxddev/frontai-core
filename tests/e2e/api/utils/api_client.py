"""
API测试客户端

提供统一的HTTP请求封装，包含日志记录和响应时间追踪。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 配置
BASE_URL = "http://localhost:8000"
AI_PREFIX = "/api/v2/ai"
ROUTING_PREFIX = "/api/v2/routing"
DEFAULT_TIMEOUT = 60.0


class APIClient:
    """API测试客户端"""
    
    def __init__(self, base_url: str = BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "APIClient":
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.aclose()
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with APIClient()' context.")
        return self._client
    
    async def request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        expected_status: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        发送HTTP请求并记录详细日志
        
        Returns:
            包含status_code, response, elapsed_ms的字典
        """
        start_time = time.time()
        
        logger.info(f"[REQUEST] {method} {path}")
        if json:
            logger.debug(f"[REQUEST BODY] {json}")
        
        try:
            resp = await self.client.request(method, path, json=json, params=params)
            elapsed_ms = (time.time() - start_time) * 1000
            
            try:
                response_data = resp.json()
            except Exception:
                response_data = {"raw": resp.text[:500]}
            
            logger.info(f"[RESPONSE] {resp.status_code} ({elapsed_ms:.0f}ms)")
            
            if expected_status and resp.status_code != expected_status:
                logger.error(f"[ASSERTION FAILED] Expected {expected_status}, got {resp.status_code}")
                logger.error(f"[RESPONSE BODY] {response_data}")
            
            return {
                "status_code": resp.status_code,
                "response": response_data,
                "elapsed_ms": elapsed_ms,
                "success": resp.status_code == expected_status if expected_status else resp.is_success,
            }
            
        except httpx.TimeoutException as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"[TIMEOUT] {method} {path} after {elapsed_ms:.0f}ms")
            return {
                "status_code": 0,
                "response": {"error": "timeout", "message": str(e)},
                "elapsed_ms": elapsed_ms,
                "success": False,
            }
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"[ERROR] {method} {path}: {e}")
            return {
                "status_code": 0,
                "response": {"error": "exception", "message": str(e)},
                "elapsed_ms": elapsed_ms,
                "success": False,
            }
    
    # AI Agent 端点
    async def health_check(self) -> Dict[str, Any]:
        return await self.request("GET", f"{AI_PREFIX}/health", expected_status=200)
    
    async def reload_rules(self) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/rules/reload", expected_status=200)
    
    async def get_rules_stats(self) -> Dict[str, Any]:
        return await self.request("GET", f"{AI_PREFIX}/rules/stats", expected_status=200)
    
    async def reset_circuit_breakers(self) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/circuit-breakers/reset", expected_status=200)
    
    # EmergencyAI 端点
    async def submit_emergency_analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/emergency-analyze", json=data, expected_status=202)
    
    async def get_emergency_analyze_result(self, task_id: str) -> Dict[str, Any]:
        return await self.request("GET", f"{AI_PREFIX}/emergency-analyze/{task_id}")
    
    async def get_emergency_analyze_by_event(self, event_id: str) -> Dict[str, Any]:
        return await self.request("GET", f"{AI_PREFIX}/emergency-analyze/by-event/{event_id}")
    
    async def confirm_emergency_scheme(self, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/emergency-analyze/{task_id}/confirm", json=data)
    
    # ReconScheduler 端点
    async def submit_recon_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/recon-schedule", json=data, expected_status=202)
    
    async def get_recon_schedule_result(self, task_id: str) -> Dict[str, Any]:
        return await self.request("GET", f"{AI_PREFIX}/recon-schedule/{task_id}")
    
    async def save_recon_checkpoint(self, task_id: str) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/recon-schedule/{task_id}/checkpoint")
    
    async def resume_recon_task(self, task_id: str, checkpoint_id: str) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/recon-schedule/{task_id}/resume", json={"checkpoint_id": checkpoint_id})
    
    async def approve_recon_degradation(self, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/recon-schedule/{task_id}/approve", json=data)
    
    # RoutePlanning 端点
    async def plan_route(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{ROUTING_PREFIX}/plan", json=data)
    
    async def plan_route_with_risk_check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{ROUTING_PREFIX}/plan-with-risk-check", json=data)
    
    async def confirm_route(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{ROUTING_PREFIX}/confirm-route", json=data)
    
    # Plotting 端点
    async def plot_point(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/plotting/point", json=data)
    
    async def plot_circle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/plotting/circle", json=data)
    
    async def plot_polygon(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request("POST", f"{AI_PREFIX}/plotting/polygon", json=data)
    
    async def delete_plot(self, entity_id: str) -> Dict[str, Any]:
        return await self.request("DELETE", f"{AI_PREFIX}/plotting/{entity_id}")
    
    # 辅助方法
    async def poll_task_result(
        self,
        get_result_func: Any,
        task_id: str,
        terminal_statuses: List[str],
        max_polls: int = 30,
        interval: float = 2.0,
    ) -> Dict[str, Any]:
        """轮询任务结果直到终态"""
        for i in range(max_polls):
            result = await get_result_func(task_id)
            status = result.get("response", {}).get("status", "unknown")
            
            logger.info(f"[POLL {i+1}/{max_polls}] task_id={task_id}, status={status}")
            
            if status in terminal_statuses:
                return result
            
            await asyncio.sleep(interval)
        
        logger.warning(f"[POLL TIMEOUT] task_id={task_id} did not reach terminal status")
        return result
