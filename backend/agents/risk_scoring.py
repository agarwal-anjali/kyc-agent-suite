"""
Risk Scoring Agent

Responsibilities:
- Synthesise document intelligence and regulatory retrieval outputs
- Apply deterministic rules for objective dimensions (jurisdiction, document expiry)
- Use LLM to synthesise nuanced signals into a cohesive risk score
- Return a structured RiskScoreBreakdown
"""

import json
import re
from datetime import date
import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from core.config import settings
from core.models import (
    DocumentIntelligenceOutput,
    RegulatoryRetrievalOutput,
    RiskScoreBreakdown,
    RiskTier,
)
from core.prompts import RISK_SCORING_PROMPT

log = structlog.get_logger()


class RiskScoringAgent:
    """
    Hybrid risk scoring: deterministic rules handle objective facts,
    the LLM synthesises contextual and nuanced signals.

    This design is intentional — pure LLM scoring is non-deterministic and
    hard to audit. Rule-based components ensure reproducibility for regulated
    environments.
    """

    def __init__(self) -> None:
        self._llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=1.0,
            max_tokens=2048,
        )

    async def score(
        self,
        doc_output: DocumentIntelligenceOutput,
        reg_output: RegulatoryRetrievalOutput,
        customer_details=None,
    ) -> RiskScoreBreakdown:
        """
        Produce a multi-dimensional risk score for the customer.

        Args:
            doc_output: Output from the Document Intelligence Agent
            reg_output: Output from the Regulatory Retrieval Agent

        Returns:
            RiskScoreBreakdown with scores, flags, tier, and recommendation
        """
        log.info("risk_scoring_agent.started")

        expiry_penalty = self._check_expiry(doc_output)
        anomaly_penalty = self._calculate_anomaly_penalty(doc_output)

        prompt = RISK_SCORING_PROMPT.format(
            document_intelligence=doc_output.model_dump_json(indent=2),
            customer_details=(
                customer_details.to_context_string()
                if customer_details and not customer_details.is_empty()
                else "None provided."
            ),
            regulatory_retrieval=reg_output.model_dump_json(indent=2),
        )

        response = await self._llm.ainvoke([HumanMessage(content=prompt)])

        # Extract text safely — Gemini can return list or string
        raw_text = self._extract_text(response.content)
        log.info("risk_scoring_agent.raw_response", raw=raw_text)

        parsed = self._parse_response(raw_text)

        # Apply deterministic adjustments on top of LLM scores
        parsed["document_validity"] = max(
            0.0,
            float(parsed.get("document_validity", 0.8)) - expiry_penalty - anomaly_penalty,
        )

        # Force at least MEDIUM if jurisdiction or PEP flags are set
        if reg_output.high_risk_jurisdiction or reg_output.pep_flag:
            if parsed.get("overall_risk_tier") == "LOW":
                parsed["overall_risk_tier"] = "MEDIUM"
                log.info("risk_scoring_agent.tier_overridden", reason="high_risk_flag")

        output = RiskScoreBreakdown(
            identity_confidence=float(parsed["identity_confidence"]),
            document_validity=float(parsed["document_validity"]),
            jurisdictional_risk=parsed["jurisdictional_risk"],
            pep_screening=parsed["pep_screening"],
            overall_risk_tier=RiskTier(parsed["overall_risk_tier"]),
            recommendation=parsed["recommendation"],
        )

        log.info(
            "risk_scoring_agent.completed",
            risk_tier=output.overall_risk_tier,
            recommendation=output.recommendation,
        )
        return output

    def _extract_text(self, content) -> str:
        """
        Safely extract plain text from a Gemini response.
        Handles both plain string and list of content blocks.
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
            "risk_scoring_agent.unexpected_response_type",
            content_type=type(content).__name__,
        )
        return str(content)

    def _parse_response(self, raw_text: str) -> dict:
        """
        Extract and parse JSON from LLM response.

        Handles multiple Gemini response formats:
        - Clean JSON
        - JSON wrapped in ```json ... ``` fences
        - JSON embedded within surrounding explanation text
        """
        # First try: strip markdown fences and parse directly
        clean = re.sub(r"```json|```", "", raw_text).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Second try: find the JSON object anywhere in the response
        # Gemini sometimes adds explanation text before or after the JSON
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Log the full raw response so we can see exactly what Gemini returned
        log.error(
            "risk_scoring_agent.parse_error",
            raw_full=raw_text,
        )
        raise ValueError(
            f"Failed to parse risk scoring response. "
            f"Raw response was: {raw_text}"
        )

    def _check_expiry(self, doc_output: DocumentIntelligenceOutput) -> float:
        """
        Returns a validity penalty if the document is expired or expiring soon.
        0.0 = valid, 0.3 = expiring within 3 months, 0.5 = already expired
        """
        expiry_str = doc_output.extracted_fields.expiry_date
        if not expiry_str:
            return 0.1

        try:
            expiry = date.fromisoformat(expiry_str)
            today = date.today()
            days_remaining = (expiry - today).days
            if days_remaining < 0:
                log.warning("risk_scoring_agent.document_expired", expiry=expiry_str)
                return 0.5
            elif days_remaining < 90:
                return 0.3
        except ValueError:
            return 0.1

        return 0.0

    def _calculate_anomaly_penalty(self, doc_output: DocumentIntelligenceOutput) -> float:
        """
        Returns a validity penalty proportional to anomalies detected.
        Each anomaly reduces validity by 0.1, capped at 0.4.
        """
        return min(len(doc_output.anomalies) * 0.1, 0.4)
