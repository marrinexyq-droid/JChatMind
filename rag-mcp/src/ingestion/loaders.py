from __future__ import annotations

import hashlib
from pathlib import Path

import fitz

from src.core.types import Document


class MarkdownLoader:
    def load(self, source_path: Path, collection: str = "default") -> Document:
        text = source_path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return Document(
            id=digest[:16],
            collection=collection,
            source_path=str(source_path),
            text=text,
            metadata={
                "file_name": source_path.name,
                "file_suffix": source_path.suffix.lower(),
                "sha256": digest,
            },
        )


class PdfLoader:
    def load(self, source_path: Path, collection: str = "default") -> Document:
        with fitz.open(source_path) as pdf:
            pages = [
                f"<!-- page: {page_number} -->\n\n{page.get_text('text').strip()}"
                for page_number, page in enumerate(pdf, start=1)
            ]
        text = "\n\n".join(pages)
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        return Document(
            id=digest[:16],
            collection=collection,
            source_path=str(source_path),
            text=text,
            metadata={
                "file_name": source_path.name,
                "file_suffix": source_path.suffix.lower(),
                "page_count": len(pages),
                "sha256": digest,
            },
        )
