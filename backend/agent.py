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
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.base.embeddings.base import BaseEmbedding
from supabase import Client

from config import Settings
from embeddings import create_embed_model
from llm import create_llm
from corpus import get_library_documents
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
    "最新 FOMC 对 2026 年下半年利率路径释放何种信号？",
    "生成超大盘科技 KPI 对比 Markdown 表格",
]

SYSTEM_PROMPT_TEMPLATE = """You are Finsight, an expert financial research analyst AI.
You analyze equities, macro trends, earnings, and regulatory filings using retrieved context when relevant.

Today (calendar, Asia/Shanghai): {today}

Rules:
- Retrieved excerpts are from the **ingested research library only**, not live market data feeds.
- Each excerpt has a **fiscal/report period** in its source label (e.g. FY2025, Q1 2026). Cite that period explicitly; do not call it "today's data" unless period_end matches the calendar year of today.
- If the user asks for "latest" figures but context only has older fiscal periods, state the newest period available in context and what newer filing would be needed.
- For financial questions: ground answers in provided context; cite tickers, figures, and source period when available.
- If context is insufficient for a financial question, say what is missing and suggest data to ingest.
- For general questions (date, time, greetings, product help): answer directly in Chinese; use the date above when asked.
- Use markdown tables for comparative metrics (revenue, margins, P/E, YoY growth).
- Be concise, institutional-grade; avoid speculation beyond the evidence on market topics.
- Prefer 200–500 Chinese characters unless the user asks for a long report or a comparison table.
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
                similarity_top_k=self.settings.rag_top_k,
            )
        return self._retriever

    def _build_context_block(
        self, nodes: list[NodeWithScore], max_nodes: int | None = None
    ) -> str:
        if not nodes:
            return "（无检索上下文）"
        limit = max_nodes or self.settings.rag_top_k
        lines: list[str] = []
        for node in nodes[:limit]:
            meta = node.metadata or {}
            content = (node.get_content() or "")[:600]
            period = meta.get("source") or meta.get("period_end") or "—"
            fy = meta.get("fiscal_year")
            fq = meta.get("fiscal_quarter")
            latest = " [LATEST]" if meta.get("is_latest") else ""
            header = f"### {meta.get('ticker', '?')} — {period}{latest}"
            if fy is not None:
                header += f" (FY{fy}"
                if fq:
                    header += f" {fq}"
                header += ")"
            lines.append(f"{header}\n{content}")
        return "\n\n".join(lines)

    def _retrieve_for_query(self, query: str) -> list[NodeWithScore]:
        retriever = self._get_retriever()
        nodes = retriever.retrieve(query)
        # Prefer documents marked is_latest in metadata when scores are close.
        return sorted(
            nodes,
            key=lambda n: (
                0 if (n.metadata or {}).get("is_latest") else 1,
                -(float(n.score or 0)),
            ),
        )

    @staticmethod
    def _relevance_label(score: float) -> str:
        if score >= 0.55:
            return "高"
        if score >= 0.45:
            return "中"
        return "低"

    def _node_to_source_ref(self, rank: int, node: NodeWithScore) -> dict[str, Any]:
        meta = node.metadata or {}
        content = (node.get_content() or "").strip()
        score = float(node.score or 0)
        node_id = getattr(node.node, "id_", None) or meta.get("id")
        return {
            "rank": rank,
            "ticker": meta.get("ticker"),
            "source": meta.get("source"),
            "score": round(score, 4),
            "relevance": self._relevance_label(score),
            "sector": meta.get("sector"),
            "doc_type": meta.get("type"),
            "fiscal_year": meta.get("fiscal_year"),
            "fiscal_quarter": meta.get("fiscal_quarter"),
            "period_end": meta.get("period_end"),
            "filed_date": meta.get("filed_date"),
            "is_latest": bool(meta.get("is_latest")),
            "document_id": str(node_id) if node_id else None,
            "excerpt": content[:520],
        }

    def _infer_analysis_plan(
        self, query: str, nodes: list[NodeWithScore]
    ) -> list[str]:
        if not nodes:
            return [
                "未检索到可用片段，将说明资料库缺口并给出分析框架（不作实时行情预测）。"
            ]

        tickers = sorted(
            {
                str((n.metadata or {}).get("ticker"))
                for n in nodes
                if (n.metadata or {}).get("ticker")
            }
        )
        plans: list[str] = []
        q = query.strip()

        if len(tickers) >= 2:
            sample = "、".join(tickers[:6])
            plans.append(
                f"横向对比 {sample} 的关键 KPI（营收、增速、利润率、分部业务等），"
                "引用各条来源的披露期间。"
            )
        elif tickers:
            plans.append(
                f"围绕 `{tickers[0]}` 归纳财报要点、同比变化与管理层表述（仅基于检索片段）。"
            )

        if any(k in q for k in ("表格", "对比", "Markdown", "markdown")):
            plans.append("使用 Markdown 表格组织指标，列标题注明期间与来源。")
        if any(k in q.upper() for k in ("FOMC", "MACRO")) or "宏观" in q:
            plans.append("区分宏观披露与个股财报，避免混用不同口径。")
        if "NVDA" in q.upper() or "数据中心" in q:
            plans.append("优先引用 NVDA 最新季报中数据中心收入与增速表述。")

        latest_count = sum(1 for n in nodes if (n.metadata or {}).get("is_latest"))
        if latest_count:
            plans.append(
                f"共 {len(nodes)} 条命中，其中 {latest_count} 条标记为库内「最新披露」。"
            )

        return plans[:5]

    def _format_node_thinking_block(self, rank: int, node: NodeWithScore) -> str:
        meta = node.metadata or {}
        ref = self._node_to_source_ref(rank, node)
        ticker = ref.get("ticker") or "—"
        source = ref.get("source") or "—"
        sector = meta.get("sector") or "—"
        doc_type = meta.get("type") or "—"
        fy = meta.get("fiscal_year")
        fq = meta.get("fiscal_quarter")
        period_parts: list[str] = []
        if fy is not None:
            period_parts.append(f"FY{fy}")
        if fq:
            period_parts.append(str(fq))
        period_label = " ".join(period_parts) if period_parts else "—"
        latest_tag = " · **最新披露**" if meta.get("is_latest") else ""
        score = ref["score"]
        rel = ref["relevance"]
        excerpt = (ref.get("excerpt") or "").replace("\n", " ")

        lines = [
            f"### {rank}. `{ticker}` — {source}{latest_tag}",
            (
                f"- **相似度：** {score}（相关度：**{rel}**） · "
                f"**板块：** {sector} · **类型：** {doc_type}"
            ),
        ]
        if meta.get("period_end"):
            lines.append(f"- **报告期末：** {meta.get('period_end')}")
        if meta.get("filed_date"):
            lines.append(f"- **披露/入库日期：** {meta.get('filed_date')}")
        lines.append(f"- **期间标签：** {period_label}")
        if ref.get("document_id"):
            lines.append(f"- **文档 ID：** `{ref['document_id']}`")
        lines.append("- **正文摘录：**")
        lines.append(f"  > {excerpt}")
        return "\n".join(lines)

    def _build_thinking_chunks(
        self, query: str, nodes: list[NodeWithScore]
    ) -> list[str]:
        """Ordered markdown sections streamed one after another."""
        chunks: list[str] = [
            f"## 问题理解\n{query.strip()}",
            (
                "## 检索策略\n"
                f"- 将问题编码为 {self.settings.embedding_dimensions} 维向量，"
                "在 `financial_documents` 表做 pgvector 余弦近邻检索。\n"
                f"- 取 Top **{self.settings.rag_top_k}** 条；同分时优先 `is_latest` 披露。\n"
                "- 资料为已入库研报/财报摘要，**非**实时行情推送。"
            ),
        ]
        if not nodes:
            chunks.append(
                "## 检索结果\n- **未命中**相关文档（语料库为空或语义不匹配）。"
            )
            chunks.append("## 分析规划\n- 明确证据缺口，不作无依据的数字预测。")
            return chunks

        chunks.append(
            "## 检索结果\n"
            f"共命中 **{len(nodes)}** 条（按语义相似度降序；"
            "相似度 ≠ 日历最新，请结合披露日期判断）。"
        )
        for i, node in enumerate(nodes[: self.settings.rag_top_k], start=1):
            chunks.append(self._format_node_thinking_block(i, node))

        plan_lines = ["## 分析规划"]
        plan_lines.extend(f"- {step}" for step in self._infer_analysis_plan(query, nodes))
        chunks.append("\n".join(plan_lines))
        chunks.append(
            "## 说明\n"
            "- 以上摘录将注入大模型上下文；回答中会再次标注引用期间。\n"
            "- 若需更新库内披露，请在侧边栏 **同步资料库**。"
        )
        return chunks

    def _format_retrieval_thinking(
        self, query: str, nodes: list[NodeWithScore]
    ) -> str:
        return "\n\n".join(self._build_thinking_chunks(query, nodes))

    @staticmethod
    def _thinking_line_delay(line: str) -> float:
        stripped = line.strip()
        if not stripped:
            return 0.012
        if stripped.startswith("### "):
            return 0.14
        if stripped.startswith("## "):
            return 0.1
        if stripped.startswith("> "):
            return 0.045
        if stripped.startswith("- "):
            return 0.038
        return 0.032

    async def _stream_thinking_events(
        self, query: str, nodes: list[NodeWithScore]
    ) -> AsyncGenerator[str, None]:
        """Yield SSE payloads for progressive thinking (status + line chunks)."""
        chunks = self._build_thinking_chunks(query, nodes)
        node_blocks = [
            c for c in chunks if c.lstrip().startswith("### ")
        ]

        if node_blocks:
            yield json.dumps(
                {
                    "type": "thinking_step",
                    "label": f"命中 {len(node_blocks)} 条，逐条核对摘录…",
                },
                ensure_ascii=False,
            )
            await asyncio.sleep(0.2)

        for chunk in chunks:
            if chunk.lstrip().startswith("## 分析规划"):
                yield json.dumps(
                    {"type": "thinking_step", "label": "拟定分析路径…"},
                    ensure_ascii=False,
                )
                await asyncio.sleep(0.18)

            for line in chunk.split("\n"):
                yield json.dumps(
                    {"type": "thinking", "content": f"{line}\n"},
                    ensure_ascii=False,
                )
                await asyncio.sleep(self._thinking_line_delay(line))

            await asyncio.sleep(0.16)

        yield json.dumps(
            {"type": "thinking_step", "label": "思考完成，正在生成回答…"},
            ensure_ascii=False,
        )
        await asyncio.sleep(0.12)

    def _stream_fallback_tokens(self, query: str) -> Iterator[str]:
        """Direct LLM answer when RAG returns no usable context."""
        llm = LlamaSettings.llm
        prompt = (
            f"{build_system_prompt()}\n\n"
            f"用户问题：{query.strip()}\n\n"
            "当前 RAG 未返回可用正文（资料不匹配或合成失败）。请用中文直接回答：\n"
            "- 日期/时间：使用系统提示中的今日日期；\n"
            "- 指数/股价涨跌预测：明确说明资料库无实时行情，不能负责任预测，"
            "但可列出应关注的宏观变量（FOMC、利率、VIX、龙头财报等）及分析框架；\n"
            "- 其它：简要说明原因并给出可执行建议。"
        )
        response = llm.stream_complete(prompt)
        for chunk in response:
            delta = getattr(chunk, "delta", None) or getattr(chunk, "text", None)
            if delta:
                yield delta

    def _stream_answer_tokens(
        self, query: str, nodes: list[NodeWithScore]
    ) -> Iterator[str]:
        """Single LLM call with pre-retrieved context (no condense / extra thinking pass)."""
        llm = LlamaSettings.llm
        context = self._build_context_block(nodes)
        prompt = (
            f"{build_system_prompt()}\n\n"
            f"## Retrieved context\n{context}\n\n"
            f"## User question\n{query.strip()}\n\n"
            "用中文直接回答。引用数字时必须写明对应财报/公告期间（如 FY2025、Q1 2026）；"
            "勿把资料库中的旧期间说成「当前最新」。若证据不足请说明缺口。避免冗长铺垫。"
        )
        response = llm.stream_complete(prompt)
        for chunk in response:
            delta = getattr(chunk, "delta", None) or getattr(chunk, "text", None)
            if delta:
                yield delta

    async def stream_chat(
        self, query: str, session_id: str = "default"
    ) -> AsyncGenerator[str, None]:
        _ = session_id  # reserved for future multi-turn memory
        yield (
            "data: "
            + json.dumps(
                {"type": "thinking_step", "label": "理解问题中…"},
                ensure_ascii=False,
            )
            + "\n\n"
        )
        await asyncio.sleep(0.2)

        yield (
            "data: "
            + json.dumps(
                {
                    "type": "thinking_step",
                    "label": "检索资料库（向量相似度）…",
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )
        nodes = await asyncio.to_thread(self._retrieve_for_query, query)

        async for thinking_payload in self._stream_thinking_events(query, nodes):
            yield f"data: {thinking_payload}\n\n"

        loop = asyncio.get_running_loop()
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def produce_answer_tokens() -> None:
            try:
                stream_fn = (
                    self._stream_answer_tokens
                    if nodes
                    else self._stream_fallback_tokens
                )
                for token in stream_fn(query, nodes) if nodes else stream_fn(query):
                    loop.call_soon_threadsafe(token_queue.put_nowait, token)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        producer_task = asyncio.create_task(asyncio.to_thread(produce_answer_tokens))

        while True:
            token = await token_queue.get()
            if token is None:
                break
            if is_empty_llm_response(token):
                continue
            payload = json.dumps({"type": "token", "content": token})
            yield f"data: {payload}\n\n"

        await producer_task

        sources = [
            self._node_to_source_ref(i, node)
            for i, node in enumerate(nodes[: self.settings.rag_top_k], start=1)
        ]

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
            library_docs = get_library_documents()
        except FileNotFoundError:
            library_docs = []
        return [
            f"- {doc['metadata'].get('ticker', '—')} · "
            f"{doc['metadata'].get('source', '—')} · "
            f"{doc['metadata'].get('type', '—')}"
            for doc in library_docs
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

    def corpus_based_suggestions(self, count: int = 4) -> list[str]:
        """Instant suggestions from library coverage tickers (no LLM)."""
        from corpus import get_library_meta

        try:
            tickers = list(get_library_meta().get("tickers") or [])
        except FileNotFoundError:
            tickers = []

        equities = [t for t in tickers if t and t != "MACRO"]
        has_macro = "MACRO" in tickers
        pool: list[str] = []

        if len(equities) >= 2:
            pool.append(
                f"对比 {equities[0]} 与 {equities[1]} 营收增速及利润率"
            )
        if "NVDA" in equities:
            pool.append("汇总 NVDA 数据中心业务前景（基于公告/财报）")
        elif equities:
            pool.append(f"汇总 {equities[0]} 最新财报要点与同比变化")
        if has_macro:
            pool.append("最新 FOMC 对 2026 年下半年利率路径释放何种信号？")
        if len(equities) >= 3:
            sample = "、".join(equities[:4])
            pool.append(f"生成 {sample} 等标的 KPI 对比 Markdown 表格")
        if "JPM" in equities:
            pool.append("分析 JPM Q1 2026 净利息收入与 ROTCE 变化及信用成本")

        seen: set[str] = set()
        unique: list[str] = []
        for item in pool:
            if item not in seen:
                seen.add(item)
                unique.append(item)

        if len(unique) >= count:
            return unique[:count]
        for fallback in DEFAULT_SUGGESTIONS:
            if fallback not in seen:
                unique.append(fallback)
            if len(unique) >= count:
                break
        return unique[:count]

    def generate_suggestions(
        self,
        recent_queries: list[str] | None = None,
        count: int = 4,
        *,
        use_ai: bool = False,
    ) -> list[str]:
        baseline = self.corpus_based_suggestions(count)
        if not use_ai:
            return baseline

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
            + ("\n".join(corpus_lines) if corpus_lines else "（资料库为空，生成通用金融研究问题）")
            + recent_block
        )

        try:
            llm = LlamaSettings.llm
            response = llm.complete(prompt)
            parsed = self._parse_suggestions_json(response.text, count)
            return parsed if parsed else baseline
        except Exception:
            return baseline

    def get_corpus_status(self) -> dict[str, Any]:
        from corpus import get_library_meta

        stored = count_documents(self.supabase_client)
        library_meta = get_library_meta()
        return {
            "stored_count": stored,
            "library_manifest_count": library_meta["document_count"],
            "library_tickers": library_meta["tickers"],
            "library_file": library_meta["file"],
            "library_version": library_meta.get("version"),
            "library_as_of": library_meta.get("as_of_calendar"),
            "is_loaded": stored > 0,
            "needs_reload": stored > 0
            and stored != library_meta["document_count"],
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
        _ = session_id
