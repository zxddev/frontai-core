"""ASR模块：语音识别服务。

提供多Provider支持、自动降级和健康检查的语音识别服务。

支持的Provider：
- firered: FireRedASR-LLM-L（本地，高精度，优先级最高）
- aliyun: 阿里云百炼 fun-asr（在线，高精度）
- local: 本地FunASR（WebSocket，低延迟）

快速使用::

    from infra.clients.asr import ASRService

    asr = ASRService()
    await asr.start()  # 启动健康检查

    result = await asr.recognize(audio_data)
    print(f"识别结果: {result.text}")
    print(f"Provider: {result.provider}")
    print(f"延迟: {result.latency_ms}ms")

    await asr.stop()

环境变量配置::

    # FireRedASR配置（本地优先）
    FIRERED_ASR_URL=http://192.168.31.50:8002

    # 阿里云配置
    DASHSCOPE_API_KEY=your_api_key

    # 本地FunASR配置
    VOICE_ASR_WS_URL=wss://127.0.0.1:10097

    # 降级配置
    ASR_PRIMARY_PROVIDER=firered   # 主Provider（默认本地FireRedASR）
    ASR_FALLBACK_PROVIDER=aliyun   # 备用Provider
    HEALTH_CHECK_INTERVAL=30       # 健康检查间隔（秒）
    ASR_FAILURE_THRESHOLD=2        # 熔断失败阈值
    ASR_RECOVERY_SECONDS=60        # 熔断恢复等待秒数
"""
from .base import ASRConfig, ASRError, ASRProvider, ASRResult
from .firered_provider import FireRedASRProvider
from .manager import ASRManager
from .service import ASRService

__all__ = [
    "ASRService",
    "ASRManager",
    "ASRProvider",
    "ASRConfig",
    "ASRResult",
    "ASRError",
    "FireRedASRProvider",
]
