"""
FastAPI application.

Session persistence is now handled by LangGraph's MemorySaver.
The _sessions dict here stores only lightweight metadata (preview, created_at)
for the sidebar — actual state lives in LangGraph's checkpointer.
"""

import json
import traceback
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from core.models import (
    ChatRequest,
    ChatResponse,
    NewSessionResponse,
    SessionContext,
    QueryIntent,
)
from core.graph import memory_checkpointer
from agents.orchestrator import OrchestratorAgent

log = structlog.get_logger()

app = FastAPI(
    title="KYC Document Intelligence Suite",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = OrchestratorAgent()

# ── Lightweight session index ──────────────────────────────────────────────────
# Stores only metadata for the UI sidebar.
# Actual state lives in LangGraph's MemorySaver keyed by session_id.
_session_index: dict[str, dict] = {}


def _get_or_create_session_context(session_id: str | None) -> SessionContext:
    """
    Get existing session context or create new one.

    On subsequent turns for the same session_id, the LangGraph checkpointer
    automatically loads the previous state — we just need to provide the
    SessionContext object as the starting point for this turn's KYCState.
    """
    if session_id and session_id in _session_index:
        # Session exists — return a fresh SessionContext with the same session_id
        # LangGraph will merge this with the checkpointed state
        ctx = SessionContext()
        ctx.session_id = session_id
        return ctx

    # New session
    ctx = SessionContext()
    _session_index[ctx.session_id] = {
        "created_at": ctx.created_at.isoformat(),
        "preview":    "New conversation",
    }
    log.info("session.created", session_id=ctx.session_id)
    return ctx


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":          "ok",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "active_sessions": len(_session_index),
    }


@app.post("/chat/session", response_model=NewSessionResponse)
async def new_session():
    """Create a new chat session."""
    ctx = SessionContext()
    _session_index[ctx.session_id] = {
        "created_at": ctx.created_at.isoformat(),
        "preview":    "New conversation",
    }
    return NewSessionResponse(
        session_id=ctx.session_id,
        created_at=ctx.created_at,
    )


@app.get("/chat/sessions")
async def list_sessions():
    """List all sessions with metadata. Used to populate the sidebar."""
    return {
        "sessions": [
            {"session_id": sid, **meta}
            for sid, meta in _session_index.items()
        ]
    }


@app.get("/chat/{session_id}/history")
async def get_history(session_id: str):
    """
    Return message history for a session.
    Reads from LangGraph's checkpointer to get the persisted state.
    """
    config = {"configurable": {"thread_id": session_id}}

    # Get the latest checkpoint for this thread
    checkpoint = memory_checkpointer.get(config)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Extract state from checkpoint
    state = checkpoint.get("channel_values", {})
    session_context = state.get("session_context")

    if not session_context:
        return {"session_id": session_id, "messages": [], "message_count": 0}

    return {
        "session_id":    session_id,
        "message_count": len(session_context.messages),
        "messages":      [m.model_dump() for m in session_context.messages],
        "customer_context": (
            session_context.customer_details.model_dump()
            if session_context.customer_details else None
        ),
        "has_document_context": session_context.last_document_intelligence is not None,
    }


@app.post("/chat/{session_id}", response_model=ChatResponse)
async def chat(session_id: str, request: ChatRequest):
    """Send a message and receive a complete response."""
    ctx = _get_or_create_session_context(session_id)

    log.info(
        "api.chat.received",
        session_id=ctx.session_id,
        query_preview=request.query[:80],
        doc_count=len(request.documents) or len(request.documents_b64),
    )

    try:
        state = request.to_kyc_state(ctx)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        state = await orchestrator.run(state)
    except Exception as e:
        log.error("api.chat.error", error=str(e), traceback=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

    if state.error:
        raise HTTPException(status_code=500, detail=state.error)

    # Update session preview for sidebar
    _session_index[ctx.session_id]["preview"] = request.query[:60]

    return ChatResponse(
        session_id=ctx.session_id,
        message_id=state.turn_id,
        intent=state.execution_plan.intent if state.execution_plan else None,
        verdict=state.verdict,
        risk_tier=state.risk_scoring.overall_risk_tier if state.risk_scoring else None,
        report=state.report or "",
        execution_plan=state.execution_plan,
        agents={
            "document_intelligence": state.document_intelligence.model_dump() if state.document_intelligence else None,
            "regulatory_retrieval":  state.regulatory_retrieval.model_dump()  if state.regulatory_retrieval  else None,
            "risk_scoring":          state.risk_scoring.model_dump()          if state.risk_scoring          else None,
        },
        completed_at=state.completed_at or datetime.now(timezone.utc),
    )


@app.post("/chat/{session_id}/stream")
async def chat_stream(session_id: str, request: ChatRequest):
    """Send a message with SSE streaming using LangGraph's astream_events."""
    ctx = _get_or_create_session_context(session_id)

    log.info(
        "api.stream.received",
        session_id=ctx.session_id,
        query_preview=request.query[:80],
    )

    try:
        state = request.to_kyc_state(ctx)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Update session preview
    _session_index[ctx.session_id]["preview"] = request.query[:60]

    async def event_generator():
        async for event in orchestrator.run_streaming(state):
            yield {"event": event["event"], "data": event["data"]}

    return EventSourceResponse(event_generator())