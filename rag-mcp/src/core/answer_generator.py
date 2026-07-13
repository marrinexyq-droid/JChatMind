from __future__ import annotations

import re
from typing import Protocol

from src.core.types import RetrievalResult


class _LLM(Protocol):
    def generate(self, prompt: str) -> str: ...


class EvidenceFallback(str):
    def __new__(cls, value: str, reason: str):
        instance = super().__new__(cls, value)
        instance.reason = reason
        return instance


class AnswerGenerator:
    def __init__(self, llm: _LLM):
        self.llm = llm

    def generate(self, query: str, evidence: list[RetrievalResult]) -> str:
        if not evidence:
            return EvidenceFallback(build_evidence_answer(evidence), "no_evidence")
        answer = self.llm.generate(_build_prompt(query, evidence)).strip()
        allowed_citations = {
            result.citation_id
            for result in evidence
            if result.citation_id is not None
        }
        citations = set(re.findall(r"\[([A-Za-z]+\d+)\]", answer))
        if not citations or not citations.issubset(allowed_citations):
            return EvidenceFallback(build_evidence_answer(evidence), "invalid_citation")
        return answer


def _build_prompt(query: str, evidence: list[RetrievalResult]) -> str:
    rendered_evidence = "\n".join(
        f"[{result.citation_id or 'C?'}] {result.text}" for result in evidence
    )
    return (
        "Only use the supplied evidence.\n"
        "Cite every conclusion using [C#].\n"
        "If the evidence is insufficient, state that the evidence is insufficient.\n\n"
        f"Question: {query}\n\nEvidence:\n{rendered_evidence}"
    )


def build_evidence_answer(evidence: list[RetrievalResult]) -> str:
    if not evidence:
        return "No evidence found."
    lines = ["Evidence found:"]
    for result in evidence:
        citation = result.citation_id or "C?"
        snippet = " ".join(result.text.replace("\ufeff", "").split())
        lines.append(f"[{citation}] {snippet}")
    return "\n".join(lines)
