"""Supabase persistence for chat message feedback."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from supabase import Client

FeedbackType = Literal["up", "down"]
FeedbackStatus = Literal["pending", "processing", "processed", "skipped"]


def upsert_feedback(
    client: Client,
    *,
    session_id: str,
    message_id: str,
    feedback: FeedbackType,
    user_query: str,
    assistant_content: str = "",
    thinking: str = "",
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    status: FeedbackStatus = "pending" if feedback == "down" else "skipped"
    row = {
        "session_id": session_id,
        "message_id": message_id,
        "feedback": feedback,
        "user_query": user_query,
        "assistant_content": assistant_content,
        "thinking": thinking or "",
        "sources": sources or [],
        "status": status,
        "processed_at": None,
        "processor_notes": None,
        "corpus_patch": None,
    }
    response = (
        client.table("message_feedback")
        .upsert(row, on_conflict="session_id,message_id")
        .execute()
    )
    data = response.data or []
    return data[0] if data else row


def list_pending_downvotes(
    client: Client, *, limit: int = 20
) -> list[dict[str, Any]]:
    response = (
        client.table("message_feedback")
        .select("*")
        .eq("feedback", "down")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return response.data or []


def mark_feedback(
    client: Client,
    feedback_id: str,
    *,
    status: FeedbackStatus,
    processor_notes: str | None = None,
    corpus_patch: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status}
    if processor_notes is not None:
        payload["processor_notes"] = processor_notes
    if corpus_patch is not None:
        payload["corpus_patch"] = corpus_patch
    if status in ("processed", "skipped"):
        payload["processed_at"] = datetime.now(timezone.utc).isoformat()
    client.table("message_feedback").update(payload).eq("id", feedback_id).execute()


def claim_feedback_for_processing(client: Client, feedback_id: str) -> bool:
    rows = (
        client.table("message_feedback")
        .update({"status": "processing"})
        .eq("id", feedback_id)
        .eq("status", "pending")
        .execute()
    )
    return bool(rows.data)
