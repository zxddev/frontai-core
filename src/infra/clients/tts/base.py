"""TTS 抽象基类与数据模型。

定义语音合成契约，规范入参/出参与健康检查接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TTSResult:
    """TTS 合成结果。

    Attributes:
        audio_data: 合成的音频二进制数据。
        format: 音频格式（如 "wav", "mp3"）。
        sample_rate: 采样率。
        duration_ms: 音频时长（毫秒）。
        provider: 提供方标识。
        latency_ms: 合成耗时（毫秒）。
        metadata: 扩展元数据。
    """

    audio_data: bytes
    format: str = "wav"
    sample_rate: int = 22050
    duration_ms: int = 0
    provider: str = ""
    latency_ms: int = 0
    metadata: Optional[dict[str, Any]] = field(default_factory=dict)


@dataclass
class TTSConfig:
    """TTS 配置项。

    Attributes:
        instruct: 语音风格指令。
        speed: 语速（1.0=正常）。
        format: 输出格式（wav/mp3）。
        sample_rate: 采样率。
    """

    instruct: str = "请用快速、简洁、清晰、权威的男性声音说话，适合紧急救援场景"
    speed: float = 1.3
    format: str = "wav"
    sample_rate: int = 22050


class TTSProvider(ABC):
    """TTS 提供方抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回提供方唯一名称。"""

    @property
    def priority(self) -> int:
        """返回提供方优先级，数值越大表示越优先。"""
        return 0

    @abstractmethod
    async def synthesize(
        self, text: str, config: TTSConfig | None = None
    ) -> TTSResult:
        """执行语音合成。

        Args:
            text: 要合成的文本。
            config: 合成配置，None 表示使用默认值。

        Returns:
            TTSResult: 合成结果对象。

        Raises:
            TTSError: 合成失败时抛出。
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查。

        Returns:
            bool: True 表示服务可用，False 表示不可用。
        """


class TTSError(Exception):
    """TTS 通用异常。"""

    def __init__(
        self,
        message: str,
        provider: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.cause = cause
