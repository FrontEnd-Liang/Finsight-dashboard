"""Load injectable financial document corpora from JSON data files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEMO_CORPUS_PATH = _DATA_DIR / "demo_corpus.json"


def _validate_document(doc: dict[str, Any], index: int) -> None:
    if not isinstance(doc.get("content"), str) or not doc["content"].strip():
        raise ValueError(f"Document #{index}: missing non-empty 'content'")
    metadata = doc.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"Document #{index}: missing 'metadata' object")


def load_corpus_from_path(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        documents = payload
    elif isinstance(payload, dict):
        documents = payload.get("documents", [])
    else:
        raise ValueError(f"Invalid corpus format in {path}")

    if not documents:
        raise ValueError(f"No documents found in {path}")

    for i, doc in enumerate(documents):
        _validate_document(doc, i)

    return documents


def get_demo_documents() -> list[dict[str, Any]]:
    """Return demo corpus documents from backend/data/demo_corpus.json."""
    if not _DEMO_CORPUS_PATH.is_file():
        raise FileNotFoundError(
            f"Demo corpus not found: {_DEMO_CORPUS_PATH}. "
            "Ensure backend/data/demo_corpus.json exists."
        )
    return load_corpus_from_path(_DEMO_CORPUS_PATH)


def get_demo_corpus_meta() -> dict[str, Any]:
    with _DEMO_CORPUS_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    documents = payload.get("documents", []) if isinstance(payload, dict) else payload
    tickers = sorted(
        {
            str(doc.get("metadata", {}).get("ticker"))
            for doc in documents
            if doc.get("metadata", {}).get("ticker")
        }
    )
    return {
        "name": payload.get("name", "demo") if isinstance(payload, dict) else "demo",
        "description": payload.get("description", "") if isinstance(payload, dict) else "",
        "version": payload.get("version") if isinstance(payload, dict) else None,
        "as_of_calendar": payload.get("as_of_calendar") if isinstance(payload, dict) else None,
        "document_count": len(documents),
        "tickers": tickers,
        "file": str(_DEMO_CORPUS_PATH.name),
    }
