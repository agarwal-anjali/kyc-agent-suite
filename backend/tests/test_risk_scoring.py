from __future__ import annotations

from datetime import date, timedelta

from agents.risk_scoring import RiskScoringAgent
from core.models import DocumentIntelligenceOutput, DocumentType, ExtractedDocumentFields


def _doc_output(*, expiry_date=None, anomalies=None):
    return DocumentIntelligenceOutput(
        document_type=DocumentType.PASSPORT,
        extracted_fields=ExtractedDocumentFields(expiry_date=expiry_date),
        anomalies=anomalies or [],
        confidence_score=0.9,
        raw_caption="passport",
    )


def test_check_expiry_returns_high_penalty_for_expired_document():
    agent = RiskScoringAgent()
    expired = (date.today() - timedelta(days=1)).isoformat()

    assert agent._check_expiry(_doc_output(expiry_date=expired)) == 0.5


def test_check_expiry_returns_medium_penalty_for_soon_expiring_document():
    agent = RiskScoringAgent()
    soon = (date.today() + timedelta(days=30)).isoformat()

    assert agent._check_expiry(_doc_output(expiry_date=soon)) == 0.3


def test_check_expiry_returns_small_penalty_when_expiry_missing():
    agent = RiskScoringAgent()

    assert agent._check_expiry(_doc_output()) == 0.1


def test_anomaly_penalty_is_capped():
    agent = RiskScoringAgent()

    assert agent._calculate_anomaly_penalty(_doc_output(anomalies=["a", "b", "c", "d", "e"])) == 0.4
