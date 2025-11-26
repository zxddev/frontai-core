"""阿里云百炼 fun-asr 提供方实现。

基于 DashScope SDK 的实时识别，适用于 16k 单声道 PCM/WAV。
优化点：
- 完善超时处理
- 轻量健康检查（可选静音识别或直接返回True）
- 详细错误信息
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

from .base import ASRConfig, ASRError, ASRProvider, ASRResult

logger = logging.getLogger(__name__)


class _AliyunASRCallback:
    """回调桥接：等待最终识别结果。"""

    def __init__(self, timeout_seconds: float) -> None:
        self.final_text: str = ""
        self.error: Optional[ASRError] = None
        self._done: asyncio.Event = asyncio.Event()
        self._timeout_seconds = timeout_seconds
        self._request_id: str = ""

    def on_open(self) -> None:
        logger.debug("aliyun_asr_open")

    def on_close(self) -> None:
        logger.debug("aliyun_asr_close")
        if not self._done.is_set():
            self._done.set()

    def on_complete(self) -> None:
        logger.debug("aliyun_asr_complete")
        self._done.set()

    def on_error(self, result) -> None:  # noqa: ANN001
        msg = getattr(result, "message", "unknown_error")
        req_id = getattr(result, "request_id", "")
        self._request_id = req_id
        logger.error("aliyun_asr_error: %s, request_id=%s", msg, req_id)
        self.error = ASRError(
            message=f"阿里云ASR错误: {msg}",
            provider="aliyun",
            request_id=req_id,
        )
        self._done.set()

    def on_event(self, result) -> None:  # noqa: ANN001
        try:
            sentence = result.get_sentence()
        except Exception:
            sentence = None
        if sentence and "text" in sentence:
            text = sentence.get("text", "")
            if text:
                self.final_text = text
            logger.debug("aliyun_asr_text: %s", text[:50] if text else "")

    async def wait(self) -> None:
        """等待识别完成，超时抛出异常。"""
        try:
            await asyncio.wait_for(self._done.wait(), timeout=self._timeout_seconds)
        except asyncio.TimeoutError:
            raise ASRError(
                message=f"阿里云ASR超时({self._timeout_seconds}s)",
                provider="aliyun",
                request_id=self._request_id,
            ) from None
        if self.error:
            raise self.error


class AliyunASRProvider(ASRProvider):
    """阿里云百炼 fun-asr 提供方。"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "fun-asr-realtime",
        timeout_seconds: float | None = None,
        health_check_mode: str = "silent",
    ) -> None:
        """初始化阿里云ASR Provider。

        Args:
            api_key: DashScope API Key，默认从环境变量读取。
            model: 模型名称，默认 fun-asr-realtime。
            timeout_seconds: 识别超时秒数，默认60秒。
            health_check_mode: 健康检查模式，"silent" 发送静音测试，"skip" 直接返回True。
        """
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if not self._api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置")
        self._model = model
        self._health_check_mode = health_check_mode

        # 超时配置
        if timeout_seconds is not None:
            self._timeout_seconds = max(30.0, timeout_seconds)
        else:
            timeout_raw = os.getenv("ALIYUN_ASR_TIMEOUT_SECONDS", "60")
            try:
                self._timeout_seconds = max(30.0, float(timeout_raw))
            except ValueError:
                self._timeout_seconds = 60.0

        # 延迟导入 SDK
        try:
            import dashscope

            dashscope.api_key = self._api_key
            self._dashscope = dashscope
        except ImportError as e:
            raise ImportError("请安装 dashscope: pip install dashscope") from e

        logger.info(
            "阿里云ASR初始化完成",
            extra={
                "model": model,
                "timeout_seconds": self._timeout_seconds,
                "health_check_mode": health_check_mode,
            },
        )

    @property
    def name(self) -> str:
        return "aliyun"

    @property
    def priority(self) -> int:
        return 100

    async def recognize(
        self, audio_data: bytes, config: ASRConfig | None = None
    ) -> ASRResult:
        """使用阿里云 fun-asr 进行识别。"""
        cfg = config or ASRConfig()
        start_ts = time.time()

        from dashscope.audio.asr import Recognition

        callback = _AliyunASRCallback(timeout_seconds=self._timeout_seconds)
        recognition = Recognition(
            model=self._model,
            format=cfg.format,
            sample_rate=cfg.sample_rate,
            callback=callback,
            semantic_punctuation_enabled=False,
            punctuation_prediction_enabled=cfg.enable_punctuation,
        )

        logger.info(
            "阿里云ASR开始识别",
            extra={"size": len(audio_data), "format": cfg.format, "sample_rate": cfg.sample_rate},
        )

        recognition.start()
        try:
            # 分块发送，约200ms每块
            chunk_size = 6400
            for i in range(0, len(audio_data), chunk_size):
                recognition.send_audio_frame(audio_data[i : i + chunk_size])
                await asyncio.sleep(0.005)

            # SDK stop() 是同步阻塞，放线程池执行
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, recognition.stop)
            await callback.wait()

        except ASRError:
            raise
        except Exception as e:
            # 确保连接关闭
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, recognition.stop)
            except Exception:
                pass
            raise ASRError(
                message=f"阿里云ASR识别失败: {e}",
                provider="aliyun",
                cause=e,
            ) from e

        latency_ms = int((time.time() - start_ts) * 1000)
        result = ASRResult(
            text=callback.final_text,
            confidence=1.0,
            is_final=True,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={"model": self._model},
        )
        logger.info(
            "阿里云ASR识别完成",
            extra={"latency_ms": latency_ms, "text_preview": result.text[:50] if result.text else ""},
        )
        return result

    async def health_check(self) -> bool:
        """健康检查。

        根据 health_check_mode 配置：
        - "silent": 发送1秒静音进行识别测试
        - "skip": 直接返回True，减少API调用
        """
        if self._health_check_mode == "skip":
            return True

        try:
            silent = b"\x00" * (16000 * 2)  # 1秒静音 @ 16k/16bit/mono
            health_timeout = min(self._timeout_seconds, 30.0)
            await asyncio.wait_for(
                self.recognize(silent, ASRConfig()),
                timeout=health_timeout,
            )
            return True
        except Exception as e:
            logger.warning("阿里云ASR健康检查失败: %s", str(e))
            return False
