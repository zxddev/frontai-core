"""语音对话 WebSocket 路由。

提供实时语音识别和AI对话能力。

端点: /ws/voice/chat
协议: 原生 WebSocket（二进制音频 + JSON控制消息）

完整流程: 用户语音 → VAD检测 → ASR识别 → LLM生成回复 → TTS合成 → 返回音频

通信协议:
1. 客户端发送 JSON 控制消息:
   - {"type": "start", "config": {...}}  开始录音会话
   - {"type": "stop"}  手动结束录音，触发识别
   - {"type": "cancel"}  取消当前会话

2. 客户端发送二进制音频数据:
   - PCM 16-bit, 16kHz, 单声道
   - 每帧 20ms (640字节)

3. 服务端返回 JSON 消息:
   - {"type": "ready"}  准备就绪
   - {"type": "recording"}  开始录音确认
   - {"type": "vad", "is_speaking": true/false, "finalized": false}  VAD状态
   - {"type": "recognized", "text": "...", "latency_ms": 123}  识别完成
   - {"type": "ai_thinking"}  AI正在思考
   - {"type": "llm_chunk", "text": "..."}  LLM流式文字块
   - {"type": "llm_done", "text": "..."}  LLM完成
   - {"type": "tts", "audio": "base64...", "audio_format": "wav"}  TTS音频
   - {"type": "error", "message": "..."}  错误

配置选项 (在 start 消息的 config 中传递):
   - enable_vad: bool  是否启用VAD自动检测（默认true）
   - enable_ai_response: bool  是否启用AI回复（默认true）
   - enable_tts: bool  是否启用语音合成（默认true）
   - system_prompt: str  系统提示词
   - tts_speed: float  TTS语速（默认1.3）
   - vad_silence_duration: float  VAD静默触发阈值秒数（默认1.0）
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["语音对话"])

# VAD 配置
VAD_SAMPLE_RATE = 16000
VAD_FRAME_MS = 20  # 每帧20ms
VAD_FRAME_BYTES = int(VAD_SAMPLE_RATE * VAD_FRAME_MS / 1000 * 2)  # 640字节
DEFAULT_SILENCE_DURATION = 1.0  # 默认静默触发时长(秒)
VAD_ENERGY_THRESHOLD = 500  # 能量阈值（根据环境调整）
VAD_SPEECH_FRAMES_REQUIRED = 3  # 连续多少帧有语音才确认开始说话
VAD_SILENCE_FRAMES_REQUIRED = 25  # 连续多少帧静默才确认停止说话（25帧≈0.5秒）

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = """你是一个智能应急救援助手，负责协助用户进行应急指挥和救援决策。
请用简洁、专业、清晰的语言回答用户的问题。
回答要简短精炼，适合语音播报，每次回复控制在100字以内。"""


@dataclass
class VoiceSession:
    """语音会话状态。"""

    session_id: str
    websocket: WebSocket
    audio_buffer: bytearray = field(default_factory=bytearray)
    is_recording: bool = False
    created_at: float = field(default_factory=time.time)
    config: dict = field(default_factory=dict)
    # 对话历史（用于多轮对话）
    chat_history: list = field(default_factory=list)
    # VAD 状态
    vad_is_speaking: bool = False  # 当前是否正在说话
    vad_speech_started: bool = False  # 本轮是否检测到过语音
    vad_silence_start: float = 0.0  # 静默开始时间
    vad_processing: bool = False  # 是否正在处理ASR（防止重复触发）
    vad_speech_frames: int = 0  # 连续语音帧计数
    vad_silence_frames: int = 0  # 连续静默帧计数


class VoiceChatManager:
    """语音对话管理器。"""

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}
        self._asr_service = None
        self._tts_service = None
        self._llm = None
    def _calculate_energy(self, audio_data: bytes) -> float:
        """计算音频帧的能量（RMS）。"""
        import struct
        if len(audio_data) < 2:
            return 0.0
        # 解析 16-bit PCM
        num_samples = len(audio_data) // 2
        samples = struct.unpack(f'<{num_samples}h', audio_data)
        # 计算 RMS
        sum_sq = sum(s * s for s in samples)
        rms = (sum_sq / num_samples) ** 0.5
        return rms

    async def _get_asr_service(self):
        """延迟加载 ASR 服务。"""
        if self._asr_service is None:
            from src.infra.clients.asr import ASRService

            self._asr_service = ASRService()
            await self._asr_service.start()
            logger.info("ASR服务已启动")
        return self._asr_service

    async def _get_tts_service(self):
        """延迟加载 TTS 服务。"""
        if self._tts_service is None:
            from src.infra.clients.tts import TTSService

            self._tts_service = TTSService()
            logger.info("TTS服务已启动")
        return self._tts_service

    def _get_llm(self):
        """延迟加载 LLM。"""
        if self._llm is None:
            from src.infra.settings import load_settings
            from src.infra.clients.llm_client import build_chat_model

            settings = load_settings()
            self._llm = build_chat_model(settings)
            logger.info("LLM已加载")
        return self._llm

    async def connect(self, websocket: WebSocket) -> VoiceSession:
        """建立连接。"""
        await websocket.accept()

        session_id = str(uuid4())
        session = VoiceSession(
            session_id=session_id,
            websocket=websocket,
        )
        self._sessions[session_id] = session

        logger.info(f"语音会话已建立: {session_id}")

        await self._send_json(websocket, {"type": "ready", "session_id": session_id})

        return session

    def disconnect(self, session_id: str) -> None:
        """断开连接。"""
        session = self._sessions.pop(session_id, None)
        if session:
            logger.info(f"语音会话已断开: {session_id}")

    async def handle_message(self, session: VoiceSession, data: bytes | str) -> None:
        """处理收到的消息。"""
        if isinstance(data, bytes):
            await self._handle_audio(session, data)
        else:
            await self._handle_control(session, data)

    async def _handle_audio(self, session: VoiceSession, audio_data: bytes) -> None:
        """处理音频数据并进行VAD检测。"""
        if not session.is_recording:
            return

        # 如果正在处理ASR，暂停接收新音频
        if session.vad_processing:
            return

        session.audio_buffer.extend(audio_data)

        # VAD 检测（仅当启用且音频帧大小正确时）
        enable_vad = session.config.get("enable_vad", True)

        if enable_vad and len(audio_data) == VAD_FRAME_BYTES:
            try:
                # 基于能量的 VAD
                energy = self._calculate_energy(audio_data)
                threshold = session.config.get("vad_energy_threshold", VAD_ENERGY_THRESHOLD)
                is_speech = energy > threshold

                if is_speech:
                    session.vad_speech_frames += 1
                    session.vad_silence_frames = 0

                    # 连续几帧有语音才确认开始说话
                    if session.vad_speech_frames >= VAD_SPEECH_FRAMES_REQUIRED and not session.vad_is_speaking:
                        session.vad_is_speaking = True
                        session.vad_speech_started = True
                        logger.debug(f"VAD: 检测到语音开始 (energy={energy:.0f})")
                        await self._send_json(
                            session.websocket,
                            {"type": "vad", "is_speaking": True, "finalized": False}
                        )
                else:
                    session.vad_silence_frames += 1
                    session.vad_speech_frames = 0

                    # 连续静默帧数达到阈值
                    if session.vad_is_speaking and session.vad_silence_frames >= VAD_SILENCE_FRAMES_REQUIRED:
                        session.vad_is_speaking = False
                        session.vad_silence_start = time.time()
                        logger.debug("VAD: 检测到语音停止，开始静默计时")
                        await self._send_json(
                            session.websocket,
                            {"type": "vad", "is_speaking": False, "finalized": False}
                        )

                # 检查是否应该触发识别
                if session.vad_speech_started and not session.vad_is_speaking and session.vad_silence_start > 0:
                    silence_duration = session.config.get("vad_silence_duration", DEFAULT_SILENCE_DURATION)
                    elapsed = time.time() - session.vad_silence_start

                    if elapsed >= silence_duration:
                        # 静默超过阈值，自动触发识别
                        logger.info(f"VAD: 静默{elapsed:.1f}秒，自动触发ASR")
                        session.vad_processing = True

                        await self._send_json(
                            session.websocket,
                            {"type": "vad", "is_speaking": False, "finalized": True}
                        )

                        # 执行识别
                        await self._recognize_and_respond(session)

                        # 重置VAD状态，准备下一轮
                        session.vad_speech_started = False
                        session.vad_silence_start = 0.0
                        session.vad_speech_frames = 0
                        session.vad_silence_frames = 0
                        session.vad_processing = False

            except Exception as e:
                logger.warning(f"VAD检测异常: {e}")

    async def _handle_control(self, session: VoiceSession, message: str) -> None:
        """处理控制消息。"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            await self._send_error(session.websocket, "无效的JSON消息")
            return

        msg_type = data.get("type", "")

        if msg_type == "start":
            session.is_recording = True
            session.audio_buffer.clear()
            session.config = data.get("config", {})
            # 重置 VAD 状态
            session.vad_is_speaking = False
            session.vad_speech_started = False
            session.vad_silence_start = 0.0
            session.vad_processing = False
            session.vad_speech_frames = 0
            session.vad_silence_frames = 0
            logger.info(f"开始录音: {session.session_id}, VAD={'启用' if session.config.get('enable_vad', True) else '禁用'}")
            await self._send_json(session.websocket, {"type": "recording"})

        elif msg_type == "stop":
            session.is_recording = False
            # 重置 VAD 状态
            session.vad_is_speaking = False
            session.vad_speech_started = False
            session.vad_silence_start = 0.0
            logger.info(f"手动停止录音: {session.session_id}, 音频大小: {len(session.audio_buffer)} bytes")

            if len(session.audio_buffer) > 0 and not session.vad_processing:
                session.vad_processing = True
                await self._recognize_and_respond(session)
                session.vad_processing = False
            else:
                await self._send_json(session.websocket, {"type": "recognized", "text": "", "latency_ms": 0})

        elif msg_type == "cancel":
            session.is_recording = False
            session.audio_buffer.clear()
            logger.info(f"取消录音: {session.session_id}")
            await self._send_json(session.websocket, {"type": "cancelled"})

        elif msg_type == "ping":
            await self._send_json(session.websocket, {"type": "pong"})

        else:
            logger.warning(f"未知消息类型: {msg_type}")

    async def _recognize_and_respond(self, session: VoiceSession) -> None:
        """执行语音识别并返回结果。"""
        audio_data = bytes(session.audio_buffer)
        session.audio_buffer.clear()

        try:
            asr = await self._get_asr_service()

            logger.info(f"开始ASR识别: {len(audio_data)} bytes")
            start_ts = time.time()

            result = await asr.recognize(audio_data)

            latency_ms = int((time.time() - start_ts) * 1000)

            await self._send_json(
                session.websocket,
                {
                    "type": "recognized",
                    "text": result.text,
                    "provider": result.provider,
                    "latency_ms": latency_ms,
                    "confidence": result.confidence,
                },
            )

            logger.info(f"ASR识别完成: '{result.text[:50] if result.text else ''}' ({latency_ms}ms, {result.provider})")

            # 如果配置了AI对话（默认启用），调用LLM生成回复
            enable_ai = session.config.get("enable_ai_response", True)
            if enable_ai and result.text.strip():
                await self._generate_ai_response(session, result.text)

        except Exception as e:
            logger.exception(f"ASR识别失败: {e}")
            await self._send_error(session.websocket, f"语音识别失败: {str(e)}")

    async def _generate_ai_response(self, session: VoiceSession, user_text: str) -> None:
        """生成AI回复并合成语音（流式输出）。

        流程：
        1. 流式调用 LLM，边生成边发送 llm_chunk
        2. 完成后发送 llm_done（完整文本）
        3. TTS 合成后发送 tts（音频）
        """
        try:
            # 通知前端AI正在思考
            await self._send_json(session.websocket, {"type": "ai_thinking"})

            # 1. 流式调用LLM
            llm = self._get_llm()
            system_prompt = session.config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            # 构建消息列表（包含历史对话）
            messages = [SystemMessage(content=system_prompt)]

            # 添加历史对话（最多保留5轮）
            for msg in session.chat_history[-10:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))

            # 添加当前用户消息
            messages.append(HumanMessage(content=user_text))

            logger.info(f"调用LLM(流式): '{user_text[:50]}...'")
            start_ts = time.time()

            # 流式调用 LLM
            ai_text = ""
            async for chunk in llm.astream(messages):
                chunk_text = chunk.content
                if chunk_text:
                    ai_text += chunk_text
                    # 发送流式文字块
                    await self._send_json(
                        session.websocket,
                        {"type": "llm_chunk", "text": chunk_text},
                    )

            llm_latency = int((time.time() - start_ts) * 1000)
            ai_text = ai_text.strip()

            logger.info(f"LLM流式完成: '{ai_text[:50]}...' ({llm_latency}ms)")

            # 发送完整文本
            await self._send_json(
                session.websocket,
                {"type": "llm_done", "text": ai_text, "llm_latency_ms": llm_latency},
            )

            # 保存对话历史
            session.chat_history.append({"role": "user", "content": user_text})
            session.chat_history.append({"role": "assistant", "content": ai_text})

            # 2. 调用TTS合成语音（如果启用）
            enable_tts = session.config.get("enable_tts", True)

            if enable_tts and ai_text:
                try:
                    tts = await self._get_tts_service()
                    from src.infra.clients.tts import TTSConfig

                    tts_config = TTSConfig(
                        speed=session.config.get("tts_speed", 1.3),
                    )

                    start_ts = time.time()
                    tts_result = await tts.synthesize(ai_text, tts_config)
                    tts_latency = int((time.time() - start_ts) * 1000)

                    audio_base64 = base64.b64encode(tts_result.audio_data).decode("utf-8")
                    logger.info(f"TTS合成完成: {len(tts_result.audio_data)} bytes ({tts_latency}ms)")

                    # 单独发送TTS音频
                    await self._send_json(
                        session.websocket,
                        {
                            "type": "tts",
                            "audio": audio_base64,
                            "audio_format": "wav",
                            "tts_latency_ms": tts_latency,
                        },
                    )

                except Exception as tts_err:
                    logger.warning(f"TTS合成失败: {tts_err}")

        except Exception as e:
            logger.exception(f"AI回复生成失败: {e}")
            await self._send_error(session.websocket, f"AI回复生成失败: {str(e)}")

    async def _send_json(self, websocket: WebSocket, data: dict) -> None:
        """发送JSON消息。"""
        await websocket.send_json(data)

    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """发送错误消息。"""
        await self._send_json(websocket, {"type": "error", "message": message})


# 全局管理器实例
voice_manager = VoiceChatManager()


@router.websocket("/chat")
async def voice_chat_endpoint(websocket: WebSocket) -> None:
    """
    语音对话 WebSocket 端点。

    协议说明:
    - 连接后服务端发送 {"type": "ready", "session_id": "..."}
    - 客户端发送 {"type": "start"} 开始录音
    - 客户端发送二进制音频数据 (PCM 16-bit, 16kHz, mono)
    - 客户端发送 {"type": "stop"} 停止录音并触发识别
    - 服务端返回 {"type": "recognized", "text": "...", "latency_ms": ...}

    可选配置 (在 start 消息中传递):
    - enable_ai_response: bool  是否启用AI回复
    """
    session: Optional[VoiceSession] = None

    try:
        session = await voice_manager.connect(websocket)

        while True:
            # 接收消息（支持文本和二进制）
            message = await websocket.receive()

            if "text" in message:
                await voice_manager.handle_message(session, message["text"])
            elif "bytes" in message:
                await voice_manager.handle_message(session, message["bytes"])

    except WebSocketDisconnect:
        logger.info(f"WebSocket断开连接")
    except Exception as e:
        logger.exception(f"WebSocket错误: {e}")
    finally:
        if session:
            voice_manager.disconnect(session.session_id)
