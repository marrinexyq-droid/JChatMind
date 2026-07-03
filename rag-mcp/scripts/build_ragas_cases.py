from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"
LEGACY_EVAL_DIR = REPO_ROOT / "jchatmind" / "reranker-service" / "rag_eval"

ANSWER_SOURCES = [
    REPO_ROOT / "RAG-selfTest.md",
    REPO_ROOT / "学习文档" / "04-RAG知识库.md",
    REPO_ROOT / "学习文档" / "RAG深度学习笔记.md",
    REPO_ROOT / "面试备战" / "RAG" / "RAG系统复习.md",
    REPO_ROOT / "面试备战" / "RAG" / "RAG缺口补充_2026-05-28.md",
    REPO_ROOT / "面试备战" / "RAG" / "RAG_v2_评估数据与面试应答.md",
    REPO_ROOT / "面试备战" / "RAG" / "RAG_v2_多轮对比报告.md",
    REPO_ROOT / "面试备战" / "模拟面试" / "RAG模拟面试记录.md",
    REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-07-03-rag-dev-spec-replacement-design.md",
    REPO_ROOT / "docs" / "superpowers" / "plans" / "2026-07-03-rag-dev-spec-replacement-1.0.md",
    REPO_ROOT / "docs" / "superpowers" / "plans" / "2026-07-03-rag-dev-spec-replacement-1.1.md",
    PROJECT_ROOT / "README.md",
]

RAW_RESULT_FILES = [
    "results.json",
    "results_k30.json",
    "results_k120.json",
    "results_pool10.json",
    "results_heading_only.json",
]

RAGAS_CASE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "JChatMind RAGAS Case",
    "type": "object",
    "required": [
        "case_id",
        "dataset_split",
        "question",
        "answer",
        "contexts",
        "ground_truth",
        "reference_contexts",
        "ground_truth_context_ids",
        "collection",
        "tags",
        "difficulty",
        "expected_answer_type",
        "tactic",
        "source_refs",
        "quality",
    ],
    "properties": {
        "case_id": {"type": "string", "minLength": 8},
        "dataset_split": {"type": "string"},
        "question": {"type": "string", "minLength": 5},
        "answer": {"type": "string"},
        "answer_status": {"type": "string"},
        "contexts": {"type": "array", "items": {"type": "string"}},
        "ground_truth": {"type": "string", "minLength": 20},
        "reference_answer": {"type": "string"},
        "reference_contexts": {"type": "array", "items": {"type": "string"}},
        "ground_truth_context_ids": {"type": "array", "items": {"type": "string"}},
        "retrieved_context_ids": {"type": "array", "items": {"type": "string"}},
        "collection": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "difficulty": {"enum": ["easy", "medium", "hard"]},
        "expected_answer_type": {"type": "string"},
        "tactic": {"type": "string"},
        "source_refs": {"type": "array", "items": {"type": "object"}},
        "quality": {"type": "object"},
    },
}


@dataclass(frozen=True)
class MarkdownSection:
    path: Path
    heading: str
    level: int
    body: str
    start_line: int
    end_line: int
    has_nested_heading: bool

    @property
    def context_id(self) -> str:
        digest = stable_hash(
            f"{self.relative_path}:{self.start_line}:{self.heading}:{self.body[:240]}"
        )
        return f"md:{digest}"

    @property
    def relative_path(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records)
    path.write_text(text + "\n", encoding="utf-8")


def normalize_spaces(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def strip_markdown_noise(value: str) -> str:
    value = re.sub(r"```.*?```", " ", value, flags=re.S)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"^\s*[-*+]\s+", "", value, flags=re.M)
    value = re.sub(r"^\s*\d+\.\s+", "", value, flags=re.M)
    value = value.replace("**", "").replace("__", "")
    return normalize_spaces(value)


def bad_text_score(value: str) -> float:
    if not value:
        return 1.0
    markers = ["�", "鐖", "鍥", "锛", "馃", "€", "绾犵", "瀛愬", "涓�"]
    bad = sum(value.count(marker) for marker in markers)
    return bad / max(1, len(value))


def cjk_count(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def is_english(value: str) -> bool:
    return cjk_count(value) < max(3, len(value) // 20)


def read_markdown_sections(path: Path) -> list[MarkdownSection]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    sections: list[MarkdownSection] = []
    for item_index, (start_line, level, heading) in enumerate(headings):
        next_line = len(lines) + 1
        for candidate_start, candidate_level, _ in headings[item_index + 1 :]:
            if candidate_level <= level:
                next_line = candidate_start
                break

        body_lines = lines[start_line: next_line - 1]
        body = normalize_spaces("\n".join(body_lines))
        has_nested = False
        if level < 4:
            has_nested = any(
                re.match(r"^#{%d,4}\s+" % (level + 1), line) for line in body_lines
            )
        sections.append(
            MarkdownSection(
                path=path,
                heading=heading,
                level=level,
                body=body,
                start_line=start_line,
                end_line=next_line - 1,
                has_nested_heading=has_nested,
            )
        )
    return sections


def should_use_section(section: MarkdownSection) -> bool:
    heading_norm = section.heading.strip().lower()
    if (
        heading_norm in {"目录", "assistant", "🤖 assistant"}
        or heading_norm.startswith("turn ")
        or "assistant" in heading_norm
    ):
        return False
    if any(marker in section.body[:300] for marker in ["非常抱歉", "Exported from", "Generated on"]):
        return False
    if section.level == 1:
        return False
    if section.level < 3 and section.has_nested_heading:
        return False
    if len(strip_markdown_noise(section.body)) < 180:
        return False
    if bad_text_score(section.heading + "\n" + section.body) > 0.0:
        return False
    return True


def section_context(section: MarkdownSection, limit: int = 2400) -> str:
    body = normalize_spaces(section.body)
    if len(body) <= limit:
        return body
    return body[:limit].rsplit("\n", 1)[0].strip()


def reference_answer(context: str, limit: int = 850) -> str:
    cleaned = strip_markdown_noise(context)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit("。", 1)[0].rsplit(".", 1)[0].strip()


def question_for_section(section: MarkdownSection) -> str:
    heading = re.sub(r"^Q\d+[：:]\s*", "", section.heading).strip()
    if "?" in heading or "？" in heading:
        return heading
    if is_english(heading):
        return f"What does the document specify about {heading}?"
    return f"根据文档，{heading}的核心要点是什么？"


def list_question_for_section(section: MarkdownSection) -> str:
    heading = section.heading.strip()
    if is_english(heading):
        return f"Which concrete items are listed under {heading}?"
    return f"文档在“{heading}”部分列出了哪些关键项？"


def risk_question_for_section(section: MarkdownSection) -> str:
    heading = section.heading.strip()
    if is_english(heading):
        return f"What risks, weaknesses, or gates are emphasized in {heading}?"
    return f"“{heading}”部分强调了哪些风险、门槛或失败模式？"


def classify_section(section: MarkdownSection, tactic_hint: str) -> tuple[str, str]:
    text = f"{section.heading}\n{section.body}".lower()
    if tactic_hint == "risk":
        return "hard", "risk"
    if tactic_hint == "list":
        return "medium", "list"
    if any(keyword in text for keyword in ["compare", "vs", "对比", "互补", "权衡"]):
        return "hard", "comparison"
    if any(keyword in text for keyword in ["criteria", "gate", "metrics", "指标", "门槛"]):
        return "medium", "metric_gate"
    if "phase" in text or "task" in text or "步骤" in text:
        return "medium", "implementation_step"
    return "easy", "summary"


def source_ref_for_section(section: MarkdownSection) -> dict[str, Any]:
    return {
        "source_path": section.relative_path,
        "heading": section.heading,
        "line_start": section.start_line,
        "line_end": section.end_line,
        "context_id": section.context_id,
    }


def build_answer_cases() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_questions: set[str] = set()

    for source in ANSWER_SOURCES:
        for section in read_markdown_sections(source):
            if not should_use_section(section):
                continue
            context = section_context(section)
            answer = reference_answer(context)
            if len(answer) < 40:
                continue

            candidates = [("section_summary", question_for_section(section))]
            bullet_count = len(re.findall(r"^\s*(?:[-*+]|\d+\.)\s+", section.body, flags=re.M))
            if bullet_count >= 3:
                candidates.append(("section_key_items", list_question_for_section(section)))
            risk_markers = [
                "weakness",
                "failure",
                "error",
                "risk",
                "out of scope",
                "gate",
                "criteria",
                "痛点",
                "失败",
                "风险",
                "门槛",
            ]
            if any(marker in f"{section.heading}\n{section.body}".lower() for marker in risk_markers):
                candidates.append(("failure_mode", risk_question_for_section(section)))

            for tactic, question in candidates:
                norm = re.sub(r"\s+", "", question.lower().rstrip("?？"))
                if norm in seen_questions:
                    continue
                seen_questions.add(norm)
                difficulty, answer_type = classify_section(section, tactic)
                case_id = f"ans-{stable_hash(section.context_id + tactic + question)}"
                records.append(
                    {
                        "case_id": case_id,
                        "dataset_split": "answer_generation",
                        "question": question,
                        "answer": "",
                        "answer_status": "to_be_filled_by_eval_runner",
                        "contexts": [context],
                        "ground_truth": answer,
                        "reference_answer": answer,
                        "reference_contexts": [context],
                        "ground_truth_context_ids": [section.context_id],
                        "collection": "rag-war-room",
                        "tags": ["ragas", "answer", "battle-data", tactic],
                        "difficulty": difficulty,
                        "expected_answer_type": answer_type,
                        "tactic": tactic,
                        "source_refs": [source_ref_for_section(section)],
                        "quality": {
                            "bad_text_score": round(bad_text_score(question + context + answer), 6),
                            "context_chars": len(context),
                            "reference_chars": len(answer),
                            "source": "clean_markdown_section",
                        },
                    }
                )

    return records


def legacy_chunk_lookup(queries_data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    logical_to_chunk: dict[str, dict[str, Any]] = {}
    uuid_to_logical: dict[str, str] = {}
    for document_id, chunks in queries_data["chunk_map"].items():
        for chunk in chunks:
            logical_id = chunk["logical_id"]
            logical_to_chunk[logical_id] = {
                **chunk,
                "document_id": document_id,
            }
            uuid_to_logical[chunk["uuid"]] = logical_id
    return logical_to_chunk, uuid_to_logical


def build_gold_retrieval_cases(queries_data: dict[str, Any]) -> list[dict[str, Any]]:
    logical_to_chunk, _ = legacy_chunk_lookup(queries_data)
    records: list[dict[str, Any]] = []
    for query in queries_data["queries"]:
        gt_ids = list(query.get("ground_truth", query.get("ground_truth_chunk_ids", [])))
        reference_contexts = [logical_to_chunk[item]["content"] for item in gt_ids]
        ground_truth = "\n\n".join(reference_contexts)
        prefix = str(query["query_id"]).split("_", 1)[0]
        records.append(
            {
                "case_id": f"gold-{query['query_id']}",
                "dataset_split": "gold_retrieval",
                "question": query["query"],
                "answer": "",
                "answer_status": "retrieval_only",
                "contexts": [],
                "ground_truth": ground_truth,
                "reference_answer": "",
                "reference_contexts": reference_contexts,
                "ground_truth_context_ids": gt_ids,
                "collection": "legacy-quantum-entanglement",
                "tags": ["ragas", "retrieval", "gold", prefix],
                "difficulty": "medium" if prefix == "glm" else "easy",
                "expected_answer_type": "retrieval_context",
                "tactic": "hypothetical_question" if prefix == "hq" else "generated_llm_question",
                "source_refs": [
                    {
                        "source_path": "jchatmind/reranker-service/rag_eval/data/queries.json",
                        "query_id": query["query_id"],
                        "ground_truth_context_ids": gt_ids,
                    }
                ],
                "quality": {
                    "bad_text_score": round(bad_text_score(query["query"] + ground_truth), 6),
                    "reference_context_count": len(reference_contexts),
                    "source": "legacy_queries_json",
                },
            }
        )
    return records


def build_retrieval_observations(queries_data: dict[str, Any]) -> list[dict[str, Any]]:
    logical_to_chunk, uuid_to_logical = legacy_chunk_lookup(queries_data)
    records: list[dict[str, Any]] = []

    for file_name in RAW_RESULT_FILES:
        run_id = Path(file_name).stem.replace("results_", "") if file_name != "results.json" else "baseline"
        raw_records = load_json(LEGACY_EVAL_DIR / "output" / "raw_results" / file_name)
        for raw in raw_records:
            if "error" in raw:
                continue
            gt_ids = list(raw["ground_truth"])
            reference_contexts = [logical_to_chunk[item]["content"] for item in gt_ids]
            ground_truth = "\n\n".join(reference_contexts)
            for mode, results in raw["results"].items():
                retrieved_contexts = [item["content"] for item in results]
                retrieved_context_ids = [
                    uuid_to_logical.get(item["id"], f"unmapped:{item['id']}") for item in results
                ]
                case_id = f"obs-{stable_hash(file_name + mode + raw['query_id'])}"
                records.append(
                    {
                        "case_id": case_id,
                        "dataset_split": "legacy_retrieval_observation",
                        "question": raw["query"],
                        "answer": "",
                        "answer_status": "retrieval_only",
                        "contexts": retrieved_contexts,
                        "ground_truth": ground_truth,
                        "reference_answer": "",
                        "reference_contexts": reference_contexts,
                        "ground_truth_context_ids": gt_ids,
                        "retrieved_context_ids": retrieved_context_ids,
                        "collection": "legacy-quantum-entanglement",
                        "tags": ["ragas", "retrieval", "observation", run_id, mode],
                        "difficulty": "medium" if raw["query_id"].startswith("glm_") else "easy",
                        "expected_answer_type": "retrieval_context",
                        "tactic": "retrieval_benchmark_observation",
                        "source_refs": [
                            {
                                "source_path": f"jchatmind/reranker-service/rag_eval/output/raw_results/{file_name}",
                                "query_id": raw["query_id"],
                                "run_id": run_id,
                                "mode": mode,
                                "ground_truth_context_ids": gt_ids,
                                "retrieved_context_ids": retrieved_context_ids,
                                "timings": raw.get("timings", {}).get(mode, {}),
                            }
                        ],
                        "quality": {
                            "bad_text_score": round(
                                bad_text_score(raw["query"] + ground_truth + "\n".join(retrieved_contexts)),
                                6,
                            ),
                            "retrieved_context_count": len(retrieved_contexts),
                            "reference_context_count": len(reference_contexts),
                            "source": "legacy_raw_results",
                        },
                    }
                )
    return records


def quarantine_summary() -> dict[str, Any]:
    source_root = REPO_ROOT / "data" / "documents"
    files = list(source_root.rglob("*.md")) if source_root.exists() else []
    structured = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "Hypothetical_Questions:" in text:
            structured += 1
    return {
        "source_root": source_root.relative_to(REPO_ROOT).as_posix(),
        "markdown_files": len(files),
        "structured_files": structured,
        "excluded_from_primary_gold": len(files),
        "known_issue": "Files under data/documents are clean UTF-8, but overlap with rag_eval labels and contain duplicate copies across knowledge bases. Primary gold cases are therefore taken from rag_eval/data/queries.json to preserve query_id and logical chunk traceability.",
        "suspected_mojibake_files": 0,
    }


def validate_records(records: list[dict[str, Any]], min_count: int, name: str) -> None:
    if len(records) < min_count:
        raise RuntimeError(f"{name} generated only {len(records)} records; expected at least {min_count}")
    ids = [record["case_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{name} contains duplicate case_id values")
    for record in records:
        if bad_text_score(record["question"]) > 0.0:
            raise RuntimeError(f"{name} contains mojibake in question {record['case_id']}")
        if len(record["ground_truth"]) < 20:
            raise RuntimeError(f"{name} has too-short ground_truth in {record['case_id']}")
        if not record["ground_truth_context_ids"]:
            raise RuntimeError(f"{name} missing ground_truth_context_ids in {record['case_id']}")


def write_manifest(
    gold: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    answer: list[dict[str, Any]],
) -> None:
    all_records = gold + observations + answer
    manifest = {
        "generated_at": "2026-07-03T00:00:00Z",
        "generator": "scripts/build_ragas_cases.py",
        "strict_quality_policy": {
            "primary_sources": "clean JSON labels or clean Markdown sections only",
            "excluded": "raw error records, duplicate results_v1.json, low-value export wrapper sections, duplicate Markdown knowledge-base copies",
            "required": [
                "stable case_id",
                "non-empty question",
                "non-empty ground_truth",
                "ground_truth_context_ids",
                "source_refs",
                "quality metadata",
            ],
        },
        "counts": {
            "gold_retrieval_cases": len(gold),
            "legacy_retrieval_observations": len(observations),
            "answer_generation_cases": len(answer),
            "total_records": len(all_records),
        },
        "tactic_counts": dict(sorted(Counter(record["tactic"] for record in all_records).items())),
        "difficulty_counts": dict(sorted(Counter(record["difficulty"] for record in all_records).items())),
        "source_counts": dict(
            sorted(Counter(record["quality"]["source"] for record in all_records).items())
        ),
        "quarantine": quarantine_summary(),
        "files": {
            "schema": "ragas_cases.schema.json",
            "gold_retrieval": "gold_retrieval_cases.jsonl",
            "legacy_observations": "legacy_retrieval_observations.jsonl",
            "answer_generation": "answer_generation_cases.jsonl",
            "combined": "ragas_cases.combined.jsonl",
        },
    }
    (OUTPUT_DIR / "ragas_cases_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    queries_data = load_json(LEGACY_EVAL_DIR / "data" / "queries.json")
    gold = build_gold_retrieval_cases(queries_data)
    observations = build_retrieval_observations(queries_data)
    answer = build_answer_cases()

    validate_records(gold, min_count=58, name="gold_retrieval_cases")
    validate_records(observations, min_count=700, name="legacy_retrieval_observations")
    validate_records(answer, min_count=80, name="answer_generation_cases")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "ragas_cases.schema.json").write_text(
        json.dumps(RAGAS_CASE_SCHEMA, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_jsonl(OUTPUT_DIR / "gold_retrieval_cases.jsonl", gold)
    write_jsonl(OUTPUT_DIR / "legacy_retrieval_observations.jsonl", observations)
    write_jsonl(OUTPUT_DIR / "answer_generation_cases.jsonl", answer)
    write_jsonl(OUTPUT_DIR / "ragas_cases.combined.jsonl", gold + observations + answer)
    write_manifest(gold, observations, answer)

    print(f"gold_retrieval_cases={len(gold)}")
    print(f"legacy_retrieval_observations={len(observations)}")
    print(f"answer_generation_cases={len(answer)}")
    print(f"total_records={len(gold) + len(observations) + len(answer)}")
    print(f"output_dir={OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
