from __future__ import annotations

from core.graph import _fallback_plan, _merge_outputs, route_after_document_intelligence, route_after_regulatory_retrieval, route_from_plan
from core.models import (
    AgentStep,
    CustomerDetails,
    DocumentIntelligenceOutput,
    DocumentType,
    ExecutionPlan,
    ExtractedDocumentFields,
    KYCState,
    QueryIntent,
)


def _doc_output(
    *,
    document_type=DocumentType.PASSPORT,
    confidence=0.9,
    full_name=None,
    nationality=None,
    address=None,
    anomalies=None,
):
    return DocumentIntelligenceOutput(
        document_type=document_type,
        extracted_fields=ExtractedDocumentFields(
            full_name=full_name,
            nationality=nationality,
            address=address,
        ),
        anomalies=anomalies or [],
        confidence_score=confidence,
        raw_caption="caption",
    )


def test_merge_outputs_prefers_higher_confidence_and_fills_missing_fields():
    primary = _doc_output(confidence=0.95, full_name="Jane Doe", nationality="SGP")
    secondary = _doc_output(confidence=0.60, address="123 Street", anomalies=["glare"])

    merged = _merge_outputs([secondary, primary])

    assert merged.document_type == DocumentType.PASSPORT
    assert merged.extracted_fields.full_name == "Jane Doe"
    assert merged.extracted_fields.address == "123 Street"
    assert merged.confidence_score == 0.775
    assert merged.anomalies == ["[Doc 2 — passport] glare"]


def test_fallback_plan_returns_insufficient_info_for_kyc_without_context():
    state = KYCState(session_id="sess-1", query="Please run KYC for this customer")

    plan = _fallback_plan(state)

    assert plan.intent == QueryIntent.INSUFFICIENT_INFO
    assert plan.steps == []
    assert "Identity documents" in plan.missing_info


def test_fallback_plan_routes_documents_with_customer_context_to_kyc():
    state = KYCState(
        session_id="sess-1",
        query="Please verify this customer",
        documents_b64=["encoded-doc"],
        customer_details=CustomerDetails(full_name="Jane Doe"),
    )

    plan = _fallback_plan(state)

    assert plan.intent == QueryIntent.KYC_CHECK
    assert plan.steps == [
        AgentStep.DOCUMENT_INTELLIGENCE,
        AgentStep.REGULATORY_RETRIEVAL,
        AgentStep.RISK_SCORING,
        AgentStep.REPORT_SUMMARISATION,
    ]


def test_route_from_plan_uses_first_matching_step():
    state = KYCState(
        session_id="sess-1",
        query="question",
        execution_plan=ExecutionPlan(
            intent=QueryIntent.KYC_CHECK,
            steps=[
                AgentStep.DOCUMENT_INTELLIGENCE,
                AgentStep.REGULATORY_RETRIEVAL,
                AgentStep.RISK_SCORING,
                AgentStep.REPORT_SUMMARISATION,
            ],
            reasoning="run full pipeline",
        ),
    )

    assert route_from_plan(state) == "document_intelligence"


def test_route_after_document_intelligence_can_skip_to_report():
    state = KYCState(
        session_id="sess-1",
        query="analyse this document",
        execution_plan=ExecutionPlan(
            intent=QueryIntent.DOCUMENT_ANALYSIS,
            steps=[AgentStep.DOCUMENT_INTELLIGENCE, AgentStep.REPORT_SUMMARISATION],
            reasoning="document analysis only",
        ),
    )

    assert route_after_document_intelligence(state) == "report_summarisation"


def test_route_after_regulatory_retrieval_moves_to_risk_when_required():
    state = KYCState(
        session_id="sess-1",
        query="run kyc",
        execution_plan=ExecutionPlan(
            intent=QueryIntent.KYC_CHECK,
            steps=[
                AgentStep.DOCUMENT_INTELLIGENCE,
                AgentStep.REGULATORY_RETRIEVAL,
                AgentStep.RISK_SCORING,
                AgentStep.REPORT_SUMMARISATION,
            ],
            reasoning="full path",
        ),
    )

    assert route_after_regulatory_retrieval(state) == "risk_scoring"

