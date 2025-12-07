from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.infra.config import AlgorithmConfigService, ConfigurationMissingError

logger = logging.getLogger(__name__)


class GRAConfigLoader:
    CATEGORY = "gra"
    PRIORITY_CODE = "GRA-PRIORITY-MAP"
    SWITCHING_CODE = "GRA-SWITCHING-COST"
    PREEMPTION_CODE = "GRA-PREEMPTION-RULES"

    def __init__(self, config_service: AlgorithmConfigService):
        self._config = config_service

    async def load_params(self) -> Dict[str, Any]:
        """
        加载GRA配置参数，用于ConflictResolver仲裁决策。
        
        配置来源: config.algorithm_parameters 表
        - GRA-PRIORITY-MAP: 任务类型优先级映射
        - GRA-SWITCHING-COST: 切换成本阈值和抢占参数
        - GRA-PREEMPTION-RULES: 抢占规则定义
        
        Returns:
            GRA参数字典，包含priority_map、cost_threshold、auto_preempt_diff等
            
        Raises:
            ConfigurationMissingError: 必需配置项缺失时抛出，不做降级处理
        """
        priority_cfg = await self._config.get_or_raise(self.CATEGORY, self.PRIORITY_CODE)
        switching_cfg = await self._config.get_or_raise(self.CATEGORY, self.SWITCHING_CODE)
        preemption_cfg = await self._config.get_or_raise(self.CATEGORY, self.PREEMPTION_CODE)

        # auto_preempt_priority_diff: 优先级差>=此值时自动抢占（如L0抢占L2）
        auto_preempt_diff: Optional[int] = switching_cfg.get("auto_preempt_priority_diff")
        if auto_preempt_diff is None:
            raise ConfigurationMissingError(
                category=self.CATEGORY,
                code=f"{self.SWITCHING_CODE}.auto_preempt_priority_diff"
            )

        # cost_threshold: 切换成本阈值，超过则不允许抢占
        cost_threshold: Optional[float] = switching_cfg.get("cost_threshold")
        if cost_threshold is None:
            raise ConfigurationMissingError(
                category=self.CATEGORY,
                code=f"{self.SWITCHING_CODE}.cost_threshold"
            )

        # min_priority_diff_for_preemption: 允许抢占的最小优先级差
        min_preempt_diff: int = switching_cfg.get("min_priority_diff_for_preemption", 1)

        # priority_map: 任务类型到优先级的映射
        priority_map: Dict[str, int] = priority_cfg.get("priority_map", {})
        if not priority_map:
            logger.warning(f"[GRA] {self.PRIORITY_CODE}.priority_map 为空，将使用默认优先级")

        params: Dict[str, Any] = {
            "gra_priority_map": priority_map,
            "gra_cost_threshold": cost_threshold,
            "gra_auto_preempt_diff": auto_preempt_diff,
            "gra_min_preempt_diff": min_preempt_diff,
        }

        logger.info(
            f"[GRA] 配置加载完成: auto_preempt_diff={auto_preempt_diff}, "
            f"cost_threshold={cost_threshold}, min_preempt_diff={min_preempt_diff}"
        )
        return params
