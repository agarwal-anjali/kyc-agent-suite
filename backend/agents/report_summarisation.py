"""
Report Summarisation Agent

Responsibilities:
- Consume all prior agent outputs
- Produce a structured, human-readable KYC compliance report
- Support both full response and async streaming modes
"""

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from datetime import datetime, timezone

from core.config import settings
from core.models import (
    KYCState,
    KYCVerdict,
    RiskTier,
)
from core.prompts import REPORT_SUMMARISATION_PROMPT

log = structlog.get_logger()

VERDICT_MAP = {
    RiskTier.LOW: KYCVerdict.PASS,
    RiskTier.MEDIUM: KYCVerdict.REFER,
    RiskTier.HIGH: KYCVerdict.FAIL,
}


class ReportSummarisationAgent:
    """
    Produces the final KYC compliance report by synthesising all agent outputs.
    Supports both full-response and streaming modes for the FastAPI SSE endpoint.
    """

    def __init__(self) -> None:
        self._llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=1.0,
            max_tokens=1500,
            streaming=True,
        )

    async def summarise(self, state: KYCState) -> KYCState:
        """
        Generate the KYC report and attach verdict and timestamp to state.
        """
        log.info("report_summarisation_agent.started", customer_id=state.customer_id)

        verdict = VERDICT_MAP.get(
            state.risk_scoring.overall_risk_tier, KYCVerdict.REFER
        )

        prompt = REPORT_SUMMARISATION_PROMPT.format(
            customer_id=state.customer_id,
            query=state.query,
            document_intelligence=state.document_intelligence.model_dump_json(indent=2),
            regulatory_retrieval=state.regulatory_retrieval.model_dump_json(indent=2),
            risk_scoring=state.risk_scoring.model_dump_json(indent=2),
            verdict=verdict.value,
        )

        response = await self._llm.ainvoke([HumanMessage(content=prompt)])

        # Extract plain text — Gemini can return list of content blocks
        report_text = self._extract_text(response.content)

        state.report = report_text
        state.verdict = verdict
        state.completed_at = datetime.now(timezone.utc)

        log.info(
            "report_summarisation_agent.completed",
            customer_id=state.customer_id,
            verdict=verdict,
        )
        return state

    async def stream(self, state: KYCState):
        """
        Stream the report token by token for SSE endpoint.
        """
        verdict = VERDICT_MAP.get(
            state.risk_scoring.overall_risk_tier, KYCVerdict.REFER
        )

        prompt = REPORT_SUMMARISATION_PROMPT.format(
            customer_id=state.customer_id,
            query=state.query,
            document_intelligence=state.document_intelligence.model_dump_json(indent=2),
            regulatory_retrieval=state.regulatory_retrieval.model_dump_json(indent=2),
            risk_scoring=state.risk_scoring.model_dump_json(indent=2),
            verdict=verdict.value,
        )

        async for chunk in self._llm.astream([HumanMessage(content=prompt)]):
            token = self._extract_text(chunk.content)
            if token:
                yield token

    def _extract_text(self, content) -> str:
        """
        Safely extract plain text from a Gemini response.
        Handles both plain string and list of typed content blocks.
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
            "report_summarisation_agent.unexpected_response_type",
            content_type=type(content).__name__,
        )
        return str(content)