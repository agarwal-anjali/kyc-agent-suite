"""
Document Intelligence Agent

Responsibilities:
- Accept a base64-encoded image or PDF
- Detect media type automatically from file header bytes
- Use Gemini vision to extract structured identity fields
- Detect document type and flag visual anomalies
- Return a DocumentIntelligenceOutput model
"""

import base64
import json
import re
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from core.config import settings
from core.models import (
    DocumentIntelligenceOutput,
    DocumentType,
    ExtractedDocumentFields,
)
from core.prompts import DOCUMENT_EXTRACTION_PROMPT

log = structlog.get_logger()


class DocumentIntelligenceAgent:
    """
    Processes identity document images and PDFs using Gemini vision.
    Automatically detects whether the input is a PDF or image and
    uses the appropriate Gemini content block format for each.
    """

    def __init__(self) -> None:
        self._llm = ChatGoogleGenerativeAI(
            model=settings.vision_model,
            google_api_key=settings.google_api_key,
            temperature=1.0,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def analyse(self, document_b64: str) -> DocumentIntelligenceOutput:
        """
        Analyse a single base64-encoded document.

        Args:
            document_b64: Base64-encoded string of a JPEG, PNG, or PDF file

        Returns:
            DocumentIntelligenceOutput with extracted fields and anomaly flags
        """
        log.info("document_intelligence_agent.started")

        try:
            media_type = self._detect_media_type(document_b64)
            log.info("document_intelligence_agent.media_type", media_type=media_type)

            if media_type == "application/pdf":
                content = [
                    {
                        "type": "media",
                        "mime_type": "application/pdf",
                        "data": document_b64,
                    },
                    {
                        "type": "text",
                        "text": DOCUMENT_EXTRACTION_PROMPT,
                    },
                ]
            else:
                content = [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{document_b64}"},
                    },
                    {
                        "type": "text",
                        "text": DOCUMENT_EXTRACTION_PROMPT,
                    },
                ]

            message = HumanMessage(content=content)
            response = await self._llm.ainvoke([message])

            # response.content can be a list of content blocks in newer
            # langchain-google-genai versions — so extracting text explicitly
            raw_text = self._extract_text(response.content)

            parsed = self._parse_response(raw_text)
            output = self._build_output(parsed)

            log.info(
                "document_intelligence_agent.completed",
                document_type=output.document_type,
                confidence=output.confidence_score,
                anomaly_count=len(output.anomalies),
            )
            return output

        except Exception as e:
            log.error(
                "document_intelligence_agent.error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _detect_media_type(self, document_b64: str) -> str:
        """
        Detect file type from the first few decoded bytes.
        Avoids requiring the caller to specify the media type explicitly.

        Returns MIME type string: application/pdf, image/jpeg, or image/png
        """
        header = base64.b64decode(document_b64[:16])

        if header[:4] == b"%PDF":
            return "application/pdf"
        elif header[:2] == b"\xff\xd8":
            return "image/jpeg"
        elif header[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        else:
            log.warning(
                "document_intelligence_agent.unknown_media_type",
                defaulting_to="image/jpeg",
            )
            return "image/jpeg"

    def _extract_text(self, content) -> str:
        """
        Safely extract plain text from a Gemini response.

        Newer versions of langchain-google-genai return response.content
        as either a plain string or a list of typed content blocks.
        This method handles both cases uniformly.
        """
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts)

        log.warning(
            "document_intelligence_agent.unexpected_response_type",
            content_type=type(content).__name__,
        )
        return str(content)

    def _parse_response(self, raw_text: str) -> dict:
        """Strip markdown fences and parse JSON from the LLM response."""
        clean = re.sub(r"```json|```", "", raw_text).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            log.error(
                "document_intelligence_agent.parse_error",
                error=str(e),
                raw=raw_text[:200],
            )
            raise ValueError(
                f"Failed to parse document intelligence response: {e}"
            ) from e

    def _build_output(self, parsed: dict) -> DocumentIntelligenceOutput:
        """Map the parsed dict onto the typed Pydantic output model."""
        fields = parsed.get("extracted_fields", {})
        return DocumentIntelligenceOutput(
            document_type=DocumentType(parsed.get("document_type", "unknown")),
            extracted_fields=ExtractedDocumentFields(
                full_name=fields.get("full_name"),
                date_of_birth=fields.get("date_of_birth"),
                nationality=fields.get("nationality"),
                document_number=fields.get("document_number"),
                expiry_date=fields.get("expiry_date"),
                address=fields.get("address"),
                issuing_country=fields.get("issuing_country"),
            ),
            anomalies=parsed.get("anomalies", []),
            confidence_score=float(parsed.get("confidence_score", 0.0)),
            raw_caption=parsed.get("raw_caption", ""),
        )

    async def analyse_multiple(
        self, documents_b64: list[str]
    ) -> list[DocumentIntelligenceOutput]:
        """Analyse multiple documents sequentially."""
        results = []
        for i, doc in enumerate(documents_b64):
            log.info(
                "document_intelligence_agent.processing",
                index=i,
                total=len(documents_b64),
            )
            result = await self.analyse(doc)
            results.append(result)
        return results