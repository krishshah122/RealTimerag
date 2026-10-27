from retrieval.dense import DenseRetriever
from retrieval.bm import get_cached_sparse_retriever
from retrieval.rrf import rrf_scores
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
def retrieve_node(state, vector_store: VectorStore):
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

    dense = DenseRetriever(vector_store).search(
        query,
        8,
        team_tag=team,
        status=status_filter,
        severity=severity_filter,
    )
    dense = _filter_docs(dense, team, status_filter, severity_filter)

    sparse_retriever, text_to_meta = get_cached_sparse_retriever(vector_store, team)
    sparse = sparse_retriever.search(query, 8)

    sparse_docs = []
    for text, bm25_score in sparse:
        meta = text_to_meta.get(text, {})
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

    fused = rrf_scores(
        dense_enriched,
        [(d["text"], d["bm25_score"]) for d in sparse_docs],
    )
    all_by_text = {d["text"]: d for d in dense_enriched}
    for doc in sparse_docs:
        all_by_text.setdefault(doc["text"], doc)
    fused_docs = [
        {
            **all_by_text.get(text, {"text": text, "score": 0, "metadata": {}}),
            "rrf_score": score,
        }
        for text, score in fused
    ]

    boosted = apply_recency_boost(fused_docs)
    reranked = simple_rerank(
        query,
        [{"text": d["text"], "final_score": d.get("final_score", 0)} for d in boosted],
    )

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


def _has_grounded_context(state) -> bool:
    return is_grounded_context_sufficient(state.get("docs", []))


def _no_context_answer(state):
    if state.get("blocked_reason"):
        return {"answer": state["blocked_reason"]}
    return {
        "answer": "🔒 **Groundedness Guard Active:** Zero relevant historical incidents matching your inquiry were found in the vector database. LLM inference has been automatically bypassed to prevent AI hallucination and conserve API token consumption."
    }


async def _safe_chat_completion(**kwargs):
    try:
        return await client.chat.completions.create(**kwargs)
    except Exception as e:
        err_str = str(e)
        if "model_not_found" in err_str or "404" in err_str:
            fallback = "openai/gpt-oss-20b"
            if kwargs.get("model") != fallback:
                kwargs["model"] = fallback
                return await client.chat.completions.create(**kwargs)
        raise


async def _run_specialist(state, role: str, instructions: str, output_key: str):
    context = sanitize_pii_and_secrets("\n".join(state["docs"]))
    prompt = f"""{_system_prompt_for_team(state.get("team"))}

You are the {role} specialist in a two-specialist incident analysis workflow.
Use ONLY the incident evidence below. Do not invent facts or add external assumptions.
Return at most 5 concise bullet points. State when the evidence is insufficient.

Task:
{instructions}

Incident evidence:
{context}

Question:
{state['query']}"""

    response = await _safe_chat_completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000,
    )
    msg = response.choices[0].message
    return {output_key: msg.content or getattr(msg, "reasoning", "") or ""}


@traceable(name="incident_analyst")
async def incident_analyst_node(state):
    return await _run_specialist(
        state,
        "incident-analysis",
        "Identify matching incidents, their severity/status/recency, and evidenced root-cause or impact patterns.",
        "incident_analysis",
    )


@traceable(name="remediation_analyst")
async def remediation_analyst_node(state):
    return await _run_specialist(
        state,
        "remediation",
        "Identify remediation actions explicitly supported by the incidents. Separate recorded actions from cautious recommendations.",
        "remediation_analysis",
    )


@traceable(name="synthesis_node")
async def synthesis_node(state):
    prompt = f"""Synthesize the two specialist notes into a direct answer to the question.
Use ONLY the notes below; do not introduce facts or assumptions. If they conflict or lack evidence, say so.
Keep the answer concise, explain the relevant incident evidence, and distinguish recorded remediation from recommendations.
Do not include greetings or sign-offs.

Incident analysis:
{state.get("incident_analysis", "")}

Remediation analysis:
{state.get("remediation_analysis", "")}

Question:
{state["query"]}"""
    response = await _safe_chat_completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1200,
    )
    msg = response.choices[0].message
    return {"answer": msg.content or getattr(msg, "reasoning", "") or ""}


@traceable(name="answer_node")
async def answer_node(state):
    if state.get("blocked_reason"):
        return {"answer": state["blocked_reason"]}

    if not _has_grounded_context(state):
        return _no_context_answer(state)

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
- Do not include conversational greetings, email sign-offs, or introductions; output direct analysis only

Context:
{context}

Question:
{state['query']}"""

    res = await _safe_chat_completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"answer": res.choices[0].message.content}


@traceable(name="summarize_node")
async def summarize_node(state):
    """Summarize retrieved incidents into structured output."""
    if state.get("blocked_reason"):
        return {"answer": state["blocked_reason"]}

    if not _has_grounded_context(state):
        return {"answer": "No valid historical incident context available for summarization."}

    context = sanitize_pii_and_secrets("\n".join(state.get("docs", [])))
    prompt = f"""Summarize these operational incidents. Provide:
1. Executive summary (2-3 sentences)
2. Root cause patterns
3. Impact assessment
4. Recommended remediation

Incidents:
{context}"""

    res = await _safe_chat_completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return {"answer": res.choices[0].message.content}
