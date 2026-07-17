from __future__ import annotations

import json
import os
import re
import statistics
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from src.evaluation.ragas_cases import load_jsonl


VERSION = "2.5"
ANSWER_GENERATION_SPLIT = "answer_generation"


@dataclass(frozen=True)
class JudgedRagasCase:
    case_id: str
    question: str
    answer: str
    contexts: list[str]
    reference_answer: str
    difficulty: str
    tactic: str
    answer_source: str


@dataclass(frozen=True)
class JudgeScore:
    faithfulness: float
    answer_relevancy: float
    reason: str


@dataclass(frozen=True)
class JudgeThresholds:
    min_mean_faithfulness: float = 0.7
    min_mean_answer_relevancy: float = 0.7
    min_case_score: float = 0.5


@dataclass(frozen=True)
class JudgeConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    timeout_seconds: float = 30.0


class JudgeClient(Protocol):
    provider: str
    model: str

    def judge(self, case: JudgedRagasCase) -> JudgeScore:
        ...


def load_answer_generation_cases(
    dataset_dir: Path,
    *,
    limit: int | None = None,
    answer_policy: str = "reference",
    pipeline_report: Path | None = None,
    pipeline_report_data: Mapping[str, Any] | None = None,
) -> list[JudgedRagasCase]:
    if answer_policy not in {"generated", "reference"}:
        raise ValueError("answer_policy must be 'generated' or 'reference'")
    if pipeline_report is not None and pipeline_report_data is not None:
        raise ValueError("provide pipeline_report or pipeline_report_data, not both")
    if (
        answer_policy == "generated"
        and pipeline_report is None
        and pipeline_report_data is None
    ):
        raise ValueError(
            "pipeline_report is required when answer_policy is 'generated'"
        )
    if limit is not None and limit <= 0:
        return []

    rows = load_jsonl(dataset_dir / "ragas_cases.combined.jsonl")
    pipeline_cases: dict[str, dict[str, Any]] = {}
    payload: Mapping[str, Any] | None = pipeline_report_data
    if pipeline_report is not None:
        payload = json.loads(pipeline_report.read_text(encoding="utf-8"))
    if payload is not None:
        pipeline_cases = {
            str(row["case_id"]): row
            for row in payload.get("cases", [])
        }
    cases: list[JudgedRagasCase] = []
    for row in rows:
        if row.get("dataset_split") != ANSWER_GENERATION_SPLIT:
            continue

        pipeline_case = pipeline_cases.get(str(row["case_id"]))
        if answer_policy == "generated" and pipeline_case is None:
            raise ValueError(f"missing current pipeline case {row['case_id']}")
        if answer_policy == "generated" and pipeline_case is not None:
            if pipeline_case.get("error"):
                raise ValueError(f"current pipeline case {row['case_id']} failed")
            answer = str(pipeline_case.get("answer") or "").strip()
            if not answer:
                raise ValueError(
                    f"current pipeline case {row['case_id']} has no answer"
                )
            answer_source = str(
                pipeline_case.get("answer_source") or "current_pipeline"
            )
            if answer_source == "reference_answer_fallback":
                raise ValueError(
                    f"current pipeline case {row['case_id']} used reference answer fallback"
                )
            if answer_source != "generated_answer":
                raise ValueError(
                    f"current pipeline case {row['case_id']} did not use a generated answer"
                )
            contexts = [
                str(context)
                for context in pipeline_case.get("retrieved_contexts") or []
                if str(context).strip()
            ]
        else:
            answer = str(row.get("answer") or "").strip()
            answer_source = "generated_answer"
            contexts = [
                str(context)
                for context in row.get("contexts") or row.get("reference_contexts") or []
                if str(context).strip()
            ]
        if not answer and answer_policy == "reference":
            answer = str(row.get("reference_answer") or row.get("ground_truth") or "").strip()
            answer_source = "reference_answer_fallback"
        if not answer:
            continue
        cases.append(
            JudgedRagasCase(
                case_id=str(row["case_id"]),
                question=str(row["question"]),
                answer=answer,
                contexts=contexts,
                reference_answer=str(
                    row.get("reference_answer") or row.get("ground_truth") or ""
                ),
                difficulty=str(row.get("difficulty") or "unknown"),
                tactic=str(row.get("tactic") or "unknown"),
                answer_source=answer_source,
            )
        )
        if limit is not None and len(cases) >= limit:
            break
    return cases


def load_judge_config(env: Mapping[str, str] | None = None) -> tuple[JudgeConfig | None, list[str]]:
    env = os.environ if env is None else env
    api_key = env.get("RAGAS_JUDGE_API_KEY") or env.get("GOOGLE_API_KEY") or ""
    provider = env.get("RAGAS_JUDGE_PROVIDER") or ("google" if api_key else "")
    model = (
        env.get("RAGAS_JUDGE_MODEL")
        or env.get("GOOGLE_GENAI_MODEL")
        or ("gemini-2.5-flash" if provider.lower() in {"google", "gemini"} else "")
    )
    missing = []
    if not provider:
        missing.append("RAGAS_JUDGE_PROVIDER")
    if not model:
        missing.append("RAGAS_JUDGE_MODEL")
    if not api_key:
        missing.append("RAGAS_JUDGE_API_KEY or GOOGLE_API_KEY")
    if missing:
        return None, missing

    timeout = float(env.get("RAGAS_JUDGE_TIMEOUT_SECONDS") or "30")
    return (
        JudgeConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=env.get("RAGAS_JUDGE_BASE_URL") or None,
            timeout_seconds=timeout,
        ),
        [],
    )


def build_configured_judge(config: JudgeConfig) -> JudgeClient:
    provider = config.provider.lower()
    if provider in {"google", "gemini"}:
        return GeminiJudgeClient(config)
    raise ValueError(f"Unsupported RAGAS judge provider: {config.provider}")


class DeterministicJudgeClient:
    provider = "deterministic"
    model = "offline-overlap"

    def judge(self, case: JudgedRagasCase) -> JudgeScore:
        faithfulness = overlap_ratio(case.answer, "\n".join(case.contexts))
        answer_relevancy = max(
            overlap_ratio(case.answer, case.reference_answer),
            overlap_ratio(case.answer, case.question),
        )
        return JudgeScore(
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            reason="Deterministic overlap judge for offline harness stability.",
        )


class GeminiJudgeClient:
    provider = "google"

    def __init__(self, config: JudgeConfig) -> None:
        self.config = config
        self.model = config.model

    def judge(self, case: JudgedRagasCase) -> JudgeScore:
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_judge_prompt(case)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        response = self._post_json(body)
        text = extract_gemini_text(response)
        payload = parse_score_payload(text)
        return JudgeScore(
            faithfulness=clamp_score(payload["faithfulness"]),
            answer_relevancy=clamp_score(payload["answer_relevancy"]),
            reason=str(payload.get("reason") or "judge did not provide a reason"),
        )

    def _post_json(self, body: dict[str, Any]) -> dict[str, Any]:
        base_url = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"
        model_name = self.config.model.removeprefix("models/")
        model = urllib.parse.quote(model_name, safe="")
        url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.config.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def build_judge_prompt(case: JudgedRagasCase) -> str:
    payload = {
        "question": case.question,
        "answer": case.answer,
        "contexts": case.contexts,
        "reference_answer": case.reference_answer,
    }
    return (
        "You are a strict RAGAS judge. Score only the supplied answer.\n"
        "Return JSON only with keys faithfulness, answer_relevancy, and reason.\n"
        "faithfulness is 0 to 1: whether the answer is supported by contexts.\n"
        "answer_relevancy is 0 to 1: whether the answer directly answers the question.\n"
        "Use the reference answer only as a calibration aid, not as additional context.\n"
        f"Case JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def evaluate_judged_ragas(
    cases: Sequence[JudgedRagasCase],
    judge: JudgeClient,
    *,
    thresholds: JudgeThresholds = JudgeThresholds(),
) -> dict[str, Any]:
    if not cases:
        return {
            "version": VERSION,
            "status": "no_cases",
            "summary": "No answer_generation cases with candidate answers were available.",
            "judge": judge_metadata(judge),
            "case_count": 0,
            "thresholds": thresholds_dict(thresholds),
            "metrics": empty_metrics(),
            "cases": [],
        }

    rows = []
    for case in cases:
        score = judge.judge(case)
        rows.append(
            {
                "case_id": case.case_id,
                "difficulty": case.difficulty,
                "tactic": case.tactic,
                "answer_source": case.answer_source,
                "faithfulness": round(score.faithfulness, 4),
                "answer_relevancy": round(score.answer_relevancy, 4),
                "reason": score.reason,
            }
        )

    faithfulness_values = [row["faithfulness"] for row in rows]
    relevancy_values = [row["answer_relevancy"] for row in rows]
    metrics = {
        "faithfulness": metric_summary(faithfulness_values),
        "answer_relevancy": metric_summary(relevancy_values),
    }
    failed_cases = [
        row["case_id"]
        for row in rows
        if row["faithfulness"] < thresholds.min_case_score
        or row["answer_relevancy"] < thresholds.min_case_score
    ]
    passed = (
        metrics["faithfulness"]["mean"] >= thresholds.min_mean_faithfulness
        and metrics["answer_relevancy"]["mean"] >= thresholds.min_mean_answer_relevancy
        and not failed_cases
    )
    return {
        "version": VERSION,
        "status": "passed" if passed else "failed",
        "judge": judge_metadata(judge),
        "case_count": len(rows),
        "thresholds": thresholds_dict(thresholds),
        "metrics": metrics,
        "failed_cases": failed_cases,
        "cases": rows,
    }


def not_configured_report(missing: Sequence[str]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": "not_configured",
        "missing": list(missing),
        "next_action": (
            "Set RAGAS_JUDGE_PROVIDER, RAGAS_JUDGE_MODEL, and RAGAS_JUDGE_API_KEY, "
            "or set GOOGLE_API_KEY for the default Gemini judge."
        ),
    }


def overlap_ratio(candidate: str, reference: str) -> float:
    left = normalized_units(candidate)
    right = normalized_units(reference)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def normalized_units(text: str) -> set[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    return {char for char in normalized if char.isalnum()}


def parse_score_payload(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("Judge response did not contain a JSON object")
        payload = json.loads(match.group(0))

    missing = {"faithfulness", "answer_relevancy"} - set(payload)
    if missing:
        raise ValueError(f"Judge response missing required score keys: {sorted(missing)}")
    return payload


def extract_gemini_text(response: Mapping[str, Any]) -> str:
    try:
        return str(response["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini response did not include candidate text") from exc


def clamp_score(value: Any) -> float:
    score = float(value)
    return max(0.0, min(1.0, score))


def metric_summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.fmean(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def empty_metrics() -> dict[str, dict[str, float]]:
    empty = {"mean": 0.0, "min": 0.0, "max": 0.0}
    return {"faithfulness": empty, "answer_relevancy": empty}


def thresholds_dict(thresholds: JudgeThresholds) -> dict[str, float]:
    return {
        "min_mean_faithfulness": thresholds.min_mean_faithfulness,
        "min_mean_answer_relevancy": thresholds.min_mean_answer_relevancy,
        "min_case_score": thresholds.min_case_score,
    }


def judge_metadata(judge: JudgeClient) -> dict[str, str]:
    return {"provider": judge.provider, "model": judge.model}
