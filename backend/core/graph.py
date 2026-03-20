"""
LangGraph state graph definition for the KYC pipeline.

The graph encodes the agent execution order and conditional routing logic.
LangGraph manages state transitions, making the pipeline inspectable,
resumable, and easy to extend with branching logic.
"""

from langgraph.graph import StateGraph, END
from core.models import KYCState
from agents.document_intelligence import DocumentIntelligenceAgent
from agents.regulatory_retrieval import RegulatoryRetrievalAgent
from agents.risk_scoring import RiskScoringAgent
from agents.report_summarisation import ReportSummarisationAgent
import structlog

log = structlog.get_logger()

# Instantiate agents (shared across graph nodes)
_doc_agent = DocumentIntelligenceAgent()
_reg_agent = RegulatoryRetrievalAgent()
_risk_agent = RiskScoringAgent()
_report_agent = ReportSummarisationAgent()


async def node_document_intelligence(state: KYCState) -> KYCState:
    doc_output = await _doc_agent.analyse(state.documents_b64[0])
    state.document_intelligence = doc_output
    return state


async def node_regulatory_retrieval(state: KYCState) -> KYCState:
    reg_output = await _reg_agent.retrieve(state.document_intelligence, state.query)
    state.regulatory_retrieval = reg_output
    return state


async def node_risk_scoring(state: KYCState) -> KYCState:
    risk_output = await _risk_agent.score(
        state.document_intelligence, state.regulatory_retrieval
    )
    state.risk_scoring = risk_output
    return state


async def node_report_summarisation(state: KYCState) -> KYCState:
    state = await _report_agent.summarise(state)
    return state


def should_proceed_after_doc(state: KYCState) -> str:
    """
    Conditional edge: if document extraction failed with very low confidence,
    skip further processing and go directly to report summarisation to explain
    the failure. Otherwise proceed normally.
    """
    if state.document_intelligence and state.document_intelligence.confidence_score < 0.3:
        log.warning("graph.low_confidence_skip", score=state.document_intelligence.confidence_score)
        return "report"
    return "regulatory"


def build_kyc_graph() -> StateGraph:
    """
    Construct and compile the KYC LangGraph state graph.
    
    Graph structure:
        document_intelligence
             │
        (conditional)
             ├── low confidence ──► report_summarisation ──► END
             │
             └── normal ──► regulatory_retrieval ──► risk_scoring ──► report_summarisation ──► END
    """
    graph = StateGraph(KYCState)

    graph.add_node("document_intelligence", node_document_intelligence)
    graph.add_node("regulatory_retrieval", node_regulatory_retrieval)
    graph.add_node("risk_scoring", node_risk_scoring)
    graph.add_node("report", node_report_summarisation)

    graph.set_entry_point("document_intelligence")

    graph.add_conditional_edges(
        "document_intelligence",
        should_proceed_after_doc,
        {
            "regulatory": "regulatory_retrieval",
            "report": "report",
        },
    )

    graph.add_edge("regulatory_retrieval", "risk_scoring")
    graph.add_edge("risk_scoring", "report")
    graph.add_edge("report", END)

    return graph.compile()


kyc_graph = build_kyc_graph()