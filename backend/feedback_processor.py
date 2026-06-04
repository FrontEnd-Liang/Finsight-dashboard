"""Batch-process pending downvotes and patch corpus.json."""

from __future__ import annotations

import logging
from typing import Any

from config import Settings, get_settings
from corpus_editor import apply_corpus_updates, corpus_excerpt_for_prompt
from database import create_supabase_client
from feedback_db import claim_feedback_for_processing, list_pending_downvotes, mark_feedback
from refinement import refine_feedback_item

logger = logging.getLogger("finsight.feedback")


def process_pending_feedback(
    settings: Settings | None = None,
    *,
    limit: int = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    client = create_supabase_client(settings)
    pending = list_pending_downvotes(client, limit=limit)
    corpus_excerpt = corpus_excerpt_for_prompt()

    results: list[dict[str, Any]] = []
    for row in pending:
        fid = str(row["id"])
        if not claim_feedback_for_processing(client, fid):
            continue

        try:
            refinement = refine_feedback_item(
                settings,
                user_query=row.get("user_query") or "",
                assistant_content=row.get("assistant_content") or "",
                thinking=row.get("thinking") or "",
                sources=row.get("sources") or [],
                corpus_excerpt=corpus_excerpt,
            )
            updates = refinement.get("updates") or []
            patch_result: dict[str, Any] | None = None

            if updates and not dry_run:
                patch_result = apply_corpus_updates(updates)
                corpus_excerpt = corpus_excerpt_for_prompt()

            notes = refinement.get("analysis", "")
            if dry_run:
                mark_feedback(
                    client,
                    fid,
                    status="pending",
                    processor_notes=f"[dry-run] {notes}",
                    corpus_patch={"refinement": refinement, "would_apply": updates},
                )
                results.append(
                    {"id": fid, "status": "dry-run", "updates": len(updates)}
                )
                continue

            if not updates:
                mark_feedback(
                    client,
                    fid,
                    status="skipped",
                    processor_notes=notes or "无资料库修订建议",
                    corpus_patch={"refinement": refinement},
                )
                results.append({"id": fid, "status": "skipped"})
                continue

            mark_feedback(
                client,
                fid,
                status="processed",
                processor_notes=notes,
                corpus_patch={"refinement": refinement, "apply": patch_result},
            )
            results.append(
                {"id": fid, "status": "processed", "apply": patch_result}
            )
        except Exception as exc:
            logger.exception("Feedback %s failed", fid)
            mark_feedback(
                client,
                fid,
                status="pending",
                processor_notes=f"error: {exc}",
            )
            results.append({"id": fid, "status": "error", "error": str(exc)})

    return {
        "processed": len(results),
        "dry_run": dry_run,
        "results": results,
    }


def reingest_library(settings: Settings | None = None) -> int:
    """Reload corpus.json into Supabase after patches."""
    from agent import FinancialResearchAgent
    from corpus import get_library_documents

    settings = settings or get_settings()
    client = create_supabase_client(settings)
    agent = FinancialResearchAgent(settings, client)
    docs = get_library_documents()
    return agent.ingest_documents(docs, replace=True)
