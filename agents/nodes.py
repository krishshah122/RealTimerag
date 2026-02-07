from retrieval.dense import DenseRetriever
from retrieval.bm import SparseRetriever
from retrieval.rrf import rrf
from retrieval.rerank import simple_rerank
from core.vector_store import VectorStore   # 🔥 IMPORTANT
from groq import Groq
from config import LLM_MODEL
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("GROQ_API_KEY not set")


def retrieve_node(state, _):
    """
    Always load the latest VectorStore from disk.
    This avoids server restart after Kafka ingestion.
    """
    query = state["query"]

    # 🔥 RELOAD latest FAISS + docs.json
    vector_store = VectorStore()

    # Dense retrieval
    dense = DenseRetriever(vector_store).search(query, 5)

    # Sparse retrieval (guarded)
    texts = vector_store.store.all_texts()
    if texts:
        sparse = SparseRetriever(texts).search(query, 5)
    else:
        sparse = []

    # Fusion
    fused = rrf(dense, sparse)

    # Re-ranking
    reranked = simple_rerank(
        query,
        [{"text": t} for t in fused]
    )

    return {
        "docs": [d["text"] for d in reranked[:3]]
    }


def answer_node(state):
    context = "\n".join(state["docs"])

    prompt = f"""
You are an operations analyst.

Using ONLY the information in the context:
- Explain the issue in your own words
- Do NOT copy sentences verbatim
- Give a concise, clear explanation
- Do NOT add external assumptions

Context:
{context}

Question:
{state['query']}
"""


    res = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        "answer": res.choices[0].message.content
    }
