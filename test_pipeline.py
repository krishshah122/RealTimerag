"""
Full RAG Pipeline Test - shows data flowing through EVERY step.
Run: python test_pipeline.py
"""
import os, sys
os.environ["PYTHONIOENCODING"] = "utf-8"

from dotenv import load_dotenv
load_dotenv()

from core.vector_store import VectorStore
from core.embeddings import EmbeddingModel
from retrieval.dense import DenseRetriever
from retrieval.bm import SparseRetriever
from retrieval.rrf import rrf
from retrieval.rerank import simple_rerank
from retrieval.recency import apply_recency_boost, within_recency_window

query = sys.argv[1] if len(sys.argv) > 1 else "database CPU critical"
team = sys.argv[2] if len(sys.argv) > 2 else None

print("=" * 70)
print(f"  QUERY: \"{query}\"")
print(f"  TEAM FILTER: {team or 'None (all teams)'}")
print("=" * 70)

store = VectorStore()

# ── STEP 1: Dense / Semantic Search (Qdrant) ──
print("\n[STEP 1] DENSE SEARCH (Qdrant embeddings)")
print("-" * 50)
dense_results = DenseRetriever(store).search(query, 8)
print(f"  Found {len(dense_results)} results from Qdrant:")
for i, d in enumerate(dense_results):
    meta = d.get("metadata", {})
    print(f"  #{i+1} score={d['score']:.4f} | team={meta.get('team_tag','N/A')} | sev={meta.get('severity','N/A')}")
    print(f"       {d['text'][:100]}...")

# ── STEP 2: Team + Status Filtering ──
print(f"\n[STEP 2] TEAM FILTERING (team={team or 'all'})")
print("-" * 50)
filtered = []
for d in dense_results:
    meta = d.get("metadata", {}) or {}
    if team and meta.get("team_tag") != team:
        continue
    if not within_recency_window(meta.get("timestamp"), meta.get("severity")):
        continue
    filtered.append(d)
print(f"  After filtering: {len(filtered)} results remain")

# ── STEP 3: BM25 Sparse Search ──
print(f"\n[STEP 3] BM25 SPARSE SEARCH (keyword matching)")
print("-" * 50)
if team:
    texts = [text for text, meta in store.iter_docs() if meta.get("team_tag") == team]
else:
    texts = store.store.all_texts()

if texts:
    sparse_results = SparseRetriever(texts).search(query, 8)
    print(f"  BM25 corpus size: {len(texts)} documents")
    print(f"  Found {len(sparse_results)} BM25 matches:")
    for i, (text, score) in enumerate(sparse_results):
        print(f"  #{i+1} bm25={score:.4f} | {text[:80]}...")
else:
    sparse_results = []
    print("  No documents in corpus for BM25")

# ── STEP 4: RRF Fusion ──
print(f"\n[STEP 4] RRF FUSION (merging dense + sparse)")
print("-" * 50)
text_to_meta = {text: meta for text, meta in store.iter_docs()}
sparse_docs = []
bm25_map = {t: s for t, s in sparse_results}
for text, bm25_score in sparse_results:
    meta = text_to_meta.get(text, {})
    sparse_docs.append({"text": text, "score": 0, "bm25_score": bm25_score, "metadata": meta})

dense_enriched = [{**d, "bm25_score": bm25_map.get(d["text"], 0)} for d in filtered]
fused = rrf(dense_enriched, [(d["text"], d["bm25_score"]) for d in sparse_docs])
print(f"  RRF produced {len(fused)} fused results")

all_by_text = {d["text"]: d for d in dense_enriched}
for t in sparse_docs:
    all_by_text.setdefault(t["text"], t)
fused_docs = [all_by_text.get(text, {"text": text, "score": 0, "metadata": {}}) for text in fused]

# ── STEP 5: Recency Boost ──
print(f"\n[STEP 5] RECENCY BOOST")
print("-" * 50)
boosted = apply_recency_boost(fused_docs)
print(f"  Boosted {len(boosted)} documents by recency")

# ── STEP 6: Reranking ──
print(f"\n[STEP 6] FINAL RERANKING")
print("-" * 50)
reranked = simple_rerank(query, [{"text": d["text"], "final_score": d.get("final_score", 0)} for d in boosted])
print(f"  Reranked to {len(reranked)} results")

# ── STEP 7: Top 3 sent to LLM ──
top3 = [d["text"] for d in reranked[:3]]
print(f"\n{'=' * 70}")
print(f"  [FINAL] TOP 3 DOCUMENTS SENT TO LLM:")
print(f"{'=' * 70}")
for i, text in enumerate(top3):
    print(f"\n  --- Document #{i+1} ---")
    print(f"  {text}")

if not top3:
    print("\n  [EMPTY] No documents retrieved! The LLM will have no context.")
    print("  This means either:")
    print("    - No documents match your query")
    print("    - Team filter excluded everything")
    print("    - Recency window filtered out old incidents")
