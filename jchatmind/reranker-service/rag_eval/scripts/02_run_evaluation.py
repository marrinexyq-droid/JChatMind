"""
Phase 2: 检索评估执行
- 加载 queries.json
- 对每条 query 跑 3 种检索模式 (vector / hybrid / hybrid-rerank)
- 记录 Top-K 结果和延迟
- 输出原始结果到 output/raw_results/
"""
import json
import os
import sys
import time

import numpy as np
import psycopg2
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *


def get_db():
    return psycopg2.connect(**DB_CONFIG)


def embed(text: str) -> np.ndarray:
    resp = requests.post(
        f"{OLLAMA_BASE}/api/embeddings",
        json={"model": OLLAMA_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return np.array(resp.json()["embedding"], dtype=np.float32)


def to_pg_vector(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


_chunk_embeddings_cache: dict[str, dict[str, np.ndarray]] = {}


def build_chunk_embeddings(conn, kb_id: str) -> dict[str, np.ndarray]:
    """heading-only 模式下，重新对 chunk 做 embedding"""
    cache_key = f"{kb_id}:{EMBED_MODE}"
    if cache_key in _chunk_embeddings_cache:
        return _chunk_embeddings_cache[cache_key]

    cur = conn.cursor()
    cur.execute(
        "SELECT id, content FROM chunk_bge_m3 WHERE kb_id = %s::uuid",
        (kb_id,),
    )
    rows = cur.fetchall()
    cur.close()

    embs = {}
    print(f"  重新计算 {len(rows)} 个 chunk 的 embedding (mode={EMBED_MODE})...")
    for cid, content in rows:
        if EMBED_MODE == "heading-only":
            text = content.split("\n")[0] if content else ""
        else:
            text = content if content else ""
        embs[cid] = embed(text)
    _chunk_embeddings_cache[cache_key] = embs
    return embs


def vector_search(conn, vec: np.ndarray, kb_id: str, limit: int) -> list[tuple]:
    if EMBED_MODE == "heading+body":
        vec_str = to_pg_vector(vec)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, kb_id, doc_id, content,
                      embedding <-> %s::vector AS distance
               FROM chunk_bge_m3
               WHERE kb_id = %s::uuid
               ORDER BY embedding <-> %s::vector
               LIMIT %s""",
            (vec_str, kb_id, vec_str, limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [(r[0], r[1], r[2], r[3], float(r[4])) for r in rows]

    # heading-only 模式：内存中计算余弦相似度
    embs = build_chunk_embeddings(conn, kb_id)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, kb_id, doc_id, content FROM chunk_bge_m3 WHERE kb_id = %s::uuid",
        (kb_id,),
    )
    rows = cur.fetchall()
    cur.close()

    vec_norm = np.linalg.norm(vec)
    scored = []
    for r in rows:
        cid = r[0]
        chunk_vec = embs[cid]
        sim = float(np.dot(vec, chunk_vec) / (vec_norm * np.linalg.norm(chunk_vec)))
        scored.append((r[0], r[1], r[2], r[3], 1.0 - sim))
    scored.sort(key=lambda x: x[4])
    return scored[:limit]


def bm25_search(conn, query: str, kb_id: str, limit: int) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(
        """SELECT id, kb_id, doc_id, content,
                  ts_rank_cd(content_tsv,
                    websearch_to_tsquery('simple', %s)) AS score
           FROM chunk_bge_m3
           WHERE kb_id = %s::uuid
             AND content_tsv @@ websearch_to_tsquery('simple', %s)
           ORDER BY score DESC
           LIMIT %s""",
        (query, kb_id, query, limit),
    )
    rows = cur.fetchall()
    cur.close()
    return [(r[0], r[1], r[2], r[3], float(r[4])) for r in rows]


def rrf_fusion(vec_results, bm25_results):
    scores: dict[str, float] = {}
    info: dict[str, dict] = {}
    for rank, r in enumerate(vec_results):
        cid = r[0]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
        info.setdefault(cid, {"id": r[0], "content": r[3], "source": "vector"})
    for rank, r in enumerate(bm25_results):
        cid = r[0]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
        info.setdefault(cid, {"id": r[0], "content": r[3], "source": "bm25"})
    sorted_ids = sorted(scores, key=scores.get, reverse=True)
    return [{**info[cid], "score": scores[cid]} for cid in sorted_ids]


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    docs = [c["content"] for c in candidates]
    resp = requests.post(
        f"{RERANKER_BASE}/rerank",
        json={"query": query, "documents": docs},
        timeout=30,
    )
    resp.raise_for_status()
    scores = resp.json()
    results = []
    for item in scores:
        idx = item["index"]
        if idx < len(candidates):
            results.append({**candidates[idx],
                            "score": item["score"], "source": "rerank"})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def run_single_query(conn, query_info: dict, kb_id: str) -> dict:
    query_text = query_info["query"]
    timings: dict[str, dict] = {}

    # embed once
    t0 = time.perf_counter()
    qvec = embed(query_text)
    t_embed = (time.perf_counter() - t0) * 1000

    # vector search
    t0 = time.perf_counter()
    vres = vector_search(conn, qvec, kb_id, CANDIDATE_POOL_SIZE)
    t_vec = (time.perf_counter() - t0) * 1000

    vec_top10 = [{"id": r[0], "content": r[3], "score": float(r[4]),
                  "source": "vector"} for r in vres[:10]]
    timings["vector"] = {"embed_ms": t_embed, "search_ms": t_vec,
                         "total_ms": t_embed + t_vec}

    # bm25
    t0 = time.perf_counter()
    bres = bm25_search(conn, query_text, kb_id, CANDIDATE_POOL_SIZE)
    t_bm25 = (time.perf_counter() - t0) * 1000

    # hybrid (rrf only, no rerank)
    fused = rrf_fusion(vres, bres)
    hybrid_top10 = fused[:10]
    timings["hybrid"] = {"embed_ms": t_embed, "vector_ms": t_vec,
                         "bm25_ms": t_bm25, "total_ms": t_embed + t_vec + t_bm25}

    # hybrid-rerank
    t0 = time.perf_counter()
    reranked = rerank(query_text, fused, 10)
    t_rerank = (time.perf_counter() - t0) * 1000
    timings["hybrid-rerank"] = {"embed_ms": t_embed, "vector_ms": t_vec,
                                "bm25_ms": t_bm25, "rerank_ms": t_rerank,
                                "total_ms": t_embed + t_vec + t_bm25 + t_rerank}

    return {
        "query_id": query_info["query_id"],
        "query": query_text,
        "ground_truth": query_info["ground_truth_chunk_ids"],
        "results": {
            "vector": vec_top10,
            "hybrid": hybrid_top10,
            "hybrid-rerank": reranked,
        },
        "timings": timings,
    }


def main():
    if not os.path.exists(QUERIES_FILE):
        print(f"queries.json 不存在，请先运行 01_build_ground_truth.py")
        sys.exit(1)

    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    kb_id = data["kb_id"]
    queries = data["queries"]
    print(f"加载 {len(queries)} 条 query, kb_id={kb_id}")

    conn = get_db()
    results = []
    for i, q in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] {q['query'][:50]}...")
        try:
            r = run_single_query(conn, q, kb_id)
            results.append(r)
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"query_id": q["query_id"], "error": str(e)})
        time.sleep(0.1)

    conn.close()
    out_path = os.path.join(RAW_DIR, "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n完成! {len(results)} 条结果 → {out_path}")


if __name__ == "__main__":
    main()
