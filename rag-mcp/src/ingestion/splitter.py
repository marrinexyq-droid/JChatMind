from __future__ import annotations

import hashlib
import re

from src.core.types import ChunkRecord, Document


class MarkdownTextSplitter:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document: Document) -> list[ChunkRecord]:
        blocks = self._blocks_with_titles(document.text)
        chunks: list[ChunkRecord] = []
        for title, block, page in blocks:
            for part in self._window(block):
                text = part.strip()
                if not text:
                    continue
                chunk_index = len(chunks)
                digest = hashlib.sha1(
                    f"{document.id}:{chunk_index}:{text}".encode("utf-8")
                ).hexdigest()[:10]
                metadata = {
                    **document.metadata,
                    "title": title,
                    "chunk_index": chunk_index,
                    "source_path": document.source_path,
                }
                if page is not None:
                    metadata["page"] = page
                chunks.append(
                    ChunkRecord(
                        id=f"{document.id}-{chunk_index:04d}-{digest}",
                        document_id=document.id,
                        collection=document.collection,
                        text=text,
                        metadata=metadata,
                    )
                )
        return chunks

    def _blocks_with_titles(self, text: str) -> list[tuple[str, str, int | None]]:
        current_title = ""
        current_page: int | None = None
        current_lines: list[str] = []
        blocks: list[tuple[str, str, int | None]] = []

        for line in text.splitlines():
            page_marker = re.match(r"^\s*<!--\s*page:\s*(\d+)\s*-->\s*$", line)
            if page_marker:
                if current_lines:
                    blocks.append((current_title, "\n".join(current_lines), current_page))
                current_page = int(page_marker.group(1))
                current_title = f"Page {current_page}"
                current_lines = [line]
                continue
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading:
                if current_lines:
                    blocks.append((current_title, "\n".join(current_lines), current_page))
                    current_lines = []
                current_title = heading.group(2).strip()
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            blocks.append((current_title, "\n".join(current_lines), current_page))
        return blocks or [("", text, None)]

    def _window(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - self.chunk_overlap
        return chunks
