"""
FastAPI application.

Session persistence is now handled by LangGraph's MemorySaver.
The _sessions dict here stores only lightweight metadata (preview, created_at)
for the sidebar — actual state lives in LangGraph's checkpointer.
"""

import json
import traceback
from datetime import datetime, timezone
import asyncio

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

@app.post("/chat/mock/stream")
async def chat_mock_stream(request: ChatRequest):
    """
    Mock SSE endpoint for frontend development.
    Matches query content to one of four canned responses.
    No LLM calls made — safe for repeated UI testing.
    """
    mock = _pick_mock_response(request.query)
    doc_count = len(request.documents) or len(request.documents_b64)

    async def mock_stream():

        # ── Planning ───────────────────────────────────────────────────────
        yield {"event": "status", "data": "Thinking..."}
        await asyncio.sleep(0.6)

        plan = {
            "intent":                mock["intent"],
            "steps":                 mock["steps"],
            "reasoning":             mock["reasoning"],
            "missing_info":          [] if mock["steps"] else ["Identity documents", "Customer details"],
            "reusing_from_session":  [],
        }
        yield {"event": "plan", "data": json.dumps(plan)}

        # Early exit for insufficient_info — skip all agent steps
        if mock["intent"] == "insufficient_info":
            await asyncio.sleep(0.3)
            yield {"event": "status", "data": "Generating response..."}
            for line in mock["lines"]:
                yield {"event": "report_token", "data": line + "\n"}
                await asyncio.sleep(0.04)
            yield {"event": "status", "data": "Complete."}
            return

        # ── Agent steps ────────────────────────────────────────────────────
        step_events = {
            "document_intelligence": ("doc",    "Analysing documents...",                  2.0),
            "regulatory_retrieval":  ("reg",    "Retrieving applicable regulations...",    1.8),
            "risk_scoring":          ("risk",   "Calculating risk score...",               1.5),
            "report_summarisation":  ("report", "Generating response...",                  0.4),
        }

        for step in mock["steps"]:
            if step == "report_summarisation":
                break  # handled separately below

            key, status_msg, delay = step_events[step]
            yield {"event": "step_update", "data": f"{key}:running"}
            yield {"event": "status",      "data": status_msg}
            await asyncio.sleep(delay)
            yield {"event": "step_update", "data": f"{key}:done"}

            # Emit risk score after risk_scoring step
            if step == "risk_scoring":
                mock_risk = {
                    "identity_confidence": 0.92,
                    "document_validity":   0.88,
                    "jurisdictional_risk": "LOW",
                    "pep_screening":       "CLEAR",
                    "overall_risk_tier":   "LOW",
                    "recommendation":      "Proceed with standard onboarding under MAS Notice 626.",
                }
                yield {"event": "risk_score", "data": json.dumps(mock_risk)}

        # ── Report streaming ───────────────────────────────────────────────
        yield {"event": "step_update", "data": "report:running"}
        yield {"event": "status",      "data": "Generating response..."}
        await asyncio.sleep(0.4)

        for line in mock["lines"]:
            yield {"event": "report_token", "data": line + "\n"}
            await asyncio.sleep(0.06)

        yield {"event": "step_update", "data": "report:done"}
        yield {"event": "status",      "data": "Complete."}

    return EventSourceResponse(mock_stream())

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

# ── Mock endpoint ──────────────────────────────────────────────────────────────

MOCK_RESPONSES = {
    "cdd": {
        "intent":    "generic_compliance",
        "steps":     ["regulatory_retrieval", "report_summarisation"],
        "reasoning": "Query is a policy question about CDD requirements — no documents needed.",
        "lines": [
            "COMPLIANCE ANSWER — CDD Requirements under MAS Notice 626",
            "─" * 52,
            "",
            "Under MAS Notice 626, all financial institutions in Singapore are required",
            "to perform Customer Due Diligence (CDD) for every customer relationship.",
            "",
            "STANDARD CDD OBLIGATIONS",
            "Institutions must identify the customer and verify their identity using",
            "reliable, independent source documents. For individuals this means a",
            "government-issued photo ID (passport or NRIC). For legal entities, it",
            "means verifying the entity's legal status, ownership structure, and",
            "identifying beneficial owners holding 25% or more.",
            "",
            "WHEN CDD MUST BE PERFORMED",
            "• At account opening or establishment of a business relationship",
            "• When carrying out occasional transactions above SGD 20,000",
            "• When there is suspicion of money laundering or terrorism financing",
            "• When there is doubt about the veracity of previously obtained information",
            "",
            "ENHANCED DUE DILIGENCE (EDD)",
            "EDD is mandatory for higher-risk customers including Politically Exposed",
            "Persons (PEPs), customers from FATF grey-listed jurisdictions, and",
            "correspondent banking relationships. EDD requires senior management",
            "approval and enhanced ongoing monitoring.",
            "",
            "RECORD KEEPING",
            "All CDD documents and findings must be retained for at least 5 years",
            "after the end of the business relationship, per MAS Notice 626 Paragraph 18.",
            "",
            "Reference: MAS Notice 626, Paragraphs 6–12 | FATF Recommendation 10",
        ],
    },
    "kyc": {
        "intent":    "insufficient_info",
        "steps":     [],
        "reasoning": "KYC check requested but no documents or customer details have been provided.",
        "lines": [
            "To perform a full KYC check I need a little more from you.",
            "",
            "Please provide at least one of the following:",
            "",
            "  📄  Identity documents — attach a passport, driving licence, or",
            "      utility bill using the paperclip button in the input box.",
            "",
            "  👤  Customer details — click the person icon to fill in the",
            "      customer details form (name, nationality, address, etc.).",
            "",
            "Once you provide those I can run the full pipeline: document",
            "analysis, regulatory retrieval, risk scoring, and a compliance",
            "report with a PASS / REFER / FAIL verdict.",
        ],
    },
    "pep": {
        "intent":    "generic_compliance",
        "steps":     ["regulatory_retrieval", "report_summarisation"],
        "reasoning": "Query is about PEP-related EDD requirements — a policy question.",
        "lines": [
            "COMPLIANCE ANSWER — Enhanced Due Diligence for PEPs in Singapore",
            "─" * 56,
            "",
            "DEFINITION OF A PEP",
            "Under MAS Notice 626 Paragraph 9 and FATF Recommendation 12, a",
            "Politically Exposed Person is an individual who holds or has held",
            "a prominent public function — including heads of state, senior",
            "politicians, senior government officials, senior judicial or military",
            "officials, and senior executives of state-owned enterprises.",
            "Immediate family members and close associates are also covered.",
            "",
            "EDD REQUIREMENTS FOR PEPs",
            "Financial institutions must:",
            "• Obtain senior management approval before establishing or continuing",
            "  the business relationship",
            "• Take reasonable measures to establish the source of wealth and",
            "  source of funds",
            "• Conduct enhanced ongoing monitoring of the business relationship",
            "",
            "FOREIGN vs DOMESTIC PEPs",
            "Foreign PEPs are always treated as higher risk and require immediate",
            "EDD. Domestic PEPs and international organisation PEPs require a",
            "risk-based assessment — EDD is applied if assessed as higher risk.",
            "",
            "ONGOING MONITORING",
            "PEP status must be reviewed at least annually. If a customer ceases",
            "to hold a prominent public function, institutions may reduce the",
            "intensity of monitoring but must consider residual risk for at",
            "least 18 months post-departure from the function.",
            "",
            "Reference: MAS Notice 626, Paragraph 9 | FATF Recommendation 12",
        ],
    },
    "analyse": {
        "intent":    "insufficient_info",
        "steps":     [],
        "reasoning": "Document analysis requested but no documents have been attached.",
        "lines": [
            "I'm ready to analyse your documents — I just don't see any attached yet.",
            "",
            "You can attach documents in two ways:",
            "",
            "  📎  Click the paperclip icon in the input box to browse and",
            "      select files from your device.",
            "",
            "  🖱️   Drag and drop files directly onto the input box.",
            "",
            "Supported formats: PDF, JPG, PNG (up to 5 files per message).",
            "",
            "Once attached, I can identify document types, extract fields",
            "(name, date of birth, nationality, document number, expiry),",
            "flag any visual anomalies, and summarise the content.",
        ],
    },
}


def _pick_mock_response(query: str) -> dict:
    """Select the appropriate mock response based on query content."""
    q = query.lower()
    if "cdd" in q or "notice 626" in q or "customer due diligence" in q:
        return MOCK_RESPONSES["cdd"]
    if "kyc" in q or "onboard" in q or "full check" in q:
        return MOCK_RESPONSES["kyc"]
    if "pep" in q or "politically exposed" in q or "enhanced due diligence" in q:
        return MOCK_RESPONSES["pep"]
    if "analys" in q or "document" in q or "attach" in q:
        return MOCK_RESPONSES["analyse"]
    # Default fallback
    return MOCK_RESPONSES["cdd"]