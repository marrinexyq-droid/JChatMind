from src.core.types import ChunkRecord
from src.ingestion.transforms import MetadataEnricher, RuleCleanupTransform


def test_rule_cleanup_removes_bom_and_normalizes_whitespace():
    chunk = ChunkRecord(
        id="chunk-1",
        document_id="document-1",
        collection="manuals",
        text="\ufeff# Evidence  \n\n\n  Reliable PDF content.  \n",
    )

    cleaned = RuleCleanupTransform().apply(chunk)

    assert cleaned.text == "# Evidence\n\n  Reliable PDF content."
    assert cleaned.id == chunk.id


def test_metadata_enricher_preserves_retrieval_metadata():
    chunk = ChunkRecord(
        id="chunk-1",
        document_id="document-1",
        collection="manuals",
        text="Evidence",
        metadata={
            "title": "PDF evidence",
            "page": 3,
            "source_path": "manual.pdf",
            "sha256": "abc123",
        },
    )

    enriched = MetadataEnricher().apply(chunk)

    assert enriched.metadata == chunk.metadata
