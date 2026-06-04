import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import FinancialResearchAgent, get_demo_documents
from config import get_settings
from database import create_supabase_client, ensure_vector_store_ready

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finsight")

agent: FinancialResearchAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    settings = get_settings()
    client = create_supabase_client(settings)
    try:
        ensure_vector_store_ready(client)
    except Exception as exc:
        logger.warning("Supabase table check failed (run supabase_schema.sql): %s", exc)
    agent = FinancialResearchAgent(settings, client)
    logger.info("Finsight agent initialized")
    yield
    agent = None


app = FastAPI(
    title="Finsight Financial Research API",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    session_id: str = Field(default="default", max_length=128)


class IngestRequest(BaseModel):
    documents: list[dict[str, Any]] | None = None
    use_demo: bool = False


class ResetRequest(BaseModel):
    session_id: str = "default"


class SuggestionsRequest(BaseModel):
    recent_queries: list[str] = Field(default_factory=list, max_length=5)
    count: int = Field(default=4, ge=1, le=6)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "finsight-api"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def event_generator():
        try:
            async for chunk in agent.stream_chat(
                query=request.query.strip(),
                session_id=request.session_id,
            ):
                yield chunk
        except Exception as exc:
            logger.exception("Chat stream error")
            import json

            err = json.dumps({"type": "error", "message": str(exc)})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ingest")
async def ingest(request: IngestRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    docs = request.documents
    if request.use_demo or not docs:
        docs = get_demo_documents()

    try:
        count = agent.ingest_documents(docs)
        return {"ingested_nodes": count, "status": "success"}
    except Exception as exc:
        logger.exception("Ingest error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/suggestions")
async def suggestions(request: SuggestionsRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        items = await asyncio.to_thread(
            agent.generate_suggestions,
            request.recent_queries,
            request.count,
        )
        return {"suggestions": items}
    except Exception as exc:
        logger.exception("Suggestions error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/reset")
async def reset_session(request: ResetRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    agent.reset_session(request.session_id)
    return {"status": "ok", "session_id": request.session_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
