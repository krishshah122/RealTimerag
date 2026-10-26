# Real-Time Incident Intelligence Platform

**Version 2.0.0**

A production-inspired Retrieval-Augmented Generation (RAG) system for engineering and operations teams to monitor, investigate, and understand operational incidents in real time.

Unlike traditional RAG systems that rely on static documents, this platform continuously ingests incident events, indexes them with lifecycle metadata, and enables team-specific question answering through a secure dashboard.


---

## What This Platform Does

| Capability | Description |
|---|---|
| Real-time ingestion | Incidents flow through Kafka/Redpanda into the vector index |
| Incident lifecycle | `OPEN` -> `INVESTIGATING` -> `MITIGATED` -> `RESOLVED` -> `CLOSED` |
| Time-aware retrieval | Recency-weighted hybrid search (semantic + BM25 + decay) |
| Summarization agent | Auto-generates summary, root cause, impact, and recommendations |
| Smart correlation | Groups related incidents by service and error patterns |
| Similar incidents | "Have we seen this before?" via semantic search |
| Resolution recommendations | LLM suggestions from historical similar incidents |
| RCA generation | Automated Root Cause Analysis reports |
| Notifications | Web, Slack, Teams, and Email channels |
| RBAC | Admin, Team Lead, SRE, Engineer, and Analyst roles |
| Analytics | MTTR, severity distribution, top services, trends |
| Auto cleanup | Background job archives and purges expired incidents |
| Alert generator | Generates synthetic monitoring alerts for demos and testing |

---

## End-to-End Architecture

```mermaid
graph TD
    subgraph Ingest["Incident ingestion and indexing"]
      A[Monitoring client or simulation] -->|POST /log_issue| API[FastAPI]
      API --> AUTH[JWT and team authorization]
      AUTH --> SQL[(SQLite: incidents, timeline, analytics, notifications)]
      AUTH --> CORR[Correlation group assignment]
      AUTH --> SUM[Incident summary via Groq]
      AUTH --> NOTIFY[Web notification and optional channels]
      AUTH -->|publish live_issues| KAFKA[Redpanda / Kafka]
      KAFKA --> WORKER[stream.consumer]
      WORKER --> EMBED[SentenceTransformer embeddings]
      EMBED --> VECTOR[(Pinecone, Qdrant, or configured FAISS backend)]
    end

    subgraph Ask["Question answering"]
      USER[Analyst in React dashboard] -->|POST /ask| API2[FastAPI auth and team access]
      API2 --> STATE[Per-request LangGraph RAGState]
      STATE --> RETRIEVE[retrieve: guardrail and hybrid retrieval]
      RETRIEVE -->|dense top 8| QDRANT
      RETRIEVE -->|sparse top 8| BM25[Cached team-scoped BM25 index]
      RETRIEVE --> FUSE[RRF fusion, recency boost, lexical overlap rerank]
      FUSE --> ROUTE{Blocked, no docs, or route?}
      ROUTE -->|blocked| BLOCK[blocked: return guardrail reason]
      ROUTE -->|no docs| EMPTY[no_context: groundedness response]
      ROUTE -->|ask, multi-agent on| IA[incident_analyst]
      ROUTE -->|ask, multi-agent on| RA[remediation_analyst]
      IA --> SYNTH[synthesize specialist notes]
      RA --> SYNTH
      ROUTE -->|ask, multi-agent off| ANSWER[answer: single grounded LLM call]
      ROUTE -->|summarize mode| SUMGRAPH[summarize: incident summary]
      SYNTH --> RESULT[Graph state response with answer]
      ANSWER --> RESULT
      SUMGRAPH --> RESULT
      BLOCK --> RESULT
      EMPTY --> RESULT
      RESULT -->|JSON state| USER
    end
```

For the exact LangGraph node/edge map, retrieval scoring details, request state,
agent coordination, and user-facing request sequence, see
[docs/retrieval.md](./docs/retrieval.md).

---

## Tech Stack & Versions

### Backend
| Component | Technology | Version |
|---|---|---|
| API Gateway | FastAPI | >= 0.115 |
| AI Orchestration | LangGraph | >= 0.2.0 |
| LLM Engine | Groq (llama-3.1-8b-instant) | >= 0.13.0 |
| Embedding Engine | BAAI/bge-small-en-v1.5 (SentenceTransformers) | >= 3.3.0 |
| Vector DB | **Pinecone** (default), Qdrant, or FAISS (optional fallback) | Pinecone serverless / Qdrant / faiss-cpu |
| Lexical Search | rank-bm25 | >= 0.2.2 |
| Stream Processing| Kafka-python + Redpanda | v24.2+ |
| Relational Storage | SQLAlchemy + SQLite | >= 2.0.0 |
| Identity & Auth | Supabase + JWT Security Middleware | >= 2.10.0 |
| Job Scheduling | APScheduler | >= 3.10.0 |

### Frontend
| Component | Technology | Version |
|---|---|---|
| UI Engine | React | 19.x |
| Build Tooling | Vite | Latest |
| Client Routing | React Router | Latest |
| Auth & Security | Supabase JS Client | Latest |
| Design & Styling | Tailwind CSS + Vanilla Custom Tokens | — |

---

## Service Ports & Networking Configuration

During local development and testing, the microservice ecosystem communicates across the following port mapping architecture:

| Service | Port | Protocol | Purpose / URL |
|---|---|---|---|
| **React Dashboard** | `5173` | HTTP / WebSocket | Main Frontend UI Command Center (`http://localhost:5173`) |
| **FastAPI Gateway** | `8000` | HTTP / OpenAPI | Main Backend RAG API Gateway (`http://localhost:8000/docs`) |
| **Pinecone** | Cloud endpoint | HTTPS | Managed vector search and metadata-filtered semantic queries |
| **Qdrant (optional)** | `6333` / `6334` | HTTP / gRPC | Optional local or hosted vector backend |
| **Redpanda Broker** | `9092` | Kafka Protocol | Event pub/sub topic streaming broker (`live_issues`) |
| **SQLite DB** | *Local File* | ACID DB Engine | Embedded local transactional database (`rag/rag_analytics.db`) |

---

## Project Structure

```text
rag/
|-- agents/               # LangGraph state, nodes, and ask/summarize graph builders
|-- app/                  # FastAPI routes, authentication, and role/team access checks
|-- core/                 # Incidents, analytics, embeddings, guardrails, notifications,
|                         # correlation, summarization, and VectorStore facade
|   `-- vector_backends/  # Pinecone (default), Qdrant, and optional FAISS
|-- retrieval/            # Dense retrieval, cached BM25, reciprocal-rank fusion,
|                         # recency weighting, and lexical overlap reranking
|-- stream/               # Kafka producer and vector-index consumer
|-- simulation/            # Synthetic alert generation for demos/testing
|-- jobs/                  # APScheduler startup and retention cleanup
|-- frontend/              # React/Vite dashboard and API client
|-- docs/                  # Architecture, module, stack, interview, and retrieval docs
|-- data/                  # Local FAISS index/documents when the FAISS backend is used
|-- scripts/               # Index migration utilities
|-- tests/                 # Backend tests
|-- config.py              # Environment-backed model, backend, RBAC, and retention config
|-- docker-compose.yaml    # Local Redpanda and optional Qdrant services
|-- requirements.txt       # Python backend dependencies
```

### Data ownership and persistence

- **SQLite** (`rag_analytics.db`, relative to the backend working directory) stores
  incident lifecycle records, timeline events, web notifications, and query/issue
  analytics. Supabase Auth and the `profiles` table supply user identity, role, and
  team information.
- **Pinecone** stores incident text as vectors with metadata used for filtering. It is
  the default shared vector backend; **Qdrant** and **FAISS** remain alternatives.
- **Redpanda/Kafka** carries `live_issues` events from the API process to the separate
  `stream.consumer` process, which embeds and indexes incident text. Indexing is
  therefore asynchronous relative to publication. If the broker is unavailable, the
  producer logs and skips publication; the SQLite incident record may still exist.
- **LangGraph state is request-scoped**. It is initialized for each `/ask` or
  `/summarize` request, merged from node result dictionaries during that graph run,
  and is not a persistent conversation history or cross-request memory store.

---

## API Endpoints Reference

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create user and profile with verified team label and role assignment |

### Incidents & Ingestion
| Method | Path | Description |
|---|---|---|
| POST | `/log_issue` | Ingest real-time incident (lifecycle + Kafka topic + automatic AI summarization) |
| GET | `/incidents` | List incidents (support filtering by status, severity, and team tags) |
| GET | `/incidents/{id}` | Detailed incident analysis + timeline events + correlated incidents |
| PATCH | `/incidents/{id}/status` | Execute lifecycle state transitions |
| PATCH | `/incidents/{id}/summary` | Override or update AI summary fields (Requires SRE role or above) |
| GET | `/incidents/{id}/similar` | Perform semantic similarity lookup for historical occurrences |
| GET | `/incidents/{id}/rca` | Generate interactive Root Cause Analysis report |
| DELETE | `/issues/{id}` | Delete incident record (Restricted to original owner or admin) |

### RAG & AI Intelligence
| Method | Path | Description |
|---|---|---|
| POST | `/ask` | Team-aware Hybrid RAG conversational Q&A (supports status/severity filters) |
| POST | `/summarize` | Generate intelligent executive summary across incidents matching a topic query |
| POST | `/recommend` | Extract actionable operational resolution suggestions from historical incidents |
| GET | `/documents` | List indexed text documents (requires JWT authentication, team-scoped) |

#### LangGraph workflow

`/ask` and `/summarize` use compiled LangGraph workflows created once by the FastAPI
application. Each request supplies a fresh state. Retrieval happens once; in
multi-agent `/ask` mode, the incident and remediation specialists receive the same
retrieved evidence and run as parallel branches. They do not message each other
directly: each writes its own analysis field, and the synthesis node reads both fields
to produce the answer. In single-agent mode, `answer` generates the answer directly.
`/summarize` uses the `summarize` node, not the two-specialist path. Blocked inputs
and empty retrieval results short-circuit before generation. Set
`RAG_MULTI_AGENT_ENABLED=false` to select the single-answer-node `/ask` path.

Successful multi-agent `/ask` normally makes three Groq calls (two specialists and
one synthesis); single-agent `/ask` and `/summarize` each make one. These paths
therefore trade token usage and latency for separation of analysis and remediation
roles. The graph is orchestration, not an autonomous agent-to-agent conversation:
branches communicate through the shared LangGraph state only.

The BM25 corpus/index is cached per process, invalidated by writes made through
`VectorStore`, and refreshed at least every 30 seconds to observe updates from other
processes. It still requires a full corpus scan on refresh and is not a substitute for a
distributed sparse index. For large or rapidly changing corpora, benchmark Qdrant sparse
vectors or a dedicated lexical-search service rather than assuming the in-process cache
removes the corpus-scan cost.

### Notifications
| Method | Path | Description |
|---|---|---|
| GET | `/notifications` | Poll web dashboard emergency notifications |
| POST | `/notifications/{id}/read` | Mark individual alert notification as acknowledged/read |

### Simulation Engine
| Method | Path | Description |
|---|---|---|
| POST | `/simulation/generate?count=N` | Trigger bulk automated alert generation test storms |
| POST | `/simulation/single` | Inject a single random high-fidelity synthetic monitoring alert |

### Analytics & Observability
| Method | Path | Description |
|---|---|---|
| GET | `/analytics/dashboard` | Aggregation endpoint for MTTR, severity heatmaps, and top services |
| GET | `/analytics/mttr` | Calculate Mean Time To Resolution metrics over time |
| GET | `/analytics/severity` | Breakdown active incident severity distributions |
| GET | `/analytics/services` | Identify most degraded or alert-heavy microservices |

### System Admin
| Method | Path | Description |
|---|---|---|
| POST | `/admin/reset` | Purge relational tables and reset vector indexes (Restricted to admin) |
| POST | `/admin/cleanup` | Manually trigger daily data retention and cleanup job (Restricted to admin) |

---

## Incident Lifecycle

```json
{
  "incident_id": "a1b2c3d4-e5f6-7a8b",
  "status": "OPEN",
  "severity": "critical",
  "service": "payment-service",
  "created_at": "2026-08-01T10:00:00",
  "resolved_at": null,
  "summary": "AI Generated Executive Summary...",
  "root_cause": "Database connection pool starvation caused by uncommitted retry loops.",
  "impact": "Payment checkout service failing with HTTP 500 across EU regions.",
  "recommendation": "Restart connection proxy and apply circuitbreaker rate-limiting."
}
```

**State Machine Progression:** `OPEN` -> `INVESTIGATING` -> `MITIGATED` -> `RESOLVED` -> `CLOSED`

**Example Natural Language RAG Queries:**
- *"Show me all open critical database incidents from today."*
- *"What Kubernetes deployment errors were resolved this week?"*
- *"Have we experienced connection pool starvation on payment-service before?"*

---

## Hybrid Retrieval and Recency

The current implementation retrieves up to eight dense candidates and eight BM25
candidates, filters them by team/status/severity and severity-specific recency windows,
then combines the ranked lists with Reciprocal Rank Fusion (`k=60`). It adds a
normalized recency contribution and applies a final lexical-overlap rerank. This is
not a direct weighted sum of raw cosine similarity and BM25 scores:

```text
RRF(document) = sum(1 / (60 + rank)) across the dense and sparse result lists
recency_score = exp(-0.693 * age_days / max(window_days / 3, 1))
pre-rerank = 0.8 * normalized_RRF + 0.2 * recency_score
rerank = 0.7 * pre-rerank + 0.3 * query-term overlap ratio
```

The retriever passes the top three document texts (not the full metadata records) into
the answer or summarization node. Missing timestamps receive the recency helper's
default score and are not rejected by the recency-window filter. BM25 uses the
`rank-bm25` implementation over whitespace-tokenized incident text; its per-process
index is rebuilt after local vector-store writes or when the refresh interval expires.

**Default maximum recency windows (`config.py`):**
| Severity Level | Expiration Tolerance Window |
|---|---|
| Critical | 90 Days |
| High | 60 Days |
| Medium / Normal / Low | 30 Days |

---

## RBAC Role Hierarchy

| Role | Operational Permissions & Boundaries |
|---|---|
| **Analyst** | Read team incidents, query `/ask` AI dashboard, and observe analytics charts |
| **Engineer** | All Analyst rights + log real-time issues and delete self-authored alerts |
| **SRE** | All Engineer rights + update AI incident summaries and execute lifecycle state machine shifts |
| **Team Lead** | All SRE rights + cross-team visibility access across different operational domains |
| **Admin** | Unrestricted global access + trigger manual database cleanup sweeps or factory resets |

---

## Enterprise LLM Guardrails & Security Architecture

The application implements a rigorous 3-layer security and token-optimization architecture in `core/guardrails.py`, designed specifically to pass enterprise DevSecOps and AI Safety audits:

| Guardrail Layer | Target Component | Action & Architectural Protection |
|---|---|---|
| **Input Security Gate** | `retrieve_node` | Intercepts adversarial jailbreak keywords (`ignore previous instructions`, `bypass rbac`, `system prompt`, `drop table`) and blocks prompt injection before spending vector search or LLM tokens. |
| **PII & Secret Scavenger** | `summarizer.py` & `nodes.py` | Automatically regex-scans all incident telemetry and queries, redacting AWS API keys (`AKIA...`), Bearer Tokens, and passwords (`[REDACTED_BY_GUARDRAIL]`) before transmission to third-party cloud LLM inferencing endpoints. |
| **Groundedness Short-Circuit** | `answer_node` & `summarize_node` | If vector hybrid similarity search yields insufficient historical evidence (< 20 characters of grounded content), execution short-circuits with an anti-hallucination warning, saving **100% of Groq LLM API tokens**. |
| **Output Integrity Gate** | `summarizer.py` | Locks parameter temperature at `0.0` for factual triage, suppresses assumption-based remediation guesses, and implements resilient JSON schema try/except fallback recovery. |
| **Network & Auth Cache** | `app/auth.py` | Implements an in-memory 10-minute Time-To-Live (`CACHE_TTL_SECONDS = 600`) dictionary for Supabase JWKS cryptographic encryption keys and PostgreSQL profile hydration, eliminating network spam during React background notification polling. |

---

## Environment Configuration

### Backend Setup (`rag/.env`)

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_JWT_SECRET=your_jwt_secret

# Vector Database (Pinecone is the default shared backend)
VECTOR_BACKEND=pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=incident-intelligence
PINECONE_NAMESPACE=incidents

# Embedding Engine Hyperparameters
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384

# LangGraph / model
RAG_MULTI_AGENT_ENABLED=true
LLM_MODEL=llama-3.1-8b-instant

# Optional Alert Notification Dispatch Channels
SLACK_WEBHOOK_URL=
TEAMS_WEBHOOK_URL=
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=

# Optional LangSmith Tracing & Telemetry
LANGCHAIN_TRACING_V2=true
LANGSMITH_PROJECT=incident-intelligence
LANGCHAIN_API_KEY=your_langchain_api_key
```

### Frontend Setup (`rag/frontend/.env`)

```env
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_anon_key
VITE_API_URL=http://127.0.0.1:8000
```

For Vercel, set `VITE_API_URL` to the public Render API URL when configuring the
frontend environment. On Render, set `CORS_ORIGINS` to the deployed Vercel origin
(for example, `https://your-app.vercel.app`); multiple origins can be comma-separated.

---

## Quickstart Run Instructions

### 1. Install Dependencies
```bash
# Navigate to backend and install python dependencies
cd rag
python -m venv venv
venv\Scripts\activate        # On Windows
pip install -r requirements.txt

# Navigate to frontend and install JavaScript dependencies
cd frontend
npm install
```

### 2. Boot local infrastructure
```bash
cd rag
docker compose up -d redpanda  # Pinecone is cloud-hosted; Redpanda may also be cloud-hosted
```

Create a Pinecone serverless index before starting the app. It must use the configured
embedding dimension (`384` by default) and the `cosine` metric. Set the same Pinecone
API key, index name, and namespace for both the FastAPI process and Kafka consumer.
For local-only testing without Pinecone, set `VECTOR_BACKEND=qdrant` and start Qdrant
with `docker compose up -d qdrant`.
Existing Qdrant vectors are not copied automatically. To retain a local Qdrant
collection, configure both backends' environment values and run
`python -m scripts.migrate_qdrant_to_pinecone` before switching the normal runtime
to Pinecone.

### 3. Launch Application Microservices
Open three separate terminal sessions inside your `rag` workspace directory:

```bash
# Terminal 1: FastAPI RAG Gateway & APScheduler worker
cd rag
uvicorn app.main:app --reload --port 8000

# Terminal 2: Kafka stream background vector ingestion worker
cd rag
python -m stream.consumer

# Terminal 3: React Vite Single Page UI
cd rag/frontend
npm run dev
```

Open your browser to **http://localhost:5173**. Inspect the hosted index and vector
count in the Pinecone console. The optional local Qdrant UI is at
`http://localhost:6333/dashboard`.


---

## Automated Retention & Database Cleanup

An automated **APScheduler** cron engine boots alongside FastAPI (`jobs/cleanup.py`), executing daily maintenance sweeps (configurable via `CLEANUP_INTERVAL_HOURS`):
1. Archives incident rows sitting in `RESOLVED` state beyond `RETENTION_DAYS_RESOLVED` (Default: 365 Days).
2. Purges stale vector points sitting in `CLOSED` state beyond `RETENTION_DAYS_CLOSED` (Default: 180 Days) to conserve vector DB RAM.
3. Compresses and cleans historical analytical request telemetry.

Manual cleanup triggering can be forced by an administrator via `POST /admin/cleanup`.

---

Pinecone index operations and vector counts can be inspected in the Pinecone console.
