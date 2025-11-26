"""CosyVoice TensorRT-LLM TTS 提供方实现。

基于 Triton GRPC 的流式语音合成服务。
服务地址默认为 192.168.31.50:18001
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import queue
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import numpy as np

from .base import TTSConfig, TTSError, TTSProvider, TTSResult

logger = logging.getLogger(__name__)

# 线程池用于执行同步的 Triton 调用
_executor = ThreadPoolExecutor(max_workers=4)


class CosyVoiceTTSProvider(TTSProvider):
    """CosyVoice TensorRT-LLM TTS 提供方。

    通过 Triton GRPC 调用本地部署的 CosyVoice 服务。
    """

    def __init__(
        self,
        server_url: str | None = None,
        model_name: str = "cosyvoice2",
        timeout_seconds: float | None = None,
    ) -> None:
        """初始化 CosyVoice TTS Provider。

        Args:
            server_url: Triton服务地址，默认从环境变量 COSYVOICE_GRPC_URL 读取。
            model_name: 模型名称，默认 cosyvoice2。
            timeout_seconds: 请求超时秒数，默认30秒。
        """
        self._url = server_url or os.getenv("COSYVOICE_GRPC_URL", "192.168.31.50:18001")
        self._model_name = model_name
        self._sample_rate = 24000  # CosyVoice 输出采样率

        if timeout_seconds is not None:
            self._timeout_seconds = max(10.0, timeout_seconds)
        else:
            timeout_raw = os.getenv("COSYVOICE_TIMEOUT_SECONDS", "30")
            try:
                self._timeout_seconds = max(10.0, float(timeout_raw))
            except ValueError:
                self._timeout_seconds = 30.0

        self._client = None

        logger.info(
            "CosyVoice TTS初始化完成",
            extra={
                "url": self._url,
                "model": self._model_name,
                "timeout_seconds": self._timeout_seconds,
            },
        )

    @property
    def name(self) -> str:
        return "cosyvoice"

    @property
    def priority(self) -> int:
        return 100

    def _get_client(self):
        """获取或创建 Triton 客户端。"""
        if self._client is None:
            try:
                import tritonclient.grpc as grpcclient
                self._client = grpcclient.InferenceServerClient(url=self._url)
            except Exception as e:
                raise TTSError(
                    message=f"无法创建Triton客户端: {e}",
                    provider=self.name,
                    cause=e,
                )
        return self._client

    def _stream_tts_sync(self, text: str) -> tuple[bytes, int]:
        """同步流式 TTS（在线程池中执行）。

        Returns:
            tuple: (WAV音频数据, 首包延迟ms)
        """
        import tritonclient.grpc as grpcclient

        client = self._get_client()
        audio_chunks = []
        result_queue = queue.Queue()
        first_chunk_time = None
        start_time = time.time()

        def _callback(result, error):
            nonlocal first_chunk_time
            if error:
                result_queue.put(("error", error))
            else:
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                result_queue.put(("data", result))

        # 创建输入
        inputs = [grpcclient.InferInput("text", [1], "BYTES")]
        inputs[0].set_data_from_numpy(np.array([text.encode('utf-8')], dtype=object))

        # 发送流式请求
        client.start_stream(callback=_callback)
        try:
            client.async_stream_infer(
                model_name=self._model_name,
                inputs=inputs,
                request_id=str(int(time.time() * 1000)),
            )

            # 接收流式响应
            while True:
                try:
                    msg_type, data = result_queue.get(timeout=self._timeout_seconds)
                    if msg_type == "error":
                        raise TTSError(
                            message=f"Triton TTS错误: {data}",
                            provider=self.name,
                        )

                    # 检查是否是最终响应
                    response = data.get_response()
                    params = response.parameters
                    if "triton_final_response" in params:
                        if params["triton_final_response"].bool_param:
                            break

                    # 获取音频数据
                    try:
                        audio = data.as_numpy("audio")
                        if audio is not None and len(audio) > 0:
                            audio_chunks.append(audio.flatten())
                    except Exception:
                        pass  # 可能没有音频输出

                except queue.Empty:
                    logger.warning("Triton TTS响应超时")
                    break

        finally:
            client.stop_stream()

        if not audio_chunks:
            raise TTSError(
                message="CosyVoice返回空音频数据",
                provider=self.name,
            )

        # 合并音频块
        full_audio = np.concatenate(audio_chunks)
        first_latency_ms = int((first_chunk_time - start_time) * 1000) if first_chunk_time else 0

        # 转换为 WAV 格式
        wav_data = self._numpy_to_wav(full_audio)

        return wav_data, first_latency_ms

    def _numpy_to_wav(self, audio: np.ndarray) -> bytes:
        """将 numpy 音频数组转换为 WAV 格式。"""
        # 归一化到 int16
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            audio = np.clip(audio, -1.0, 1.0)
            audio_int16 = (audio * 32767).astype(np.int16)
        else:
            audio_int16 = audio.astype(np.int16)

        # 构建 WAV 头
        num_samples = len(audio_int16)
        bytes_per_sample = 2
        num_channels = 1
        data_size = num_samples * bytes_per_sample * num_channels

        wav_buffer = io.BytesIO()

        # RIFF 头
        wav_buffer.write(b'RIFF')
        wav_buffer.write(struct.pack('<I', 36 + data_size))
        wav_buffer.write(b'WAVE')

        # fmt 块
        wav_buffer.write(b'fmt ')
        wav_buffer.write(struct.pack('<I', 16))  # fmt chunk size
        wav_buffer.write(struct.pack('<H', 1))   # PCM format
        wav_buffer.write(struct.pack('<H', num_channels))
        wav_buffer.write(struct.pack('<I', self._sample_rate))
        wav_buffer.write(struct.pack('<I', self._sample_rate * num_channels * bytes_per_sample))
        wav_buffer.write(struct.pack('<H', num_channels * bytes_per_sample))
        wav_buffer.write(struct.pack('<H', 8 * bytes_per_sample))

        # data 块
        wav_buffer.write(b'data')
        wav_buffer.write(struct.pack('<I', data_size))
        wav_buffer.write(audio_int16.tobytes())

        return wav_buffer.getvalue()

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
        cfg = config or TTSConfig()
        start_ts = time.time()

        logger.info(
            "CosyVoice TTS开始合成",
            extra={"url": self._url, "text_length": len(text)},
        )

        try:
            loop = asyncio.get_event_loop()
            audio_data, first_latency_ms = await loop.run_in_executor(
                _executor,
                self._stream_tts_sync,
                text,
            )
        except TTSError:
            raise
        except Exception as e:
            raise TTSError(
                message=f"CosyVoice合成失败: {e}",
                provider=self.name,
                cause=e,
            ) from e

        latency_ms = int((time.time() - start_ts) * 1000)

        # 计算音频时长
        audio_samples = (len(audio_data) - 44) // 2 if len(audio_data) > 44 else 0
        duration_ms = int(audio_samples / self._sample_rate * 1000)

        result = TTSResult(
            audio_data=audio_data,
            format="wav",
            sample_rate=self._sample_rate,
            duration_ms=duration_ms,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={
                "url": self._url,
                "text_length": len(text),
                "first_chunk_latency_ms": first_latency_ms,
            },
        )

        logger.info(
            "CosyVoice TTS合成完成",
            extra={
                "latency_ms": latency_ms,
                "first_chunk_latency_ms": first_latency_ms,
                "audio_size": len(audio_data),
                "duration_ms": duration_ms,
            },
        )
        return result

    async def health_check(self) -> bool:
        """健康检查：检查 Triton 服务是否可用。"""
        try:
            loop = asyncio.get_event_loop()

            def _check():
                client = self._get_client()
                return client.is_server_live() and client.is_model_ready(self._model_name)

            is_healthy = await loop.run_in_executor(_executor, _check)
            return is_healthy
        except Exception as e:
            logger.warning("CosyVoice健康检查失败: %s", str(e))
            return False

    async def close(self) -> None:
        """关闭客户端。"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
