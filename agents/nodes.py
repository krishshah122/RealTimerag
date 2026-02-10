from retrieval.dense import DenseRetriever
from retrieval.bm import SparseRetriever
from retrieval.rrf import rrf
from retrieval.rerank import simple_rerank
from core.vector_store import VectorStore  # 🔥 IMPORTANT
from groq import Groq
from config import LLM_MODEL
from dotenv import load_dotenv
import os
from langsmith import traceable

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("GROQ_API_KEY not set")


@traceable(name="retrieve_node")
def retrieve_node(state, _):
    """
    Always load the latest VectorStore from disk.
    This avoids server restart after Kafka ingestion.

    Now team-aware: only returns documents whose metadata.team_tag matches the
    requested team (when provided).
    """
    query = state["query"]
    team = state.get("team")

    # 🔥 RELOAD latest FAISS + docs.json
    vector_store = VectorStore()
    
    # DEBUG: Print team and store stats
    print(f"DEBUG: retrieve_node called with team='{team}'")
    print(f"DEBUG: VectorStore has {len(vector_store.store.docs)} docs")
    if len(vector_store.store.docs) > 0:
        sample_doc = list(vector_store.store.docs.values())[0]
        print(f"DEBUG: Sample doc metadata: {sample_doc.get('metadata')}")

    # Dense retrieval over full store, then filter by team if present
    dense = DenseRetriever(vector_store).search(query, 5)
    if team:
        dense_before = len(dense)
        dense = [
            d
            for d in dense
            if d.get("metadata", {}).get("team_tag") == team
        ]
        print(f"DEBUG: Dense filtered from {dense_before} to {len(dense)} docs for team '{team}'")

    # Sparse retrieval corpus is built from the document store (optionally filtered by team)
    if team:
        texts = [
            v["text"]
            for v in vector_store.store.docs.values()
            if v.get("metadata", {}).get("team_tag") == team
        ]
    else:
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


def _system_prompt_for_team(team: str | None, user_context: dict | None = None) -> str:
    """
    Choose a team-specific system prompt, personalized for the user.
    """
    base_prompt = "You are an operations analyst."
    
    if team:
        team_lower = team.lower()
        if "devops" in team_lower:
            base_prompt = (
                "You are a DevOps SRE assistant focused on infrastructure, "
                "deployments, CI/CD pipelines, and system reliability."
            )
        elif "security" in team_lower:
            base_prompt = (
                "You are a security analyst assistant focused on vulnerabilities, "
                "threats, access anomalies, and compliance-related events."
            )
        elif "ops" in team_lower or "operations" in team_lower:
            base_prompt = (
                "You are an operations analyst focused on business processes, "
                "customer impact, SLAs, and incident coordination."
            )

    # Personalization
    if user_context:
        user_email = user_context.get("email", "User")
        base_prompt += f"\n\nYou are speaking to {user_email}. Address them professionally."

    return base_prompt


def answer_node(state):
    context = "\n".join(state["docs"])
    team = state.get("team")
    user_context = state.get("user_context")

    system_prompt = _system_prompt_for_team(team, user_context)

    prompt = f"""
{system_prompt}

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
