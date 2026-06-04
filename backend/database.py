from typing import Any

from llama_index.core.schema import NodeWithScore, TextNode
from supabase import Client, create_client

from config import Settings


def create_supabase_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def ensure_vector_store_ready(client: Client) -> None:
    """Verify the financial_documents table is reachable."""
    client.table("financial_documents").select("id").limit(1).execute()


def match_documents(
    client: Client,
    query_embedding: list[float],
    match_count: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    response = client.rpc(
        "match_financial_documents",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "filter": metadata_filter or {},
        },
    ).execute()
    return response.data or []


def insert_document(
    client: Client,
    content: str,
    metadata: dict[str, Any],
    embedding: list[float],
) -> None:
    client.table("financial_documents").insert(
        {
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
        }
    ).execute()


def nodes_from_matches(matches: list[dict[str, Any]]) -> list[NodeWithScore]:
    nodes: list[NodeWithScore] = []
    for row in matches:
        node = TextNode(
            text=row["content"],
            metadata=row.get("metadata") or {},
            id_=str(row["id"]),
        )
        nodes.append(
            NodeWithScore(node=node, score=float(row.get("similarity") or 0.0))
        )
    return nodes
