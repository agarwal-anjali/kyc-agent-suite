"""
Orchestrator Agent

Now a thin wrapper around the LangGraph graph.
Responsibility split:
  - Planning: graph's node_plan node
  - Execution: graph nodes with conditional routing
  - Persistence: LangGraph MemorySaver checkpointer
  - Streaming: graph.astream_events(version="v2")
"""

import structlog
from core.models import KYCState, QueryIntent
from core.graph import kyc_graph

log = structlog.get_logger()

# ── Node name → human-readable status message ──────────────────────────────────
NODE_STATUS = {
    "plan":                   "Thinking...",
    "document_intelligence":  "Analysing documents...",
    "regulatory_retrieval":   "Retrieving applicable regulations...",
    "risk_scoring":           "Calculating risk score...",
    "report_summarisation":   "Generating response...",
}

# ── Node name → pipeline step key (for frontend step tracker) ─────────────────
NODE_STEP_KEY = {
    "document_intelligence": "doc",
    "regulatory_retrieval":  "reg",
    "risk_scoring":          "risk",
    "report_summarisation":  "report",
}


class OrchestratorAgent:
    """
    Thin orchestrator that delegates to the LangGraph graph.

    Uses:
    - graph.ainvoke()        for non-streaming requests
    - graph.astream_events() for SSE streaming requests

    Session persistence is handled by LangGraph's MemorySaver checkpointer.
    Each session maps to a LangGraph thread_id.
    """

    @staticmethod
    def _make_config(session_id: str) -> dict:
        """
        Build the LangGraph run config for a session.
        thread_id is how LangGraph identifies which checkpoint to load/save.
        """
        return {"configurable": {"thread_id": session_id}}

    async def run(self, state: KYCState) -> KYCState:
        """
        Execute the full pipeline and return the completed state.
        LangGraph loads the previous checkpoint for this session_id,
        runs the graph, and saves the new checkpoint on completion.
        """
        log.info("orchestrator.run_started", session_id=state.session_id)

        config = self._make_config(state.session_id)
        result = await kyc_graph.ainvoke(state, config=config)

        log.info(
            "orchestrator.run_completed",
            session_id=state.session_id,
            intent=result.execution_plan.intent if result.execution_plan else None,
            verdict=result.verdict,
        )
        return result

    async def run_streaming(self, state: KYCState):
        """
        Execute the pipeline with SSE streaming using LangGraph's
        native astream_events() API.

        Event types yielded:
          status       — Node start/end progress messages
          plan         — ExecutionPlan JSON (after planning node completes)
          step_update  — Which pipeline step is now active (for UI tracker)
          risk_score   — RiskScoreBreakdown JSON (after risk_scoring node)
          report_token — Individual LLM tokens from report summarisation
          error        — Pipeline error message
        """
        log.info("orchestrator.stream_started", session_id=state.session_id)

        config = self._make_config(state.session_id)

        try:
            async for event in kyc_graph.astream_events(
                state,
                config=config,
                version="v2",        # use v2 for richer metadata
            ):
                kind     = event["event"]
                name     = event.get("name", "")
                metadata = event.get("metadata", {})

                # ── Node started ───────────────────────────────────────────
                if kind == "on_chain_start" and name in NODE_STATUS:
                    yield {
                        "event": "status",
                        "data":  NODE_STATUS[name],
                    }
                    # Emit step key for UI pipeline tracker
                    if name in NODE_STEP_KEY:
                        yield {
                            "event": "step_update",
                            "data":  f"{NODE_STEP_KEY[name]}:running",
                        }

                # ── Node completed ─────────────────────────────────────────
                elif kind == "on_chain_end" and name in NODE_STATUS:

                    # After planning: emit the execution plan
                    if name == "plan":
                        output = event["data"].get("output")
                        if output and hasattr(output, "execution_plan") and output.execution_plan:
                            yield {
                                "event": "plan",
                                "data":  output.execution_plan.model_dump_json(),
                            }

                    # After risk scoring: emit risk score
                    elif name == "risk_scoring":
                        output = event["data"].get("output")
                        if output and hasattr(output, "risk_scoring") and output.risk_scoring:
                            yield {
                                "event": "risk_score",
                                "data":  output.risk_scoring.model_dump_json(),
                            }

                    # Mark step as done in UI tracker
                    if name in NODE_STEP_KEY:
                        yield {
                            "event": "step_update",
                            "data":  f"{NODE_STEP_KEY[name]}:done",
                        }

                # ── LLM token streaming ────────────────────────────────────
                # Only surface tokens from the report summarisation node
                elif kind == "on_chat_model_stream":
                    # metadata["langgraph_node"] tells us which node is streaming
                    node = metadata.get("langgraph_node", "")
                    if node == "report_summarisation":
                        chunk = event["data"].get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            token = (
                                chunk.content if isinstance(chunk.content, str)
                                else "".join(
                                    b.get("text", "") if isinstance(b, dict) else b
                                    for b in chunk.content
                                    if b
                                )
                            )
                            if token:
                                yield {"event": "report_token", "data": token}

        except Exception as e:
            log.error("orchestrator.stream_error", error=str(e))
            yield {"event": "error", "data": str(e)}

        yield {"event": "status", "data": "Complete."}