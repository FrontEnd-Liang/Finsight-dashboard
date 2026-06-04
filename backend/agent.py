import asyncio
import json
import re
from collections.abc import AsyncGenerator, Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[misc, assignment]

from llama_index.core import Settings as LlamaSettings
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.base.embeddings.base import BaseEmbedding
from supabase import Client

from config import Settings
from embeddings import create_embed_model
from llm import create_llm
from corpus import get_demo_documents
from database import (
    clear_documents,
    count_documents,
    insert_document,
    list_document_summaries,
    match_documents,
    nodes_from_matches,
)

DEFAULT_SUGGESTIONS = [
    "对比 AAPL 与 MSFT 营收增速及利润率",
    "汇总 NVDA 数据中心业务前景（基于公告/财报）",
    "最新 FOMC 对 2025 年降息路径释放何种信号？",
    "生成超大盘科技 KPI 对比 Markdown 表格",
]

SYSTEM_PROMPT_TEMPLATE = """You are Finsight, an expert financial research analyst AI.
You analyze equities, macro trends, earnings, and regulatory filings using retrieved context when relevant.

Today (Asia/Shanghai): {today}

Rules:
- For financial questions: ground answers in provided context; cite tickers and figures when available.
- If context is insufficient for a financial question, say what is missing and suggest data to ingest.
- For general questions (date, time, greetings, product help): answer directly in Chinese; use the date above when asked.
- Use markdown tables for comparative metrics (revenue, margins, P/E, YoY growth).
- Be concise, institutional-grade; avoid speculation beyond the evidence on market topics.
"""


def _now_shanghai() -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("Asia/Shanghai"))
        except Exception:
            pass
    return datetime.now(timezone(timedelta(hours=8)))


def build_system_prompt() -> str:
    now = _now_shanghai()
    today = now.strftime("%Y年%m月%d日（%A）")
    return SYSTEM_PROMPT_TEMPLATE.format(today=today)


EMPTY_RESPONSE_MARKER = "Empty Response"


def is_empty_llm_response(text: str) -> bool:
    stripped = text.strip()
    return not stripped or stripped == EMPTY_RESPONSE_MARKER


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
                system_prompt=build_system_prompt(),
                verbose=False,
            )
        return self._chat_engines[session_id]

    def _retrieve_for_query(self, query: str) -> list[NodeWithScore]:
        retriever = self._get_retriever()
        return retriever.retrieve(query)

    def _format_retrieval_thinking(
        self, query: str, nodes: list[NodeWithScore]
    ) -> str:
        lines = [
            f"**问题理解：** {query.strip()}",
            "",
            "**知识库检索：**",
        ]
        if not nodes:
            lines.append(
                "- 未命中相关文档（相似度低于阈值或语料库为空），将基于模型常识作答并标注证据缺口。"
            )
            return "\n".join(lines)

        lines.append(f"- 命中 {len(nodes)} 条相关记录：")
        for i, node in enumerate(nodes[:5], start=1):
            meta = node.metadata or {}
            ticker = meta.get("ticker") or "—"
            source = meta.get("source") or "—"
            score = round(float(node.score or 0), 4)
            snippet = (node.get_content() or "").replace("\n", " ")[:120]
            lines.append(
                f"  {i}. `{ticker}` · {source} · 相似度 {score} — {snippet}…"
            )
        lines.extend(["", "**分析规划：**"])
        return "\n".join(lines)

    def _stream_fallback_tokens(self, query: str) -> Iterator[str]:
        """Direct LLM answer when RAG returns no usable context."""
        llm = LlamaSettings.llm
        prompt = (
            f"{build_system_prompt()}\n\n"
            f"用户问题：{query.strip()}\n\n"
            "当前 RAG 未返回可用正文（语料不匹配或合成失败）。请用中文直接回答：\n"
            "- 日期/时间：使用系统提示中的今日日期；\n"
            "- 指数/股价涨跌预测：明确说明演示环境无实时行情，不能负责任预测，"
            "但可列出应关注的宏观变量（FOMC、利率、VIX、龙头财报等）及分析框架；\n"
            "- 其它：简要说明原因并给出可执行建议。"
        )
        response = llm.stream_complete(prompt)
        for chunk in response:
            delta = getattr(chunk, "delta", None) or getattr(chunk, "text", None)
            if delta:
                yield delta

    def _stream_thinking_tokens(self, query: str, nodes: list[NodeWithScore]):
        llm = LlamaSettings.llm
        context_lines: list[str] = []
        for node in nodes[:3]:
            meta = node.metadata or {}
            context_lines.append(
                f"- {meta.get('ticker', '?')} ({meta.get('source', '?')}): "
                f"{(node.get_content() or '')[:280]}"
            )
        context_block = (
            "\n".join(context_lines) if context_lines else "（无检索上下文）"
        )
        prompt = (
            "你是 Finsight 金融研究助手。根据用户问题与检索片段，"
            "用中文写出简明的内部分析思路（3～5 条要点，可用 Markdown 列表），"
            "说明将如何论证、对比哪些指标、需注意哪些风险。"
            "不要写最终结论或完整报告，仅输出思考过程。\n\n"
            f"用户问题：{query.strip()}\n\n"
            f"检索片段：\n{context_block}"
        )
        response = llm.stream_complete(prompt)
        for chunk in response:
            delta = getattr(chunk, "delta", None) or getattr(chunk, "text", None)
            if delta:
                yield delta

    async def stream_chat(
        self, query: str, session_id: str = "default"
    ) -> AsyncGenerator[str, None]:
        nodes = await asyncio.to_thread(self._retrieve_for_query, query)
        retrieval_thinking = self._format_retrieval_thinking(query, nodes)
        payload = json.dumps({"type": "thinking", "content": retrieval_thinking})
        yield f"data: {payload}\n\n"

        loop = asyncio.get_running_loop()
        thinking_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def produce_thinking_tokens() -> None:
            try:
                for token in self._stream_thinking_tokens(query, nodes):
                    loop.call_soon_threadsafe(thinking_queue.put_nowait, token)
            finally:
                loop.call_soon_threadsafe(thinking_queue.put_nowait, None)

        producer = asyncio.to_thread(produce_thinking_tokens)
        producer_task = asyncio.create_task(producer)

        while True:
            token = await thinking_queue.get()
            if token is None:
                break
            payload = json.dumps({"type": "thinking", "content": token})
            yield f"data: {payload}\n\n"

        await producer_task

        def run_main_answer() -> str:
            if not nodes:
                return ""

            chat_engine = self._get_chat_engine(session_id)
            streaming_response = chat_engine.stream_chat(query)
            parts = [t for t in streaming_response.response_gen if t]
            text = "".join(parts)

            if is_empty_llm_response(text):
                resp_obj = getattr(streaming_response, "response", None)
                if resp_obj is not None:
                    alt = str(getattr(resp_obj, "response", resp_obj) or "")
                    if not is_empty_llm_response(alt):
                        text = alt
            return text

        main_text = await asyncio.to_thread(run_main_answer)

        if is_empty_llm_response(main_text):

            def run_fallback():
                return list(self._stream_fallback_tokens(query))

            fallback_tokens = await asyncio.to_thread(run_fallback)
            stream_text = "".join(fallback_tokens)
        else:
            stream_text = main_text

        chunk_size = 16
        for i in range(0, len(stream_text), chunk_size):
            chunk = stream_text[i : i + chunk_size]
            payload = json.dumps({"type": "token", "content": chunk})
            yield f"data: {payload}\n\n"

        streaming_response = None

        sources = []
        rag_nodes = nodes[:5]
        if rag_nodes:
            for node in rag_nodes:
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

    def _corpus_summary_lines(self) -> list[str]:
        rows = list_document_summaries(self.supabase_client, limit=8)
        if rows:
            lines: list[str] = []
            for row in rows:
                meta = row.get("metadata") or {}
                ticker = meta.get("ticker") or "—"
                source = meta.get("source") or "—"
                doc_type = meta.get("type") or "—"
                snippet = (row.get("content") or "").replace("\n", " ")[:100]
                lines.append(f"- {ticker} · {source} · {doc_type} — {snippet}")
            return lines

        try:
            demo_docs = get_demo_documents()
        except FileNotFoundError:
            demo_docs = []
        return [
            f"- {doc['metadata'].get('ticker', '—')} · "
            f"{doc['metadata'].get('source', '—')} · "
            f"{doc['metadata'].get('type', '—')}"
            for doc in demo_docs
        ]

    def _parse_suggestions_json(self, text: str, count: int) -> list[str] | None:
        cleaned = text.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if fence:
            cleaned = fence.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, list):
            return None
        items = [str(item).strip() for item in data if str(item).strip()]
        if len(items) < count:
            return None
        return items[:count]

    def generate_suggestions(
        self,
        recent_queries: list[str] | None = None,
        count: int = 4,
    ) -> list[str]:
        corpus_lines = self._corpus_summary_lines()
        recent_block = ""
        if recent_queries:
            recent_block = (
                "\n用户最近提问（请避开重复、可延伸新角度）：\n"
                + "\n".join(f"- {q.strip()}" for q in recent_queries[-3:] if q.strip())
            )

        prompt = (
            "你是 Finsight 金融研究终端。根据当前知识库与近期提问，"
            f"生成 {count} 条中文推荐研究问题，供分析师一键点击。\n"
            "要求：\n"
            "- 每条 18～45 字，具体可执行（对比、汇总、表格、宏观解读等）\n"
            "- 覆盖知识库中不同 ticker/主题，优先引用库内已有标的\n"
            "- 仅输出 JSON 字符串数组，不要 markdown 或其它说明\n\n"
            f"知识库概况：\n"
            + ("\n".join(corpus_lines) if corpus_lines else "（语料库为空，生成通用金融研究问题）")
            + recent_block
        )

        llm = LlamaSettings.llm
        response = llm.complete(prompt)
        parsed = self._parse_suggestions_json(response.text, count)
        return parsed if parsed else DEFAULT_SUGGESTIONS[:count]

    def get_corpus_status(self) -> dict[str, Any]:
        from corpus import get_demo_corpus_meta

        stored = count_documents(self.supabase_client)
        demo_meta = get_demo_corpus_meta()
        return {
            "stored_count": stored,
            "demo_file_count": demo_meta["document_count"],
            "demo_tickers": demo_meta["tickers"],
            "demo_file": demo_meta["file"],
            "is_loaded": stored > 0,
        }

    def ingest_documents(
        self, documents: list[dict[str, Any]], *, replace: bool = False
    ) -> int:
        if not documents:
            return 0

        if replace:
            clear_documents(self.supabase_client)

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
