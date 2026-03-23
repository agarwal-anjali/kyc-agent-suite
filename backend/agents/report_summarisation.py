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
from core.prompts import (
    CUSTOMER_CONTEXT_BLOCK,
    DOCUMENT_CONTEXT_BLOCK,
    REGULATORY_CONTEXT_BLOCK,
    RISK_CONTEXT_BLOCK,
    HISTORY_CONTEXT_BLOCK,
)

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
            max_tokens=2200,
            streaming=True,
        )

    def _build_prompt(self, state: KYCState, verdict: KYCVerdict) -> str:
        effective_customer = state.get_effective_customer_details()
        now = datetime.now(timezone.utc)
        report_generation_date = f"{now.strftime('%B')} {now.day}, {now.year}"

        customer_context = (
            CUSTOMER_CONTEXT_BLOCK.format(customer_details=effective_customer.to_context_string())
            if effective_customer and not effective_customer.is_empty()
            else "Customer Details:\nNone provided."
        )

        conditional_sections = []
        if state.document_intelligence:
            conditional_sections.append(
                DOCUMENT_CONTEXT_BLOCK.format(
                    document_intelligence=state.document_intelligence.model_dump_json(indent=2),
                )
            )
        if state.regulatory_retrieval:
            conditional_sections.append(
                REGULATORY_CONTEXT_BLOCK.format(
                    regulatory_retrieval=state.regulatory_retrieval.model_dump_json(indent=2),
                )
            )
        if state.risk_scoring:
            conditional_sections.append(
                RISK_CONTEXT_BLOCK.format(
                    risk_scoring=state.risk_scoring.model_dump_json(indent=2),
                    verdict=verdict.value,
                )
            )

        history_summary = (
            state.session_context.get_recent_messages_summary()
            if state.session_context else "No prior messages."
        )

        return REPORT_SUMMARISATION_PROMPT.format(
            intent=state.execution_plan.intent.value if state.execution_plan else "generic_compliance",
            query=state.query,
            report_generation_date=report_generation_date,
            customer_context=customer_context,
            conditional_context="\n\n".join(conditional_sections) if conditional_sections else "No additional analytical context available.",
            history_context=HISTORY_CONTEXT_BLOCK.format(history_summary=history_summary),
        )

    def _finalise_report(self, report_text: str) -> str:
        """
        Trim obviously incomplete trailing fragments so the final UI state does not
        end mid-sentence when generation hits a token boundary.
        """
        text = (report_text or "").strip()
        if not text:
            return ""

        if text.endswith((".", "!", "?", "`")):
            return text

        lines = text.splitlines()
        while lines:
            candidate = lines[-1].strip()
            if not candidate:
                lines.pop()
                continue

            # Keep complete headings and list items; trim incomplete prose tails.
            if candidate.startswith(("#", "##", "###", "-", "*")):
                break
            if candidate.endswith((".", "!", "?", ":", "`")):
                break
            lines.pop()

        final_text = "\n".join(lines).strip()
        return final_text or text

    async def summarise(self, state: KYCState) -> KYCState:
        """
        Generate the KYC report and attach verdict and timestamp to state.
        """
        customer_id = (
            state.get_effective_customer_details().customer_id
            if state.get_effective_customer_details()
            and state.get_effective_customer_details().customer_id
            else f"SESSION-{state.session_id[:8].upper()}"
        )
        log.info("report_summarisation_agent.started", customer_id=customer_id)

        verdict = (
            VERDICT_MAP.get(state.risk_scoring.overall_risk_tier, KYCVerdict.REFER)
            if state.risk_scoring
            else (state.verdict or KYCVerdict.REFER)
        )

        prompt = self._build_prompt(state, verdict)

        response = await self._llm.ainvoke([HumanMessage(content=prompt)])

        # Extract plain text — Gemini can return list of content blocks
        report_text = self._finalise_report(self._extract_text(response.content))

        state.report = report_text
        state.verdict = verdict
        state.completed_at = datetime.now(timezone.utc)

        log.info(
            "report_summarisation_agent.completed",
            customer_id=customer_id,
            verdict=verdict,
        )
        return state

    async def stream(self, state: KYCState):
        """
        Stream the report token by token for SSE endpoint.
        """
        verdict = (
            VERDICT_MAP.get(state.risk_scoring.overall_risk_tier, KYCVerdict.REFER)
            if state.risk_scoring
            else (state.verdict or KYCVerdict.REFER)
        )

        prompt = self._build_prompt(state, verdict)

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
