from retrieval.dense import DenseRetriever
from retrieval.bm import SparseRetriever
from retrieval.rrf import rrf
from retrieval.rerank import simple_rerank
from retrieval.recency import apply_recency_boost, within_recency_window
from core.vector_store import VectorStore
from groq import AsyncGroq
from config import LLM_MODEL
from dotenv import load_dotenv
import os
from langsmith import traceable
from core.guardrails import validate_input_guardrail, sanitize_pii_and_secrets, is_grounded_context_sufficient

load_dotenv()

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("GROQ_API_KEY not set")


def _filter_docs(docs: list, team: str | None, status_filter: str | None, severity_filter: str | None) -> list:
    filtered = []
    for d in docs:
        meta = d.get("metadata", {}) or {}
        if team and meta.get("team_tag") != team:
            continue
        if status_filter and meta.get("status", "OPEN") != status_filter.upper():
            continue
        if severity_filter and meta.get("severity", "").lower() != severity_filter.lower():
            continue
        sev = meta.get("severity")
        if not within_recency_window(meta.get("timestamp"), sev):
            continue
        filtered.append(d)
    return filtered


@traceable(name="retrieve_node")
def retrieve_node(state, _):
    """
    Hybrid retrieval with team filtering, recency weighting, and lifecycle filters.
    """
    query = state["query"]
    is_valid, processed_query = validate_input_guardrail(query)
    if not is_valid:
        return {"docs": [], "blocked_reason": processed_query}
    query = sanitize_pii_and_secrets(processed_query)
    team = state.get("team")
    status_filter = state.get("status_filter")
    severity_filter = state.get("severity_filter")

    vector_store = VectorStore()

    dense = DenseRetriever(vector_store).search(query, 8)
    dense = _filter_docs(dense, team, status_filter, severity_filter)

    if team:
        texts = [text for text, meta in vector_store.iter_docs() if meta.get("team_tag") == team]
    else:
        texts = vector_store.store.all_texts()

    sparse = SparseRetriever(texts).search(query, 8) if texts else []

    sparse_docs = []
    text_to_meta = {text: meta for text, meta in vector_store.iter_docs()}
    for text, bm25_score in sparse:
        meta = text_to_meta.get(text, {})
        if team and meta.get("team_tag") != team:
            continue
        if status_filter and meta.get("status", "OPEN") != status_filter.upper():
            continue
        if severity_filter and meta.get("severity", "").lower() != severity_filter.lower():
            continue
        if not within_recency_window(meta.get("timestamp"), meta.get("severity")):
            continue
        sparse_docs.append({"text": text, "score": 0, "bm25_score": bm25_score, "metadata": meta})

    # Merge dense with bm25 scores
    dense_enriched = []
    bm25_map = {t: s for t, s in sparse}
    for d in dense:
        dense_enriched.append({**d, "bm25_score": bm25_map.get(d["text"], 0)})

    fused = rrf(dense_enriched, [(d["text"], d["bm25_score"]) for d in sparse_docs])
    fused_docs = []
    all_by_text = {d["text"]: d for d in dense_enriched}
    for t in sparse_docs:
        all_by_text.setdefault(t["text"], t)
    for text in fused:
        fused_docs.append(all_by_text.get(text, {"text": text, "score": 0, "metadata": {}}))

    boosted = apply_recency_boost(fused_docs)
    reranked = simple_rerank(query, [{"text": d["text"], "final_score": d.get("final_score", 0)} for d in boosted])

    return {"docs": [d["text"] for d in reranked[:3]]}


def _system_prompt_for_team(team: str | None, user_context: dict | None = None) -> str:
    base_prompt = "You are an operations analyst for an incident intelligence platform."
    if team:
        team_lower = team.lower()
        if "devops" in team_lower:
            base_prompt = "You are a DevOps SRE assistant focused on infrastructure, deployments, and reliability."
        elif "security" in team_lower:
            base_prompt = "You are a security analyst assistant focused on vulnerabilities and threats."
        elif "ops" in team_lower or "backend" in team_lower:
            base_prompt = "You are an operations analyst focused on incidents, SLAs, and service health."

    if user_context:
        base_prompt += f"\n\nSpeaking to {user_context.get('email', 'engineer')} (role: {user_context.get('role', 'engineer')})."
    return base_prompt


@traceable(name="answer_node")
async def answer_node(state):
    if state.get("blocked_reason"):
        return {"answer": state["blocked_reason"]}

    if not is_grounded_context_sufficient(state.get("docs", [])):
        return {
            "answer": "🔒 **Groundedness Guard Active:** Zero relevant historical incidents matching your inquiry were found in the vector database. LLM inference has been automatically bypassed to prevent AI hallucination and conserve API token consumption."
        }

    context = sanitize_pii_and_secrets("\n".join(state["docs"]))
    team = state.get("team")
    user_context = state.get("user_context")
    system_prompt = _system_prompt_for_team(team, user_context)

    prompt = f"""{system_prompt}

Using ONLY the incident context below:
- Explain relevant incidents in your own words
- Note severity, status, and recency when available
- Do NOT copy sentences verbatim
- Do NOT add external assumptions

Context:
{context}

Question:
{state['query']}"""

    res = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"answer": res.choices[0].message.content}


@traceable(name="summarize_node")
async def summarize_node(state):
    """Summarize retrieved incidents into structured output."""
    if state.get("blocked_reason"):
        return {"answer": state["blocked_reason"]}

    if not is_grounded_context_sufficient(state.get("docs", [])):
        return {"answer": "No valid historical incident context available for summarization."}

    context = sanitize_pii_and_secrets("\n".join(state.get("docs", [])))
    prompt = f"""Summarize these operational incidents. Provide:
1. Executive summary (2-3 sentences)
2. Root cause patterns
3. Impact assessment
4. Recommended remediation

Incidents:
{context}"""

    res = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return {"answer": res.choices[0].message.content}
