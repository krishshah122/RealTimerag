from langgraph.graph import StateGraph
from agents.state import RAGState
from agents.nodes import retrieve_node, answer_node

def build_graph(vector_store):
    graph = StateGraph(RAGState)

    graph.add_node("retrieve", lambda s: retrieve_node(s, vector_store))
    graph.add_node("answer", answer_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "answer")

    return graph.compile()
