"""向 Qdrant 写入规则检索文档，使用真实向量生成。
- 依赖环境变量：QDRANT_URL/QDRANT_API_KEY/QDRANT_COLLECTION/OPENAI_BASE_URL/OPENAI_API_KEY/EMBEDDING_MODEL
- 不做降级，任一缺失即抛错。
"""
from __future__ import annotations

import os  # 读取环境变量
from typing import List  # 类型提示

from langchain_openai import OpenAIEmbeddings  # 向量模型
from qdrant_client import QdrantClient  # Qdrant 客户端
from qdrant_client.http import models as rest  # Qdrant REST 模型


def _require(name: str) -> str:
    """读取必填环境变量，缺失直接抛错。"""
    value = os.getenv(name)  # 读取值
    if value is None or value.strip() == "":  # 校验空值
        raise RuntimeError(f"缺少必要环境变量 {name}")  # 抛错
    return value.strip()  # 返回去空格后的值


def main() -> None:
    """创建集合并写入样例规则文档。"""
    qdrant_url = _require("QDRANT_URL")  # Qdrant 地址
    qdrant_api_key = _require("QDRANT_API_KEY")  # Qdrant 密钥
    collection = _require("QDRANT_COLLECTION")  # 集合名
    openai_base_url = _require("OPENAI_BASE_URL")  # 向量模型服务
    openai_api_key = _require("OPENAI_API_KEY")  # 向量模型密钥
    embedding_model = os.getenv("EMBEDDING_MODEL", "embedding-3")  # 向量模型名

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)  # 初始化 Qdrant 客户端
    embeddings = OpenAIEmbeddings(  # 初始化向量模型
        model=embedding_model, base_url=openai_base_url, api_key=openai_api_key
    )

    # 样例文档：规则描述 + 场景标签，scene_id 供规划图选择场景
    docs: List[dict] = [
        {
            "id": "R-001",
            "text": "R-001 反隐身空战：空中隐身目标，诱骗开机后远程打击，适用 S1",
            "scene_id": "S1",
        },
        {
            "id": "R-004",
            "text": "R-004 对海饱和攻击：目标驱护舰且防御强，防区外多轴向齐射，适用 S3",
            "scene_id": "S3",
        },
        {
            "id": "R-005",
            "text": "R-005 防空压制：辐射源活跃，诱饵前出+反辐射压制，适用 S4",
            "scene_id": "S4",
        },
    ]

    vectors = embeddings.embed_documents([d["text"] for d in docs])  # 生成真实向量

    # 创建/替换集合，使用向量模型维度
    client.recreate_collection(
        collection_name=collection,
        vectors_config=rest.VectorParams(size=len(vectors[0]), distance=rest.Distance.COSINE),
    )

    client.upsert(
        collection_name=collection,
        points=[
            rest.PointStruct(
                id=idx + 1,  # 使用数值 ID
                vector=vectors[idx],  # 向量
                payload={"id": doc["id"], "scene_id": doc["scene_id"], "text": doc["text"]},  # 元数据
            )
            for idx, doc in enumerate(docs)
        ],
    )
    print(f"已写入 {len(docs)} 条规则文档到集合 {collection}")


if __name__ == "__main__":
    main()
