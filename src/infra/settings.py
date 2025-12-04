"""环境配置加载，确保所有外部依赖参数齐全。
- 优先读取本地配置文件 config/private.yaml（硬编码密钥与端点），无则读取环境变量。
- 任何必填项缺失直接抛出异常，不做降级或默认猜测。
"""
from __future__ import annotations

import os  # 导入标准库 os 用于读取环境变量
from dataclasses import dataclass  # 使用 dataclass 保证字段强类型
from pathlib import Path  # 用于定位配置文件
from typing import Optional  # Optional 类型提示

import yaml  # 解析 YAML 配置


@dataclass(frozen=True)
class Settings:
    """运行时配置，覆盖大模型、向量库、图数据库与 Postgres。"""
    openai_base_url: str  # vLLM 网关地址
    openai_api_key: str  # vLLM 兼容密钥
    llm_model: str  # 模型名称或路径
    request_timeout: float  # 请求超时秒
    max_concurrency: int  # 最大并发
    embedding_base_url: str  # 向量服务网关
    embedding_model: str  # 向量模型
    embedding_api_key: str  # 向量模型密钥
    qdrant_url: str  # Qdrant 服务地址
    qdrant_api_key: str  # Qdrant 密钥
    qdrant_collection: str  # Qdrant 集合名
    rag_top_k: int  # RAG 检索数量
    neo4j_uri: str  # Neo4j 地址
    neo4j_user: str  # Neo4j 用户
    neo4j_password: str  # Neo4j 密码
    postgres_dsn: str  # Postgres 连接串
    amap_api_key: str  # 高德地图Web服务API Key
    # 语音指挥Agent配置
    semantic_router_embedding_model: str  # 语义路由embedding模型（中文优化）
    semantic_router_embedding_base_url: str  # 语义路由embedding服务地址
    robot_command_enabled: bool  # 机器人控制功能开关
    # 机器狗适配器配置
    adapter_hub_base_url: str  # adapter-hub 服务地址，如 http://192.168.31.40:8082
    default_robotdog_id: str  # 默认机器狗设备ID


def _require_env(name: str, default: Optional[str] = None) -> str:
    """读取必填环境变量，缺失则抛错，避免隐式降级。"""
    raw = os.getenv(name, default)  # 读取环境变量或默认值
    if raw is None or str(raw).strip() == "":  # 检查空值
        raise RuntimeError(f"缺少必要环境变量 {name}")  # 抛出异常
    return str(raw).strip()  # 返回去除空白的字符串


def _load_private_config() -> dict[str, str]:
    """优先读取本地私有配置文件 config/private.yaml。"""
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "private.yaml"  # 配置路径
    if not cfg_path.exists():  # 若不存在，返回空
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:  # 打开文件
        data = yaml.safe_load(f) or {}  # 解析 YAML
        if not isinstance(data, dict):  # 校验类型
            raise RuntimeError("config/private.yaml 内容必须是对象")  # 抛错
        return {str(k): str(v) for k, v in data.items()}  # 转为字符串字典


def load_settings() -> Settings:
    """加载并校验全部配置，不做任何回退。"""
    priv = _load_private_config()  # 读取本地私有配置

    def pick(name: str, default: Optional[str] = None) -> str:
        """优先使用私有配置，其次环境变量，最后默认值。"""
        if name in priv and str(priv[name]).strip():  # 私有配置存在且非空
            return str(priv[name]).strip()
        return _require_env(name, default)  # 回退到环境变量/默认

    def pick_optional(name: str, default: str = "") -> str:
        """可选配置，允许空字符串，不抛异常。"""
        if name in priv and str(priv[name]).strip():
            return str(priv[name]).strip()
        return os.getenv(name, default) or default

    openai_base_url = pick("OPENAI_BASE_URL", "http://localhost:8000/v1")  # vLLM 网关地址
    openai_api_key = pick("OPENAI_API_KEY", "your-api-key")  # 必填密钥
    llm_model = pick("LLM_MODEL", "gpt-4")  # 模型名称
    request_timeout = float(pick("LLM_REQUEST_TIMEOUT_SECONDS", "120"))  # 请求超时
    max_concurrency = int(pick("LLM_MAX_CONCURRENCY", "10"))  # 并发上限
    embedding_base_url = pick("EMBEDDING_BASE_URL", "http://localhost:8001/v1")  # embedding 网关
    embedding_model = pick("EMBEDDING_MODEL", "text-embedding-3-small")  # embedding 模型名
    embedding_api_key = pick("RAG_OPENAI_API_KEY", openai_api_key)  # 向量密钥
    qdrant_url = pick("QDRANT_URL", "http://localhost:6333")  # Qdrant 地址
    qdrant_api_key = pick("QDRANT_API_KEY", "your-qdrant-key")  # Qdrant 密钥
    qdrant_collection = pick("QDRANT_COLLECTION", "emergency_rules")  # 集合名
    rag_top_k = int(pick("RAG_TOP_K", "4"))  # 检索条数
    neo4j_uri = pick("NEO4J_URI", "bolt://localhost:7687")  # Neo4j 地址
    neo4j_user = pick("NEO4J_USER", "neo4j")  # Neo4j 用户
    neo4j_password = pick("NEO4J_PASSWORD", "your-neo4j-password")  # Neo4j 密码
    postgres_dsn = pick("POSTGRES_DSN", "postgresql://postgres:password@localhost:5432/emergency_planner")  # Postgres DSN
    amap_api_key = pick_optional("AMAP_API_KEY", "")  # 高德地图API Key（可选）
    # 语音指挥Agent配置
    semantic_router_embedding_model = pick_optional(
        "SEMANTIC_ROUTER_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )  # 中文优化embedding
    semantic_router_embedding_base_url = pick_optional(
        "SEMANTIC_ROUTER_EMBEDDING_BASE_URL", embedding_base_url
    )  # 默认复用现有embedding服务
    robot_command_enabled = pick_optional(
        "ROBOT_COMMAND_ENABLED", "false"
    ).lower() in ("true", "1", "yes")  # 默认关闭机器人控制
    # 机器狗适配器配置（固定值）
    adapter_hub_base_url = "http://192.168.31.40:8082"
    default_robotdog_id = "11"
    return Settings(
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        request_timeout=request_timeout,
        max_concurrency=max_concurrency,
        embedding_base_url=embedding_base_url,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        qdrant_collection=qdrant_collection,
        rag_top_k=rag_top_k,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        postgres_dsn=postgres_dsn,
        amap_api_key=amap_api_key,
        semantic_router_embedding_model=semantic_router_embedding_model,
        semantic_router_embedding_base_url=semantic_router_embedding_base_url,
        robot_command_enabled=robot_command_enabled,
        adapter_hub_base_url=adapter_hub_base_url,
        default_robotdog_id=default_robotdog_id,
    )
