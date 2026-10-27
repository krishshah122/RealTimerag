"""Exercise the hosted API -> Kafka -> consumer -> Pinecone -> /ask flow.

Run the API on a staging deployment and start the consumer locally with the same
staging Kafka topic and Pinecone namespace. Credentials are read from environment.
"""

import json
import os
import statistics
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()


def _required_env(primary, fallback=None):
    value = os.getenv(primary) or (os.getenv(fallback) if fallback else None)
    if not value:
        raise RuntimeError(f"Set {primary}" + (f" or {fallback}" if fallback else ""))
    return value


def _request(url, *, method="GET", headers=None, body=None, timeout=90):
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _percentile(values, percentile):
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _find_incident(documents, incident_id):
    if isinstance(documents, dict):
        for document_id, document in documents.items():
            metadata = (document or {}).get("metadata", {}) or {}
            if (
                str(document_id) == incident_id
                or metadata.get("issue_id") == incident_id
                or metadata.get("incident_id") == incident_id
            ):
                return True
    return False


def main():
    api_url = _required_env("E2E_API_URL").rstrip("/")
    supabase_url = _required_env("E2E_SUPABASE_URL", "VITE_SUPABASE_URL").rstrip("/")
    anon_key = _required_env("E2E_SUPABASE_ANON_KEY", "VITE_SUPABASE_ANON_KEY")
    email = _required_env("E2E_EMAIL")
    password = _required_env("E2E_PASSWORD")
    team = os.getenv("E2E_TEAM", "ops")
    timeout_seconds = int(os.getenv("E2E_INDEX_TIMEOUT_SECONDS", "120"))
    run_count = int(os.getenv("E2E_RUN_COUNT", "1"))
    if run_count < 1:
        raise RuntimeError("E2E_RUN_COUNT must be at least 1")

    _, login = _request(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        method="POST",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        body=json.dumps({"email": email, "password": password}).encode("utf-8"),
    )
    token = login.get("access_token")
    if not token:
        raise RuntimeError("Supabase login returned no access token.")
    auth_headers = {"Authorization": f"Bearer {token}"}

    ingest_times = []
    ack_times = []
    index_times = []
    ask_times = []
    retrieval_hits = []
    full_run_started = time.perf_counter()

    for run_number in range(1, run_count + 1):
        marker = f"e2e-{uuid.uuid4().hex[:12]}"
        incident_text = (
            f"Synthetic staging evaluation incident {marker}: "
            "checkout API returned HTTP 503 because the PostgreSQL connection "
            "pool was exhausted. Restarting the worker restored service."
        )
        question = (
            f"For staging test {marker}, what failed and what action restored service?"
        )
        issue = {
            "type": "e2e_evaluation",
            "text": incident_text,
            "metadata": {
                "severity": "medium",
                "status": "OPEN",
                "service": "e2e-evaluation",
                "evaluation_marker": marker,
            },
        }

        started = time.perf_counter()
        _, created = _request(
            f"{api_url}/log_issue",
            method="POST",
            headers={
                **auth_headers,
                "Content-Type": "application/json",
            },
            body=json.dumps(issue).encode("utf-8"),
        )
        api_ingest_ms = (time.perf_counter() - started) * 1000
        incident_id = str((created.get("event") or {}).get("id") or "")
        publish = created.get("kafka_publish") or {}
        if not incident_id:
            raise RuntimeError("API response did not include the created incident ID.")
        if publish.get("status") != "published":
            raise RuntimeError(
                f"Incident {incident_id} was created but Kafka publish was not "
                f"confirmed: {publish.get('status', 'missing')}"
            )

        index_started = time.perf_counter()
        indexed = False
        while time.perf_counter() - index_started < timeout_seconds:
            _, documents = _request(
                f"{api_url}/documents",
                headers=auth_headers,
                timeout=30,
            )
            if _find_incident(documents, incident_id):
                indexed = True
                break
            time.sleep(1)
        if not indexed:
            raise TimeoutError(
                f"Incident {incident_id} was acknowledged by Kafka but did not "
                f"appear in the API's vector documents within {timeout_seconds}s. "
                "Check consumer logs and staging topic/namespace configuration."
            )
        submit_to_index_ms = (time.perf_counter() - started) * 1000

        ask_url = f"{api_url}/ask?{urlencode({'team_id': team})}"
        ask_started = time.perf_counter()
        _, answer = _request(
            ask_url,
            method="POST",
            headers={
                **auth_headers,
                "Content-Type": "text/plain",
            },
            body=question.encode("utf-8"),
        )
        ask_ms = (time.perf_counter() - ask_started) * 1000
        retrieved_docs = answer.get("docs", []) if isinstance(answer, dict) else []
        retrieval_hit = any(
            marker in str(document) for document in retrieved_docs
        )

        ingest_times.append(api_ingest_ms)
        ack_times.append(float(publish.get("duration_ms", 0)))
        index_times.append(submit_to_index_ms)
        ask_times.append(ask_ms)
        retrieval_hits.append(int(retrieval_hit))
        print(
            f"run={run_number} incident_id={incident_id} "
            f"kafka={publish.get('topic')}:{publish.get('partition')}"
            f"@{publish.get('offset')} "
            f"api_ingest_ms={api_ingest_ms:.1f} "
            f"kafka_ack_ms={ack_times[-1]:.1f} "
            f"submit_to_index_ms={submit_to_index_ms:.1f} "
            f"ask_api_ms={ask_ms:.1f} "
            f"retrieval_hit_at_3={retrieval_hit}"
        )

    total_ms = (time.perf_counter() - full_run_started) * 1000
    print("\nStaging end-to-end evaluation summary")
    print(f"successful_runs: {len(retrieval_hits)}/{run_count}")
    print(f"mean_api_ingest_ms: {statistics.mean(ingest_times):.1f}")
    print(f"mean_kafka_ack_ms: {statistics.mean(ack_times):.1f}")
    print(f"submit_to_index_p50_ms: {_percentile(index_times, 50):.1f}")
    print(f"submit_to_index_p95_ms: {_percentile(index_times, 95):.1f}")
    print(f"ask_api_p50_ms: {_percentile(ask_times, 50):.1f}")
    print(f"ask_api_p95_ms: {_percentile(ask_times, 95):.1f}")
    print(f"retrieval_hit_rate_at_3: {statistics.mean(retrieval_hits):.3f}")
    print(f"overall_run_elapsed_ms: {total_ms:.1f}")
    print(
        "Note: run multiple samples for useful percentiles. This smoke benchmark "
        "does not calculate semantic answer correctness or load-test throughput."
    )


if __name__ == "__main__":
    main()
