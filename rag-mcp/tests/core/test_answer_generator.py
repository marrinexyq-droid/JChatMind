from src.core.answer_generator import AnswerGenerator
from src.core.types import RetrievalResult


class FakeLLM:
    def __init__(self, answer: str):
        self.answer = answer
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def test_answer_generator_keeps_valid_evidence_citation():
    llm = FakeLLM("RRF combines ranked lists [C1].")

    answer = AnswerGenerator(llm).generate("What is RRF?", [_result("C1")])

    assert answer == "RRF combines ranked lists [C1]."


def test_answer_generator_falls_back_when_llm_uses_unknown_citation():
    llm = FakeLLM("RRF combines ranked lists [C9].")

    answer = AnswerGenerator(llm).generate("What is RRF?", [_result("C1")])

    assert answer == "Evidence found:\n[C1] RRF combines ranked retrieval lists."


def test_answer_generator_falls_back_when_llm_omits_citations():
    llm = FakeLLM("RRF combines ranked lists.")

    answer = AnswerGenerator(llm).generate("What is RRF?", [_result("C1")])

    assert answer == "Evidence found:\n[C1] RRF combines ranked retrieval lists."


def test_answer_generator_declines_without_evidence_without_calling_llm():
    llm = FakeLLM("Untrusted answer [C1].")

    answer = AnswerGenerator(llm).generate("What is RRF?", [])

    assert answer == "No evidence found."
    assert llm.prompts == []


def test_answer_generator_prompt_requires_grounded_cited_refusal():
    llm = FakeLLM("RRF combines ranked lists [C1].")

    AnswerGenerator(llm).generate("What is RRF?", [_result("C1")])

    prompt = llm.prompts[0]
    assert "Only use the supplied evidence." in prompt
    assert "Cite every conclusion using [C#]." in prompt
    assert "state that the evidence is insufficient" in prompt
    assert "[C1] RRF combines ranked retrieval lists." in prompt


def _result(citation_id: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="RRF combines ranked retrieval lists.",
        score=1.0,
        source="test",
        citation_id=citation_id,
    )
