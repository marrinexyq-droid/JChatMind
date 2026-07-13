from pathlib import Path

from src.core.types import Document
from src.ingestion.loaders import MarkdownLoader, PdfLoader


def load_document(path: Path, collection: str) -> Document:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return MarkdownLoader().load(path, collection)
    if suffix == ".pdf":
        return PdfLoader().load(path, collection)
    raise ValueError(f"unsupported document type: {suffix or '<none>'}")
