import asyncio
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("GROQ_API_KEY", "test-key")

from agents import graph
from retrieval.bm import _corpus_cache, get_cached_sparse_retriever
from retrieval.recency import apply_recency_boost
from retrieval.rerank import simple_rerank
from retrieval.rrf import rrf, rrf_scores


class FakeVectorStore:
    backend_name = "test-backend"

    def __init__(self, documents):
        self.documents = documents
        self.corpus_revision = 1
        self.iterations = 0

    def iter_docs(self):
        self.iterations += 1
        return iter(self.documents)


class RetrievalTests(unittest.TestCase):
    def test_rrf_merges_ranks_and_ignores_duplicates_per_retriever(self):
        dense = [{"text": "same"}, {"text": "same"}, {"text": "dense"}]
        sparse = [("same", 100.0), ("sparse", 90.0)]

        scores = dict(rrf_scores(dense, sparse, k=60))

        self.assertAlmostEqual(scores["same"], 2 / 60)
        self.assertEqual(rrf(dense, sparse, k=60)[0], "same")
        self.assertEqual(len(scores), 3)

    def test_rrf_rejects_nonpositive_k(self):
        with self.assertRaises(ValueError):
            rrf([], [], k=0)

    def test_sparse_index_is_reused_and_refreshed_after_write(self):
        _corpus_cache.pop("test-backend", None)
        store = FakeVectorStore([("alpha incident", {"team_tag": "ops"})])

        first, _ = get_cached_sparse_retriever(store, "ops")
        second, _ = get_cached_sparse_retriever(store, "ops")
        self.assertIs(first, second)
        self.assertEqual(store.iterations, 1)

        store.documents.append(("beta incident", {"team_tag": "ops"}))
        store.corpus_revision += 1
        updated, _ = get_cached_sparse_retriever(store, "ops")
        self.assertIsNot(first, updated)
        self.assertEqual(store.iterations, 2)

    def test_recency_uses_fused_relevance_and_rerank_breaks_overlap_ties(self):
        docs = [
            {"text": "same words", "score": 1.0, "rrf_score": 0.02, "metadata": {}},
            {"text": "same words", "score": 0.1, "rrf_score": 0.01, "metadata": {}},
        ]
        boosted = apply_recency_boost(docs)
        self.assertGreater(boosted[0]["final_score"], boosted[1]["final_score"])

        reranked = simple_rerank(
            "same",
            [
                {"text": "same words", "final_score": 0.1},
                {"text": "same words", "final_score": 0.9},
            ],
        )
        self.assertEqual(reranked[0]["final_score"], 0.9)


class GraphWorkflowTests(unittest.TestCase):
    def test_single_agent_and_summary_graphs_compile(self):
        graph.build_graph(object(), multi_agent=False)
        graph.build_graph(object(), mode="summarize")
        with patch.dict(os.environ, {"RAG_MULTI_AGENT_ENABLED": "false"}):
            graph.build_graph(object())

    def test_parallel_specialists_join_before_synthesis(self):
        async def incident_node(_state):
            return {"incident_analysis": "incident facts"}

        async def remediation_node(_state):
            return {"remediation_analysis": "remediation facts"}

        async def synthesize_node(state):
            return {
                "answer": state["incident_analysis"] + " + " + state["remediation_analysis"]
            }

        with (
            patch.object(graph, "retrieve_node", return_value={"docs": ["evidence"]}),
            patch.object(graph, "incident_analyst_node", incident_node),
            patch.object(graph, "remediation_analyst_node", remediation_node),
            patch.object(graph, "synthesis_node", synthesize_node),
        ):
            workflow = graph.build_graph(object(), multi_agent=True)
            result = asyncio.run(workflow.ainvoke({"query": "question"}))

        self.assertEqual(result["answer"], "incident facts + remediation facts")

    def test_blocked_and_summarize_routes_do_not_fan_out(self):
        self.assertEqual(
            graph._route_after_retrieval(
                {"blocked_reason": "blocked"}, mode="ask", multi_agent=True
            ),
            "blocked",
        )
        self.assertEqual(
            graph._route_after_retrieval(
                {"docs": ["evidence"]}, mode="summarize", multi_agent=True
            ),
            "summarize",
        )


if __name__ == "__main__":
    unittest.main()
