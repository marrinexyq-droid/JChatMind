"""
Phase 1: Ground Truth 构建
- 从 DB 读取 chunk，建立逻辑 ID → UUID 映射
- 提取子切片的 Hypothetical_Questions
- 对 Intro/Conclusion chunk 用智谱 GLM 反向生成 query
- 输出 queries.json
"""
import json
import os
import sys
import time

import psycopg2
from zhipuai import ZhipuAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *


def get_db():
    return psycopg2.connect(**DB_CONFIG)


def build_chunk_map(kb_id: str) -> dict:
    """从 DB 读取所有 chunk，按 doc_id 分组，created_at 排序，建立逻辑 ID 映射"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, kb_id, doc_id, content
           FROM chunk_bge_m3
           WHERE kb_id = %s::uuid
           ORDER BY doc_id, created_at""",
        (kb_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    docs: dict[str, list[tuple]] = {}
    for row in rows:
        docs.setdefault(row[2], []).append(row)

    mapping: dict[str, list[dict]] = {}
    for doc_id, chunks in docs.items():
        for i, (uuid, _kb, _doc, content) in enumerate(chunks):
            logical_id = f"{doc_id}_chunk_{i}"
            mapping.setdefault(doc_id, []).append({
                "logical_id": logical_id,
                "uuid": uuid,
                "content": content,
            })

    print(f"Chunk 映射: {len(mapping)} docs, "
          f"{sum(len(v) for v in mapping.values())} chunks total")
    for doc_id, entries in mapping.items():
        print(f"  {doc_id}: {len(entries)} chunks "
              f"({[e['logical_id'] for e in entries]})")
    return mapping


def extract_hq_queries(chunk_map: dict) -> list[dict]:
    """从 chunk 内容中提取已有的 Hypothetical_Questions"""
    queries = []
    for doc_id, entries in chunk_map.items():
        for entry in entries:
            content = entry["content"]
            for line in content.split("\n"):
                line = line.strip()
                if "Hypothetical_Questions:" in line:
                    bracket = line.find("[")
                    if bracket > 0:
                        try:
                            hqs = json.loads(line[bracket:])
                            for hq in hqs:
                                queries.append({
                                    "query_id": f"hq_{len(queries):03d}",
                                    "query": hq,
                                    "ground_truth_chunk_ids": [
                                        entry["logical_id"]],
                                    "source": "hq",
                                    "doc_id": doc_id,
                                })
                        except json.JSONDecodeError:
                            pass
    return queries


def generate_queries_glm(chunk_map: dict) -> list[dict]:
    """对 Intro/Conclusion chunk 用 GLM 反向生成 query"""
    client = ZhipuAI(api_key=ZHIPUAI_API_KEY)
    queries = []

    for doc_id, entries in chunk_map.items():
        for entry in entries:
            content = entry["content"]
            if "Hypothetical_Questions" in content:
                continue
            if len(content) < 50:
                continue

            prompt = f"""请根据以下文本内容，生成2-3个只能由这段文本
才能准确回答的专业问题。问题需要覆盖文本的核心知识点，不要过于宽泛。

文本：
{content[:2000]}

要求：
- 问题应该具体，提到关键概念
- 每个问题应该能被文本中不超过3句话回答
- 输出格式：每行一个问句，不要编号"""

            try:
                resp = client.chat.completions.create(
                    model=ZHIPUAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                text = resp.choices[0].message.content.strip()
                for line in text.split("\n"):
                    line = line.strip()
                    if line and len(line) > 5:
                        queries.append({
                            "query_id": f"glm_{len(queries):03d}",
                            "query": line,
                            "ground_truth_chunk_ids": [
                                entry["logical_id"]],
                            "source": "glm",
                            "doc_id": doc_id,
                        })
                print(f"  {entry['logical_id']}: "
                      f"生成 {len(text.split(chr(10)))} 条 query")
                time.sleep(0.5)
            except Exception as e:
                print(f"  GLM 失败 {entry['logical_id']}: {e}")

    return queries


def main():
    kb_id = input("输入知识库 ID: ").strip()
    if not kb_id:
        print("错误: 需要提供知识库 ID")
        sys.exit(1)

    print("Step 1: 构建 chunk ID 映射...")
    chunk_map = build_chunk_map(kb_id)

    print("\nStep 2: 提取 Hypothetical_Questions...")
    hq_queries = extract_hq_queries(chunk_map)
    print(f"  从 HQ 提取了 {len(hq_queries)} 条 query")

    print("\nStep 3: 用智谱 GLM 反向生成 query...")
    glm_queries = generate_queries_glm(chunk_map)
    print(f"  GLM 生成了 {len(glm_queries)} 条 query")

    all_queries = hq_queries + glm_queries
    seen = set()
    deduped = []
    for q in all_queries:
        key = q["query"][:30]
        if key not in seen:
            seen.add(key)
            deduped.append(q)

    output = {
        "kb_id": kb_id,
        "total_queries": len(deduped),
        "hq_count": len(hq_queries),
        "glm_count": len(glm_queries),
        "chunk_map": chunk_map,
        "queries": deduped,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 共 {len(deduped)} 条 query → {QUERIES_FILE}")


if __name__ == "__main__":
    main()
