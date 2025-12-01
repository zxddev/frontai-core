"""
语义路由层 (Hybrid)

基于 semantic-router 库的毫秒级意图分流 + LLM fallback。
高置信度时直接路由，低置信度时用 LLM 兜底。

参考: vLLM Semantic Router, RouteLLM, EMNLP 2024 Intent Detection
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Tuple

from semantic_router import Route, SemanticRouter
from semantic_router.encoders import OpenAIEncoder

from src.infra.settings import load_settings

logger = logging.getLogger(__name__)

# Hybrid路由置信度阈值
HYBRID_CONFIDENCE_THRESHOLD = 0.78


# 路由名称到目标Agent的映射
ROUTE_TARGETS: Dict[str, str] = {
    "spatial_query": "spatial_agent",      # 空间位置查询
    "task_status": "task_agent",           # 任务状态查询
    "resource_status": "resource_agent",   # 资源状态查询
    "robot_command": "commander_agent",    # 机器人控制
    "chitchat": "basic_llm",               # 闲聊
}


# 关键词规则（优先于语义路由，按优先级排序）
KEYWORD_RULES: Dict[str, list[str]] = {
    "spatial_query": ["在哪", "什么位置", "最近的", "多远", "附近有"],
    "resource_status": ["可调度", "资源统计", "可以调动", "队伍状态"],
    "task_status": ["任务"],
}


def keyword_classify(text: str) -> Optional[str]:
    """
    关键词规则匹配（优先于语义路由）
    
    对包含明确关键词的查询直接返回路由结果，无需语义匹配。
    特殊处理：
    - "X队在执行什么任务" → resource_status（询问队伍状态）
    - "正在执行什么任务" → task_status（询问任务状态）
    """
    # 特殊规则：队伍执行任务查询
    if "执行什么任务" in text:
        if "队" in text:
            return "resource_status"
        else:
            return "task_status"
    
    # 通用关键词匹配
    for route, keywords in KEYWORD_RULES.items():
        for kw in keywords:
            if kw in text:
                return route
    return None


def _create_default_routes() -> list[Route]:
    """创建默认路由配置，增加更多训练样本提高准确率"""
    return [
        Route(
            name="spatial_query",
            utterances=[
                # 位置查询 - "在哪里"系列
                "消防大队在哪里",
                "茂县消防大队在哪里",
                "救援队在哪里",
                "一号车辆在哪里",
                "无人机在哪里",
                "机器狗在哪里",
                "他们在哪里",
                "队伍在哪里",
                "在哪",
                "在什么位置",
                "指挥部在哪里",
                "医疗队在哪里",
                "安置点在什么位置",
                # 位置查询 - "位置"系列
                "一号车辆当前位置",
                "消防队的位置",
                "救援队位置",
                "查询位置",
                "当前位置",
                "实时位置",
                "无人机的位置",
                "机器狗的位置",
                "所有队伍的位置",
                # 最近查询
                "离震中最近的救援队",
                "离震中最近的救援队是哪支",
                "哪个队伍离这里最近",
                "最近的消防队",
                "最近的医疗队",
                "最近的救援力量",
                "谁离这里最近",
                "谁离伤员最近",
                "找最近的",
                "附近有什么队伍",
                "附近有哪些救援力量",
                "周边有什么",
                "离我最近的医疗点",
                "最近的消防站在哪",
                "从指挥部到受灾点多远",
                # 区域查询
                "B区有多少救援人员",
                "这个区域有哪些队伍",
                "当前区域有哪些队伍",
                "区域内有多少队伍",
                "A区的情况",
                "A区域现在什么情况",
                "B区状态怎么样",
                "附近有什么资源",
                "哪里需要支援",
                # 通用查询
                "显示所有队伍",
                "查看当前队伍位置",
                "找到救援队",
                "查一下位置",
                "定位",
            ],
            score_threshold=0.75,  # 降低阈值提高召回率
        ),
        Route(
            name="robot_command",
            utterances=[
                # 派遣指令
                "派无人机去东门侦察",
                "派遣无人机去侦查",
                "派一号无人机去化工厂",
                "派无人机过去",
                "派机器狗去",
                # 移动指令
                "让机器狗去化工厂",
                "让机器狗前往B区",
                "让无人机去东门巡逻",
                "机器狗去那边看看",
                "无人机飞到那个位置",
                "去那个位置",
                "移动到",
                # 控制指令
                "停止前进",
                "返航",
                "跟随我",
                "出发",
                "开始巡逻",
                "执行侦查任务",
                "停",
                "回来",
            ],
            score_threshold=0.80,  # 高阈值防止误触发
        ),
        Route(
            name="task_status",
            utterances=[
                # 任务进度查询
                "任务进度怎么样",
                "任务进度",
                "任务完成了多少",
                "任务进展如何",
                "任务执行情况",
                "当前有多少任务",
                "当前有多少任务在执行",
                "任务完成情况怎么样",
                "查看任务进度",
                "任务列表",
                "有哪些任务",
                "正在执行什么任务",
                # 按类型查询
                "搜救任务有多少",
                "搜救任务进度",
                "转运任务怎么样了",
                "侦察任务完成了吗",
                "紧急任务有几个",
                # 救援进度（映射到任务）
                "救援进度怎么样",
                "救援行动进展如何",
                "救援情况",
                "救了多少人",
            ],
            score_threshold=0.75,
        ),
        Route(
            name="resource_status",
            utterances=[
                # 队伍状态
                "消防队在干什么",
                "消防队在做什么",
                "一号车队在干什么",
                "他们在做什么",
                "队伍状态",
                "队伍在执行什么任务",
                # 具体队伍状态查询
                "一号车队状态",
                "二号队在执行什么任务",
                "救援队现在忙吗",
                "医疗队忙不忙",
                "三号队在做什么",
                "消防队现在忙吗",
                # 空闲资源
                "还有哪些队伍可用",
                "哪些队伍空闲",
                "有多少队伍待命",
                "可用的救援力量",
                "空闲的队伍",
                "谁还没有任务",
                "有没有空闲的救援队",
                "可调度的队伍有哪些",
                # 人员资源
                "还有多少人员待命",
                "消防车可以调动吗",
                # 资源统计
                "有多少救援队伍",
                "当前有多少队伍",
                "资源情况",
                "队伍数量",
                "队伍部署情况",
                "队伍资源情况",
                "资源统计",
                "队伍状态汇总",
            ],
            score_threshold=0.75,
        ),
        Route(
            name="chitchat",
            utterances=[
                "你好",
                "听得见吗",
                "谢谢",
                "好的",
                "明白了",
                "收到",
                "在吗",
                "你是谁",
                "嗯",
                "今天天气怎么样",
                "能听到吗",
                "测试",
                "好",
                "可以",
            ],
            score_threshold=0.75,
        ),
    ]


class VoiceSemanticRouter:
    """
    语音意图语义路由器
    
    基于 semantic-router 库进行快速意图分类，支持：
    - OpenAI兼容的embedding服务
    - 自定义路由配置和阈值
    - 降级到全量LLM
    - 路由准确率监控
    """
    
    def __init__(
        self,
        routes: Optional[list[Route]] = None,
        encoder: Optional[OpenAIEncoder] = None,
    ) -> None:
        """
        初始化语义路由器
        
        Args:
            routes: 路由配置列表，默认使用_create_default_routes()
            encoder: 自定义encoder，默认从settings加载
        """
        self._routes = routes or _create_default_routes()
        self._encoder = encoder
        self._semantic_router: Optional[SemanticRouter] = None
        self._initialized = False
        
        logger.info(
            "语义路由器创建",
            extra={"routes": [r.name for r in self._routes]},
        )
    
    async def _ensure_initialized(self) -> None:
        """确保路由器已初始化（懒加载）"""
        if self._initialized:
            return
        
        # 初始化encoder
        if self._encoder is None:
            settings = load_settings()
            # 使用OpenAI兼容的embedding服务
            # 创建一个自定义encoder，绕过tiktoken的模型名检查
            encoder_name = settings.embedding_model  # 使用实际的embedding模型名
            
            # Monkey-patch tiktoken.encoding_for_model 来处理未知模型名
            import tiktoken
            original_encoding_for_model = tiktoken.encoding_for_model
            
            def patched_encoding_for_model(model_name: str):
                try:
                    return original_encoding_for_model(model_name)
                except KeyError:
                    # 对于未知模型，使用cl100k_base（适用于大多数新模型）
                    return tiktoken.get_encoding("cl100k_base")
            
            tiktoken.encoding_for_model = patched_encoding_for_model
            
            try:
                self._encoder = OpenAIEncoder(
                    name=encoder_name,
                    openai_base_url=settings.semantic_router_embedding_base_url,
                    openai_api_key=settings.embedding_api_key,
                    score_threshold=0.5,
                )
            finally:
                # 恢复原始函数
                tiktoken.encoding_for_model = original_encoding_for_model
            
            logger.info(
                f"Encoder初始化: model={encoder_name}, "
                f"base_url={settings.semantic_router_embedding_base_url}"
            )
        
        # 创建SemanticRouter
        # auto_sync="local" 会在初始化时同步路由embeddings到本地索引
        try:
            self._semantic_router = SemanticRouter(
                encoder=self._encoder,
                routes=self._routes,
                auto_sync="local",  # 启用本地同步
            )
        except (TypeError, Exception) as e:
            logger.warning(f"使用auto_sync='local'失败: {e}, 尝试不带该参数")
            self._semantic_router = SemanticRouter(
                encoder=self._encoder,
                routes=self._routes,
            )
        
        self._initialized = True
        logger.info("语义路由器初始化完成")
    
    async def _semantic_classify(self, text: str) -> Tuple[str, float]:
        """
        执行快速语义分类（内部方法）
        
        Returns:
            (route_name, confidence)
        """
        await self._ensure_initialized()
        
        result = self._semantic_router(text)
        
        route_name = result.name if result.name else "chitchat"
        
        # 获取相似度分数
        confidence = 0.0
        if hasattr(result, 'similarity_score') and result.similarity_score is not None:
            confidence = result.similarity_score
        elif result.name is not None:
            confidence = 0.85
        
        return route_name, confidence
    
    async def _llm_classify(self, text: str) -> str:
        """
        LLM fallback 分类
        
        Returns:
            route_name
        """
        from src.agents.voice_commander.llm_router import get_llm_router
        
        llm_router = get_llm_router()
        route, _ = await llm_router.classify(text)
        return route
    
    async def classify(self, text: str) -> tuple[str, float, bool]:
        """
        Hybrid 意图分类
        
        流程:
        1. 关键词规则匹配（毫秒级，100%准确）
        2. Semantic Router 初筛（毫秒级）
        3. 置信度 >= 0.78 → 直接返回
        4. 置信度 < 0.78 → LLM fallback（秒级）
        
        Args:
            text: 用户输入文本
            
        Returns:
            (route_name, confidence, used_llm_fallback)
        """
        start_ts = time.time()
        
        try:
            # 1. 关键词规则匹配（优先，100%准确）
            keyword_result = keyword_classify(text)
            if keyword_result:
                logger.info(
                    f"Hybrid路由[Keyword]: '{text[:30]}' -> {keyword_result} "
                    f"({(time.time()-start_ts)*1000:.0f}ms)"
                )
                return keyword_result, 1.0, False
            
            # 2. Semantic Router 初筛
            route_name, confidence = await self._semantic_classify(text)
            
            # 3. 高置信度直接返回
            if confidence >= HYBRID_CONFIDENCE_THRESHOLD:
                logger.info(
                    f"Hybrid路由[Semantic]: '{text[:30]}' -> {route_name} "
                    f"(conf={confidence:.2f}, {(time.time()-start_ts)*1000:.0f}ms)"
                )
                return route_name, confidence, False
            
            # 4. 低置信度用 LLM 兜底
            logger.info(
                f"Hybrid路由置信度低({confidence:.2f}), 使用LLM fallback"
            )
            route_name = await self._llm_classify(text)
            
            logger.info(
                f"Hybrid路由[LLM]: '{text[:30]}' -> {route_name} "
                f"({(time.time()-start_ts)*1000:.0f}ms)"
            )
            return route_name, 1.0, True  # LLM决策视为高置信
            
        except Exception as e:
            logger.error(f"Hybrid路由失败: {e}")
            return "chitchat", 0.0, True
    
    def get_target(self, route_name: str) -> str:
        """获取路由目标Agent"""
        return ROUTE_TARGETS.get(route_name, "basic_llm")
    
    def get_routes(self) -> list[Route]:
        """获取所有路由配置"""
        return self._routes


# 全局单例
_router_instance: Optional[VoiceSemanticRouter] = None


def get_semantic_router() -> VoiceSemanticRouter:
    """获取语义路由器单例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = VoiceSemanticRouter()
    return _router_instance


async def reset_semantic_router() -> None:
    """重置语义路由器（用于测试或重新加载配置）"""
    global _router_instance
    _router_instance = None
    logger.info("语义路由器已重置")
