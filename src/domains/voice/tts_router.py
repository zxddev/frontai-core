"""TTS 语音合成 HTTP API 路由。

提供独立的语音合成接口，支持文本转语音播报。

端点:
- POST /api/v2/tts/synthesize  合成语音（返回Base64）
- POST /api/v2/tts/synthesize/stream  合成语音（返回二进制流）
- GET /api/v2/tts/health  健康检查
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["TTS语音合成"])

# TTS 服务单例
_tts_service = None


async def get_tts_service():
    """获取 TTS 服务单例。"""
    global _tts_service
    if _tts_service is None:
        from src.infra.clients.tts import TTSService

        _tts_service = TTSService()
        logger.info("TTS服务已初始化")
    return _tts_service


class TTSSynthesizeRequest(BaseModel):
    """TTS 合成请求。"""

    text: str = Field(..., min_length=1, max_length=2000, description="要合成的文本")
    instruct: Optional[str] = Field(
        None,
        max_length=500,
        description="语音风格指令，如：'用紧急、严肃的声音说话'",
    )
    speed: float = Field(
        1.3,
        ge=0.5,
        le=2.0,
        description="语速，1.0为正常速度，1.3为较快",
    )
    format: str = Field(
        "wav",
        description="输出格式：wav 或 mp3",
    )


class TTSSynthesizeResponse(BaseModel):
    """TTS 合成响应。"""

    success: bool = Field(..., description="是否成功")
    audio: str = Field(..., description="Base64编码的音频数据")
    format: str = Field(..., description="音频格式")
    duration_ms: int = Field(..., description="音频时长（毫秒）")
    latency_ms: int = Field(..., description="合成耗时（毫秒）")
    text_length: int = Field(..., description="文本长度")


class TTSHealthResponse(BaseModel):
    """TTS 健康检查响应。"""

    status: str = Field(..., description="服务状态")
    provider: str = Field(..., description="当前Provider")
    healthy: bool = Field(..., description="是否健康")


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def synthesize_speech(request: TTSSynthesizeRequest) -> TTSSynthesizeResponse:
    """
    合成语音（返回Base64编码）。

    适用于需要在前端播放或存储的场景。

    示例请求:
    ```json
    {
        "text": "紧急通知，请立即撤离",
        "instruct": "用紧急、严肃的声音说话",
        "speed": 1.5,
        "format": "wav"
    }
    ```
    """
    try:
        tts = await get_tts_service()
        from src.infra.clients.tts import TTSConfig

        config = TTSConfig(
            instruct=request.instruct or TTSConfig.instruct,
            speed=request.speed,
            format=request.format,
        )

        result = await tts.synthesize(request.text, config)

        audio_base64 = base64.b64encode(result.audio_data).decode("utf-8")

        logger.info(
            "TTS合成成功",
            extra={
                "text_length": len(request.text),
                "audio_size": len(result.audio_data),
                "latency_ms": result.latency_ms,
            },
        )

        return TTSSynthesizeResponse(
            success=True,
            audio=audio_base64,
            format=result.format,
            duration_ms=result.duration_ms,
            latency_ms=result.latency_ms,
            text_length=len(request.text),
        )

    except Exception as e:
        logger.exception(f"TTS合成失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@router.post("/synthesize/stream")
async def synthesize_speech_stream(request: TTSSynthesizeRequest) -> Response:
    """
    合成语音（返回二进制音频流）。

    适用于直接下载或流式播放的场景。
    返回的 Content-Type 根据 format 参数设置。
    """
    try:
        tts = await get_tts_service()
        from src.infra.clients.tts import TTSConfig

        config = TTSConfig(
            instruct=request.instruct or TTSConfig.instruct,
            speed=request.speed,
            format=request.format,
        )

        result = await tts.synthesize(request.text, config)

        content_type = "audio/wav" if request.format == "wav" else "audio/mpeg"

        logger.info(
            "TTS流式合成成功",
            extra={
                "text_length": len(request.text),
                "audio_size": len(result.audio_data),
                "latency_ms": result.latency_ms,
            },
        )

        return Response(
            content=result.audio_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="tts_output.{request.format}"',
                "X-TTS-Latency-Ms": str(result.latency_ms),
                "X-TTS-Duration-Ms": str(result.duration_ms),
            },
        )

    except Exception as e:
        logger.exception(f"TTS流式合成失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@router.get("/health", response_model=TTSHealthResponse)
async def tts_health_check() -> TTSHealthResponse:
    """
    TTS 服务健康检查。

    检查 TTS Provider 是否可用。
    """
    try:
        tts = await get_tts_service()
        healthy = await tts.health_check()

        return TTSHealthResponse(
            status="healthy" if healthy else "unhealthy",
            provider=tts.provider_name,
            healthy=healthy,
        )

    except Exception as e:
        logger.warning(f"TTS健康检查失败: {e}")
        return TTSHealthResponse(
            status="error",
            provider="unknown",
            healthy=False,
        )
