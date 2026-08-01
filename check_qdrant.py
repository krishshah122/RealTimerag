"""
Verify RAG pipeline: embeddings storage + retrieval quality
Run: python check_qdrant.py
"""
import os, json
os.environ["PYTHONIOENCODING"] = "utf-8"

from qdrant_client import QdrantClient
from core.embeddings import EmbeddingModel
from qdrant_client.models import Filter, FieldCondition, MatchValue
from config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION

c = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)

# 1. How many documents are embedded in Qdrant?
info = c.get_collection(QDRANT_COLLECTION)
print("=" * 60)
print(f"  QDRANT COLLECTION: {QDRANT_COLLECTION}")
print(f"  Total embedded documents: {info.points_count}")
print(f"  Vector dimensions: {info.config.params.vectors.size}")
print("=" * 60)

# 2. Show ALL stored documents
print("\n ALL STORED DOCUMENTS:")
print("-" * 60)
all_points = []
offset = None
while True:
    pts, offset = c.scroll(
        collection_name=QDRANT_COLLECTION, limit=100,
        offset=offset, with_vectors=False,
    )
    all_points.extend(pts)
    if offset is None:
        break

for i, p in enumerate(all_points):
    text = p.payload.get("text", "")[:100]
    team = p.payload.get("team_tag", "N/A")
    sev = p.payload.get("severity", "N/A")
    status = p.payload.get("status", "N/A")
    print(f"  [{p.id}] team={team} | severity={sev} | status={status}")
    print(f"       {text}...")
    print()

# 3. Test retrieval with a sample query
test_query = "database CPU usage critical"
print("=" * 60)
print(f"  TEST QUERY: \"{test_query}\"")
print("=" * 60)

emb = EmbeddingModel.encode([test_query])[0].tolist()
results = c.query_points(
    collection_name=QDRANT_COLLECTION,
    query=emb,
    limit=3,
)

if results.points:
    print("\n  [OK] RETRIEVAL IS WORKING! Top results:\n")
    for i, r in enumerate(results.points):
        text = r.payload.get("text", "")[:120]
        score = r.score
        team = r.payload.get("team_tag", "N/A")
        print(f"  #{i+1} (similarity: {score:.4f}) team={team}")
        print(f"      {text}...")
        print()
else:
    print("\n  [FAIL] No results returned - retrieval may not be working.")

# 4. Test team-filtered retrieval
print("-" * 60)
print("  TEAM-FILTERED RETRIEVAL:")
for team in ["devops", "security", "ops"]:
    results = c.query_points(
        collection_name=QDRANT_COLLECTION,
        query=emb,
        limit=3,
        query_filter=Filter(must=[FieldCondition(key="team_tag", match=MatchValue(value=team))]),
    )
    count = len(results.points)
    print(f"    Team '{team}': {count} results found")

# 5. Check old FAISS data
faiss_path = os.path.join("data", "docs.json")
if os.path.exists(faiss_path):
    with open(faiss_path) as f:
        old_docs = json.load(f)
    print(f"\n  [WARNING] OLD docs.json has {len(old_docs)} documents NOT in Qdrant!")
    print(f"  Run: python -m scripts.migrate_faiss_to_qdrant  to migrate them.")
