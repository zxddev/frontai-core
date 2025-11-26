"""语音模块。

提供实时语音对话 WebSocket 端点和 TTS 语音合成 API。
"""
from .router import router as voice_router
from .tts_router import router as tts_router

__all__ = ["voice_router", "tts_router"]
