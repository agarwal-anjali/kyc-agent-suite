"""
FastAPI application entry point.

Endpoints:
    POST /kyc/analyse        — Full pipeline, returns complete JSON response
    POST /kyc/analyse/stream — Full pipeline with SSE streaming for the frontend
    POST /kyc/analyse/mock   — Mock SSE endpoint for UI development (no LLM calls)
    GET  /health             — Health check
"""

import asyncio
import json
import traceback
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from core.models import KYCRequest, KYCResponse
from agents.orchestrator import OrchestratorAgent

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

    Accepts either:
    - documents: list of DocumentSubmission (new structured format)
    - documents_b64: list of base64 strings (legacy flat format)

    Returns a structured KYC verdict, risk breakdown, and narrative report.
    """
    log.info(
        "api.analyse.received",
        customer_id=request.customer_id,
        document_count=len(request.documents) or len(request.documents_b64),
    )

    try:
        state = request.to_kyc_state()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        state = await orchestrator.run(state)
    except Exception as e:
        log.error("api.analyse.exception", error=str(e), traceback=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

    if state.error:
        log.error("api.analyse.pipeline_error", error=state.error)
        raise HTTPException(status_code=500, detail=state.error)

    return KYCResponse(
        customer_id=state.customer_id,
        verdict=state.verdict,
        risk_tier=state.risk_scoring.overall_risk_tier,
        report=state.report,
        document_count=len(state.documents) or len(state.documents_b64),
        agents={
            "document_intelligence": state.document_intelligence.model_dump(),
            "regulatory_retrieval":  state.regulatory_retrieval.model_dump(),
            "risk_scoring":          state.risk_scoring.model_dump(),
        },
        completed_at=state.completed_at,
    )


@app.post("/kyc/analyse/stream")
async def analyse_stream(request: KYCRequest):
    """
    Run the KYC pipeline with SSE streaming.

    Streams status events, risk score, and report tokens in real time.

    Event types:
        status       — Pipeline progress messages
        risk_score   — JSON risk score (emitted after risk scoring completes)
        report_token — Individual tokens of the narrative report
        error        — Error message if the pipeline fails
    """
    log.info(
        "api.stream.received",
        customer_id=request.customer_id,
        document_count=len(request.documents) or len(request.documents_b64),
    )

    try:
        state = request.to_kyc_state()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    async def event_generator():
        async for event in orchestrator.run_streaming(state):
            yield {
                "event": event["event"],
                "data":  event["data"],
            }

    return EventSourceResponse(event_generator())


@app.post("/kyc/analyse/mock")
async def analyse_mock(request: KYCRequest):
    """
    Mock SSE endpoint for frontend development.
    Returns a realistic hardcoded response with simulated delays.
    No LLM calls are made — safe to call freely during UI development.
    """
    # Count documents regardless of which format was submitted
    doc_count = len(request.documents) or len(request.documents_b64)

    async def mock_stream():

        yield {"event": "status", "data": f"Analysing {doc_count} document{'s' if doc_count > 1 else ''} in parallel..."}
        await asyncio.sleep(2)
        yield {"event": "status", "data": "Document analysis complete."}

        await asyncio.sleep(1)
        yield {"event": "status", "data": "Retrieving applicable regulations..."}
        await asyncio.sleep(2)
        yield {"event": "status", "data": "Regulatory retrieval complete."}

        await asyncio.sleep(1)
        yield {"event": "status", "data": "Calculating risk score..."}
        await asyncio.sleep(1.5)

        mock_risk = {
            "identity_confidence": 0.91,
            "document_validity":   0.87,
            "jurisdictional_risk": "LOW",
            "pep_screening":       "CLEAR",
            "overall_risk_tier":   "LOW",
            "recommendation":      "Proceed with standard onboarding. Identity verified with high confidence.",
        }
        yield {"event": "risk_score", "data": json.dumps(mock_risk)}

        await asyncio.sleep(1)
        yield {"event": "status", "data": "Generating compliance report..."}
        await asyncio.sleep(0.5)

        mock_report_lines = [
            "KYC COMPLIANCE REPORT",
            f"Customer ID: {request.customer_id}",
            f"Documents submitted: {doc_count}",
            "Generated: 2026-03-20",
            "",
            "1. CUSTOMER IDENTITY SUMMARY",
            "The customer has been identified as a Canadian national based on the submitted passport document.",
            "Full name, date of birth, and document number have been successfully extracted with high confidence (91%).",
            "",
            "2. DOCUMENT VERIFICATION FINDINGS",
            f"All {doc_count} submitted document(s) were analysed in parallel.",
            "The submitted passport document appears genuine with no visual anomalies detected.",
            "The document is valid and not approaching expiry. Confidence score: 87%.",
            "",
            "3. APPLICABLE REGULATORY REQUIREMENTS",
            "Per MAS Notice 626, standard Customer Due Diligence (CDD) applies.",
            "No enhanced due diligence is required as the customer's nationality does not appear",
            "on the FATF grey or black list, and no PEP indicators were identified.",
            "",
            "4. RISK ASSESSMENT BREAKDOWN",
            "- Identity Confidence: 91% ✓",
            "- Document Validity: 87% ✓",
            "- Jurisdictional Risk: LOW ✓",
            "- PEP Screening: CLEAR ✓",
            "- Overall Risk Tier: LOW",
            "",
            "5. VERDICT AND RECOMMENDED NEXT STEPS",
            "PASS — Approve for standard onboarding.",
            "Proceed with account opening under standard CDD procedures.",
            "Retain document copies per MAS Notice 626 record-keeping requirements.",
            "Schedule periodic review in 12 months.",
        ]

        for line in mock_report_lines:
            yield {"event": "report_token", "data": line + "\n"}
            await asyncio.sleep(0.08)

        yield {"event": "status", "data": "Complete."}

    return EventSourceResponse(mock_stream())