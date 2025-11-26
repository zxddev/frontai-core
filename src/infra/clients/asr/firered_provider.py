"""FireRedASR-LLM-L 提供方实现（HTTP API）。

基于 HTTP API 的语音转写服务，兼容 OpenAI 格式。
服务地址默认为 http://192.168.31.50:8002
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from typing import Optional

from .base import ASRConfig, ASRError, ASRProvider, ASRResult

logger = logging.getLogger(__name__)


class FireRedASRProvider(ASRProvider):
    """FireRedASR-LLM-L 提供方。

    通过 HTTP API 调用本地部署的 FireRedASR 服务。
    """

    def __init__(
        self,
        api_url: str | None = None,
        model: str = "fireredasr-llm-l",
        timeout_seconds: float | None = None,
    ) -> None:
        """初始化 FireRedASR Provider。

        Args:
            api_url: API服务地址，默认从环境变量 FIRERED_ASR_URL 读取。
            model: 模型名称，默认 fireredasr-llm-l。
            timeout_seconds: 请求超时秒数，默认60秒。
        """
        self._url = api_url or os.getenv("FIRERED_ASR_URL", "http://192.168.31.50:8002")
        self._model = model

        if timeout_seconds is not None:
            self._timeout_seconds = max(30.0, timeout_seconds)
        else:
            timeout_raw = os.getenv("FIRERED_ASR_TIMEOUT_SECONDS", "60")
            try:
                self._timeout_seconds = max(30.0, float(timeout_raw))
            except ValueError:
                self._timeout_seconds = 60.0

        self._session: Optional["aiohttp.ClientSession"] = None

        logger.info(
            "FireRedASR初始化完成",
            extra={
                "url": self._url,
                "model": model,
                "timeout_seconds": self._timeout_seconds,
            },
        )

    @property
    def name(self) -> str:
        return "firered"

    @property
    def priority(self) -> int:
        return 200  # 高于阿里云(100)和原本地FunASR(0)

    async def _get_session(self) -> "aiohttp.ClientSession":
        """获取或创建 aiohttp session。"""
        import aiohttp

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def recognize(
        self, audio_data: bytes, config: ASRConfig | None = None
    ) -> ASRResult:
        """使用 FireRedASR 进行语音转写。

        Args:
            audio_data: 音频数据（支持 PCM/WAV 等格式）。
            config: 识别配置。

        Returns:
            ASRResult: 识别结果。
        """
        try:
            import aiohttp
        except ImportError as e:
            raise ImportError("请安装 aiohttp: pip install aiohttp") from e

        cfg = config or ASRConfig()
        start_ts = time.time()

        url = f"{self._url}/v1/audio/transcriptions"

        logger.info(
            "FireRedASR开始识别",
            extra={"url": url, "size": len(audio_data), "format": cfg.format},
        )

        try:
            session = await self._get_session()

            # 根据格式确定文件扩展名
            ext = "wav" if cfg.format in ("wav", "pcm") else cfg.format
            filename = f"audio.{ext}"

            # 构建 multipart/form-data
            data = aiohttp.FormData()
            data.add_field(
                "file",
                io.BytesIO(audio_data),
                filename=filename,
                content_type=f"audio/{ext}",
            )
            data.add_field("model", self._model)

            async with session.post(url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ASRError(
                        message=f"FireRedASR请求失败: HTTP {response.status} - {error_text}",
                        provider=self.name,
                    )

                result_json = await response.json()
                text = result_json.get("text", "")

        except aiohttp.ClientError as e:
            raise ASRError(
                message=f"FireRedASR网络错误: {e}",
                provider=self.name,
                cause=e,
            ) from e
        except asyncio.TimeoutError:
            raise ASRError(
                message=f"FireRedASR超时({self._timeout_seconds}s)",
                provider=self.name,
            ) from None
        except ASRError:
            raise
        except Exception as e:
            raise ASRError(
                message=f"FireRedASR识别失败: {e}",
                provider=self.name,
                cause=e,
            ) from e

        latency_ms = int((time.time() - start_ts) * 1000)
        result = ASRResult(
            text=text,
            confidence=1.0,
            is_final=True,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={"model": self._model, "url": self._url},
        )

        logger.info(
            "FireRedASR识别完成",
            extra={
                "latency_ms": latency_ms,
                "text_preview": text[:50] if text else "",
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
                        is_healthy = (
                            data.get("status") == "healthy"
                            and data.get("model_loaded", False)
                        )
                        if not is_healthy:
                            logger.warning(
                                "FireRedASR健康检查: 服务异常",
                                extra={"response": data},
                            )
                        return is_healthy
                    return False
        except Exception as e:
            logger.warning("FireRedASR健康检查失败: %s", str(e))
            return False

    async def close(self) -> None:
        """关闭 HTTP session。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
