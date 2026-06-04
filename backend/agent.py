import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from llama_index.core import Settings as LlamaSettings
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.base.embeddings.base import BaseEmbedding
from supabase import Client

from config import Settings
from embeddings import create_embed_model
from llm import create_llm
from database import insert_document, match_documents, nodes_from_matches

SYSTEM_PROMPT = """You are Finsight, an expert financial research analyst AI.
You analyze equities, macro trends, earnings, and regulatory filings using retrieved context.

Rules:
- Ground answers in the provided context; cite tickers and figures when available.
- If context is insufficient, state what is missing and suggest data to ingest.
- Use markdown tables for comparative metrics (revenue, margins, P/E, YoY growth).
- Be concise, institutional-grade, and avoid speculation beyond the evidence.
"""


class SupabaseFinancialRetriever(BaseRetriever):
    """Retrieves financial documents via Supabase pgvector RPC."""

    def __init__(
        self,
        client: Client,
        embed_model: BaseEmbedding,
        similarity_top_k: int = 5,
    ) -> None:
        super().__init__()
        self._client = client
        self._embed_model = embed_model
        self._similarity_top_k = similarity_top_k

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        query_embedding = self._embed_model.get_query_embedding(
            query_bundle.query_str
        )
        matches = match_documents(
            self._client,
            query_embedding=query_embedding,
            match_count=self._similarity_top_k,
        )
        return nodes_from_matches(matches)

    async def _aretrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        return await asyncio.to_thread(self._retrieve, query_bundle)


class FinancialResearchAgent:
    def __init__(self, settings: Settings, supabase_client: Client) -> None:
        self.settings = settings
        self.supabase_client = supabase_client
        self._chat_engines: dict[str, CondensePlusContextChatEngine] = {}
        self._retriever: SupabaseFinancialRetriever | None = None
        self._configure_llama()

    def _configure_llama(self) -> None:
        LlamaSettings.llm = create_llm(self.settings)
        LlamaSettings.embed_model = create_embed_model(self.settings)
        LlamaSettings.chunk_size = 1024
        LlamaSettings.chunk_overlap = 128

    def _get_retriever(self) -> SupabaseFinancialRetriever:
        if self._retriever is None:
            self._retriever = SupabaseFinancialRetriever(
                client=self.supabase_client,
                embed_model=LlamaSettings.embed_model,  # type: ignore[arg-type]
                similarity_top_k=5,
            )
        return self._retriever

    def _get_chat_engine(self, session_id: str) -> CondensePlusContextChatEngine:
        if session_id not in self._chat_engines:
            memory = ChatMemoryBuffer.from_defaults(token_limit=3900)
            retriever = self._get_retriever()
            self._chat_engines[session_id] = CondensePlusContextChatEngine.from_defaults(
                retriever=retriever,
                llm=LlamaSettings.llm,
                memory=memory,
                system_prompt=SYSTEM_PROMPT,
                node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.55)],
                verbose=False,
            )
        return self._chat_engines[session_id]

    async def stream_chat(
        self, query: str, session_id: str = "default"
    ) -> AsyncGenerator[str, None]:
        chat_engine = self._get_chat_engine(session_id)

        def run_stream():
            return chat_engine.stream_chat(query)

        streaming_response = await asyncio.to_thread(run_stream)

        for token in streaming_response.response_gen:
            payload = json.dumps({"type": "token", "content": token})
            yield f"data: {payload}\n\n"

        sources = []
        if streaming_response.source_nodes:
            for node in streaming_response.source_nodes[:5]:
                meta = node.metadata or {}
                sources.append(
                    {
                        "ticker": meta.get("ticker"),
                        "source": meta.get("source"),
                        "score": round(float(node.score or 0), 4),
                    }
                )

        done_payload = json.dumps({"type": "done", "sources": sources})
        yield f"data: {done_payload}\n\n"

    def ingest_documents(self, documents: list[dict[str, Any]]) -> int:
        if not documents:
            return 0

        embed_model: BaseEmbedding = LlamaSettings.embed_model  # type: ignore[assignment]
        ingested = 0

        for doc in documents:
            content = doc["content"]
            metadata = doc.get("metadata", {})
            embedding = embed_model.get_text_embedding(content)
            insert_document(
                self.supabase_client,
                content=content,
                metadata=metadata,
                embedding=embedding,
            )
            ingested += 1

        return ingested

    def reset_session(self, session_id: str) -> None:
        self._chat_engines.pop(session_id, None)


def get_demo_documents() -> list[dict[str, Any]]:
    return [
        {
            "content": (
                "Apple Inc. (AAPL) FY2024: Revenue $391.0B (+2.0% YoY), "
                "Gross Margin 46.2%, Operating Margin 31.5%, EPS $6.42. "
                "Services revenue reached $96.2B (+13% YoY). iPhone revenue $201.2B. "
                "Cash and equivalents $65.2B. R&D spend $31.3B."
            ),
            "metadata": {
                "ticker": "AAPL",
                "sector": "Technology",
                "source": "10-K FY2024",
                "type": "earnings",
            },
        },
        {
            "content": (
                "Microsoft Corporation (MSFT) FY2024: Revenue $245.1B (+16% YoY), "
                "Cloud (Azure + other) $137.0B (+23% YoY). Operating income $109.4B. "
                "Net income $88.1B. Commercial cloud gross margin 72%. "
                "Copilot adoption cited across Enterprise segment."
            ),
            "metadata": {
                "ticker": "MSFT",
                "sector": "Technology",
                "source": "10-K FY2024",
                "type": "earnings",
            },
        },
        {
            "content": (
                "NVIDIA Corporation (NVDA) Q3 FY2025: Revenue $35.1B (+94% YoY), "
                "Data Center revenue $30.8B. Gross margin 74.6%. "
                "Blackwell architecture demand exceeds supply. "
                "H200 shipments ramping; inference workload mix increasing."
            ),
            "metadata": {
                "ticker": "NVDA",
                "sector": "Semiconductors",
                "source": "Earnings Call Q3 FY2025",
                "type": "earnings",
            },
        },
        {
            "content": (
                "Federal Reserve FOMC Summary (Dec 2024): Policy rate held at 4.25%-4.50%. "
                "Inflation progress noted but remains above 2% target. "
                "Labor market cooling with unemployment 4.2%. "
                "Dot plot implies two 25bp cuts in 2025. "
                "QT pace unchanged; balance sheet normalization ongoing."
            ),
            "metadata": {
                "ticker": "MACRO",
                "sector": "Macro",
                "source": "FOMC Statement",
                "type": "macro",
            },
        },
        {
            "content": (
                "JPMorgan Chase (JPM) Q4 2024: Net revenue $42.5B, Net income $14.0B. "
                "ROTCE 22%. Investment Banking fees +12% QoQ. "
                "NII $23.1B; credit provisions $2.8B. CET1 ratio 15.8%. "
                "Guidance: mid-single-digit NII growth for 2025."
            ),
            "metadata": {
                "ticker": "JPM",
                "sector": "Financials",
                "source": "Earnings Release Q4 2024",
                "type": "earnings",
            },
        },
    ]
