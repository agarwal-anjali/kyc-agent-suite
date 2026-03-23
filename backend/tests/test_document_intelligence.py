from __future__ import annotations

import base64

import pytest

from agents.document_intelligence import DocumentIntelligenceAgent
from core.models import DocumentType


@pytest.fixture
def agent():
    return DocumentIntelligenceAgent()


def test_detect_media_type_identifies_pdf(agent):
    encoded = base64.b64encode(b"%PDF-sample").decode()

    assert agent._detect_media_type(encoded) == "application/pdf"


def test_detect_media_type_identifies_jpeg(agent):
    encoded = base64.b64encode(b"\xff\xd8\xff\xe0rest").decode()

    assert agent._detect_media_type(encoded) == "image/jpeg"


def test_detect_media_type_identifies_png(agent):
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\nrest").decode()

    assert agent._detect_media_type(encoded) == "image/png"


def test_extract_text_supports_block_content(agent):
    content = [
        {"type": "text", "text": "Hello"},
        {"type": "image_url", "image_url": {"url": "ignored"}},
        " world",
    ]

    assert agent._extract_text(content) == "Hello\n world"


def test_build_output_maps_parsed_payload(agent):
    payload = {
        "document_type": "passport",
        "extracted_fields": {
            "full_name": "Jane Doe",
            "date_of_birth": "1990-01-01",
            "nationality": "SGP",
            "document_number": "E1234567",
            "expiry_date": "2030-01-01",
            "address": "123 Street",
            "issuing_country": "Singapore",
        },
        "anomalies": ["blurred text"],
        "confidence_score": 0.93,
        "raw_caption": "Singapore passport.",
    }

    output = agent._build_output(payload)

    assert output.document_type == DocumentType.PASSPORT
    assert output.extracted_fields.full_name == "Jane Doe"
    assert output.confidence_score == 0.93
    assert output.anomalies == ["blurred text"]

