"""CosyVoice 2.0 TTS 提供方实现。

基于 HTTP API 的语音合成服务。
服务地址默认为 http://192.168.31.50:10097
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from typing import Optional

from .base import TTSConfig, TTSError, TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class CosyVoiceTTSProvider(TTSProvider):
    """CosyVoice 2.0 TTS 提供方。

    通过 HTTP API 调用本地部署的 CosyVoice 服务。
    """

    def __init__(
        self,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """初始化 CosyVoice TTS Provider。

        Args:
            api_url: API服务地址，默认从环境变量 COSYVOICE_URL 读取。
            timeout_seconds: 请求超时秒数，默认30秒。
        """
        self._url = api_url or os.getenv("COSYVOICE_URL", "http://192.168.31.50:10097")

        if timeout_seconds is not None:
            self._timeout_seconds = max(10.0, timeout_seconds)
        else:
            timeout_raw = os.getenv("COSYVOICE_TIMEOUT_SECONDS", "30")
            try:
                self._timeout_seconds = max(10.0, float(timeout_raw))
            except ValueError:
                self._timeout_seconds = 30.0

        self._session: Optional["aiohttp.ClientSession"] = None

        logger.info(
            "CosyVoice TTS初始化完成",
            extra={
                "url": self._url,
                "timeout_seconds": self._timeout_seconds,
            },
        )

    @property
    def name(self) -> str:
        return "cosyvoice"

    @property
    def priority(self) -> int:
        return 100

    async def _get_session(self) -> "aiohttp.ClientSession":
        """获取或创建 aiohttp session。"""
        import aiohttp

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def synthesize(
        self, text: str, config: TTSConfig | None = None
    ) -> TTSResult:
        """使用 CosyVoice 进行语音合成。

        Args:
            text: 要合成的文本。
            config: 合成配置。

        Returns:
            TTSResult: 合成结果。
        """
        try:
            import aiohttp
        except ImportError as e:
            raise ImportError("请安装 aiohttp: pip install aiohttp") from e

        cfg = config or TTSConfig()
        start_ts = time.time()

        url = f"{self._url}/v1/tts/generate"

        payload = {
            "text": text,
            "instruct": cfg.instruct,
            "speed": cfg.speed,
            "format": cfg.format,
        }

        logger.info(
            "CosyVoice TTS开始合成",
            extra={"url": url, "text_length": len(text), "speed": cfg.speed},
        )

        try:
            session = await self._get_session()

            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise TTSError(
                        message=f"CosyVoice请求失败: HTTP {response.status} - {error_text}",
                        provider=self.name,
                    )

                result_json = await response.json()
                audio_base64 = result_json.get("audio", "")

                if not audio_base64:
                    raise TTSError(
                        message="CosyVoice返回空音频数据",
                        provider=self.name,
                    )

                audio_data = base64.b64decode(audio_base64)

        except aiohttp.ClientError as e:
            raise TTSError(
                message=f"CosyVoice网络错误: {e}",
                provider=self.name,
                cause=e,
            ) from e
        except asyncio.TimeoutError:
            raise TTSError(
                message=f"CosyVoice超时({self._timeout_seconds}s)",
                provider=self.name,
            ) from None
        except TTSError:
            raise
        except Exception as e:
            raise TTSError(
                message=f"CosyVoice合成失败: {e}",
                provider=self.name,
                cause=e,
            ) from e

        latency_ms = int((time.time() - start_ts) * 1000)

        # 估算音频时长（WAV格式：16-bit, 22050Hz, mono）
        duration_ms = 0
        if cfg.format == "wav" and len(audio_data) > 44:
            # WAV 头部44字节，剩余是音频数据
            audio_samples = (len(audio_data) - 44) // 2  # 16-bit = 2 bytes
            duration_ms = int(audio_samples / cfg.sample_rate * 1000)

        result = TTSResult(
            audio_data=audio_data,
            format=cfg.format,
            sample_rate=cfg.sample_rate,
            duration_ms=duration_ms,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={"url": self._url, "text_length": len(text)},
        )

        logger.info(
            "CosyVoice TTS合成完成",
            extra={
                "latency_ms": latency_ms,
                "audio_size": len(audio_data),
                "duration_ms": duration_ms,
            },
        )
        return result

    async def health_check(self) -> bool:
        """健康检查：调用 /health 接口。"""
        try:
            import aiohttp
        except ImportError:
            return False

        url = f"{self._url}/health"

        try:
            session = await self._get_session()
            async with asyncio.timeout(10.0):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        is_healthy = data.get("status") == "healthy"
                        if not is_healthy:
                            logger.warning(
                                "CosyVoice健康检查: 服务异常",
                                extra={"response": data},
                            )
                        return is_healthy
                    return False
        except Exception as e:
            logger.warning("CosyVoice健康检查失败: %s", str(e))
            return False

    async def close(self) -> None:
        """关闭 HTTP session。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
