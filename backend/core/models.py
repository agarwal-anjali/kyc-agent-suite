"""
Pydantic schemas for all inter-agent data contracts.
"""

from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# ── Enums ─────────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    PASSPORT             = "passport"
    DRIVING_LICENCE      = "driving_licence"
    UTILITY_BILL         = "utility_bill"
    COMPANY_REGISTRATION = "company_registration"
    UNKNOWN              = "unknown"


class RiskTier(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class KYCVerdict(str, Enum):
    PASS  = "PASS"
    REFER = "REFER"
    FAIL  = "FAIL"


class DDType(str, Enum):
    STANDARD = "standard"
    ENHANCED = "enhanced"


class QueryIntent(str, Enum):
    GENERIC_COMPLIANCE = "generic_compliance"
    DOCUMENT_ANALYSIS  = "document_analysis"
    KYC_CHECK          = "kyc_check"
    HYBRID             = "hybrid"
    INSUFFICIENT_INFO  = "insufficient_info"  # orchestrator signals missing context


class AgentStep(str, Enum):
    DOCUMENT_INTELLIGENCE = "document_intelligence"
    REGULATORY_RETRIEVAL  = "regulatory_retrieval"
    RISK_SCORING          = "risk_scoring"
    REPORT_SUMMARISATION  = "report_summarisation"


# ── Customer Details ───────────────────────────────────────────────────────────

class CustomerDetails(BaseModel):
    """
    Optional structured customer context submitted via the UI form.
    All fields are optional — the user fills in what they know.
    The orchestrator uses whatever is provided to supplement document extraction.
    """
    customer_id:  str | None = None
    full_name:    str | None = None
    age:          int | None = None
    nationality:  str | None = None
    address:      str | None = None
    occupation:   str | None = None
    email:        str | None = None

    def is_empty(self) -> bool:
        """True if no fields beyond customer_id have been filled in."""
        return all(
            v is None for v in [
                self.full_name, self.age, self.nationality,
                self.address, self.occupation, self.email,
            ]
        )

    def to_context_string(self) -> str:
        """Serialise to a readable string for injection into prompts."""
        fields = {
            "Customer ID":  self.customer_id,
            "Full Name":    self.full_name,
            "Age":          self.age,
            "Nationality":  self.nationality,
            "Address":      self.address,
            "Occupation":   self.occupation,
            "Email":        self.email,
        }
        return "\n".join(
            f"  {k}: {v}"
            for k, v in fields.items()
            if v is not None
        )


# ── Document Intelligence ──────────────────────────────────────────────────────

class ExtractedDocumentFields(BaseModel):
    full_name:       str | None = None
    date_of_birth:   str | None = None
    nationality:     str | None = None
    document_number: str | None = None
    expiry_date:     str | None = None
    address:         str | None = None
    issuing_country: str | None = None


class DocumentIntelligenceOutput(BaseModel):
    document_type:    DocumentType
    extracted_fields: ExtractedDocumentFields
    anomalies:        list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    raw_caption:      str


# ── Regulatory Retrieval ───────────────────────────────────────────────────────

class RegulatoryPassage(BaseModel):
    source:          str
    clause:          str
    content:         str
    relevance_score: float


class RegulatoryRetrievalOutput(BaseModel):
    passages:               list[RegulatoryPassage]
    due_diligence_type:     DDType
    pep_flag:               bool
    high_risk_jurisdiction: bool
    applicable_frameworks:  list[str]


# ── Risk Scoring ───────────────────────────────────────────────────────────────

class RiskScoreBreakdown(BaseModel):
    identity_confidence: float = Field(ge=0.0, le=1.0)
    document_validity:   float = Field(ge=0.0, le=1.0)
    jurisdictional_risk: str
    pep_screening:       str
    overall_risk_tier:   RiskTier
    recommendation:      str


# ── Execution Plan ─────────────────────────────────────────────────────────────

class ExecutionPlan(BaseModel):
    intent:           QueryIntent
    steps:            list[AgentStep]
    reasoning:        str
    missing_info:     list[str] = Field(default_factory=list)
    # What the orchestrator found in session context that it's reusing
    reusing_from_session: list[str] = Field(default_factory=list)


# ── Chat / Session persistence ─────────────────────────────────────────────────

class ChatRole(str, Enum):
    USER      = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """A single message in a chat thread."""
    message_id:   str = Field(default_factory=lambda: uuid.uuid4().hex)
    role:         ChatRole
    content:      str
    timestamp:    datetime = Field(default_factory=datetime.utcnow)

    # Metadata attached to assistant messages
    intent:        QueryIntent | None = None
    execution_plan: ExecutionPlan | None = None
    risk_score:    RiskScoreBreakdown | None = None
    verdict:       KYCVerdict | None = None

    # Documents attached to this user message (base64 stored in session, not here)
    document_count: int = 0
    customer_details: CustomerDetails | None = None

    def infer_intent_from_content(self) -> QueryIntent | None:
        text = self.content.lower()

        if any(term in text for term in ["kyc", "onboard", "onboarding", "customer risk", "risk assessment"]):
            return QueryIntent.KYC_CHECK
        if any(term in text for term in ["document", "passport", "licence", "license", "pdf", "extract"]):
            return QueryIntent.DOCUMENT_ANALYSIS
        if any(term in text for term in ["mas notice", "cdd", "edd", "pep", "regulation", "policy", "fatf"]):
            return QueryIntent.GENERIC_COMPLIANCE
        return None


class SessionContext(BaseModel):
    """
    Accumulated context across all turns in a session.
    The orchestrator reads this to avoid asking for info already provided.

    Persistence strategy:
    - Stored in-memory on the server keyed by session_id
    - In future: serialise to Redis or a database
    - Frontend sends session_id on every request; server looks up context
    """
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Accumulated customer context across turns
    customer_details: CustomerDetails | None = None

    # Most recent document intelligence output — reused in follow-up questions
    # without requiring the user to re-upload documents
    last_document_intelligence: DocumentIntelligenceOutput | None = None
    last_regulatory_retrieval:  RegulatoryRetrievalOutput  | None = None
    last_risk_scoring:          RiskScoreBreakdown          | None = None
    last_verdict:               KYCVerdict | None = None

    # Full message history for this session
    messages: list[ChatMessage] = Field(default_factory=list)

    def get_recent_messages_summary(self, n: int = 5) -> str:
        """
        Produce a short text summary of the last N messages.
        Injected into planning prompts so the orchestrator has conversation context.
        """
        recent = self.messages[-n:] if len(self.messages) >= n else self.messages
        if not recent:
            return "No prior messages."
        lines = []
        for m in recent:
            prefix = "User" if m.role == ChatRole.USER else "Assistant"
            intent_tag = f" [{m.intent.value}]" if m.intent else ""
            lines.append(f"{prefix}{intent_tag}: {m.content[:150]}...")
        return "\n".join(lines)

    def get_last_user_message(self) -> ChatMessage | None:
        for message in reversed(self.messages):
            if message.role == ChatRole.USER:
                return message
        return None

    def get_last_assistant_message(self) -> ChatMessage | None:
        for message in reversed(self.messages):
            if message.role == ChatRole.ASSISTANT:
                return message
        return None

    def get_pending_follow_up_intent(self) -> QueryIntent | None:
        assistant = self.get_last_assistant_message()
        if not assistant or not assistant.execution_plan:
            return None

        if assistant.execution_plan.intent == QueryIntent.INSUFFICIENT_INFO:
            for message in reversed(self.messages):
                if message.role == ChatRole.USER:
                    inferred = message.infer_intent_from_content()
                    if inferred in {
                        QueryIntent.KYC_CHECK,
                        QueryIntent.HYBRID,
                        QueryIntent.DOCUMENT_ANALYSIS,
                    }:
                        return inferred
            return QueryIntent.KYC_CHECK

        return None

    def get_planning_context_summary(self) -> str:
        last_user = self.get_last_user_message()
        last_assistant = self.get_last_assistant_message()
        pending_intent = self.get_pending_follow_up_intent()

        lines = []
        if pending_intent:
            lines.append(f"Pending prior request awaiting more info: {pending_intent.value}")
        if last_user:
            lines.append(f"Last user message: {last_user.content[:180]}")
        if last_assistant and last_assistant.execution_plan:
            lines.append(
                "Last assistant execution: "
                f"{last_assistant.execution_plan.intent.value} "
                f"via {[step.value for step in last_assistant.execution_plan.steps]}"
            )
        if self.last_verdict:
            lines.append(f"Most recent KYC verdict in session: {self.last_verdict.value}")
        return "\n".join(lines) if lines else "No notable planning context."

    def has_customer_context(self) -> bool:
        return (
            self.customer_details is not None
            or self.last_document_intelligence is not None
        )


# ── Document submission ────────────────────────────────────────────────────────

class DocumentSubmission(BaseModel):
    content_b64: str
    label:       str | None = None


# ── Orchestrator turn state ────────────────────────────────────────────────────

class KYCState(BaseModel):
    """
    State for a single pipeline turn.
    Session context is loaded into this state at the start of each turn
    and written back to the session store after completion.
    """
    # Turn identity
    session_id:  str
    turn_id:     str = Field(default_factory=lambda: uuid.uuid4().hex)
    query:       str

    # Customer details from form (this turn) — merged with session context
    customer_details: CustomerDetails | None = None

    # Documents submitted this turn
    documents:     list[DocumentSubmission] = Field(default_factory=list)
    documents_b64: list[str] = Field(default_factory=list)

    # Session context carried in from prior turns
    session_context: SessionContext | None = None

    # Orchestrator planning output
    execution_plan: ExecutionPlan | None = None

    # Agent outputs for this turn
    document_intelligence: DocumentIntelligenceOutput | None = None
    regulatory_retrieval:  RegulatoryRetrievalOutput  | None = None
    risk_scoring:          RiskScoreBreakdown          | None = None
    individual_document_outputs: list[DocumentIntelligenceOutput] = Field(
        default_factory=list
    )

    # Final outputs
    verdict:      KYCVerdict | None = None
    report:       str | None = None
    error:        str | None = None
    completed_at: datetime | None = None

    def get_documents_b64(self) -> list[str]:
        if self.documents:
            return [d.content_b64 for d in self.documents]
        return self.documents_b64

    def has_documents(self) -> bool:
        return bool(self.documents or self.documents_b64)

    def get_effective_customer_details(self) -> CustomerDetails | None:
        """
        Return customer details for this turn, falling back to session context.
        This is how follow-up questions reuse previously submitted details.
        """
        if self.customer_details and not self.customer_details.is_empty():
            return self.customer_details
        if self.session_context and self.session_context.customer_details:
            return self.session_context.customer_details
        return None

    def get_effective_document_intelligence(self) -> DocumentIntelligenceOutput | None:
        """
        Return document intelligence for this turn or from session context.
        Allows follow-up questions to reference previously uploaded documents.
        """
        return (
            self.document_intelligence
            or (self.session_context.last_document_intelligence if self.session_context else None)
        )


# ── API Schemas ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    A single chat message sent by the user.
    This is the only API request shape — one unified interface.
    """
    session_id:       str | None = Field(
        default=None,
        description="Omit to start a new session. Provide to continue an existing one."
    )
    query:            str
    documents:        list[DocumentSubmission] = Field(default_factory=list)
    documents_b64:    list[str] = Field(default_factory=list)
    customer_details: CustomerDetails | None = None

    def to_kyc_state(self, session_context: SessionContext) -> KYCState:
        docs = self.documents
        if not docs and self.documents_b64:
            docs = [DocumentSubmission(content_b64=b64) for b64 in self.documents_b64]

        return KYCState(
            session_id=session_context.session_id,
            query=self.query,
            customer_details=self.customer_details,
            documents=docs,
            session_context=session_context,
        )


class ChatResponse(BaseModel):
    session_id:     str
    message_id:     str
    intent:         QueryIntent | None
    verdict:        KYCVerdict | None
    risk_tier:      RiskTier | None
    report:         str
    execution_plan: ExecutionPlan | None
    agents:         dict[str, Any]
    completed_at:   datetime


class NewSessionResponse(BaseModel):
    session_id: str
    created_at: datetime
