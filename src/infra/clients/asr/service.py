"""ASR服务封装层。

提供简洁的API，封装ASRManager的复杂性。
"""
from __future__ import annotations

import logging

from .base import ASRConfig, ASRResult
from .manager import ASRManager

logger = logging.getLogger(__name__)


class ASRService:
    """ASR服务：统一的语音识别入口。

    封装ASRManager，提供简洁的API和生命周期管理。

    用法示例::

        asr = ASRService()
        await asr.start()  # 启动健康检查

        result = await asr.recognize(audio_data)
        print(result.text)

        await asr.stop()  # 停止健康检查
    """

    def __init__(self) -> None:
        """初始化ASR服务。"""
        self._manager = ASRManager()
        logger.info("ASR服务创建完成")

    @property
    def provider_name(self) -> str:
        """获取当前主Provider名称。"""
        return f"{self._manager._primary}(primary)"

    @property
    def provider_status(self) -> dict[str, bool]:
        """获取所有Provider的健康状态。"""
        return self._manager.provider_status

    async def recognize(
        self, audio_data: bytes, config: ASRConfig | None = None
    ) -> ASRResult:
        """执行语音识别。

        Args:
            audio_data: 原始音频数据（16k/16bit/mono PCM）。
            config: 识别配置，None使用默认配置。

        Returns:
            ASRResult: 识别结果。

        Raises:
            ASRError: 识别失败时抛出。
        """
        return await self._manager.recognize(audio_data, config)

    async def start(self) -> None:
        """启动ASR服务（启动健康检查）。"""
        await self._manager.start_health_check()
        logger.info("ASR服务已启动")

    async def stop(self) -> None:
        """停止ASR服务（停止健康检查）。"""
        await self._manager.stop_health_check()
        logger.info("ASR服务已停止")

    # 兼容旧接口
    async def start_health_check(self) -> None:
        """启动健康检查（兼容旧接口）。"""
        await self.start()

    async def stop_health_check(self) -> None:
        """停止健康检查（兼容旧接口）。"""
        await self.stop()
