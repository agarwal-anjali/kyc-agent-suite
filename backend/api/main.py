"""
FastAPI application entry point.

Endpoints:
    POST /kyc/analyse        — Full pipeline, returns complete JSON response
    POST /kyc/analyse/stream — Full pipeline with SSE streaming for the frontend
    GET  /health             — Health check
"""

import json
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from core.models import KYCRequest, KYCResponse, KYCState
from agents.orchestrator import OrchestratorAgent

import asyncio

log = structlog.get_logger()

app = FastAPI(
    title="KYC Document Intelligence Suite",
    description="Multi-agent system for KYC document analysis and risk scoring.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = OrchestratorAgent()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/kyc/analyse", response_model=KYCResponse)
async def analyse(request: KYCRequest):
    """
    Run the full KYC pipeline and return a complete structured report.

    Accepts a customer ID, query, and list of base64-encoded documents.
    Returns a structured KYC verdict, risk breakdown, and narrative report.
    """
    log.info("api.analyse.received", customer_id=request.customer_id)

    state = KYCState(
        customer_id=request.customer_id,
        query=request.query,
        documents_b64=request.documents_b64,
    )

    state = await orchestrator.run(state)

    if state.error:
        raise HTTPException(status_code=500, detail=state.error)

    return KYCResponse(
        customer_id=state.customer_id,
        verdict=state.verdict,
        risk_tier=state.risk_scoring.overall_risk_tier,
        report=state.report,
        agents={
            "document_intelligence": state.document_intelligence.model_dump(),
            "regulatory_retrieval": state.regulatory_retrieval.model_dump(),
            "risk_scoring": state.risk_scoring.model_dump(),
        },
        completed_at=state.completed_at,
    )


@app.post("/kyc/analyse/stream")
async def analyse_stream(request: KYCRequest):
    """
    Run the KYC pipeline with SSE streaming.
    
    Streams status events, risk score, and report tokens in real time.
    Designed for consumption by the React frontend.
    
    Event types:
        status       — Pipeline progress messages
        risk_score   — JSON risk score (emitted after risk scoring completes)
        report_token — Individual tokens of the narrative report
        error        — Error message if the pipeline fails
    """
    log.info("api.stream.received", customer_id=request.customer_id)

    state = KYCState(
        customer_id=request.customer_id,
        query=request.query,
        documents_b64=request.documents_b64,
    )

    async def event_generator():
        async for event in orchestrator.run_streaming(state):
            yield {
                "event": event["event"],
                "data": event["data"],
            }

    return EventSourceResponse(event_generator())