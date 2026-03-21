"""
Orchestrator Agent

Responsibilities:
- Entry point for the entire KYC pipeline
- Manages execution order of sub-agents
- Handles errors and partial failures gracefully
- Delegates to LangGraph graph for stateful routing
"""

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from core.config import settings
from core.models import KYCState
from core.prompts import ORCHESTRATOR_PLAN_PROMPT
from agents.document_intelligence import DocumentIntelligenceAgent
from agents.regulatory_retrieval import RegulatoryRetrievalAgent
from agents.risk_scoring import RiskScoringAgent
from agents.report_summarisation import ReportSummarisationAgent

log = structlog.get_logger()


class OrchestratorAgent:
    """
    Coordinates the end-to-end KYC pipeline.
    
    Execution order:
    1. Document Intelligence (parallel across submitted documents)
    2. Regulatory Retrieval (uses doc output and original user query as context)
    3. Risk Scoring (synthesises steps 1 and 2 to access risk level)
    4. Report Summarisation (produces final output)
    """

    def __init__(self) -> None:
        self._doc_agent = DocumentIntelligenceAgent()
        self._reg_agent = RegulatoryRetrievalAgent()
        self._risk_agent = RiskScoringAgent()
        self._report_agent = ReportSummarisationAgent()
        self._llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=1.0,
            max_tokens=200,
        )

    async def run(self, state: KYCState) -> KYCState:
        """
        Execute the full KYC pipeline for a given state.

        Args:
            state: Initial KYCState with customer_id, query, and documents

        Returns:
            Completed KYCState with all agent outputs and final report
        """
        log.info("orchestrator.run_started", customer_id=state.customer_id)

        try:
            # Step 1: Document Intelligence
            # Only accepts one document as primary identity document
            log.info("orchestrator.invoking_document_intelligence")
            doc_outputs = await self._analyse_documents_parallel(state.get_documents_b64())
            state.document_intelligence = doc_outputs

            # Step 2: Regulatory Retrieval
            log.info("orchestrator.invoking_regulatory_retrieval")
            reg_output = await self._reg_agent.retrieve(doc_outputs, state.query)
            state.regulatory_retrieval = reg_output

            # Step 3: Risk Scoring
            log.info("orchestrator.invoking_risk_scoring")
            risk_output = await self._risk_agent.score(doc_outputs, reg_output)
            state.risk_scoring = risk_output

            # Step 4: Report Summarisation
            log.info("orchestrator.invoking_report_summarisation")
            state = await self._report_agent.summarise(state)

        except Exception as e:
            log.error("orchestrator.pipeline_error", error=str(e), customer_id=state.customer_id)
            state.error = str(e)

        log.info(
            "orchestrator.run_completed",
            customer_id=state.customer_id,
            verdict=state.verdict,
            error=state.error,
        )
        return state

    async def run_streaming(self, state: KYCState):
        """
        Execute the pipeline with streaming for the final report step.
        
        Yields status events and then streams the report tokens.
        Each yielded value is a dict suitable for SSE serialisation.
        """
        log.info("orchestrator.stream_started", customer_id=state.customer_id)

        try:
            yield {"event": "status", "data": "Running document analysis..."}
            doc_count = len(state.get_documents_b64())
            yield {
                "event": "status",
                "data": f"Analysing {doc_count} document{'s' if doc_count > 1 else ''} in parallel...",
            }
            doc_outputs = await self._analyse_documents_parallel(state.get_documents_b64())
            state.document_intelligence = doc_output
            yield {"event": "status", "data": "Document analysis complete."}

            yield {"event": "status", "data": "Retrieving applicable regulations..."}
            reg_output = await self._reg_agent.retrieve(doc_output, state.query)
            state.regulatory_retrieval = reg_output
            yield {"event": "status", "data": "Regulatory retrieval complete."}

            yield {"event": "status", "data": "Calculating risk score..."}
            risk_output = await self._risk_agent.score(doc_output, reg_output)
            state.risk_scoring = risk_output
            yield {
                "event": "risk_score",
                "data": risk_output.model_dump_json(),
            }

            yield {"event": "status", "data": "Generating compliance report..."}
            async for token in self._report_agent.stream(state):
                yield {"event": "report_token", "data": token}

            yield {"event": "status", "data": "Complete."}

        except Exception as e:
            log.error("orchestrator.stream_error", error=str(e))
            yield {"event": "error", "data": str(e)}