import os

from langgraph.graph import END, START, StateGraph

from config import RAG_MULTI_AGENT_ENABLED
from agents.nodes import (
    answer_node,
    incident_analyst_node,
    remediation_analyst_node,
    retrieve_node,
    summarize_node,
    synthesis_node,
    _no_context_answer,
)
from agents.state import RAGState


def _route_after_retrieval(state, mode: str, multi_agent: bool) -> str | list[str]:
    if state.get("blocked_reason"):
        return "blocked"
    if not state.get("docs"):
        return "no_context"
    if mode == "summarize":
        return "summarize"
    if multi_agent:
        return ["incident_analyst", "remediation_analyst"]
    return "answer_generation"


def _blocked_node(state):
    return {"answer": state["blocked_reason"]}


def build_graph(vector_store, mode: str = "ask", multi_agent: bool | None = None):
    if multi_agent is None:
        multi_agent = os.getenv(
            "RAG_MULTI_AGENT_ENABLED", str(RAG_MULTI_AGENT_ENABLED)
        ).strip().lower() == "true"

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", lambda state: retrieve_node(state, vector_store))
    graph.add_node("answer_generation", answer_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("blocked", _blocked_node)
    graph.add_node("no_context", _no_context_answer)
    graph.add_edge(START, "retrieve")
    route_map = {
        "blocked": "blocked",
        "no_context": "no_context",
        "summarize": "summarize",
        "answer_generation": "answer_generation",
    }
    if multi_agent and mode != "summarize":
        route_map.update(
            {
                "incident_analyst": "incident_analyst",
                "remediation_analyst": "remediation_analyst",
            }
        )
    graph.add_conditional_edges(
        "retrieve",
        lambda state: _route_after_retrieval(state, mode, multi_agent),
        route_map,
    )

    if multi_agent and mode != "summarize":
        graph.add_node("incident_analyst", incident_analyst_node)
        graph.add_node("remediation_analyst", remediation_analyst_node)
        graph.add_node("synthesize", synthesis_node)
        graph.add_edge("incident_analyst", "synthesize")
        graph.add_edge("remediation_analyst", "synthesize")
        graph.add_edge("synthesize", END)

    graph.add_edge("answer_generation", END)
    graph.add_edge("summarize", END)
    graph.add_edge("blocked", END)
    graph.add_edge("no_context", END)

    return graph.compile()
