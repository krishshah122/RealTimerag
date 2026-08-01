"""LLM-powered incident summarization and RCA generation."""

import os

from groq import AsyncGroq
from dotenv import load_dotenv

from config import LLM_MODEL

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


async def summarize_incident(text: str, metadata: dict | None = None) -> dict:
    """Generate structured summary fields for an incident."""
    meta = metadata or {}
    context = f"Severity: {meta.get('severity', 'unknown')}\nService: {meta.get('service', 'unknown')}\nTeam: {meta.get('team_tag', 'unknown')}\n\nIncident:\n{text}"

    prompt = f"""Analyze this operational incident and respond in JSON format with exactly these keys:
- summary: 1-2 sentence objective factual overview based strictly on the provided text
- root_cause: extract root cause ONLY if explicitly documented in the text, otherwise write "Pending investigation"
- impact: extract impact ONLY if explicitly stated in the text, otherwise write "Pending assessment"
- recommendation: write exactly "Reference historical RAG incidents for verified remediation solutions."

CRITICAL RULE: Do NOT make external assumptions, guess root causes, or invent recommendations that are not explicitly present in the incident text.

{context}

Respond ONLY with valid JSON, no markdown."""

    res = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,  # Zero temperature for maximum factual consistency
    )
    content = res.choices[0].message.content or "{}"

    import json
    try:
        # Strip markdown fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(content)
        # Ensure zero assumptions on recommendations during initial triage
        data["recommendation"] = "Reference historical RAG incidents for verified remediation solutions."
        return data
    except (json.JSONDecodeError, KeyError, TypeError):
        return {
            "summary": content[:300],
            "root_cause": "Pending investigation",
            "impact": "Pending assessment",
            "recommendation": "Reference historical RAG incidents for verified remediation solutions.",
        }


async def generate_rca(incident: dict, timeline: list[dict]) -> str:
    """Generate a Root Cause Analysis report."""
    timeline_text = "\n".join(
        f"- [{e.get('timestamp', '')}] {e.get('event_type', '')}: {e.get('description', '')}"
        for e in timeline
    )
    prompt = f"""Write a concise Root Cause Analysis (RCA) report for this incident.

Incident ID: {incident.get('incident_id')}
Status: {incident.get('status')}
Severity: {incident.get('severity')}
Service: {incident.get('service')}
Description: {incident.get('text')}

Timeline:
{timeline_text or 'No timeline events yet.'}

Existing analysis:
- Summary: {incident.get('summary', 'N/A')}
- Root cause: {incident.get('root_cause', 'N/A')}

Format the RCA with sections: Executive Summary, Timeline, Root Cause, Impact, Resolution, Prevention."""

    res = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return res.choices[0].message.content or "RCA generation failed."


async def recommend_resolution(similar_incidents: list[dict], query_text: str) -> str:
    """Suggest fixes based on similar historical incidents."""
    if not similar_incidents:
        return "No similar historical incidents found. Escalate to on-call engineer."

    context = "\n\n".join(
        f"Incident {s.get('issue_id')}: {s.get('text', '')[:200]}\nRecommendation: {s.get('recommendation', 'N/A')}"
        for s in similar_incidents[:3]
    )
    prompt = f"""Based on these similar past incidents, recommend a resolution for:

"{query_text}"

Historical context:
{context}

Provide actionable remediation steps in 3-5 bullet points."""

    res = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return res.choices[0].message.content or "Unable to generate recommendation."
