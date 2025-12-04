"""鼎桥机器狗适配器 HTTP 客户端。

通过 adapter-hub 服务控制机器狗设备，支持移动指令和对话指令。
接口地址：/adapter-hub/api/v3/device-access/control
"""
from __future__ import annotations

import logging
import re
from typing import Any, Mapping

import httpx

logger = logging.getLogger(__name__)


class AdapterHubError(RuntimeError):
    """适配器基础异常"""


class AdapterHubConfigurationError(AdapterHubError):
    """适配器配置缺失"""


class AdapterHubRequestError(AdapterHubError):
    """适配器网络请求失败"""


class AdapterHubResponseError(AdapterHubError):
    """适配器返回业务错误"""


class AdapterHubClient:
    """机器狗控制 HTTP 客户端
    
    封装与 adapter-hub 服务的 HTTP 通信，发送设备控制命令。
    """

    def __init__(self, base_url: str | None, timeout: float = 5.0) -> None:
        """初始化客户端
        
        Args:
            base_url: adapter-hub 服务基础地址，如 http://192.168.31.40:8082
            timeout: 请求超时秒数
        """
        if not base_url:
            raise AdapterHubConfigurationError("adapter_hub_base_url 未配置")
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout, connect=timeout)

    async def send_command(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        """发送设备控制命令
        
        Args:
            command: 设备命令字典，包含 deviceId/deviceVendor/commandType/params
            
        Returns:
            适配器返回的响应数据
            
        Raises:
            AdapterHubRequestError: 网络请求失败
            AdapterHubResponseError: 业务错误或响应解析失败
        """
        path = "/adapter-hub/api/v3/device-access/control"
        logger.info(
            "adapter_hub_send_command",
            extra={"base_url": self._base_url, "path": path, "command": dict(command)},
        )
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                trust_env=False,
            ) as client:
                resp = await client.post(path, json=dict(command))
        except httpx.HTTPError as exc:
            logger.error("adapter_hub_request_failed", extra={"error": str(exc)})
            raise AdapterHubRequestError(f"请求失败: {exc}") from exc

        logger.info(
            "adapter_hub_response",
            extra={"status_code": resp.status_code, "text": resp.text[:500]},
        )

        try:
            data = resp.json()
        except ValueError as exc:
            raise AdapterHubResponseError("响应非有效 JSON") from exc

        if resp.status_code >= 400:
            raise AdapterHubResponseError(f"HTTP {resp.status_code}: {data}")

        if isinstance(data, dict):
            code = data.get("code")
            if code is not None and str(code) not in {"0", "200"}:
                raise AdapterHubResponseError(f"业务错误: {data}")

        return data


# 中文动作到标准动作的映射表
_ROBOTDOG_ACTION_MAP: dict[str, str] = {
    # 前进
    "forward": "forward",
    "前进": "forward",
    "向前": "forward",
    # 后退
    "back": "back",
    "后退": "back",
    "向后": "back",
    # 起立
    "up": "up",
    "起立": "up",
    "站立": "up",
    "站起来": "up",
    # 趴下
    "down": "down",
    "趴下": "down",
    "坐下": "down",
    # 左转
    "turnLeft": "turnLeft",
    "左转": "turnLeft",
    # 右转
    "turnRight": "turnRight",
    "右转": "turnRight",
    # 停止
    "stop": "stop",
    "停止": "stop",
    # 急停
    "forceStop": "forceStop",
    "急停": "forceStop",
}


def normalize_robotdog_action(action: str) -> str:
    """将中文或自然语言动作映射为标准动作枚举
    
    Args:
        action: 用户输入的动作，如"前进"、"forward"
        
    Returns:
        标准化动作字符串，如 forward/back/up/down/turnLeft/turnRight/stop/forceStop
        
    Raises:
        ValueError: 不支持的动作
    """
    if not action:
        raise ValueError("动作不能为空")
    key = re.sub(r"[\s_\-]", "", action.strip().lower())
    normalized = _ROBOTDOG_ACTION_MAP.get(key) or _ROBOTDOG_ACTION_MAP.get(action.strip())
    if not normalized:
        raise ValueError(f"不支持的动作: {action}")
    return normalized


def build_robotdog_command(device_id: str, action: str, control_target: str = "main") -> dict[str, Any]:
    """构造鼎桥机器狗移动命令
    
    Args:
        device_id: 设备ID，如 "11"
        action: 动作，支持中文或英文，如"前进"、"forward"
        control_target: 控制目标，默认 "main"
        
    Returns:
        符合 adapter-hub 协议的命令字典
    """
    if not device_id:
        raise ValueError("device_id 不能为空")
    normalized_action = normalize_robotdog_action(action)
    return {
        "deviceId": str(device_id),
        "deviceVendor": "dqDog",
        "controlTarget": control_target,
        "commandType": "move",
        "params": {"action": normalized_action},
    }


def build_robotdog_talk_command(device_id: str, text: str) -> dict[str, Any]:
    """构造鼎桥机器狗对话命令
    
    Args:
        device_id: 设备ID
        text: 对话文本，如"识别前方目标"
        
    Returns:
        符合 adapter-hub 协议的命令字典
    """
    if not device_id:
        raise ValueError("device_id 不能为空")
    if not text:
        raise ValueError("对话文本不能为空")
    return {
        "deviceId": str(device_id),
        "deviceVendor": "dqDog",
        "commandType": "talk",
        "params": {"text": text},
    }
