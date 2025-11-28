"""ASR管理器：负责Provider选择、自动降级和健康检查。

实现多Provider管理，支持阿里云优先、本地备用的自动降级策略。
优化点：
- 更清晰的熔断器状态管理
- 半开状态试探机制
- 详细的状态日志
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from .base import ASRConfig, ASRError, ASRProvider, ASRResult

logger = logging.getLogger(__name__)


@dataclass
class ProviderStatus:
    """Provider健康状态。

    Attributes:
        available: 是否可用。
        consecutive_successes: 连续成功次数。
        consecutive_failures: 连续失败次数。
        last_check_time: 最后检查时间戳。
        last_latency_ms: 最后一次操作延迟（毫秒）。
        half_open: 是否处于半开试探阶段。
        recovery_at: 允许再次尝试的时间戳。
    """

    available: bool = True  # 默认可用，等待健康检查确认
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_check_time: float = 0.0
    last_latency_ms: int = 0
    half_open: bool = False
    recovery_at: float = 0.0


class ASRManager:
    """ASR管理器：管理多个Provider，实现自动降级。

    核心功能：
    1. Provider选择：根据健康状态和优先级选择最佳Provider
    2. 自动降级：主Provider失败时自动切换到备用Provider
    3. 健康检查：后台定期检查各Provider健康状态
    4. 熔断恢复：服务恢复后自动切回高优先级Provider
    """

    def __init__(
        self,
        providers: list[ASRProvider] | None = None,
        primary_provider: str | None = None,
        fallback_provider: str | None = None,
        health_check_interval: int | None = None,
        failure_threshold: int | None = None,
        recovery_seconds: int | None = None,
    ) -> None:
        """初始化ASR管理器。

        Args:
            providers: Provider列表，None时自动创建默认Provider。
            primary_provider: 主Provider名称，默认从环境变量读取。
            fallback_provider: 备用Provider名称，默认从环境变量读取。
            health_check_interval: 健康检查间隔秒数，默认30秒。
            failure_threshold: 熔断失败阈值，默认2次。
            recovery_seconds: 熔断恢复等待秒数，默认60秒。
        """
        # 创建默认Provider
        if providers is None:
            providers = self._create_default_providers()

        self._providers: dict[str, ASRProvider] = {p.name: p for p in providers}

        # 从参数或环境变量读取配置（默认本地FireRedASR优先）
        self._primary = primary_provider or os.getenv("ASR_PRIMARY_PROVIDER", "firered")
        self._fallback = fallback_provider or os.getenv("ASR_FALLBACK_PROVIDER", "aliyun")
        self._health_check_interval = health_check_interval or int(
            os.getenv("HEALTH_CHECK_INTERVAL", "30")
        )
        self._failure_threshold = failure_threshold or max(
            1, int(os.getenv("ASR_FAILURE_THRESHOLD", "2"))
        )
        self._recovery_seconds = recovery_seconds or max(
            10, int(os.getenv("ASR_RECOVERY_SECONDS", "60"))
        )

        # 初始化状态
        self._provider_status: dict[str, ProviderStatus] = {
            name: ProviderStatus() for name in self._providers
        }

        # 健康检查任务
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_running = False

        logger.info(
            "ASR管理器初始化完成",
            extra={
                "providers": list(self._providers.keys()),
                "primary": self._primary,
                "fallback": self._fallback,
                "health_check_interval": self._health_check_interval,
                "failure_threshold": self._failure_threshold,
                "recovery_seconds": self._recovery_seconds,
            },
        )

    def _create_default_providers(self) -> list[ASRProvider]:
        """创建默认的Provider列表。"""
        providers: list[ASRProvider] = []

        # 尝试创建 FireRedASR Provider（优先级最高）
        try:
            from .firered_provider import FireRedASRProvider

            providers.append(FireRedASRProvider())
            logger.info("FireRedASR Provider创建成功")
        except Exception as e:
            logger.warning("FireRedASR Provider创建失败: %s", str(e))

        # 尝试创建阿里云Provider
        try:
            from .aliyun_provider import AliyunASRProvider

            dashscope_key = os.getenv("DASHSCOPE_API_KEY")
            if dashscope_key:
                providers.append(AliyunASRProvider(api_key=dashscope_key))
                logger.info("阿里云ASR Provider创建成功")
            else:
                logger.warning("DASHSCOPE_API_KEY未配置，跳过阿里云Provider")
        except Exception as e:
            logger.warning("阿里云ASR Provider创建失败: %s", str(e))

        # 本地FunASR Provider（WebSocket）已弃用，不再创建
        # 保留代码供需要时启用：
        # try:
        #     from .local_provider import LocalFunASRProvider
        #     providers.append(LocalFunASRProvider())
        #     logger.info("本地FunASR Provider创建成功")
        # except Exception as e:
        #     logger.warning("本地FunASR Provider创建失败: %s", str(e))

        if not providers:
            raise RuntimeError("没有可用的ASR Provider")

        return providers

    def _mark_success(self, name: str) -> None:
        """标记Provider成功，重置失败计数。"""
        status = self._provider_status[name]
        status.consecutive_successes += 1
        status.consecutive_failures = 0
        status.available = True
        status.half_open = False
        status.recovery_at = 0.0

    def _mark_failure(self, name: str) -> None:
        """标记Provider失败，超过阈值后进入熔断。"""
        status = self._provider_status[name]
        status.consecutive_failures += 1
        status.consecutive_successes = 0
        if status.consecutive_failures >= self._failure_threshold:
            was_available = status.available
            status.available = False
            status.half_open = False
            status.recovery_at = time.time() + self._recovery_seconds
            if was_available:
                logger.warning(
                    "Provider进入熔断状态",
                    extra={
                        "provider": name,
                        "consecutive_failures": status.consecutive_failures,
                        "recovery_at": status.recovery_at,
                    },
                )

    async def recognize(
        self, audio_data: bytes, config: ASRConfig | None = None
    ) -> ASRResult:
        """执行语音识别，支持自动降级。

        流程：
        1. 选择Provider（根据健康状态和优先级）
        2. 尝试识别
        3. 失败时自动降级到备用Provider

        Raises:
            ASRError: 所有Provider都失败时抛出。
        """
        provider = self._select_provider()

        logger.info(
            "ASR开始识别",
            extra={
                "provider": provider.name,
                "audio_size": len(audio_data),
                "status": self._get_status_snapshot(),
            },
        )

        start_ts = time.time()

        try:
            result = await provider.recognize(audio_data, config)
            self._mark_success(provider.name)
            logger.info(
                "ASR识别成功",
                extra={
                    "provider": result.provider,
                    "latency_ms": result.latency_ms,
                    "text_preview": result.text[:30] if result.text else "",
                },
            )
            return result

        except Exception as e:
            latency_ms = int((time.time() - start_ts) * 1000)
            logger.warning(
                "ASR识别失败，尝试降级",
                extra={"provider": provider.name, "error": str(e), "latency_ms": latency_ms},
            )
            self._mark_failure(provider.name)

            # 尝试降级到备用Provider
            fallback = self._get_fallback_provider(exclude=provider.name)
            if fallback:
                logger.info(
                    "ASR降级切换",
                    extra={"from": provider.name, "to": fallback.name},
                )
                try:
                    result = await fallback.recognize(audio_data, config)
                    self._mark_success(fallback.name)
                    logger.info(
                        "ASR降级识别成功",
                        extra={
                            "provider": result.provider,
                            "latency_ms": result.latency_ms,
                        },
                    )
                    return result
                except Exception as fallback_error:
                    self._mark_failure(fallback.name)
                    raise ASRError(
                        message=f"所有ASR Provider失败: primary={provider.name}, fallback={fallback.name}",
                        provider="manager",
                        cause=fallback_error,
                    ) from fallback_error

            raise ASRError(
                message=f"ASR Provider失败且无备用: {provider.name}",
                provider=provider.name,
                cause=e if isinstance(e, Exception) else None,
            ) from e

    def _select_provider(self) -> ASRProvider:
        """选择最佳Provider。"""
        now = time.time()

        # 1. 尝试主Provider
        if self._primary in self._providers:
            primary = self._providers[self._primary]
            status = self._provider_status[primary.name]

            # 检查是否可以尝试恢复
            if not status.available and now >= status.recovery_at:
                status.available = True
                status.half_open = True
                logger.info("Provider进入半开状态", extra={"provider": primary.name})

            if status.available or not self._health_check_running:
                return primary

        # 2. 使用备用Provider
        if self._fallback in self._providers:
            fallback = self._providers[self._fallback]
            status = self._provider_status[fallback.name]
            if not status.available and now >= status.recovery_at:
                status.available = True
                status.half_open = True
            return fallback

        # 3. 按优先级选择
        sorted_providers = sorted(
            self._providers.values(), key=lambda p: p.priority, reverse=True
        )
        if sorted_providers:
            return sorted_providers[0]

        raise RuntimeError("没有可用的ASR Provider")

    def _get_fallback_provider(self, exclude: str) -> Optional[ASRProvider]:
        """获取备用Provider（排除指定的）。"""
        if self._fallback in self._providers and self._fallback != exclude:
            return self._providers[self._fallback]

        # 选择优先级次高的
        sorted_providers = sorted(
            self._providers.values(), key=lambda p: p.priority, reverse=True
        )
        for p in sorted_providers:
            if p.name != exclude:
                status = self._provider_status[p.name]
                if status.available or time.time() >= status.recovery_at:
                    return p
        return None

    def _get_status_snapshot(self) -> dict[str, bool]:
        """获取所有Provider的状态快照。"""
        return {name: status.available for name, status in self._provider_status.items()}

    @property
    def provider_status(self) -> dict[str, bool]:
        """获取所有Provider的健康状态。"""
        return self._get_status_snapshot()

    async def start_health_check(self) -> None:
        """启动后台健康检查任务。"""
        if self._health_check_task is not None:
            logger.warning("健康检查已在运行")
            return

        self._health_check_running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(
            "健康检查已启动",
            extra={"interval": self._health_check_interval, "providers": list(self._providers.keys())},
        )

    async def stop_health_check(self) -> None:
        """停止后台健康检查任务。"""
        if self._health_check_task is None:
            return

        self._health_check_running = False
        self._health_check_task.cancel()
        try:
            await self._health_check_task
        except asyncio.CancelledError:
            pass
        self._health_check_task = None
        logger.info("健康检查已停止")

    async def _health_check_loop(self) -> None:
        """健康检查循环。"""
        while self._health_check_running:
            try:
                await self._perform_health_checks()
            except Exception as e:
                logger.error("健康检查循环出错: %s", str(e))
            await asyncio.sleep(self._health_check_interval)

    async def _perform_health_checks(self) -> None:
        """执行一次健康检查。"""
        for name, provider in self._providers.items():
            status = self._provider_status[name]
            check_start = time.time()

            try:
                is_healthy = await provider.health_check()
                latency_ms = int((time.time() - check_start) * 1000)
                status.last_check_time = time.time()
                status.last_latency_ms = latency_ms

                if is_healthy:
                    status.consecutive_successes += 1
                    status.consecutive_failures = 0
                    # 连续成功2次后恢复可用
                    if status.consecutive_successes >= 2:
                        was_unavailable = not status.available
                        status.available = True
                        status.half_open = False
                        status.recovery_at = 0.0
                        if was_unavailable:
                            logger.info("Provider恢复可用", extra={"provider": name})
                else:
                    status.consecutive_failures += 1
                    status.consecutive_successes = 0
                    # 连续失败3次后标记不可用
                    if status.consecutive_failures >= 3:
                        was_available = status.available
                        status.available = False
                        status.recovery_at = time.time() + self._recovery_seconds
                        if was_available:
                            logger.warning("Provider标记为不可用", extra={"provider": name})

            except Exception as e:
                logger.error("健康检查异常", extra={"provider": name, "error": str(e)})
                status.consecutive_failures += 1
                status.consecutive_successes = 0

        logger.debug("健康检查完成", extra={"status": self._get_status_snapshot()})
