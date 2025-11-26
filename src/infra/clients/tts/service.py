"""TTS服务封装层。

提供简洁的API，封装TTS Provider的复杂性。
"""
from __future__ import annotations

import logging
from typing import Optional

from .base import TTSConfig, TTSResult, TTSError
from .cosyvoice_provider import CosyVoiceTTSProvider

logger = logging.getLogger(__name__)


class TTSService:
    """TTS服务：统一的语音合成入口。

    封装TTS Provider，提供简洁的API。

    用法示例::

        tts = TTSService()

        result = await tts.synthesize("你好，这是测试")
        with open("output.wav", "wb") as f:
            f.write(result.audio_data)

        await tts.close()
    """

    def __init__(self, provider: Optional[CosyVoiceTTSProvider] = None) -> None:
        """初始化TTS服务。

        Args:
            provider: TTS Provider实例，默认创建CosyVoice Provider。
        """
        self._provider = provider or CosyVoiceTTSProvider()
        self._healthy: bool = True
        logger.info("TTS服务创建完成", extra={"provider": self._provider.name})

    @property
    def provider_name(self) -> str:
        """获取当前Provider名称。"""
        return self._provider.name

    @property
    def is_healthy(self) -> bool:
        """获取服务健康状态。"""
        return self._healthy

    async def synthesize(
        self,
        text: str,
        config: TTSConfig | None = None,
    ) -> TTSResult:
        """执行语音合成。

        Args:
            text: 要合成的文本。
            config: 合成配置，None使用默认配置。

        Returns:
            TTSResult: 合成结果。

        Raises:
            TTSError: 合成失败时抛出。
        """
        if not text or not text.strip():
            raise TTSError(message="合成文本不能为空", provider=self._provider.name)

        try:
            result = await self._provider.synthesize(text, config)
            self._healthy = True
            return result
        except TTSError:
            self._healthy = False
            raise
        except Exception as e:
            self._healthy = False
            raise TTSError(
                message=f"TTS合成失败: {e}",
                provider=self._provider.name,
                cause=e,
            ) from e

    async def synthesize_to_base64(
        self,
        text: str,
        config: TTSConfig | None = None,
    ) -> str:
        """执行语音合成并返回Base64编码。

        Args:
            text: 要合成的文本。
            config: 合成配置。

        Returns:
            str: Base64编码的音频数据。
        """
        import base64

        result = await self.synthesize(text, config)
        return base64.b64encode(result.audio_data).decode("utf-8")

    async def health_check(self) -> bool:
        """执行健康检查。"""
        try:
            self._healthy = await self._provider.health_check()
            return self._healthy
        except Exception as e:
            logger.warning("TTS健康检查失败: %s", str(e))
            self._healthy = False
            return False

    async def close(self) -> None:
        """关闭服务，释放资源。"""
        await self._provider.close()
        logger.info("TTS服务已关闭")
