"""Read/write backend/data/corpus.json and apply refinement patches."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from corpus import _CORPUS_PATH, _validate_document, load_corpus_from_path

_CORPUS_BACKUP_DIR = _CORPUS_PATH.parent / "backups"


def load_corpus_payload() -> dict[str, Any]:
    with _CORPUS_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("corpus.json must be a JSON object with a documents array")
    return payload


def save_corpus_payload(payload: dict[str, Any]) -> None:
    documents = payload.get("documents", [])
    for i, doc in enumerate(documents):
        _validate_document(doc, i)
    _CORPUS_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if _CORPUS_PATH.is_file():
        stamp = date.today().isoformat()
        backup = _CORPUS_BACKUP_DIR / f"corpus_{stamp}_{payload.get('version', 'bak')}.json"
        backup.write_text(_CORPUS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with _CORPUS_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _bump_version(version: str | None) -> str:
    if not version:
        return "1.0.1"
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", str(version))
    if not match:
        return f"{version}-rev1"
    major, minor, patch = match.group(1), match.group(2), match.group(3) or "0"
    return f"{major}.{minor}.{int(patch) + 1}"


def _find_document_index(
    documents: list[dict[str, Any]], update: dict[str, Any]
) -> int | None:
    ticker = (update.get("match_ticker") or update.get("ticker") or "").upper()
    source_hint = (update.get("match_source_contains") or update.get("source") or "").lower()
    for idx, doc in enumerate(documents):
        meta = doc.get("metadata") or {}
        doc_ticker = str(meta.get("ticker", "")).upper()
        doc_source = str(meta.get("source", "")).lower()
        if ticker and doc_ticker != ticker:
            continue
        if source_hint and source_hint not in doc_source:
            continue
        return idx
    if ticker:
        for idx, doc in enumerate(documents):
            meta = doc.get("metadata") or {}
            if str(meta.get("ticker", "")).upper() == ticker:
                return idx
    return None


def apply_corpus_updates(updates: list[dict[str, Any]]) -> dict[str, Any]:
    payload = load_corpus_payload()
    documents: list[dict[str, Any]] = list(payload.get("documents") or [])
    applied: list[str] = []

    for raw in updates:
        action = str(raw.get("action", "update")).lower()
        content = str(raw.get("content", "")).strip()
        if not content:
            continue
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        metadata.setdefault("ticker", raw.get("match_ticker") or raw.get("ticker") or "MACRO")

        if action == "add":
            documents.append({"content": content, "metadata": metadata})
            applied.append(f"add:{metadata.get('ticker')}")
            continue

        idx = _find_document_index(documents, raw)
        if idx is None:
            documents.append({"content": content, "metadata": metadata})
            applied.append(f"add-fallback:{metadata.get('ticker')}")
            continue

        documents[idx] = {
            "content": content,
            "metadata": {**(documents[idx].get("metadata") or {}), **metadata},
        }
        applied.append(f"update:{metadata.get('ticker')}:{idx}")

    payload["documents"] = documents
    payload["version"] = _bump_version(payload.get("version"))
    payload["as_of_calendar"] = date.today().isoformat()
    save_corpus_payload(payload)
    return {"applied": applied, "version": payload["version"], "document_count": len(documents)}


def corpus_excerpt_for_prompt(max_docs: int = 6, max_chars: int = 400) -> str:
    docs = load_corpus_from_path(_CORPUS_PATH)
    lines: list[str] = []
    for doc in docs[:max_docs]:
        meta = doc.get("metadata") or {}
        snippet = (doc.get("content") or "")[:max_chars]
        lines.append(
            f"- {meta.get('ticker')} | {meta.get('source')} | {snippet}"
        )
    return "\n".join(lines)
