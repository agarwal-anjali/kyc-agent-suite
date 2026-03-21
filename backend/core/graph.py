"""
LangGraph state graph for the KYC pipeline.

Uses LangGraph's native capabilities:
- MemorySaver checkpointer for session persistence across turns
- Conditional edges driven by ExecutionPlan intent
- astream_events() for streaming (used by orchestrator)

Graph nodes:
  node_plan                  — Planning LLM: detects intent, builds ExecutionPlan
  node_document_intelligence — Parallel document analysis
  node_regulatory_retrieval  — Semantic search over regulatory corpus
  node_risk_scoring          — Hybrid rule+LLM risk scoring
  node_report_summarisation  — Final response generation

Execution paths (determined at runtime by node_plan):
  generic_compliance → regulatory_retrieval → report_summarisation
  document_analysis  → document_intelligence → report_summarisation
  kyc_check          → document_intelligence → regulatory_retrieval
                       → risk_scoring → report_summarisation
  hybrid             → document_intelligence → regulatory_retrieval
                       → report_summarisation
  insufficient_info  → report_summarisation (guidance message only)
"""

import asyncio
import json
import re
import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from datetime import datetime, timezone

from core.config import settings
from core.models import (
    KYCState,
    KYCVerdict,
    RiskTier,
    QueryIntent,
    AgentStep,
    ExecutionPlan,
    DocumentType,
    ExtractedDocumentFields,
    DocumentIntelligenceOutput,
    ChatMessage,
    ChatRole,
)
from core.prompts import (
    ORCHESTRATOR_PLAN_PROMPT,
    INSUFFICIENT_INFO_PROMPT,
)
from agents.document_intelligence import DocumentIntelligenceAgent
from agents.regulatory_retrieval import RegulatoryRetrievalAgent
from agents.risk_scoring import RiskScoringAgent
from agents.report_summarisation import ReportSummarisationAgent

log = structlog.get_logger()

VERDICT_MAP = {
    RiskTier.LOW:    KYCVerdict.PASS,
    RiskTier.MEDIUM: KYCVerdict.REFER,
    RiskTier.HIGH:   KYCVerdict.FAIL,
}

# ── Agent singletons ───────────────────────────────────────────────────────────
_doc_agent    = DocumentIntelligenceAgent()
_reg_agent    = RegulatoryRetrievalAgent()
_risk_agent   = RiskScoringAgent()
_report_agent = ReportSummarisationAgent()

_planner_llm = ChatGoogleGenerativeAI(
    model=settings.llm_model,
    google_api_key=settings.google_api_key,
    temperature=1.0,
    max_tokens=500,
)

# ── Helper ─────────────────────────────────────────────────────────────────────

def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b if isinstance(b, str)
            else b.get("text", "") if isinstance(b, dict)
            else ""
            for b in content
        )
    return str(content)


def _empty_doc_output() -> DocumentIntelligenceOutput:
    return DocumentIntelligenceOutput(
        document_type=DocumentType.UNKNOWN,
        extracted_fields=ExtractedDocumentFields(),
        anomalies=[],
        confidence_score=0.0,
        raw_caption="No identity document submitted.",
    )


def _query_mentions_kyc(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in [
        "kyc", "know your customer", "onboard", "onboarding",
        "risk assessment", "verify this customer",
    ])


def _query_is_policy_follow_up(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in [
        "mas notice", "cdd", "edd", "pep", "policy", "regulation",
        "what are", "what is", "which regulation", "requirements",
    ])


def _query_supplies_requested_info(state: KYCState) -> bool:
    return bool(
        state.has_documents()
        or (state.customer_details and not state.customer_details.is_empty())
    )


def _postprocess_plan(state: KYCState, plan: ExecutionPlan) -> ExecutionPlan:
    ctx = state.session_context
    if not ctx:
        return plan

    pending_intent = ctx.get_pending_follow_up_intent()
    query_lower = state.query.lower()

    if pending_intent and _query_supplies_requested_info(state) and not _query_is_policy_follow_up(query_lower):
        if plan.intent in {QueryIntent.DOCUMENT_ANALYSIS, QueryIntent.GENERIC_COMPLIANCE, QueryIntent.INSUFFICIENT_INFO}:
            if pending_intent == QueryIntent.KYC_CHECK:
                return ExecutionPlan(
                    intent=QueryIntent.KYC_CHECK,
                    steps=[
                        AgentStep.DOCUMENT_INTELLIGENCE,
                        AgentStep.REGULATORY_RETRIEVAL,
                        AgentStep.RISK_SCORING,
                        AgentStep.REPORT_SUMMARISATION,
                    ],
                    reasoning="Adjusted plan: user supplied the missing information needed to continue the earlier KYC request.",
                    reusing_from_session=["Prior turn requested additional information before running KYC."],
                )
            if pending_intent == QueryIntent.HYBRID:
                return ExecutionPlan(
                    intent=QueryIntent.HYBRID,
                    steps=[
                        AgentStep.DOCUMENT_INTELLIGENCE,
                        AgentStep.REGULATORY_RETRIEVAL,
                        AgentStep.REPORT_SUMMARISATION,
                    ],
                    reasoning="Adjusted plan: user supplied the missing information needed to continue the earlier analysis request.",
                    reusing_from_session=["Prior turn requested additional information before continuing analysis."],
                )

    if _query_is_policy_follow_up(query_lower) and not _query_mentions_kyc(query_lower):
        if plan.intent in {QueryIntent.KYC_CHECK, QueryIntent.DOCUMENT_ANALYSIS, QueryIntent.HYBRID}:
            return ExecutionPlan(
                intent=QueryIntent.GENERIC_COMPLIANCE,
                steps=[AgentStep.REGULATORY_RETRIEVAL, AgentStep.REPORT_SUMMARISATION],
                reasoning="Adjusted plan: current turn is a policy/compliance follow-up, so the system should answer the question rather than rerun KYC.",
                reusing_from_session=["Conversation history and any established customer context relevant to the question."],
            )

    return plan


# ── Node: Planning ─────────────────────────────────────────────────────────────

async def node_plan(state: KYCState) -> KYCState:
    """
    Planning node — always runs first.

    Uses the planning LLM to detect query intent and build an execution plan.
    The plan determines which subsequent nodes LangGraph will route to.

    Falls back to rule-based planning if the LLM call fails, ensuring
    the graph always has a valid plan to route on.
    """
    log.info("graph.plan.started", session_id=state.session_id)

    ctx = state.session_context

    # Build context strings for the planning prompt
    session_customer = "None"
    if ctx and ctx.customer_details and not ctx.customer_details.is_empty():
        session_customer = ctx.customer_details.to_context_string()

    session_doc = "None"
    if ctx and ctx.last_document_intelligence:
        d = ctx.last_document_intelligence
        session_doc = (
            f"{d.document_type.value} from prior turn "
            f"(confidence: {d.confidence_score})"
        )

    customer_this_turn = "None"
    if state.customer_details and not state.customer_details.is_empty():
        customer_this_turn = state.customer_details.to_context_string()

    doc_labels = [d.label for d in state.documents if d.label] if state.documents else []

    prompt = ORCHESTRATOR_PLAN_PROMPT.format(
        query=state.query,
        doc_count=len(state.get_documents_b64()),
        doc_labels=doc_labels or "none",
        customer_details=customer_this_turn,
        conversation_summary=ctx.get_recent_messages_summary() if ctx else "No prior messages.",
        planning_context=ctx.get_planning_context_summary() if ctx else "No notable planning context.",
        session_customer_context=session_customer,
        session_doc_context=session_doc,
    )

    try:
        response = await _planner_llm.ainvoke([HumanMessage(content=prompt)])
        raw      = _extract_text(response.content)
        clean    = re.sub(r"```json|```", "", raw).strip()
        parsed   = json.loads(clean)

        plan = ExecutionPlan(
            intent=QueryIntent(parsed["intent"]),
            steps=[AgentStep(s) for s in parsed.get("steps", [])],
            reasoning=parsed.get("reasoning", ""),
            missing_info=parsed.get("missing_info", []),
            reusing_from_session=parsed.get("reusing_from_session", []),
        )

    except Exception as e:
        log.warning("graph.plan.llm_failed_using_fallback", error=str(e))
        plan = _fallback_plan(state)

    state.execution_plan = _postprocess_plan(state, plan)
    log.info(
        "graph.plan.completed",
        intent=state.execution_plan.intent,
        steps=[s.value for s in state.execution_plan.steps],
        reasoning=state.execution_plan.reasoning,
    )
    return state


def _fallback_plan(state: KYCState) -> ExecutionPlan:
    """Rule-based fallback when the planning LLM fails."""
    query_lower = state.query.lower()
    pending_intent = (
        state.session_context.get_pending_follow_up_intent()
        if state.session_context else None
    )
    has_docs = (
        state.has_documents()
        or (state.session_context and state.session_context.last_document_intelligence)
    )
    has_customer = (
        (state.customer_details and not state.customer_details.is_empty())
        or (state.session_context and state.session_context.customer_details)
    )

    # If the prior assistant asked for missing info and the user is now supplying it,
    # continue the earlier task even if the current message is short or non-specific.
    if pending_intent and _query_supplies_requested_info(state) and not _query_is_policy_follow_up(query_lower):
        if pending_intent == QueryIntent.KYC_CHECK:
            return ExecutionPlan(
                intent=QueryIntent.KYC_CHECK,
                steps=[
                    AgentStep.DOCUMENT_INTELLIGENCE,
                    AgentStep.REGULATORY_RETRIEVAL,
                    AgentStep.RISK_SCORING,
                    AgentStep.REPORT_SUMMARISATION,
                ],
                reasoning="Fallback: user supplied missing information for the prior KYC request.",
                reusing_from_session=["Prior turn requested additional information before running KYC."],
            )
        if pending_intent == QueryIntent.HYBRID:
            return ExecutionPlan(
                intent=QueryIntent.HYBRID,
                steps=[
                    AgentStep.DOCUMENT_INTELLIGENCE,
                    AgentStep.REGULATORY_RETRIEVAL,
                    AgentStep.REPORT_SUMMARISATION,
                ],
                reasoning="Fallback: user supplied missing information for the prior hybrid request.",
                reusing_from_session=["Prior turn requested additional information before continuing analysis."],
            )

    # If the current turn is clearly a policy/compliance follow-up, don't rerun KYC
    # just because session context now contains documents and customer details.
    if _query_is_policy_follow_up(query_lower) and not _query_mentions_kyc(query_lower):
        return ExecutionPlan(
            intent=QueryIntent.GENERIC_COMPLIANCE,
            steps=[AgentStep.REGULATORY_RETRIEVAL, AgentStep.REPORT_SUMMARISATION],
            reasoning="Fallback: current turn is a policy/compliance follow-up, so skipping full KYC re-execution.",
            reusing_from_session=["Conversation history and any previously established customer context."],
        )

    if _query_mentions_kyc(query_lower) and not has_docs and not has_customer:
        return ExecutionPlan(
            intent=QueryIntent.INSUFFICIENT_INFO,
            steps=[],
            reasoning="KYC requested but no documents or customer details found.",
            missing_info=["Identity documents", "Customer details"],
        )
    elif has_docs and (_query_mentions_kyc(query_lower) or has_customer):
        return ExecutionPlan(
            intent=QueryIntent.KYC_CHECK,
            steps=[
                AgentStep.DOCUMENT_INTELLIGENCE,
                AgentStep.REGULATORY_RETRIEVAL,
                AgentStep.RISK_SCORING,
                AgentStep.REPORT_SUMMARISATION,
            ],
            reasoning="Fallback: documents present with KYC intent.",
        )
    elif has_docs:
        return ExecutionPlan(
            intent=QueryIntent.DOCUMENT_ANALYSIS,
            steps=[AgentStep.DOCUMENT_INTELLIGENCE, AgentStep.REPORT_SUMMARISATION],
            reasoning="Fallback: documents present, no KYC intent.",
        )
    else:
        return ExecutionPlan(
            intent=QueryIntent.GENERIC_COMPLIANCE,
            steps=[AgentStep.REGULATORY_RETRIEVAL, AgentStep.REPORT_SUMMARISATION],
            reasoning="Fallback: no documents, treating as compliance question.",
        )


# ── Node: Document Intelligence ────────────────────────────────────────────────

async def node_document_intelligence(state: KYCState) -> KYCState:
    """
    Analyse all submitted documents in parallel.
    Reuses session context if no new documents submitted this turn.
    """
    log.info("graph.document_intelligence.started")

    docs_b64 = state.get_documents_b64()

    if not docs_b64:
        # Reuse from session if available — enables follow-up questions
        # without re-uploading documents
        if state.session_context and state.session_context.last_document_intelligence:
            state.document_intelligence = state.session_context.last_document_intelligence
            log.info("graph.document_intelligence.reusing_from_session")
        return state

    results = await asyncio.gather(
        *[_doc_agent.analyse(doc) for doc in docs_b64],
        return_exceptions=True,
    )

    outputs = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    for i, e in enumerate(failures):
        log.warning("graph.document_intelligence.doc_failed", index=i, error=str(e))

    if not outputs:
        raise ValueError("All document analyses failed.")

    state.individual_document_outputs = outputs
    state.document_intelligence = _merge_outputs(outputs)

    log.info(
        "graph.document_intelligence.completed",
        doc_count=len(outputs),
        merged_type=state.document_intelligence.document_type,
        confidence=state.document_intelligence.confidence_score,
    )
    return state


def _merge_outputs(outputs: list[DocumentIntelligenceOutput]) -> DocumentIntelligenceOutput:
    if len(outputs) == 1:
        return outputs[0]

    sorted_out = sorted(outputs, key=lambda o: o.confidence_score, reverse=True)
    primary    = sorted_out[0]

    field_names = [
        "full_name", "date_of_birth", "nationality",
        "document_number", "expiry_date", "address", "issuing_country",
    ]
    merged_fields = {
        f: next(
            (getattr(o.extracted_fields, f) for o in sorted_out
             if getattr(o.extracted_fields, f) is not None),
            None,
        )
        for f in field_names
    }

    anomalies = [
        f"[Doc {i+1} — {o.document_type.value}] {a}"
        for i, o in enumerate(sorted_out)
        for a in o.anomalies
    ]

    return DocumentIntelligenceOutput(
        document_type=primary.document_type,
        extracted_fields=ExtractedDocumentFields(**merged_fields),
        anomalies=anomalies,
        confidence_score=round(sum(o.confidence_score for o in outputs) / len(outputs), 3),
        raw_caption=" | ".join(
            f"Doc {i+1}: {o.raw_caption}" for i, o in enumerate(sorted_out)
        ),
    )


# ── Node: Regulatory Retrieval ─────────────────────────────────────────────────

async def node_regulatory_retrieval(state: KYCState) -> KYCState:
    """Retrieve relevant regulatory passages from the vector store."""
    log.info("graph.regulatory_retrieval.started")

    doc_ctx = (
        state.document_intelligence
        or (state.session_context.last_document_intelligence if state.session_context else None)
        or _empty_doc_output()
    )

    state.regulatory_retrieval = await _reg_agent.retrieve(doc_ctx, state.query)

    log.info(
        "graph.regulatory_retrieval.completed",
        passages=len(state.regulatory_retrieval.passages),
        dd_type=state.regulatory_retrieval.due_diligence_type,
    )
    return state


# ── Node: Risk Scoring ─────────────────────────────────────────────────────────

async def node_risk_scoring(state: KYCState) -> KYCState:
    """Score customer risk. Only reached for kyc_check intent."""
    log.info("graph.risk_scoring.started")

    doc_ctx = (
        state.document_intelligence
        or (state.session_context.last_document_intelligence if state.session_context else None)
    )

    if not doc_ctx or not state.regulatory_retrieval:
        raise ValueError(
            "Risk scoring requires both document intelligence and regulatory retrieval."
        )

    state.risk_scoring = await _risk_agent.score(
        doc_ctx,
        state.regulatory_retrieval,
        customer_details=state.get_effective_customer_details(),
    )
    state.verdict      = VERDICT_MAP.get(state.risk_scoring.overall_risk_tier, KYCVerdict.REFER)

    log.info(
        "graph.risk_scoring.completed",
        tier=state.risk_scoring.overall_risk_tier,
        verdict=state.verdict,
    )
    return state


# ── Node: Report Summarisation ─────────────────────────────────────────────────

async def node_report_summarisation(state: KYCState) -> KYCState:
    """
    Generate the final response.

    For insufficient_info intent, generates a helpful guidance message.
    For all other intents, delegates to ReportSummarisationAgent.
    """
    log.info("graph.report_summarisation.started")

    plan = state.execution_plan

    if plan and plan.intent == QueryIntent.INSUFFICIENT_INFO:
        prompt = INSUFFICIENT_INFO_PROMPT.format(
            query=state.query,
            missing_info=", ".join(plan.missing_info) if plan.missing_info
                         else "documents or customer details",
            has_prior_context=state.session_context.has_customer_context()
                              if state.session_context else False,
        )
        response = await _planner_llm.ainvoke([HumanMessage(content=prompt)])
        state.report       = _extract_text(response.content)
        state.completed_at = datetime.now(timezone.utc)
    else:
        state = await _report_agent.summarise(state)

    # Persist completed turn to session context
    state = _persist_turn_to_session(state)

    log.info("graph.report_summarisation.completed", verdict=state.verdict)
    return state


def _persist_turn_to_session(state: KYCState) -> KYCState:
    """
    Write turn outputs back to session context after completion.
    LangGraph checkpoints this updated state automatically.
    """
    ctx = state.session_context
    if not ctx:
        return state

    # Accumulate customer context
    if state.customer_details and not state.customer_details.is_empty():
        ctx.customer_details = state.customer_details
    elif ctx.customer_details is None and state.session_context:
        pass  # no update needed

    # Store agent outputs for reuse in follow-up questions
    if state.document_intelligence:
        ctx.last_document_intelligence = state.document_intelligence
    if state.regulatory_retrieval:
        ctx.last_regulatory_retrieval = state.regulatory_retrieval
    if state.risk_scoring:
        ctx.last_risk_scoring = state.risk_scoring
    if state.verdict:
        ctx.last_verdict = state.verdict

    # Append to message history
    ctx.messages.append(ChatMessage(
        role=ChatRole.USER,
        content=state.query,
        document_count=len(state.get_documents_b64()),
        customer_details=state.customer_details,
    ))

    if state.report:
        ctx.messages.append(ChatMessage(
            role=ChatRole.ASSISTANT,
            content=state.report,
            intent=state.execution_plan.intent if state.execution_plan else None,
            execution_plan=state.execution_plan,
            risk_score=state.risk_scoring,
            verdict=state.verdict,
        ))

    log.info(
        "graph.session_persisted",
        session_id=ctx.session_id,
        total_messages=len(ctx.messages),
    )
    return state


# ── Conditional routing ────────────────────────────────────────────────────────

def route_from_plan(state: KYCState) -> str:
    """
    Entry router — reads the ExecutionPlan and routes to the first step.
    Called by LangGraph's conditional entry point after node_plan completes.
    """
    plan = state.execution_plan
    if not plan or plan.intent == QueryIntent.INSUFFICIENT_INFO:
        return "report_summarisation"

    steps = [s.value for s in plan.steps]
    if AgentStep.DOCUMENT_INTELLIGENCE.value in steps:
        return "document_intelligence"
    if AgentStep.REGULATORY_RETRIEVAL.value in steps:
        return "regulatory_retrieval"
    return "report_summarisation"


def route_after_document_intelligence(state: KYCState) -> str:
    plan  = state.execution_plan
    steps = [s.value for s in plan.steps] if plan else []
    return (
        "regulatory_retrieval"
        if AgentStep.REGULATORY_RETRIEVAL.value in steps
        else "report_summarisation"
    )


def route_after_regulatory_retrieval(state: KYCState) -> str:
    plan  = state.execution_plan
    steps = [s.value for s in plan.steps] if plan else []
    return (
        "risk_scoring"
        if AgentStep.RISK_SCORING.value in steps
        else "report_summarisation"
    )


# ── Graph construction ─────────────────────────────────────────────────────────

def build_kyc_graph(checkpointer=None) -> StateGraph:
    """
    Build and compile the KYC LangGraph state graph.

    Args:
        checkpointer: LangGraph checkpointer instance.
                      Pass MemorySaver() for in-memory persistence.
                      Pass AsyncSqliteSaver for production persistence.
                      None disables persistence (useful for testing).

    Returns:
        Compiled StateGraph ready for ainvoke() and astream_events()
    """
    graph = StateGraph(KYCState)

    # ── Register all nodes ─────────────────────────────────────────────────
    graph.add_node("plan",                   node_plan)
    graph.add_node("document_intelligence",  node_document_intelligence)
    graph.add_node("regulatory_retrieval",   node_regulatory_retrieval)
    graph.add_node("risk_scoring",           node_risk_scoring)
    graph.add_node("report_summarisation",   node_report_summarisation)

    # ── Entry: always start with planning ──────────────────────────────────
    graph.set_entry_point("plan")

    # ── After planning: conditional route to first agent ──────────────────
    graph.add_conditional_edges(
        "plan",
        route_from_plan,
        {
            "document_intelligence": "document_intelligence",
            "regulatory_retrieval":  "regulatory_retrieval",
            "report_summarisation":  "report_summarisation",
        }
    )

    # ── After document intelligence: may skip to report ───────────────────
    graph.add_conditional_edges(
        "document_intelligence",
        route_after_document_intelligence,
        {
            "regulatory_retrieval": "regulatory_retrieval",
            "report_summarisation": "report_summarisation",
        }
    )

    # ── After regulatory retrieval: may skip risk scoring ─────────────────
    graph.add_conditional_edges(
        "regulatory_retrieval",
        route_after_regulatory_retrieval,
        {
            "risk_scoring":         "risk_scoring",
            "report_summarisation": "report_summarisation",
        }
    )

    # ── Fixed edges ────────────────────────────────────────────────────────
    graph.add_edge("risk_scoring",         "report_summarisation")
    graph.add_edge("report_summarisation", END)

    return graph.compile(checkpointer=checkpointer)


# ── Shared instances ───────────────────────────────────────────────────────────

# In-memory checkpointer — persists state across turns within the same process.
# Replace with AsyncSqliteSaver or RedisSaver for production persistence.
memory_checkpointer = MemorySaver()

# Compiled graph with persistence enabled
kyc_graph = build_kyc_graph(checkpointer=memory_checkpointer)

# Graph without persistence — used in tests to avoid state bleed between runs
kyc_graph_no_persist = build_kyc_graph(checkpointer=None)
