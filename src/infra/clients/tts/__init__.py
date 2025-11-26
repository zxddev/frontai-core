"""TTS模块：语音合成服务。

提供语音合成能力，支持多Provider扩展。

支持的Provider：
- cosyvoice: CosyVoice 2.0（本地部署，高质量）

快速使用::

    from infra.clients.tts import TTSService

    tts = TTSService()

    result = await tts.synthesize("你好，这是测试语音")
    print(f"音频大小: {len(result.audio_data)} bytes")
    print(f"Provider: {result.provider}")
    print(f"延迟: {result.latency_ms}ms")

    # 保存音频文件
    with open("output.wav", "wb") as f:
        f.write(result.audio_data)

    await tts.close()

环境变量配置::

    # CosyVoice配置
    COSYVOICE_URL=http://192.168.31.50:10097
    COSYVOICE_TIMEOUT_SECONDS=30
"""
from .base import TTSConfig, TTSError, TTSProvider, TTSResult
from .cosyvoice_provider import CosyVoiceTTSProvider
from .service import TTSService

__all__ = [
    "TTSService",
    "TTSProvider",
    "TTSConfig",
    "TTSResult",
    "TTSError",
    "CosyVoiceTTSProvider",
]
