from __future__ import annotations

import re
from abc import ABC, abstractmethod

from src.core.types import ChunkRecord


class Transform(ABC):
    @abstractmethod
    def apply(self, chunk: ChunkRecord) -> ChunkRecord:
        raise NotImplementedError


class RuleCleanupTransform(Transform):
    def apply(self, chunk: ChunkRecord) -> ChunkRecord:
        text = chunk.text.lstrip("\ufeff")
        text = "\n".join(line.rstrip() for line in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return ChunkRecord(
            id=chunk.id,
            document_id=chunk.document_id,
            collection=chunk.collection,
            text=text,
            metadata=dict(chunk.metadata),
        )


class MetadataEnricher(Transform):
    def apply(self, chunk: ChunkRecord) -> ChunkRecord:
        return ChunkRecord(
            id=chunk.id,
            document_id=chunk.document_id,
            collection=chunk.collection,
            text=chunk.text,
            metadata=dict(chunk.metadata),
        )
