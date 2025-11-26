"""本地 FunASR 提供方实现（WebSocket）。

通过 WebSocket 连接本地 FunASR 服务，支持流式识别。
优化点：
- 添加识别超时处理
- SSL证书验证可配置
- 完善错误处理
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import time
from typing import Any

from .base import ASRConfig, ASRError, ASRProvider, ASRResult

logger = logging.getLogger(__name__)


class LocalFunASRProvider(ASRProvider):
    """本地 FunASR 提供方。"""

    def __init__(
        self,
        asr_ws_url: str | None = None,
        timeout_seconds: float | None = None,
        ssl_verify: bool = False,
    ) -> None:
        """初始化本地FunASR Provider。

        Args:
            asr_ws_url: WebSocket服务地址，默认从环境变量读取。
            timeout_seconds: 识别超时秒数，默认30秒。
            ssl_verify: 是否验证SSL证书，默认False（本地服务通常自签名）。
        """
        self._url = asr_ws_url or os.getenv("VOICE_ASR_WS_URL", "wss://127.0.0.1:10097")
        self._hotwords_json = os.getenv("FUNASR_HOTWORDS_JSON", "{}")
        self._chunk_cfg = self._parse_chunk_size(os.getenv("FUNASR_CHUNK_SIZE", "5,10,5"))
        self._ssl_verify = ssl_verify

        # 超时配置
        if timeout_seconds is not None:
            self._timeout_seconds = max(10.0, timeout_seconds)
        else:
            timeout_raw = os.getenv("LOCAL_ASR_TIMEOUT_SECONDS", "30")
            try:
                self._timeout_seconds = max(10.0, float(timeout_raw))
            except ValueError:
                self._timeout_seconds = 30.0

        if not self._url:
            logger.error("本地FunASR URL未配置，请设置 VOICE_ASR_WS_URL")

        logger.info(
            "本地FunASR初始化完成",
            extra={
                "url": self._url,
                "chunk": self._chunk_cfg,
                "timeout_seconds": self._timeout_seconds,
                "ssl_verify": ssl_verify,
            },
        )

    @staticmethod
    def _parse_chunk_size(csv: str) -> list[int]:
        """解析分块配置。"""
        try:
            return [int(x.strip()) for x in csv.split(",") if x.strip()]
        except Exception:
            return [5, 10, 5]

    @property
    def name(self) -> str:
        return "local"

    @property
    def priority(self) -> int:
        return 0

    def _get_ssl_context(self) -> ssl.SSLContext | None:
        """获取SSL上下文。"""
        if not self._url.startswith("wss://"):
            return None

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if not self._ssl_verify:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        return ssl_ctx

    async def recognize(
        self, audio_data: bytes, config: ASRConfig | None = None
    ) -> ASRResult:
        """使用本地 FunASR 进行识别。"""
        try:
            import websockets
        except ImportError as e:
            raise ImportError("请安装 websockets: pip install websockets") from e

        cfg = config or ASRConfig()
        start_ts = time.time()
        ssl_ctx = self._get_ssl_context()

        logger.info(
            "本地ASR开始连接",
            extra={"url": self._url, "size": len(audio_data)},
        )

        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with websockets.connect(
                    self._url,
                    open_timeout=10,
                    ping_interval=None,
                    subprotocols=["binary"],
                    additional_headers={"User-Agent": "FrontAI-ASR/1.0"},
                    user_agent_header="FrontAI-ASR/1.0",
                    max_size=None,
                    ssl=ssl_ctx,
                ) as ws:
                    # 发送开始消息
                    start_msg: dict[str, Any] = {
                        "mode": "2pass",
                        "wav_name": "audio_stream",
                        "is_speaking": True,
                        "wav_format": cfg.format,
                        "audio_fs": cfg.sample_rate,
                        "chunk_size": self._chunk_cfg,
                        "hotwords": self._hotwords_json,
                        "itn": True,
                    }
                    await ws.send(json.dumps(start_msg))

                    # 分块发送音频（200ms每块）
                    chunk_bytes = 6400
                    for i in range(0, len(audio_data), chunk_bytes):
                        await ws.send(audio_data[i : i + chunk_bytes])
                        await asyncio.sleep(0.005)

                    # 发送结束帧
                    await ws.send(json.dumps({"is_speaking": False}))

                    # 接收识别结果
                    final_text = ""
                    try:
                        async for message in ws:
                            try:
                                obj = json.loads(message)
                            except json.JSONDecodeError:
                                continue
                            text = obj.get("text", "")
                            mode = obj.get("mode", "")
                            is_final = bool(obj.get("is_final", False))
                            if text:
                                final_text = text
                            if mode == "2pass-offline" or (not mode and is_final):
                                break
                    except Exception:
                        pass  # 服务器可能主动关闭

        except asyncio.TimeoutError:
            raise ASRError(
                message=f"本地FunASR超时({self._timeout_seconds}s)",
                provider="local",
            ) from None
        except Exception as e:
            raise ASRError(
                message=f"本地FunASR识别失败: {e}",
                provider="local",
                cause=e,
            ) from e

        latency_ms = int((time.time() - start_ts) * 1000)
        result = ASRResult(
            text=final_text,
            confidence=1.0,
            is_final=True,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={"url": self._url},
        )
        logger.info(
            "本地ASR识别完成",
            extra={"latency_ms": latency_ms, "text_preview": final_text[:50] if final_text else ""},
        )
        return result

    async def health_check(self) -> bool:
        """健康检查：尝试WebSocket握手。"""
        try:
            import websockets
        except ImportError:
            return False

        ssl_ctx = self._get_ssl_context()
        try:
            async with asyncio.timeout(5.0):
                async with websockets.connect(
                    self._url,
                    open_timeout=5,
                    ssl=ssl_ctx,
                ) as ws:
                    await ws.send(json.dumps({"type": "ping"}))
                    await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.warning("本地FunASR健康检查失败: %s", str(e))
            return False
