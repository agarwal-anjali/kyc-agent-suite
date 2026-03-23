from __future__ import annotations

from core.models import (
    AgentStep,
    ChatMessage,
    ChatRole,
    CustomerDetails,
    DocumentIntelligenceOutput,
    DocumentType,
    ExecutionPlan,
    ExtractedDocumentFields,
    KYCState,
    QueryIntent,
    SessionContext,
)


def test_customer_details_is_empty_and_context_string():
    details = CustomerDetails(customer_id="CUST-1")

    assert details.is_empty() is True

    filled = CustomerDetails(full_name="Jane Doe", nationality="SGP", occupation="Analyst")

    assert filled.is_empty() is False
    assert "Full Name: Jane Doe" in filled.to_context_string()
    assert "Nationality: SGP" in filled.to_context_string()


def test_session_context_detects_pending_follow_up_intent():
    ctx = SessionContext(
        messages=[
            ChatMessage(role=ChatRole.USER, content="Run KYC on this customer"),
            ChatMessage(
                role=ChatRole.ASSISTANT,
                content="I need more information.",
                execution_plan=ExecutionPlan(
                    intent=QueryIntent.INSUFFICIENT_INFO,
                    steps=[],
                    reasoning="need more input",
                ),
            ),
        ]
    )

    assert ctx.get_pending_follow_up_intent() == QueryIntent.KYC_CHECK


def test_kyc_state_uses_session_context_as_fallback():
    session_doc = DocumentIntelligenceOutput(
        document_type=DocumentType.PASSPORT,
        extracted_fields=ExtractedDocumentFields(full_name="Jane Doe"),
        anomalies=[],
        confidence_score=0.9,
        raw_caption="passport",
    )
    session_ctx = SessionContext(
        customer_details=CustomerDetails(full_name="Stored User"),
        last_document_intelligence=session_doc,
    )
    state = KYCState(
        session_id="sess-1",
        query="follow up",
        session_context=session_ctx,
    )

    assert state.get_effective_customer_details().full_name == "Stored User"
    assert state.get_effective_document_intelligence().document_type == DocumentType.PASSPORT


def test_chat_message_infers_basic_intent():
    message = ChatMessage(role=ChatRole.USER, content="What does MAS Notice 626 say about PEPs?")

    assert message.infer_intent_from_content() == QueryIntent.GENERIC_COMPLIANCE

