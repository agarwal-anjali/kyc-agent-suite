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
    PASSPORT = "passport"
    DRIVING_LICENCE = "driving_licence"
    UTILITY_BILL = "utility_bill"
    COMPANY_REGISTRATION = "company_registration"
    UNKNOWN = "unknown"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class KYCVerdict(str, Enum):
    PASS = "PASS"
    REFER = "REFER"
    FAIL = "FAIL"


class DDType(str, Enum):
    STANDARD = "standard"
    ENHANCED = "enhanced"


# ── Document Intelligence ──────────────────────────────────────────────────────

class ExtractedDocumentFields(BaseModel):
    full_name: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    document_number: str | None = None
    expiry_date: str | None = None
    address: str | None = None
    issuing_country: str | None = None


class DocumentIntelligenceOutput(BaseModel):
    document_type: DocumentType
    extracted_fields: ExtractedDocumentFields
    anomalies: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    raw_caption: str


# ── Regulatory Retrieval ───────────────────────────────────────────────────────

class RegulatoryPassage(BaseModel):
    source: str
    clause: str
    content: str
    relevance_score: float


class RegulatoryRetrievalOutput(BaseModel):
    passages: list[RegulatoryPassage]
    due_diligence_type: DDType
    pep_flag: bool
    high_risk_jurisdiction: bool
    applicable_frameworks: list[str]


# ── Risk Scoring ───────────────────────────────────────────────────────────────

class RiskScoreBreakdown(BaseModel):
    identity_confidence: float = Field(ge=0.0, le=1.0)
    document_validity: float = Field(ge=0.0, le=1.0)
    jurisdictional_risk: str  # LOW / MEDIUM / HIGH
    pep_screening: str        # CLEAR / FLAGGED
    overall_risk_tier: RiskTier
    recommendation: str


# ── Orchestrator State (LangGraph) ─────────────────────────────────────────────

class KYCState(BaseModel):
    """
    Shared state passed between all nodes in the LangGraph graph.
    Each agent reads what it needs and writes its output back here.
    """
    customer_id: str
    query: str
    documents_b64: list[str] = Field(default_factory=list)

    # Agent outputs — populated as the graph executes
    document_intelligence: DocumentIntelligenceOutput | None = None
    regulatory_retrieval: RegulatoryRetrievalOutput | None = None
    risk_scoring: RiskScoreBreakdown | None = None

    # Final outputs
    verdict: KYCVerdict | None = None
    report: str | None = None
    error: str | None = None
    completed_at: datetime | None = None


# ── API Schemas ────────────────────────────────────────────────────────────────

class KYCRequest(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    query: str = Field(
        default="Perform a full KYC check on this customer.",
        description="Natural language instruction for the KYC analysis"
    )
    documents_b64: list[str] = Field(
        ...,
        description="List of base64-encoded document images or PDFs",
        min_length=1
    )


class KYCResponse(BaseModel):
    customer_id: str
    verdict: KYCVerdict
    risk_tier: RiskTier
    report: str
    agents: dict[str, Any]
    completed_at: datetime