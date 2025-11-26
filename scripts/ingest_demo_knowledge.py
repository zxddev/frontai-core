"""一次性向 Qdrant/Neo4j 写入演示知识数据。

数据来源：
- config/military/mt_library.json           (任务库)
- config/military/s[1-4]_capabilities.json  (能力指标与约束)
- config/military/trr_rules_docx.json       (触发规则)
- config/military/hard_rules_docx.json      (硬约束规则)

用途：让 /agent 的 RAG 与图谱查询有最基本的返回，避免空结果报错。
"""
from __future__ import annotations

import argparse
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Sequence

from langchain_openai import OpenAIEmbeddings
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from infra.settings import load_settings


logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_docs() -> List[Dict[str, Any]]:
    """构造待写入的文档列表，每个文档包含 text/payload。"""
    docs: List[Dict[str, Any]] = []

    # 任务库
    mt_data = _load_json(ROOT / "config/military/mt_library.json").get("mt_library", [])
    for mt in mt_data:
        scenes: Sequence[str] = mt.get("typical_scenes", [])
        text = (
            f"[任务]{mt.get('id')} {mt.get('name')} 阶段:{mt.get('phase')} "
            f"前置:{mt.get('precondition')} 效果:{mt.get('effect')} 场景:{','.join(scenes)}"
        )
        docs.append(
            {
                "text": text,
                "payload": {
                    "type": "task",
                    "id": mt.get("id"),
                    "name": mt.get("name"),
                    "phase": mt.get("phase"),
                    "scene_ids": list(scenes),
                    "source": "mt_library",
                },
            }
        )

    # 能力指标（按场景）
    for sid in ("s1", "s2", "s3", "s4"):
        data = _load_json(ROOT / f"config/military/{sid}_capabilities.json")
        scene_id = sid.upper()
        for metric in data.get("metrics", []):
            text = (
                f"[能力]{metric.get('id')} {metric.get('name')} 类型:{metric.get('type')} "
                f"目标:{metric.get('target')}{metric.get('unit')} 约束:{','.join(metric.get('constraints', []))}"
            )
            docs.append(
                {
                    "text": text,
                    "payload": {
                        "type": "capability",
                        "id": metric.get("id"),
                        "name": metric.get("name"),
                        "scene_ids": [scene_id],
                        "source": f"{scene_id}_capabilities",
                    },
                }
            )
        for con in data.get("constraints", []):
            text = f"[约束]{con.get('id')} {con.get('name')} 类别:{con.get('category')} 描述:{con.get('description')} 优先级:{con.get('priority')}"
            docs.append(
                {
                    "text": text,
                    "payload": {
                        "type": "constraint",
                        "id": con.get("id"),
                        "name": con.get("name"),
                        "scene_ids": [scene_id],
                        "source": f"{scene_id}_capabilities",
                    },
                }
            )

    # 规则（TRR + Hard）
    def _rules_from(path: Path, rule_type: str) -> None:
        data = _load_json(path)
        for rule in data.get("rules", []):
            scene_ids = rule.get("scene") or ["S1", "S2", "S3", "S4"]
            if isinstance(scene_ids, str):
                scene_ids = [scene_ids]
            body = rule.get("content") or rule.get("description") or rule.get("name")
            text = f"[规则]{rule.get('id')} {rule.get('name')} 内容:{body} 场景:{','.join(scene_ids)}"
            docs.append(
                {
                    "text": text,
                    "payload": {
                        "type": rule_type,
                        "id": rule.get("id"),
                        "name": rule.get("name"),
                        "scene_ids": list(scene_ids),
                        "source": path.name,
                    },
                }
            )

    _rules_from(ROOT / "config/military/trr_rules_docx.json", "trr_rule")
    _rules_from(ROOT / "config/military/hard_rules_docx.json", "hard_rule")

    return docs


def _ensure_collection(client: QdrantClient, collection: str, dim: int) -> None:
    if client.collection_exists(collection):
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )


def ingest_qdrant(docs: List[Dict[str, Any]]) -> None:
    settings = load_settings()
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
    )
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    # 预先计算一个向量，创建集合
    sample_vec = embeddings.embed_query(docs[0]["text"])
    _ensure_collection(client, settings.qdrant_collection, len(sample_vec))

    points: List[PointStruct] = []
    for doc in docs:
        vec = embeddings.embed_query(doc["text"])
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": doc["text"], **doc["payload"]},
            )
        )

    client.upsert(collection_name=settings.qdrant_collection, points=points)
    logger.info("Qdrant 已写入 %d 条文档", len(points))


def ingest_neo4j(docs: List[Dict[str, Any]]) -> None:
    settings = load_settings()
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

    scene_names = {
        "S1": "拦打隐身战斗机",
        "S2": "拦截来袭非隐身目标",
        "S3": "对海火力打击",
        "S4": "防区外压制防空",
    }

    scenes = [{"id": sid, "name": scene_names.get(sid, sid)} for sid in scene_names]
    rules = [d for d in docs if d["payload"].get("type") in {"trr_rule", "hard_rule"}]

    with driver.session() as session:
        session.run(
            """
            UNWIND $scenes AS s
            MERGE (scene:Scene {id:s.id})
            SET scene.name = coalesce(s.name, scene.name)
            """,
            scenes=scenes,
        )

        session.run(
            """
            UNWIND $rules AS r
            MERGE (rule:Rule {id:r.id})
            SET rule.name = coalesce(r.name, rule.name), rule.source = r.source
            WITH rule, r
            UNWIND r.scene_ids AS sid
            MERGE (scene:Scene {id:sid})
            MERGE (scene)-[:HAS_RULE]->(rule)
            """,
            rules=[r["payload"] for r in rules],
        )

    driver.close()
    logger.info("Neo4j 已写入 Scene/Rule 节点: 场景 %d，规则关系 %d", len(scenes), len(rules))


def main(skip_qdrant: bool, skip_neo4j: bool) -> None:
    logging.basicConfig(level=logging.INFO)
    docs = _build_docs()
    logger.info("构造文档 %d 条", len(docs))
    if not skip_qdrant:
        ingest_qdrant(docs)
    if not skip_neo4j:
        ingest_neo4j(docs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="写入演示知识数据到 Qdrant/Neo4j")
    parser.add_argument("--skip-qdrant", action="store_true", help="仅写 Neo4j，跳过 Qdrant")
    parser.add_argument("--skip-neo4j", action="store_true", help="仅写 Qdrant，跳过 Neo4j")
    args = parser.parse_args()
    main(skip_qdrant=args.skip_qdrant, skip_neo4j=args.skip_neo4j)
