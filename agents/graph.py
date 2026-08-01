from langgraph.graph import StateGraph
from agents.state import RAGState
from agents.nodes import retrieve_node, answer_node, summarize_node


def build_graph(vector_store, mode: str = "ask"):
    graph = StateGraph(RAGState)
    graph.add_node("retrieve", lambda s: retrieve_node(s, vector_store))

    if mode == "summarize":
        graph.add_node("summarize", summarize_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "summarize")
    else:
        graph.add_node("answer", answer_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "answer")

    return graph.compile()
