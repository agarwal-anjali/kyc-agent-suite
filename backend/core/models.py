"""
Pydantic schemas for all inter-agent data contracts.
Every agent reads and writes these models — never raw dicts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime


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
    document_type:   DocumentType
    extracted_fields: ExtractedDocumentFields
    anomalies:       list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    raw_caption:     str


# ── Regulatory Retrieval ───────────────────────────────────────────────────────

class RegulatoryPassage(BaseModel):
    source:          str
    clause:          str
    content:         str
    relevance_score: float


class RegulatoryRetrievalOutput(BaseModel):
    passages:              list[RegulatoryPassage]
    due_diligence_type:    DDType
    pep_flag:              bool
    high_risk_jurisdiction: bool
    applicable_frameworks: list[str]


# ── Risk Scoring ───────────────────────────────────────────────────────────────

class RiskScoreBreakdown(BaseModel):
    identity_confidence:  float = Field(ge=0.0, le=1.0)
    document_validity:    float = Field(ge=0.0, le=1.0)
    jurisdictional_risk:  str
    pep_screening:        str
    overall_risk_tier:    RiskTier
    recommendation:       str


# ── Multi-document submission ──────────────────────────────────────────────────

class DocumentSubmission(BaseModel):
    """
    A single document within a multi-document KYC submission.
    Wraps the base64 content with an optional human-readable label
    so the caller can hint at document type (e.g. "passport", "utility_bill").
    The label is advisory — the Document Intelligence Agent will independently
    detect the actual document type from the content.
    """
    content_b64: str = Field(
        ...,
        description="Base64-encoded document content (PDF, JPEG, or PNG)"
    )
    label: str | None = Field(
        default=None,
        description="Optional hint about document type e.g. 'passport', 'utility_bill'"
    )


# ── Orchestrator State (LangGraph) ─────────────────────────────────────────────

class KYCState(BaseModel):
    """
    Shared state passed between all nodes in the LangGraph graph.
    Each agent reads what it needs and writes its output back here.
    """
    customer_id:    str
    query:          str

    # Supports multiple documents — replaces the old flat documents_b64 list
    # Each DocumentSubmission carries its content and an optional label
    documents:      list[DocumentSubmission] = Field(default_factory=list)

    # Kept for backwards compatibility with test fixtures and curl examples
    # If populated, these are wrapped into DocumentSubmission objects at API layer
    documents_b64:  list[str] = Field(default_factory=list)

    # Agent outputs — populated as the graph executes
    document_intelligence: DocumentIntelligenceOutput | None = None
    regulatory_retrieval:  RegulatoryRetrievalOutput  | None = None
    risk_scoring:          RiskScoreBreakdown          | None = None

    # Per-document raw outputs before merging — useful for the report
    # and for surfacing individual document findings in the UI
    individual_document_outputs: list[DocumentIntelligenceOutput] = Field(
        default_factory=list
    )

    # Final outputs
    verdict:      KYCVerdict | None = None
    report:       str | None = None
    error:        str | None = None
    completed_at: datetime | None = None

    def get_documents_b64(self) -> list[str]:
        """
        Return base64 strings regardless of which input format was used.
        Centralises the documents_b64 vs documents duality in one place.
        """
        if self.documents:
            return [d.content_b64 for d in self.documents]
        return self.documents_b64


# ── API Schemas ────────────────────────────────────────────────────────────────

class KYCRequest(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    query: str = Field(
        default="Perform a full KYC check on this customer.",
        description="Natural language instruction for the KYC analysis"
    )
    documents: list[DocumentSubmission] = Field(
        default_factory=list,
        description="List of documents with optional labels"
    )
    # Flat base64 list kept for backwards compatibility with existing curl examples
    documents_b64: list[str] = Field(
        default_factory=list,
        description="Flat list of base64-encoded documents (legacy format)"
    )

    def to_kyc_state(self) -> "KYCState":
        """
        Convert the API request into a KYCState.

        Handles both input formats:
        - New format: documents=[DocumentSubmission(...), ...]
        - Legacy format: documents_b64=["base64...", ...]

        If both are provided, the structured documents list takes precedence.
        """
        if self.documents:
            # New structured format — use as-is
            return KYCState(
                customer_id=self.customer_id,
                query=self.query,
                documents=self.documents,
            )
        elif self.documents_b64:
            # Legacy flat format — wrap each into a DocumentSubmission
            return KYCState(
                customer_id=self.customer_id,
                query=self.query,
                documents=[
                    DocumentSubmission(content_b64=b64)
                    for b64 in self.documents_b64
                ],
            )
        else:
            raise ValueError("Either 'documents' or 'documents_b64' must be provided.")


class KYCResponse(BaseModel):
    customer_id:  str
    verdict:      KYCVerdict
    risk_tier:    RiskTier
    report:       str
    document_count: int
    agents:       dict[str, Any]
    completed_at: datetime